"""Regole del motore, casi limite e validazione, con valori calcolati a mano."""

import random
from datetime import date
from decimal import Decimal

import pytest

from app.engine import (
    CalculationError,
    CEInput,
    LineInput,
    PhaseInput,
    ProfileRate,
    calculate,
    validate,
)

D = Decimal
JAN, FEB, MAR = date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)

RATES = {
    "Manager": ProfileRate(D("1200"), D("800")),
    "Senior": ProfileRate(D("850"), D("330")),
    "Specialist": ProfileRate(D("725"), D("280")),
    "Esterni": ProfileRate(D("750"), D("360"), is_external=True),
}


def ce(phases, mode="hours", start=date(2026, 1, 1), end=date(2026, 3, 31), **kw):
    kw.setdefault("rates", RATES)
    return CEInput(start_date=start, end_date=end, mode=mode, phases=phases, **kw)


def line(profile="Senior", hours=None, pct=None, pm=False, activity="Attività"):
    return LineInput(
        activity, profile, hours=hours, allocations=pct or {}, is_project_management=pm
    )


def one_phase(*lines, contingency="0"):
    return [PhaseInput("Fase", list(lines), D(contingency))]


# ------------------------------------------------------------------ formule base
def test_hours_revenue_and_cost():
    r = calculate(ce(one_phase(line("Senior", D("16")))))
    assert r.total.days == D("2")  # 16 h / 8
    assert r.total.revenue == D("1700.00")  # 2 x 850
    assert r.total.cost == D("660.00")  # 2 x 330
    assert r.total.margin == D("1040.00")
    assert r.total.margin_pct == D("0.611765")
    assert r.total.cost_ratio == D("0.388235")


def test_percent_mode_uses_the_whole_month_not_the_start_day():
    """Decisione: mese intero come nel foglio. Un progetto che parte il 20/1 conta tutto gennaio."""
    r = calculate(
        ce(
            one_phase(line("Senior", pct={JAN: D("100")})),
            mode="percent",
            start=date(2026, 1, 20),
            end=date(2026, 1, 31),
        )
    )
    assert [m.work_days for m in r.months] == [22]
    assert r.total.days == D("22")


def test_non_working_days_reduce_work_days_per_month():
    base = {JAN: D("100"), FEB: D("50")}
    r = calculate(
        ce(
            one_phase(line("Senior", pct=base)),
            mode="percent",
            end=date(2026, 2, 28),
            non_working_days={JAN: 5, FEB: 2},
        )
    )
    assert [m.work_days for m in r.months] == [17, 18]  # 22-5, 20-2
    assert r.total.days == D("26")  # 100% x 17 + 50% x 18
    assert r.lines[0].monthly_days == {JAN: D("17"), FEB: D("9")}


def test_hours_are_spread_over_months_in_proportion_to_work_days():
    r = calculate(
        ce(
            one_phase(line("Senior", D("86"))),
            end=date(2026, 2, 28),
            non_working_days={JAN: 2},  # gennaio 20, febbraio 20 lavorativi
        )
    )
    assert [m.hours for m in r.monthly] == [D("43"), D("43")]
    assert sum(m.days for m in r.monthly) == D("10.75")


def test_unused_months_have_zero_staffing_in_percent_mode():
    r = calculate(ce(one_phase(line("Senior", pct={FEB: D("50")})), mode="percent"))
    assert [m.days for m in r.monthly] == [D("0"), D("10"), D("0")]
    assert r.lines[0].fte == D("0.500000")  # media pesata solo sui mesi valorizzati


def test_fte_per_month():
    r = calculate(
        ce(
            one_phase(line("Senior", pct={JAN: D("100")}), line("Manager", pct={JAN: D("50")})),
            mode="percent",
        )
    )
    assert r.monthly[0].fte == D("1.500000")  # 100% + 50%


