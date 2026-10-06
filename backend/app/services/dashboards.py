"""Dashboard portfolio e carico risorse.

Regole (documentate in docs/dashboard.md):
* **Approvati**: ultima versione approvata di ogni CE non eliminato.
* **Pipeline**: ultima versione aperta (bozza, in approvazione, rifiutata) dei CE che **non hanno
  ancora nessuna versione approvata**. Una revisione in corso di un CE già approvato non si somma:
  si conta solo nel numero `revisions_in_progress`.
* Il periodo seleziona i CE come la ricerca (periodo sovrapposto, estremi inclusi); i totali per
  cliente / business unit / stato sono i totali interi dei CE. La vista per mese usa gli importi
  mensili, **senza contingency**.
* Il calcolo è quello del motore sui dati congelati nella versione (tariffe e calendario).
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import engine
from app.engine import CalculationError, CEResult
from app.engine.periods import month_start, months_between, weekdays_in_month
from app.exports.common import STATUS_LABELS
from app.models import (
    CE,
    CEVersion,
    CEVersionRate,
    Client,
    Employee,
    Profile,
)
from app.schemas.dashboard import (
    GroupRow,
    MonthFigures,
    MonthRow,
    PortfolioItem,
    PortfolioOut,
    ResourceCell,
    ResourceMonth,
    ResourceRow,
    ResourcesOut,
    StatusRow,
    Totals,
)
from app.services import ce as svc
from app.services.ce_search import latest_subquery

logger = logging.getLogger("ce_portal.dashboard")
ZERO = Decimal(0)
CENT = Decimal("0.01")
RATIO = Decimal("0.000001")
MAX_MONTHS = 36
OVERLOAD_FTE = Decimal(1)


@dataclass
class Entry:
    ce: CE
    version: CEVersion
    client: Client
    scope: str  # approved | pipeline
    result: CEResult | None = None


@dataclass
class Selection:
    entries: list[Entry] = field(default_factory=list)
    revisions_in_progress: int = 0
    skipped: list[str] = field(default_factory=list)


def _ratio(num: Decimal, den: Decimal) -> Decimal | None:
    return None if den == 0 else (num / den).quantize(RATIO, rounding=ROUND_HALF_UP)


# ====================================================================== selezione dei CE
def _select(
    session: Session,
    *,
    include_pipeline: bool,
    client_id: uuid.UUID | None,
    business_unit: str | None,
    date_from: date | None,
    date_to: date | None,
) -> Selection:
    def narrow(stmt):
        if client_id:
            stmt = stmt.where(CEVersion.client_id == client_id)
        if business_unit:
            stmt = stmt.where(func.lower(CEVersion.business_unit) == business_unit.lower())
        if date_to:
            stmt = stmt.where(CEVersion.start_date <= date_to)
        if date_from:
            stmt = stmt.where(CEVersion.end_date >= date_from)
        return stmt

    approved_ids = select(CEVersion.ce_id).where(CEVersion.status == "approved")
    base = lambda latest: (  # noqa: E731
        select(CE, CEVersion, Client)
        .join(latest, latest.c.ce_id == CE.id)
        .join(CEVersion, and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n))
        .join(Client, Client.id == CEVersion.client_id)
        .where(CE.deleted_at.is_(None))
    )
    selection = Selection()
    rows = session.execute(
        narrow(base(latest_subquery(only_approved=True))).order_by(func.lower(CE.code))
    ).all()
    selection.entries += [Entry(ce, v, c, "approved") for ce, v, c in rows]

    latest_any = latest_subquery(only_approved=False)
    open_statuses = ("draft", "submitted", "rejected")
    if include_pipeline:
        rows = session.execute(
            narrow(base(latest_any))
            .where(CEVersion.status.in_(open_statuses), CE.id.not_in(approved_ids))
            .order_by(func.lower(CE.code))
        ).all()
        selection.entries += [Entry(ce, v, c, "pipeline") for ce, v, c in rows]
    selection.revisions_in_progress = (
        session.scalar(
            select(func.count()).select_from(
                narrow(base(latest_any))
                .where(CEVersion.status.in_(open_statuses), CE.id.in_(approved_ids))
                .subquery()
            )
        )
        or 0
    )
    _calculate(session, selection)
    return selection


def _calculate(session: Session, selection: Selection) -> None:
    """Esegue il motore su ogni versione (dati e tariffe congelati nella versione)."""
    ids = [e.version.id for e in selection.entries]
    if not ids:
        return
    versions = {
        v.id: v
        for v in session.scalars(
            select(CEVersion).where(CEVersion.id.in_(ids)).options(*svc.FULL_LOAD)
        )
    }
    rates: dict[uuid.UUID, dict[uuid.UUID, svc.RateInfo]] = defaultdict(dict)
    for rate, profile in session.execute(
        select(CEVersionRate, Profile)
        .join(Profile, Profile.id == CEVersionRate.profile_id)
        .where(CEVersionRate.version_id.in_(ids))
        .order_by(Profile.sort_order, func.lower(Profile.name))
    ):
        rates[rate.version_id][profile.id] = svc.RateInfo(
            profile.id, profile.name, profile.is_external, profile.sort_order,
            rate.daily_price, rate.daily_cost,
        )  # fmt: skip
    kept = []
    for entry in selection.entries:
        version = versions[entry.version.id]
        entry.version = version
        try:
            ce_input = svc.to_engine_input(
                svc.content_from_version(version),
                rates[version.id],
                {m.month: m.non_working_days for m in version.months},
            )
            entry.result = engine.calculate(ce_input)
            kept.append(entry)
        except CalculationError as exc:  # non dovrebbe succedere: dati già validati al salvataggio
            logger.warning(
                "CE %s v%s non calcolabile: %s", entry.ce.code, version.version_number, exc
            )
            selection.skipped.append(f"{entry.ce.code} v{version.version_number}")
    selection.entries = kept


# ====================================================================== portfolio
def _totals(items: list[Entry]) -> Totals:
    revenue = sum((e.result.total.revenue for e in items), ZERO)
    cost = sum((e.result.total.cost for e in items), ZERO)
    margin = revenue - cost
    return Totals(
        count=len(items),
        revenue=revenue,
        cost=cost,
        margin=margin,
        margin_pct=_ratio(margin, revenue),
        days=sum((e.result.kpis.days_total for e in items), ZERO),
    )


def _groups(entries: list[Entry], key_of) -> list[GroupRow]:
    keys: dict[str, str] = {}
    for e in entries:
        key, label = key_of(e)
        keys[key] = label
    rows = []
    for key, label in sorted(keys.items(), key=lambda kv: kv[1].lower()):
        members = [e for e in entries if key_of(e)[0] == key]
        rows.append(
            GroupRow(
                key=key,
                label=label,
                approved=_totals([e for e in members if e.scope == "approved"]),
                pipeline=_totals([e for e in members if e.scope == "pipeline"]),
            )
        )
    return rows


def portfolio(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: uuid.UUID | None = None,
    business_unit: str | None = None,
    include_pipeline: bool = True,
) -> PortfolioOut:
    sel = _select(
        session, include_pipeline=include_pipeline, client_id=client_id,
        business_unit=business_unit, date_from=date_from, date_to=date_to,
    )  # fmt: skip
    entries = sel.entries
    approved = [e for e in entries if e.scope == "approved"]
    pipeline = [e for e in entries if e.scope == "pipeline"]

    lo = month_start(date_from) if date_from else None
    hi = month_start(date_to) if date_to else None
    monthly: dict[date, dict[str, dict[str, Decimal]]] = defaultdict(
        lambda: {s: {"revenue": ZERO, "cost": ZERO, "days": ZERO} for s in ("approved", "pipeline")}
    )
    for e in entries:
        for m in e.result.monthly:
            if (lo and m.month < lo) or (hi and m.month > hi):
                continue
            cell = monthly[m.month][e.scope]
            cell["revenue"] += m.revenue
            cell["cost"] += m.cost
            cell["days"] += m.days

    def figures(cell: dict[str, Decimal]) -> MonthFigures:
        return MonthFigures(
            revenue=cell["revenue"],
            cost=cell["cost"],
            margin=cell["revenue"] - cell["cost"],
            days=cell["days"],
        )

    status_rows = []
    for status in ("approved", "submitted", "draft", "rejected"):
        members = [e for e in entries if e.version.status == status]
        if members:
            status_rows.append(StatusRow(
                status=status, label=STATUS_LABELS[status], scope=members[0].scope, count=len(members),
                revenue=sum((e.result.total.revenue for e in members), ZERO),
            ))  # fmt: skip

    return PortfolioOut(
        date_from=date_from,
        date_to=date_to,
        include_pipeline=include_pipeline,
        approved=_totals(approved),
        pipeline=_totals(pipeline),
        by_client=_groups(entries, lambda e: (str(e.client.id), e.client.name)),
        by_business_unit=_groups(entries, lambda e: (e.version.business_unit or "", e.version.business_unit or "Non indicata")),
        by_status=status_rows,
        by_month=[
            MonthRow(month=m, approved=figures(monthly[m]["approved"]), pipeline=figures(monthly[m]["pipeline"]))
            for m in sorted(monthly)
        ],
        items=[
            PortfolioItem(
                ce_id=e.ce.id, code=e.ce.code, client_name=e.client.name, project_name=e.version.project_name,
                business_unit=e.version.business_unit, status=e.version.status, scope=e.scope,
                version_number=e.version.version_number, start_date=e.version.start_date, end_date=e.version.end_date,
                revenue=e.result.total.revenue, cost=e.result.total.cost, margin=e.result.total.margin,
                margin_pct=e.result.total.margin_pct, days=e.result.kpis.days_total,
            )
            for e in entries
        ],
        revisions_in_progress=sel.revisions_in_progress,
        skipped=sel.skipped,
    )  # fmt: skip


# ====================================================================== carico risorse
def _profile_names(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return {p.id: p.name for p in session.scalars(select(Profile).where(Profile.id.in_(ids)))}


def _employees(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, Employee]:
    if not ids:
        return {}
    return {e.id: e for e in session.scalars(select(Employee).where(Employee.id.in_(ids)))}


def default_window(today: date | None = None) -> tuple[date, date]:
    """Da questo mese a 11 mesi dopo: il periodo utile per pianificare."""
    first = month_start(today or date.today())
    total = first.year * 12 + first.month - 1 + 11
    return first, date(total // 12, total % 12 + 1, 1)


def resources(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: uuid.UUID | None = None,
    profile_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    include_pipeline: bool = False,
) -> ResourcesOut:
    default_from, default_to = default_window()
    first = month_start(date_from or default_from)
    last = month_start(date_to or (date_from and max(date_from, first) or default_to))
    if last < first:
        raise ValueError("La data finale precede quella iniziale")
    months = months_between(first, last)
    if len(months) > MAX_MONTHS:
        raise ValueError(f"Il periodo copre {len(months)} mesi: il massimo è {MAX_MONTHS}")
    window_end = date(
        last.year, last.month, 28
    )  # qualunque giorno del mese finale basta per l'intersezione

    sel = _select(
        session, include_pipeline=include_pipeline, client_id=client_id, business_unit=None,
        date_from=first, date_to=window_end,
    )  # fmt: skip
    non_working = svc.suggested_non_working(session, months)
    capacity = {m: weekdays_in_month(m) - non_working.get(m, 0) for m in months}
    index = {m: i for i, m in enumerate(months)}

    # (chiave) -> mese -> [approvati, pipeline]
    emp: dict[uuid.UUID, dict[date, list[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [ZERO, ZERO])
    )
    prof: dict[uuid.UUID, dict[date, list[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [ZERO, ZERO])
    )
    unassigned: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for entry in sel.entries:
        slot = 0 if entry.scope == "approved" else 1
        for line_result in entry.result.lines:
            db_line = entry.version.phases[line_result.phase_index].lines[line_result.line_index]
            if profile_id and db_line.profile_id != profile_id:
                continue
            if employee_id and db_line.employee_id != employee_id:
                continue
            for month, days in line_result.monthly_days.items():
                if month not in index or days == 0:
                    continue
                prof[db_line.profile_id][month][slot] += days
                if db_line.employee_id:
                    emp[db_line.employee_id][month][slot] += days
                else:
                    unassigned[db_line.profile_id] += days

    names = _profile_names(session, set(prof))
    employees = _employees(session, set(emp))
    default_profiles = _profile_names(session, {e.default_profile_id for e in employees.values()})

    def cells_for(per_month: dict[date, list[Decimal]], flag_overload: bool) -> list[ResourceCell]:
        cells = []
        for month in months:
            approved, pipeline_days = per_month.get(month, [ZERO, ZERO])
            total = approved + pipeline_days
            cap = Decimal(capacity[month])
            fte = _ratio(total, cap)
            over = flag_overload and total > 0 and (cap == 0 or total / cap > OVERLOAD_FTE)
            cells.append(ResourceCell(days_approved=approved, days_pipeline=pipeline_days, days=total,
                                      hours=total * 8, fte=fte, overloaded=bool(over)))  # fmt: skip
        return cells

    def row(kind, key, name, profile_name, per_month, flag, unassigned_days=ZERO) -> ResourceRow:
        cells = cells_for(per_month, flag)
        return ResourceRow(
            kind=kind, id=key, name=name, profile_name=profile_name, cells=cells,
            total_days=sum((c.days for c in cells), ZERO), unassigned_days=unassigned_days,
            overloaded_months=sum(1 for c in cells if c.overloaded),
        )  # fmt: skip

    employee_rows = sorted(
        (row("employee", eid, f"{e.first_name} {e.last_name}", default_profiles.get(e.default_profile_id), emp[eid], True)
         for eid, e in employees.items()),
        key=lambda r: r.name.lower(),
    )  # fmt: skip
    profile_rows = sorted(
        (row("profile", pid, names.get(pid, "?"), None, prof[pid], False, unassigned[pid]) for pid in prof),
        key=lambda r: r.name.lower(),
    )  # fmt: skip
    return ResourcesOut(
        date_from=first, date_to=last, include_pipeline=include_pipeline, overload_threshold_fte=OVERLOAD_FTE,
        months=[ResourceMonth(month=m, capacity_days=capacity[m]) for m in months],
        employees=employee_rows, profiles=profile_rows, ces_count=len(sel.entries), skipped=sel.skipped,
    )  # fmt: skip
