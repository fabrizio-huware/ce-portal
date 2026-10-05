"""Motore di calcolo dei conti economici.

Replica la logica del foglio "CE di progetto" (DATA_PROJECT, DASHBOARD, Allocazione %):

* 1 giorno = 8 ore; ricavi = giorni x prezzo/giorno; costi = giorni x costo/giorno.
* Modalità "hours": ore per riga, ripartite sui mesi in proporzione ai giorni lavorativi.
* Modalità "percent": giorni del mese = % x giorni lavorativi del mese intero.
* Giorni lavorativi del mese = giorni lun-ven del mese intero - giorni non lavorativi del CE.
* Contingency per fase: ricavo aggiuntivo = ricavi della fase x %, senza costi.
* Nessun arrotondamento intermedio: gli importi finali sono arrotondati al centesimo.
"""

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.engine.models import (
    ZERO,
    Bucket,
    CalculationError,
    CEInput,
    CEResult,
    Kpis,
    LineResult,
    MonthInfo,
    MonthStaffing,
    PhaseResult,
    ProfileRate,
    ProfileResult,
)
from app.engine.periods import MAX_MONTHS, distribute, months_between, weekdays_in_month

HOURS_PER_DAY = Decimal(8)
DAYS_PER_WEEK = Decimal(5)
HUNDRED = Decimal(100)
CENT = Decimal("0.01")
# 5 decimali: ore con 2 decimali / 8 giorni non perdono mai precisione, quindi le somme tornano.
QTY = Decimal("0.00001")
RATIO = Decimal("0.000001")