# ------------------------------------------------------------------ servizi esterni, PM
def test_external_profile_goes_to_external_services_and_counts_in_days():
    r = calculate(ce(one_phase(line("Senior", D("8")), line("Esterni", D("16")))))
    assert r.internal.revenue == D("850.00") and r.internal.cost == D("330.00")
    assert r.external.revenue == D("1500.00") and r.external.cost == D("720.00")  # 2 g x 750 / 360
    assert r.external.margin_pct == D("0.520000")  # 52% come nel listino
    assert r.total.revenue == D("2350.00")
    assert r.kpis.days_total == D("3")  # esterni inclusi, come il foglio
    assert {p.profile: p.is_external for p in r.profiles} == {"Senior": False, "Esterni": True}


def test_project_management_days_and_delivery_days():
    r = calculate(
        ce(
            [
                PhaseInput("PM", [line("Manager", D("16"), pm=True)]),
                PhaseInput("Delivery", [line("Senior", D("40"))]),
            ]
        )
    )
    assert r.kpis.days_project_management == D("2")
    assert r.kpis.days_delivery == D("5")
    assert r.kpis.days_total == D("7")


# ------------------------------------------------------------------ contingency
def test_contingency_adds_revenue_but_no_cost():
    r = calculate(ce(one_phase(line("Senior", D("40")), contingency="10")))  # 5 g = 4.250 ricavi
    assert r.contingency.revenue == D("425.00")
    assert r.contingency.cost == D("0.00")
    assert r.total.revenue == D("4675.00")
    assert r.total.cost == D("1650.00")
    assert r.total.margin == D("3025.00")
    assert r.phases[0].revenue_with_contingency == D("4675.00")
    assert r.kpis.days_total == D("5")  # le giornate "base" non cambiano...
    assert r.kpis.days_total_with_contingency == D(
        "5.5"
    )  # ...ma c'è anche il totale con contingency
    assert r.kpis.weeks_with_contingency == D("1.1")


def test_contingency_is_applied_phase_by_phase():
    r = calculate(
        ce(
            [
                PhaseInput("A", [line("Manager", D("8"))], D("50")),  # 1.200 x 50% = 600
                PhaseInput("B", [line("Specialist", D("8"))], D("0")),
            ]
        )
    )
    assert [p.contingency_revenue for p in r.phases] == [D("600.00"), D("0.00")]
    assert r.contingency.revenue == D("600.00")


def test_contingency_also_applies_to_external_revenue_like_the_sheet():
    r = calculate(ce(one_phase(line("Esterni", D("8")), contingency="10")))
    assert r.contingency.revenue == D("75.00")


# ------------------------------------------------------------------ sconto e prezzo firmato
def test_max_discount_and_minimum_price():
    r = calculate(ce(one_phase(line("Senior", D("16"))), max_discount_pct=D("10")))
    assert r.kpis.price_project == D("1700.00")
    assert r.kpis.price_min == D("1530.00")
    assert r.kpis.fee_media_min == D("765.00")  # 1.530 / 2 giornate


def test_signed_price_metrics():
    r = calculate(ce(one_phase(line("Senior", D("16"))), signed_price=D("1600")))
    k = r.kpis
    assert k.fee_media_signed == D("800.00")
    assert k.margin_signed == D("940.00")  # 1.600 - 660
    assert k.margin_pct_signed == D("0.587500")
    assert k.cost_ratio_signed == D("0.412500")


def test_signed_price_zero_gives_negative_margin_and_no_percentages():
    k = calculate(ce(one_phase(line("Senior", D("16"))), signed_price=D("0"))).kpis
    assert k.margin_signed == D("-660.00")
    assert k.margin_pct_signed is None and k.cost_ratio_signed is None


# ------------------------------------------------------------------ casi limite
def test_empty_ce_has_zero_totals_and_no_percentages():
    r = calculate(ce([]))
    assert r.total.revenue == r.total.cost == D("0.00")
    assert r.total.margin_pct is None and r.total.cost_ratio is None
    assert r.kpis.fee_media_min is None and r.kpis.price_min == D("0.00")
    assert r.profiles == []