def _money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _qty(x: Decimal) -> Decimal:
    return x.quantize(QTY, rounding=ROUND_HALF_UP)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Rapporto come frazione (0.5717 = 57,17%). None se il denominatore è zero."""
    if denominator == 0:
        return None
    return (numerator / denominator).quantize(RATIO, rounding=ROUND_HALF_UP)


def _max_decimals(x: Decimal, places: int = 2) -> bool:
    return x == x.quantize(Decimal(1).scaleb(-places))


# ---------------------------------------------------------------- validazione
def validate(ce: CEInput) -> list[str]:
    """Elenca tutti i problemi dei dati in ingresso (lista vuota = dati validi)."""
    issues: list[str] = []
    if ce.mode not in ("hours", "percent"):
        issues.append(f"Modalità di pianificazione sconosciuta: {ce.mode!r}")
    if ce.end_date < ce.start_date:
        return [*issues, "La data di fine precede la data di inizio"]

    months = months_between(ce.start_date, ce.end_date)
    if len(months) > MAX_MONTHS:
        issues.append(f"Il progetto copre {len(months)} mesi: il massimo è {MAX_MONTHS}")
    month_set = set(months)
    weekdays = {m: weekdays_in_month(m) for m in months}

    for month, count in ce.non_working_days.items():
        if month.day != 1:
            issues.append(f"Giorni non lavorativi: {month} non è il primo giorno del mese")
        elif month in month_set and not 0 <= count <= weekdays[month]:
            issues.append(
                f"Giorni non lavorativi di {month:%m/%Y}: {count} "
                f"(devono essere tra 0 e {weekdays[month]})"
            )

    if not 0 <= ce.max_discount_pct <= 100:
        issues.append("Il max sconto deve essere tra 0 e 100")
    if ce.signed_price is not None and ce.signed_price < 0:
        issues.append("Il prezzo firmato non può essere negativo")
    for name, rate in ce.rates.items():
        if rate.daily_price < 0 or rate.daily_cost < 0:
            issues.append(f"Tariffe negative per il profilo '{name}'")

    total_work_days = sum(
        weekdays[m] - ce.non_working_days.get(m, 0)
        for m in months
        if 0 <= ce.non_working_days.get(m, 0) <= weekdays[m]
    )
    for phase in ce.phases:
        if not 0 <= phase.contingency_pct <= 100 or not _max_decimals(phase.contingency_pct):
            issues.append(f"Fase '{phase.name}': contingency tra 0 e 100 con al massimo 2 decimali")
        for line in phase.lines:
            where = f"Fase '{phase.name}', riga '{line.activity}'"
            if line.profile not in ce.rates:
                issues.append(f"{where}: profilo '{line.profile}' senza tariffe")
            if ce.mode == "hours" and line.hours is not None:
                if line.hours < 0:
                    issues.append(f"{where}: ore negative")
                elif not _max_decimals(line.hours):
                    issues.append(f"{where}: le ore possono avere al massimo 2 decimali")
                elif line.hours > 0 and total_work_days == 0:
                    issues.append(f"{where}: nessun giorno lavorativo nel periodo del progetto")
            if ce.mode == "percent":
                for month, pct in line.allocations.items():
                    if month.day != 1 or month not in month_set:
                        issues.append(f"{where}: allocazione fuori dal periodo ({month})")
                    elif not 0 <= pct <= 100 or not _max_decimals(pct):
                        issues.append(
                            f"{where}: percentuale di {month:%m/%Y} non valida "
                            "(tra 0 e 100, massimo 2 decimali)"
                        )
    return issues


# ---------------------------------------------------------------- calcolo
def _bucket(days: Decimal, revenue: Decimal, cost: Decimal) -> Bucket:
    margin = revenue - cost
    return Bucket(
        days=_qty(days),
        revenue=_money(revenue),
        cost=_money(cost),
        margin=_money(margin),
        margin_pct=_ratio(margin, revenue),
        cost_ratio=_ratio(cost, revenue),
    )


def calculate(ce: CEInput) -> CEResult:
    issues = validate(ce)
    if issues:
        raise CalculationError(issues)
    with localcontext() as ctx:
        ctx.prec = (
            50  # le divisioni per 8, 5 e 100 sono esatte: la precisione extra è solo una guardia
        )
        return _calculate(ce)


def _calculate(ce: CEInput) -> CEResult:
    months = months_between(ce.start_date, ce.end_date)
    infos = []
    work_days: dict[date, int] = {}
    for month in months:
        weekdays = weekdays_in_month(month)
        non_working = ce.non_working_days.get(month, 0)
        work_days[month] = weekdays - non_working
        infos.append(MonthInfo(month, weekdays, non_working, weekdays - non_working))

    warnings: list[str] = []
    line_results: list[LineResult] = []
    phase_results: list[PhaseResult] = []

    month_days = {m: ZERO for m in months}
    month_revenue = {m: ZERO for m in months}
    month_cost = {m: ZERO for m in months}
    by_profile: dict[str, list[Decimal]] = {}  # hours, days, revenue, cost
    sums = {  # (days, revenue, cost)
        "internal": [ZERO, ZERO, ZERO],
        "external": [ZERO, ZERO, ZERO],
    }
    days_pm = ZERO
    contingency_revenue_total = ZERO
    days_with_contingency_total = ZERO

    for p_index, phase in enumerate(ce.phases):
        ph_hours = ph_days = ph_revenue = ph_cost = ZERO
        for l_index, line in enumerate(phase.lines):
            rate = ce.rates[line.profile]
            where = f"Fase '{phase.name}', riga '{line.activity}'"

            if ce.mode == "hours":
                hours_in = line.hours or ZERO
                spread = distribute(hours_in, [work_days[m] for m in months], places=2)
                monthly = {m: h / HOURS_PER_DAY for m, h in zip(months, spread, strict=True)}
                considered = months
                if line.allocations:
                    warnings.append(f"{where}: percentuali ignorate in modalità ore")
            else:
                monthly = {
                    m: (line.allocations[m] / HUNDRED * work_days[m])
                    if m in line.allocations
                    else ZERO
                    for m in months
                }
                considered = [m for m in months if m in line.allocations]
                if line.hours:
                    warnings.append(f"{where}: ore ignorate in modalità percentuali")

            days = sum(monthly.values(), ZERO)
            hours = days * HOURS_PER_DAY
            revenue = days * rate.daily_price
            cost = days * rate.daily_cost
            considered_days = sum(work_days[m] for m in considered)

            for m, d in monthly.items():
                month_days[m] += d
                month_revenue[m] += d * rate.daily_price
                month_cost[m] += d * rate.daily_cost

            bucket = sums["external" if rate.is_external else "internal"]
            bucket[0] += days
            bucket[1] += revenue
            bucket[2] += cost
            agg = by_profile.setdefault(line.profile, [ZERO, ZERO, ZERO, ZERO])
            agg[0] += hours
            agg[1] += days
            agg[2] += revenue
            agg[3] += cost
            if line.is_project_management:
                days_pm += days
            ph_hours += hours
            ph_days += days
            ph_revenue += revenue
            ph_cost += cost

            line_results.append(
                LineResult(
                    phase_index=p_index,
                    line_index=l_index,
                    activity=line.activity,
                    profile=line.profile,
                    is_external=rate.is_external,
                    is_project_management=line.is_project_management,
                    hours=_qty(hours),
                    days=_qty(days),
                    revenue=_money(revenue),
                    cost=_money(cost),
                    margin=_money(revenue - cost),
                    fte=_ratio(days, considered_days) or ZERO,
                    monthly_days={m: _qty(d) for m, d in monthly.items()},
                )
            )

        pct = phase.contingency_pct
        contingency = ph_revenue * pct / HUNDRED
        contingency_revenue_total += contingency
        days_with_cont = ph_days * (1 + pct / HUNDRED)
        days_with_contingency_total += days_with_cont
        phase_results.append(
            PhaseResult(
                name=phase.name,
                contingency_pct=pct,
                hours=_qty(ph_hours),
                days=_qty(ph_days),
                days_with_contingency=_qty(days_with_cont),
                revenue=_money(ph_revenue),
                cost=_money(ph_cost),
                contingency_revenue=_money(contingency),
                revenue_with_contingency=_money(ph_revenue + contingency),
            )
        )

    # ---- profili
    total_hours = sum((v[0] for v in by_profile.values()), ZERO)
    profile_results = [
        ProfileResult(
            profile=name,
            is_external=ce.rates[name].is_external,
            hours=_qty(by_profile[name][0]),
            days=_qty(by_profile[name][1]),
            hours_share=_ratio(by_profile[name][0], total_hours),
            revenue=_money(by_profile[name][2]),
            cost=_money(by_profile[name][3]),
            margin=_money(by_profile[name][2] - by_profile[name][3]),
        )
        for name in ce.rates
        if name in by_profile
    ]

    # ---- riepiloghi
    internal = _bucket(*sums["internal"])
    external = _bucket(*sums["external"])
    contingency = _bucket(ZERO, contingency_revenue_total, ZERO)
    days_total = sums["internal"][0] + sums["external"][0]
    revenue_total = sums["internal"][1] + sums["external"][1] + contingency_revenue_total
    cost_total = sums["internal"][2] + sums["external"][2]
    total = _bucket(days_total, revenue_total, cost_total)

    # ---- staffing mensile
    monthly_results = [
        MonthStaffing(
            month=m,
            work_days=work_days[m],
            days=_qty(month_days[m]),
            hours=_qty(month_days[m] * HOURS_PER_DAY),
            fte=_ratio(month_days[m], Decimal(work_days[m])),
            revenue=_money(month_revenue[m]),
            cost=_money(month_cost[m]),
        )
        for m in months
    ]

    # ---- KPI della dashboard
    price_min = revenue_total * (1 - ce.max_discount_pct / HUNDRED)
    signed = ce.signed_price
    kpis = Kpis(
        price_project=_money(revenue_total),
        max_discount_pct=ce.max_discount_pct,
        price_min=_money(price_min),
        days_total=_qty(days_total),
        days_project_management=_qty(days_pm),
        days_delivery=_qty(days_total - days_pm),
        days_total_with_contingency=_qty(days_with_contingency_total),
        weeks=_qty(days_total / DAYS_PER_WEEK),
        weeks_with_contingency=_qty(days_with_contingency_total / DAYS_PER_WEEK),
        fee_media_min=_money(price_min / days_total) if days_total else None,
        signed_price=_money(signed) if signed is not None else None,
        fee_media_signed=_money(signed / days_total) if signed is not None and days_total else None,
        margin_signed=_money(signed - cost_total) if signed is not None else None,
        margin_pct_signed=_ratio(signed - cost_total, signed) if signed is not None else None,
        cost_ratio_signed=_ratio(cost_total, signed) if signed is not None else None,
    )

    return CEResult(
        months=infos,
        phases=phase_results,
        lines=line_results,
        profiles=profile_results,
        internal=internal,
        external=external,
        contingency=contingency,
        total=total,
        monthly=monthly_results,
        kpis=kpis,
        warnings=warnings,
    )


def rates_from_mapping(raw: Mapping[str, Mapping[str, object]], external: set[str] = frozenset()):
    """Converte {'Senior': {'daily_price': '850', 'daily_cost': '330'}} in ProfileRate."""
    return {
        name: ProfileRate(
            Decimal(str(r["daily_price"])),
            Decimal(str(r["daily_cost"])),
            is_external=name in external,
        )
        for name, r in raw.items()
    }