def test_zero_hours_lines_are_harmless():
    r = calculate(ce(one_phase(line("Senior", D("0")), line("Manager", None))))
    assert r.total.days == D("0")
    assert r.kpis.fee_media_min is None


def test_rounding_is_applied_only_to_final_amounts():
    """1 ora di Specialist = 90,625 €: ogni riga mostra 90,63 ma il totale è la somma esatta."""
    r = calculate(ce(one_phase(line("Specialist", D("1")), line("Specialist", D("1")))))
    assert [x.revenue for x in r.lines] == [D("90.63"), D("90.63")]
    assert r.total.revenue == D("181.25")  # non 181,26


def test_results_are_decimals_never_floats():
    r = calculate(ce(one_phase(line("Senior", D("13.37")))))
    for value in (
        r.total.revenue,
        r.total.cost,
        r.kpis.price_min,
        r.lines[0].hours,
        r.monthly[0].fte,
    ):
        assert isinstance(value, Decimal)


def test_wrong_mode_data_is_ignored_with_a_warning():
    hours_mode = calculate(ce(one_phase(line("Senior", D("8"), pct={JAN: D("50")}))))
    assert hours_mode.total.days == D("1") and len(hours_mode.warnings) == 1
    percent_mode = calculate(
        ce(one_phase(line("Senior", D("8"), pct={JAN: D("50")})), mode="percent")
    )
    assert percent_mode.total.days == D("11") and len(percent_mode.warnings) == 1


def test_calculation_is_pure_and_repeatable():
    data = ce(one_phase(line("Senior", D("13.5")), contingency="7.5"), max_discount_pct=D("3"))
    assert calculate(data) == calculate(data)


# ------------------------------------------------------------------ validazione
@pytest.mark.parametrize(
    "build,fragment",
    [
        (lambda: ce([], end=date(2025, 12, 31)), "fine precede"),
        (lambda: ce([], start=date(2026, 1, 1), end=date(2027, 1, 31)), "massimo è 12"),
        (lambda: ce(one_phase(line("Fantasma", D("1")))), "senza tariffe"),
        (lambda: ce(one_phase(line("Senior", D("-1")))), "ore negative"),
        (lambda: ce(one_phase(line("Senior", D("7.555")))), "2 decimali"),
        (lambda: ce(one_phase(line("Senior", D("1")), contingency="101")), "contingency"),
        (lambda: ce([], max_discount_pct=D("100.5")), "max sconto"),
        (lambda: ce([], signed_price=D("-1")), "prezzo firmato"),
        (lambda: ce([], non_working_days={JAN: 23}), "devono essere tra 0 e 22"),
        (lambda: ce([], non_working_days={JAN: -1}), "devono essere tra 0 e 22"),
        (lambda: ce([], non_working_days={date(2026, 1, 15): 1}), "primo giorno"),
        (
            lambda: ce(one_phase(line("Senior", pct={JAN: D("100.01")})), mode="percent"),
            "non valida",
        ),
        (lambda: ce(one_phase(line("Senior", pct={JAN: D("-1")})), mode="percent"), "non valida"),
        (
            lambda: ce(one_phase(line("Senior", pct={JAN: D("33.333")})), mode="percent"),
            "non valida",
        ),
        (
            lambda: ce(one_phase(line("Senior", pct={date(2026, 6, 1): D("50")})), mode="percent"),
            "fuori dal periodo",
        ),
        (
            lambda: ce(one_phase(line("Senior", pct={date(2026, 1, 15): D("50")})), mode="percent"),
            "fuori dal periodo",
        ),
        (lambda: ce([], mode="giorni"), "Modalità"),
    ],
)
def test_invalid_input_is_rejected(build, fragment):
    data = build()
    assert any(fragment in issue for issue in validate(data)), validate(data)
    with pytest.raises(CalculationError, match=fragment):
        calculate(data)


def test_all_problems_are_reported_together():
    data = ce(
        one_phase(line("Fantasma", D("1")), line("Senior", D("-5")), contingency="200"),
        max_discount_pct=D("150"),
    )
    with pytest.raises(CalculationError) as exc:
        calculate(data)
    assert len(exc.value.issues) == 4


def test_hours_with_no_work_days_cannot_be_spread():
    data = ce(one_phase(line("Senior", D("8"))), end=date(2026, 1, 31), non_working_days={JAN: 22})
    with pytest.raises(CalculationError, match="nessun giorno lavorativo"):
        calculate(data)
    assert (
        calculate(
            ce(one_phase(line("Senior", D("0"))), end=date(2026, 1, 31), non_working_days={JAN: 22})
        ).total.days
        == 0
    )


# ------------------------------------------------------------------ invarianti su dati casuali
def _random_ce(rng: random.Random, mode: str) -> CEInput:
    start = date(2026, rng.randint(1, 6), 1)
    months = rng.randint(1, 6)
    end_month = start.month + months - 1
    end = date(start.year + (end_month - 1) // 12, (end_month - 1) % 12 + 1, 28)
    from app.engine.periods import months_between, weekdays_in_month

    period = months_between(start, end)
    non_working = {m: rng.randint(0, 4) for m in period if rng.random() < 0.5}
    phases = []
    for p in range(rng.randint(1, 4)):
        lines = []
        for _ in range(rng.randint(1, 5)):
            profile = rng.choice(list(RATES))
            if mode == "hours":
                lines.append(line(profile, D(rng.randint(0, 40000)) / 100, pm=rng.random() < 0.2))
            else:
                alloc = {m: D(rng.randint(0, 10000)) / 100 for m in period if rng.random() < 0.7}
                lines.append(line(profile, pct=alloc, pm=rng.random() < 0.2))
        phases.append(PhaseInput(f"F{p}", lines, D(rng.randint(0, 3000)) / 100))
    assert all(weekdays_in_month(m) >= non_working.get(m, 0) for m in period)
    return CEInput(start, end, mode, phases, RATES, non_working, D(rng.randint(0, 2000)) / 100)


@pytest.mark.parametrize("mode", ["hours", "percent"])
def test_invariants_hold_on_random_ces(mode):
    rng = random.Random(2026)
    cent = D("0.01")
    for _ in range(150):
        r = calculate(_random_ce(rng, mode))
        n = len(r.lines) + 1
        # giornate e ore sono esatte in ogni aggregazione
        assert sum(m.days for m in r.monthly) == r.total.days
        assert sum(line.days for line in r.lines) == r.total.days
        assert sum(p.days for p in r.profiles) == r.total.days
        assert sum(p.days for p in r.phases) == r.total.days
        assert r.total.days == r.internal.days + r.external.days
        assert r.kpis.days_project_management + r.kpis.days_delivery == r.kpis.days_total
        # gli importi tornano entro 1 centesimo per voce (arrotondamento di ogni voce)
        assert (
            abs(sum(x.revenue for x in r.lines) + r.contingency.revenue - r.total.revenue)
            <= cent * n
        )
        assert abs(sum(x.cost for x in r.lines) - r.total.cost) <= cent * n
        assert abs(sum(m.revenue for m in r.monthly) - sum(x.revenue for x in r.lines)) <= cent * n
        assert abs(r.total.margin - (r.total.revenue - r.total.cost)) <= cent
        assert r.contingency.cost == 0
        assert r.kpis.price_min <= r.kpis.price_project
        assert r.kpis.days_total_with_contingency >= r.kpis.days_total
        # nessun valore negativo; in modalità percentuali l'occupazione di una riga non supera il 100%
        # (in modalità ore una riga può rappresentare più persone: FTE > 1 è legittimo)
        for line_result in r.lines:
            assert line_result.hours >= 0 and line_result.revenue >= 0 and line_result.fte >= 0
            if mode == "percent":
                assert line_result.fte <= 1
        if r.total.margin_pct is not None:
            assert r.total.margin_pct + r.total.cost_ratio == D("1.000000")
