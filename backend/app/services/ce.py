"""Logica di business dei conti economici: creazione, salvataggio, versioni, workflow."""

import calendar
import dataclasses
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app import engine
from app.engine import CalculationError, CEInput, CEResult, LineInput, PhaseInput
from app.engine import ProfileRate as EngineRate
from app.engine.periods import months_between
from app.models import (
    CE,
    DEFAULT_BUSINESS_UNIT,
    AuditLog,
    BusinessUnit,
    CEBusinessUnit,
    CELine,
    CELineAllocation,
    CEMilestone,
    CEPhase,
    CEVersion,
    CEVersionMonth,
    CEVersionRate,
    Client,
    Employee,
    NonWorkingDay,
    Practice,
    Profile,
    ProfileRate,
    User,
)
from app.models.accounts import AUTHOR_ROLES, EDITOR_ROLES
from app.notifications import (
    notify_ce_approved,
    notify_ce_new_version,
    notify_ce_rejected,
    notify_ce_submitted,
)
from app.schemas.business_units import BusinessUnitRef
from app.schemas.ce import (
    OUTCOME_LABELS,
    Actions,
    AllocationIn,
    AllocationOut,
    CalculationOut,
    CECreate,
    CEDetail,
    CEMeta,
    ContentIn,
    DuplicateIn,
    HeaderIn,
    HeaderOut,
    LineIn,
    LineOut,
    MilestoneIn,
    MilestoneOut,
    MonthIn,
    Outcome,
    OutcomeOut,
    PhaseIn,
    PhaseOut,
    RateOut,
    UserRef,
    VersionMeta,
)
from app.schemas.clients import ClientRef
from app.services import audit

OPEN_STATUSES = ("draft", "submitted", "rejected")
STANDARD_PHASES = [
    "Project Management",
    "Analysis",
    "Solution Design",
    "Tech Activities",
    "Testing",
    "Training",
    "Documentation",
    "Go-Live",
    "Stability Period",
]
FULL_LOAD = (
    selectinload(CEVersion.phases).selectinload(CEPhase.lines).selectinload(CELine.allocations),
    selectinload(CEVersion.rates),
    selectinload(CEVersion.months),
    selectinload(CEVersion.milestones),
)


# ======= errori
def unprocessable(message: str, issues: list[str] | None = None) -> HTTPException:
    return HTTPException(422, detail={"message": message, "issues": issues or [message]})


def conflict(message: str) -> HTTPException:
    return HTTPException(409, detail=message)


# ======= caricamento
def get_ce(session: Session, ce_id: uuid.UUID, *, include_deleted: bool = False) -> CE:
    ce = session.get(CE, ce_id)
    if ce is None or (ce.deleted_at is not None and not include_deleted):
        raise HTTPException(404, "CE non trovato")
    return ce


def get_latest_version(session: Session, ce: CE) -> CEVersion:
    return session.scalars(
        select(CEVersion)
        .where(CEVersion.ce_id == ce.id)
        .order_by(CEVersion.version_number.desc())
        .limit(1)
        .options(*FULL_LOAD)
    ).one()


def get_version(session: Session, ce: CE, number: int) -> CEVersion:
    version = session.scalars(
        select(CEVersion)
        .where(CEVersion.ce_id == ce.id, CEVersion.version_number == number)
        .options(*FULL_LOAD)
    ).one_or_none()
    if version is None:
        raise HTTPException(404, "Versione non trovata")
    return version


def get_latest_approved(session: Session, ce: CE) -> CEVersion | None:
    return session.scalars(
        select(CEVersion)
        .where(CEVersion.ce_id == ce.id, CEVersion.status == "approved")
        .order_by(CEVersion.version_number.desc())
        .limit(1)
    ).one_or_none()


def lock_version(session: Session, version: CEVersion) -> None:
    """Blocca la riga della versione fino al commit: serializza le modifiche concorrenti."""
    session.execute(select(CEVersion.id).where(CEVersion.id == version.id).with_for_update())
    session.refresh(version)


def latest_number(session: Session, ce: CE) -> int:
    return session.scalar(
        select(func.max(CEVersion.version_number)).where(CEVersion.ce_id == ce.id)
    )


# ======= tariffe e calendario
@dataclass(frozen=True)
class RateInfo:
    profile_id: uuid.UUID
    name: str
    is_external: bool
    sort_order: int
    daily_price: Any
    daily_cost: Any


def version_rates(session: Session, version: CEVersion) -> dict[uuid.UUID, RateInfo]:
    rows = session.execute(
        select(CEVersionRate, Profile)
        .join(Profile, Profile.id == CEVersionRate.profile_id)
        .where(CEVersionRate.version_id == version.id)
        .order_by(Profile.sort_order, func.lower(Profile.name))
    ).all()
    return {
        profile.id: RateInfo(
            profile.id,
            profile.name,
            profile.is_external,
            profile.sort_order,
            rate.daily_price,
            rate.daily_cost,
        )
        for rate, profile in rows
    }


def ensure_rates(
    session: Session,
    version: CEVersion,
    rates: dict[uuid.UUID, RateInfo],
    used: set[uuid.UUID],
    *,
    persist: bool,
    allow_inactive: bool = False,
) -> dict[uuid.UUID, RateInfo]:
    """Aggiunge dal listino dell'anno del CE le tariffe dei profili usati ma non ancora presenti."""
    missing = [pid for pid in used if pid not in rates]
    if not missing:
        return rates
    profiles = {p.id: p for p in session.scalars(select(Profile).where(Profile.id.in_(missing)))}
    listino = {
        r.profile_id: r
        for r in session.scalars(
            select(ProfileRate).where(
                ProfileRate.profile_id.in_(missing), ProfileRate.year == version.rate_year
            )
        )
    }
    issues, merged = [], dict(rates)
    for pid in missing:
        profile = profiles.get(pid)
        if profile is None:
            issues.append(f"Profilo {pid} non trovato")
        elif not profile.is_active and not allow_inactive:
            issues.append(f"Il profilo '{profile.name}' non è attivo")
        elif pid not in listino:
            issues.append(f"Nessuna tariffa {version.rate_year} per il profilo '{profile.name}'")
        else:
            rate = listino[pid]
            merged[pid] = RateInfo(
                pid,
                profile.name,
                profile.is_external,
                profile.sort_order,
                rate.daily_price,
                rate.daily_cost,
            )
            if persist:
                session.add(
                    CEVersionRate(
                        version_id=version.id,
                        profile_id=pid,
                        daily_price=rate.daily_price,
                        daily_cost=rate.daily_cost,
                    )
                )
    if issues:
        raise unprocessable("Tariffe non disponibili", issues)
    return dict(sorted(merged.items(), key=lambda kv: (kv[1].sort_order, kv[1].name.lower())))


def suggested_non_working(session: Session, months: list[date]) -> dict[date, int]:
    """Giorni feriali (lun-ven) del calendario generale che cadono in ciascun mese."""
    if not months:
        return {}
    last = max(months)
    upper = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
    counts: dict[date, int] = defaultdict(int)
    for day in session.scalars(
        select(NonWorkingDay.day).where(
            NonWorkingDay.day >= min(months), NonWorkingDay.day <= upper
        )
    ):
        if day.weekday() < 5:
            counts[day.replace(day=1)] += 1
    return {m: counts.get(m, 0) for m in months}


def resolve_non_working(
    session: Session, header: HeaderIn, provided: list[MonthIn]
) -> tuple[dict[date, int], list[str]]:
    """Giorni non lavorativi di ogni mese del progetto: inviati, altrimenti dal calendario."""
    issues: list[str] = []
    try:
        count = (header.end_date.year - header.start_date.year) * 12
        count += header.end_date.month - header.start_date.month + 1
        months = months_between(header.start_date, header.end_date) if 0 < count <= 12 else []
    except ValueError:  # pragma: no cover
        months = []
    given: dict[date, int] = {}
    for item in provided:
        if item.month.day != 1:
            issues.append(f"Giorni non lavorativi: {item.month} non è il primo giorno del mese")
        elif item.month not in months:
            issues.append(f"Giorni non lavorativi di {item.month:%m/%Y}: mese fuori dal progetto")
        elif item.month in given:
            issues.append(f"Giorni non lavorativi di {item.month:%m/%Y} indicati due volte")
        else:
            given[item.month] = item.non_working_days
    missing = [m for m in months if m not in given]
    suggestion = suggested_non_working(session, missing)
    return {m: given.get(m, suggestion.get(m, 0)) for m in months}, issues


# ======= contenuto <-> motore
def content_from_version(version: CEVersion) -> ContentIn:
    return ContentIn(
        header=HeaderIn(
            client_id=version.client_id,
            project_name=version.project_name,
            start_date=version.start_date,
            end_date=version.end_date,
            planning_mode=version.planning_mode,
            sf_opportunity=version.sf_opportunity,
            business_unit=version.business_unit,
            notes=version.notes,
            max_discount_pct=version.max_discount_pct,
            signed_price=version.signed_price,
        ),
        non_working_days=[
            MonthIn(month=m.month, non_working_days=m.non_working_days) for m in version.months
        ],
        phases=[
            PhaseIn(
                name=phase.name,
                contingency_pct=phase.contingency_pct,
                lines=[
                    LineIn(
                        activity=line.activity,
                        profile_id=line.profile_id,
                        employee_id=line.employee_id,
                        is_project_management=line.is_project_management,
                        hours=line.hours,
                        allocations=[
                            AllocationIn(month=a.month, pct=a.allocation_pct)
                            for a in line.allocations
                        ],
                    )
                    for line in phase.lines
                ],
            )
            for phase in version.phases
        ],
        milestones=[MilestoneIn(month=m.month, label=m.label) for m in version.milestones],
    )


def _pct(value):
    """Percentuali sempre a 2 decimali, come nel database: anteprima e salvataggio coincidono."""
    return value.quantize(Decimal("0.01"))


def to_engine_input(
    content: ContentIn, rates: dict[uuid.UUID, RateInfo], non_working: dict[date, int]
) -> CEInput:
    h = content.header
    return CEInput(
        start_date=h.start_date,
        end_date=h.end_date,
        mode=h.planning_mode,
        phases=[
            PhaseInput(
                name=phase.name,
                contingency_pct=_pct(phase.contingency_pct),
                lines=[
                    LineInput(
                        activity=line.activity,
                        profile=str(line.profile_id),
                        hours=line.hours,
                        allocations={a.month: a.pct for a in line.allocations},
                        is_project_management=line.is_project_management,
                    )
                    for line in phase.lines
                ],
            )
            for phase in content.phases
        ],
        rates={
            str(pid): EngineRate(r.daily_price, r.daily_cost, r.is_external)
            for pid, r in rates.items()
        },
        non_working_days=non_working,
        max_discount_pct=_pct(h.max_discount_pct),
        signed_price=h.signed_price,
    )


def _shape_issues(content: ContentIn) -> list[str]:
    issues = []
    for phase in content.phases:
        for line in phase.lines:
            months = [a.month for a in line.allocations]
            if len(months) != len(set(months)):
                issues.append(f"Fase '{phase.name}', riga '{line.activity}': mesi ripetuti nelle %")
    return issues


def _check_references(session: Session, content: ContentIn, *, new_client_check: bool) -> None:
    """Cliente e collaboratori devono esistere."""
    issues = []
    client = session.get(Client, content.header.client_id)
    if client is None:
        issues.append("Cliente non trovato")
    elif new_client_check and not client.is_active:
        issues.append(f"Il cliente '{client.name}' non è attivo")
    employee_ids = {
        line.employee_id for phase in content.phases for line in phase.lines if line.employee_id
    }
    if employee_ids:
        found = set(session.scalars(select(Employee.id).where(Employee.id.in_(employee_ids))))
        issues += [f"Collaboratore {e} non trovato" for e in sorted(employee_ids - found, key=str)]
    if issues:
        raise unprocessable("Riferimenti non validi", issues)


def prepare(
    session: Session,
    version: CEVersion,
    content: ContentIn,
    *,
    persist_rates: bool,
    allow_inactive: bool = False,
    new_client_check: bool = False,
) -> tuple[CEResult, dict[uuid.UUID, RateInfo], dict[date, int]]:
    """Controlla il contenuto, completa le tariffe e lo calcola. Solleva 422 se non è valido."""
    _check_references(session, content, new_client_check=new_client_check)
    non_working, issues = resolve_non_working(session, content.header, content.non_working_days)
    issues += _shape_issues(content)
    if issues:
        raise unprocessable("Dati del CE non validi", issues)
    used = {line.profile_id for phase in content.phases for line in phase.lines}
    rates = ensure_rates(
        session,
        version,
        version_rates(session, version) if version.id else {},
        used,
        persist=persist_rates,
        allow_inactive=allow_inactive,
    )
    ce_input = to_engine_input(content, rates, non_working)
    found = engine.validate(ce_input)
    if found:
        raise unprocessable("Dati del CE non validi", found)
    return engine.calculate(ce_input), rates, non_working


def build_summary(result: CEResult) -> dict[str, Any]:
    """Totali sintetici salvati sulla versione (elenchi veloci e viste ridotte)."""
    total, k = result.total, result.kpis

    def text(value):
        return None if value is None else str(value)

    return {
        "revenue": text(total.revenue),
        "cost": text(total.cost),
        "margin": text(total.margin),
        "margin_pct": text(total.margin_pct),
        "cost_ratio": text(total.cost_ratio),
        "days_total": text(k.days_total),
        "days_project_management": text(k.days_project_management),
        "days_delivery": text(k.days_delivery),
        "price_min": text(k.price_min),
        "signed_price": text(k.signed_price),
        "phases": [
            {"name": p.name, "revenue": text(p.revenue_with_contingency)} for p in result.phases
        ],
    }


def completeness_issues(result: CEResult) -> list[str]:
    issues = []
    if result.total.days == 0:
        issues.append("Il CE non contiene ore o percentuali di occupazione")
    return issues


# ======= scrittura del contenuto
def _write_content(
    session: Session,
    version: CEVersion,
    content: ContentIn,
    non_working: dict[date, int],
) -> None:
    """Sostituisce fasi, righe, mesi e milestone della versione con il contenuto indicato."""
    for model in (CEPhase, CEVersionMonth, CEMilestone):
        session.execute(delete(model).where(model.version_id == version.id))
    session.expire(version, ["phases", "months", "milestones"])
    for p_index, phase in enumerate(content.phases):
        session.add(
            CEPhase(
                version_id=version.id,
                position=p_index,
                name=phase.name,
                contingency_pct=phase.contingency_pct,
                lines=[
                    CELine(
                        position=l_index,
                        activity=line.activity,
                        profile_id=line.profile_id,
                        employee_id=line.employee_id,
                        is_project_management=line.is_project_management,
                        hours=line.hours,
                        allocations=[
                            CELineAllocation(month=a.month, allocation_pct=a.pct)
                            for a in line.allocations
                        ],
                    )
                    for l_index, line in enumerate(phase.lines)
                ],
            )
        )
    for month, days in non_working.items():
        session.add(CEVersionMonth(version_id=version.id, month=month, non_working_days=days))
    for milestone in content.milestones:
        session.add(
            CEMilestone(version_id=version.id, month=milestone.month, label=milestone.label)
        )


def _apply_header(version: CEVersion, header: HeaderIn) -> None:
    version.client_id = header.client_id
    version.project_name = header.project_name
    version.start_date = header.start_date
    version.end_date = header.end_date
    version.planning_mode = header.planning_mode
    version.sf_opportunity = header.sf_opportunity
    # `header.business_unit` è obsoleto e si ignora: il testo lo ricava il server dalle business
    # unit dichiarate (`ce_business_units`).
    version.notes = header.notes
    version.max_discount_pct = header.max_discount_pct
    version.signed_price = header.signed_price


def _bump(version: CEVersion) -> None:
    version.revision += 1


def _now() -> datetime:
    return datetime.now(UTC)


# ======= permessi
def is_owner_or_admin(user: User, ce: CE) -> bool:
    return user.role == "admin" or (user.role in AUTHOR_ROLES and ce.created_by == user.id)


OUTCOME_LABEL = OUTCOME_LABELS


def compute_actions(
    user: User,
    ce: CE,
    version: CEVersion,
    latest: int,
    owner_is_service: bool = False,
    has_business_units: bool = True,
    manager_involved: bool = False,
) -> Actions:
    is_admin = user.role == "admin"
    mine = is_owner_or_admin(user, ce)
    is_latest = version.version_number == latest
    status = version.status
    open_ = is_latest and status in OPEN_STATUSES
    return Actions(
        edit=is_latest
        and ((status in ("draft", "rejected") and mine) or (status == "submitted" and is_admin)),
        submit=open_ and status in ("draft", "rejected") and mine,
        withdraw=open_ and status == "submitted" and mine,
        # admin: sempre; responsabile di una business unit coinvolta: solo un CE in approvazione
        approve=open_ and (is_admin or (manager_involved and status == "submitted")),
        reject=open_ and status == "submitted" and (is_admin or manager_involved),
        # dopo Close Lost non si fa una nuova versione finché l'esito non viene tolto
        new_version=is_latest and status == "approved" and mine and ce.outcome != "lost",
        discard_version=open_
        and version.version_number > 1
        and mine
        and (is_admin or status in ("draft", "rejected")),
        realign=open_ and is_admin,
        delete=is_admin and ce.outcome is None,
        delete_blocked_reason=(
            f"Il CE ha l'esito «{OUTCOME_LABEL[ce.outcome]}»: toglilo prima di eliminarlo"
            if is_admin and ce.outcome
            else None
        ),
        assign=is_admin and owner_is_service,
        # in bozza o rifiutato; e, per riparare un CE vecchio che non ne ha nessuna, l'admin sempre
        set_business_units=is_latest
        and mine
        and (status in ("draft", "rejected") or (is_admin and not has_business_units)),
        # l'esito si gestisce solo quando l'ultima versione è approvata
        set_outcome=is_latest
        and status == "approved"
        and ce.deleted_at is None
        and (
            is_admin or manager_involved or (user.role in EDITOR_ROLES and ce.created_by == user.id)
        ),
    )


def is_involved_manager(user: User, involved_unit_ids: list[uuid.UUID]) -> bool:
    """Responsabile di business unit la cui business unit è tra quelle coinvolte nel CE."""
    return (
        user.role == "bu_manager"
        and user.business_unit_id is not None
        and user.business_unit_id in involved_unit_ids
    )


def require_approver(session: Session, user: User, ce: CE, version: CEVersion) -> None:
    """Approva o rifiuta: un admin sempre; il responsabile di una business unit coinvolta solo un CE
    in approvazione (con più business unit basta il responsabile di una qualsiasi)."""
    if user.role == "admin":
        return
    involved = [u[0] for u in ce_business_units(session, [ce.id]).get(ce.id, [])]
    if is_involved_manager(user, involved) and version.status == "submitted":
        return
    raise HTTPException(
        403,
        "Può approvare o rifiutare solo un amministratore o il responsabile di una business unit "
        "coinvolta (un CE in approvazione)",
    )


def require_owner(user: User, ce: CE) -> None:
    if not is_owner_or_admin(user, ce):
        raise HTTPException(403, "Puoi modificare solo i CE creati da te")


def require_latest(session: Session, ce: CE, version: CEVersion) -> None:
    if version.version_number != latest_number(session, ce):
        raise conflict("Si può operare solo sull'ultima versione del CE")


# ======= creazione
def validate_header(header: HeaderIn) -> None:
    """Controlli sulla testata (date, periodo, sconto, prezzo firmato) prima di scrivere dati."""
    issues = engine.validate(
        CEInput(
            start_date=header.start_date,
            end_date=header.end_date,
            mode=header.planning_mode,
            phases=[],
            rates={},
            max_discount_pct=header.max_discount_pct,
            signed_price=header.signed_price,
        )
    )
    if issues:
        raise unprocessable("Dati del CE non validi", issues)


def _new_ce_with_version(
    session: Session, actor: User, code: str, header: HeaderIn
) -> tuple[CE, CEVersion]:
    if session.scalar(select(CE.id).where(func.lower(CE.code) == code.lower())):
        raise conflict("Esiste già un CE con questo codice (anche tra quelli eliminati)")
    year = header.start_date.year
    listino = session.execute(
        select(Profile, ProfileRate)
        .join(ProfileRate, ProfileRate.profile_id == Profile.id)
        .where(ProfileRate.year == year, Profile.is_active)
    ).all()
    if not listino:
        raise unprocessable(
            f"Nessuna tariffa per l'anno {year}",
            [f"Il listino {year} non è stato caricato: chiedi a un amministratore"],
        )
    ce = CE(code=code, created_by=actor.id)
    session.add(ce)
    session.flush()
    version = CEVersion(
        ce_id=ce.id,
        version_number=1,
        status="draft",
        rate_year=year,
        created_by=actor.id,
        client_id=header.client_id,
        project_name=header.project_name,
        start_date=header.start_date,
        end_date=header.end_date,
        planning_mode=header.planning_mode,
    )
    _apply_header(version, header)
    session.add(version)
    session.flush()
    for profile, rate in listino:
        session.add(
            CEVersionRate(
                version_id=version.id,
                profile_id=profile.id,
                daily_price=rate.daily_price,
                daily_cost=rate.daily_cost,
            )
        )
    session.flush()
    return ce, version


# ======= business unit coinvolte
def business_unit_label(names: list[str]) -> str | None:
    """Il testo (max 100 caratteri) che dashboard, Excel e PDF mostrano come «business unit»."""
    label = " · ".join(sorted(names, key=str.lower))
    if not label:
        return None
    return label if len(label) <= 100 else label[:99] + "…"


def ce_business_units(
    session: Session, ce_ids
) -> dict[uuid.UUID, list[tuple[uuid.UUID, str, bool]]]:
    """Business unit coinvolte di ciascun CE (id, nome, attiva), in ordine alfabetico."""
    ids = list(ce_ids)
    if not ids:
        return {}
    rows = session.execute(
        select(CEBusinessUnit.ce_id, BusinessUnit.id, BusinessUnit.name, BusinessUnit.is_active)
        .join(BusinessUnit, BusinessUnit.id == CEBusinessUnit.business_unit_id)
        .where(CEBusinessUnit.ce_id.in_(ids))
        .order_by(func.lower(BusinessUnit.name))
    ).all()
    out: dict[uuid.UUID, list[tuple[uuid.UUID, str, bool]]] = {}
    for ce_id, unit_id, name, active in rows:
        out.setdefault(ce_id, []).append((unit_id, name, active))
    return out


def line_business_units(session: Session, version: CEVersion) -> list[tuple[uuid.UUID, str, bool]]:
    """Business unit dei collaboratori indicati nelle righe (quella della loro practice)."""
    return [
        (r[0], r[1], r[2])
        for r in session.execute(
            select(BusinessUnit.id, BusinessUnit.name, BusinessUnit.is_active)
            .join(Practice, Practice.business_unit_id == BusinessUnit.id)
            .join(Employee, Employee.practice_id == Practice.id)
            .join(CELine, CELine.employee_id == Employee.id)
            .join(CEPhase, CEPhase.id == CELine.phase_id)
            .where(
                CEPhase.version_id == version.id,
                func.lower(BusinessUnit.name) != DEFAULT_BUSINESS_UNIT.lower(),
            )
            .group_by(BusinessUnit.id, BusinessUnit.name, BusinessUnit.is_active)
            .order_by(func.lower(BusinessUnit.name))
        ).all()
    ]


def undeclared_business_units(
    session: Session, version: CEVersion, declared: list[tuple[uuid.UUID, str, bool]]
) -> list[tuple[uuid.UUID, str, bool]]:
    """Business unit che hanno collaboratori nelle righe ma non sono tra quelle coinvolte."""
    declared_ids = {u[0] for u in declared}
    return [u for u in line_business_units(session, version) if u[0] not in declared_ids]


def _validate_business_units(
    session: Session, ids: list[uuid.UUID], keep: frozenset[uuid.UUID] = frozenset()
) -> list[BusinessUnit]:
    """Almeno una, esistenti, vere (non «Da assegnare») e attive, salvo quelle già coinvolte."""
    unique = list(dict.fromkeys(ids))
    if not unique:
        raise unprocessable("Indica almeno una business unit coinvolta")
    found = {
        u.id: u for u in session.scalars(select(BusinessUnit).where(BusinessUnit.id.in_(unique)))
    }
    for unit_id in unique:
        unit = found.get(unit_id)
        if unit is None:
            raise unprocessable("Business unit non trovata")
        if unit.name.lower() == DEFAULT_BUSINESS_UNIT.lower():
            raise unprocessable(
                f"«{DEFAULT_BUSINESS_UNIT}» non è coinvolgibile: scegli una business unit vera"
            )
        if not unit.is_active and unit_id not in keep:
            raise unprocessable(f"La business unit «{unit.name}» è disattivata: scegline un'altra")
    return [found[i] for i in unique]


def _attach_business_units(
    session: Session, ce: CE, version: CEVersion, units: list[BusinessUnit]
) -> None:
    for unit in units:
        session.add(CEBusinessUnit(ce_id=ce.id, business_unit_id=unit.id))
    version.business_unit = business_unit_label([u.name for u in units])
    session.flush()


def set_business_units(
    session: Session, actor: User, ce: CE, ids: list[uuid.UUID], *, commit: bool = True
) -> None:
    """Cambia le business unit coinvolte: autore o admin, finché il CE è in bozza o rifiutato."""
    require_owner(actor, ce)
    version = get_latest_version(session, ce)
    lock_version(session, version)
    current = ce_business_units(session, [ce.id]).get(ce.id, [])
    repair = (
        actor.role == "admin" and not current
    )  # CE vecchio senza business unit: lo ripara l'admin
    if version.status not in ("draft", "rejected") and not repair:
        raise conflict(
            "Le business unit coinvolte si cambiano solo finché il CE è in bozza o rifiutato"
        )
    units = _validate_business_units(session, ids, keep=frozenset(u[0] for u in current))
    if {u.id for u in units} == {u[0] for u in current}:
        return
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id == ce.id))
    session.flush()
    _attach_business_units(session, ce, version, units)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "set_business_units",
        {"from": [u[1] for u in current], "to": sorted((u.name for u in units), key=str.lower)},
    )
    if commit:
        session.commit()
    else:
        session.flush()


def derive_business_units_for_existing(
    session: Session, actor: User
) -> tuple[int, list[tuple[uuid.UUID, str]]]:
    """Assegna le business unit ai CE che non ne hanno, ricavandole dal testo libero della versione
    (i nomi separati da «·», virgola, barra o punto e virgola) e dalle practice dei collaboratori
    delle righe. Non tocca i CE che ne hanno già e non assegna mai «Da assegnare». Ritorna quanti
    CE ha aggiornato e quali restano senza business unit (visibili solo ad autore e admin)."""
    units = {
        u.id: u
        for u in session.scalars(
            select(BusinessUnit).where(
                func.lower(BusinessUnit.name) != DEFAULT_BUSINESS_UNIT.lower()
            )
        )
    }
    by_name = {u.name.lower(): u for u in units.values()}
    declared = select(CEBusinessUnit.ce_id)
    updated = 0
    without: list[tuple[uuid.UUID, str]] = []
    for ce in session.scalars(
        select(CE).where(CE.id.not_in(declared)).order_by(func.lower(CE.code))
    ):
        version = get_latest_version(session, ce)
        found: dict[uuid.UUID, BusinessUnit] = {}
        for part in re.split(r"[·,;/|]", version.business_unit or ""):
            if unit := by_name.get(part.strip().lower()):
                found[unit.id] = unit
        for unit_id, _, _ in line_business_units(session, version):
            if unit_id in units:
                found.setdefault(unit_id, units[unit_id])
        if not found:
            without.append((ce.id, ce.code))
            continue
        chosen = sorted(found.values(), key=lambda u: u.name.lower())
        _attach_business_units(session, ce, version, chosen)
        audit.record(
            session,
            actor,
            "ce",
            ce.id,
            "set_business_units",
            {"from": [], "to": [u.name for u in chosen], "origin": "assegnazione ai CE esistenti"},
        )
        updated += 1
    session.commit()
    return updated, without


def create_ce(session: Session, actor: User, data: CECreate, *, commit: bool = True) -> CEVersion:
    units = _validate_business_units(session, data.business_unit_ids)
    header = HeaderIn(**data.model_dump(exclude={"code", "standard_phases", "business_unit_ids"}))
    validate_header(header)
    content = ContentIn(
        header=header,
        phases=[PhaseIn(name=name) for name in STANDARD_PHASES] if data.standard_phases else [],
    )
    _check_references(session, content, new_client_check=True)
    ce, version = _new_ce_with_version(session, actor, data.code, header)
    _attach_business_units(session, ce, version, units)
    session.refresh(version)
    result, _, non_working = prepare(session, version, content, persist_rates=False)
    _write_content(session, version, content, non_working)
    version.summary = build_summary(result)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "create",
        {
            "code": ce.code,
            "version": 1,
            "rate_year": version.rate_year,
            "planning_mode": header.planning_mode,
            "business_units": sorted((u.name for u in units), key=str.lower),
        },
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return get_latest_version(session, ce)


# ======= salvataggio
def save_content(
    session: Session,
    actor: User,
    ce: CE,
    version: CEVersion,
    content: ContentIn,
    *,
    commit: bool = True,
) -> None:
    require_owner(actor, ce)
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status == "approved":
        raise conflict("Un CE approvato non si modifica: crea una nuova versione")
    if version.status == "submitted" and actor.role != "admin":
        raise conflict("Il CE è in approvazione: ritiralo per modificarlo")
    if content.expected_revision is None:
        raise unprocessable(
            "Manca la revisione", ["Indica expected_revision (quella ricevuta nell'ultima lettura)"]
        )
    if content.expected_revision != version.revision:
        raise HTTPException(
            409,
            detail={
                "message": "Il CE è stato modificato da qualcun altro: ricarica prima di salvare",
                "current_revision": version.revision,
            },
        )
    new_client = content.header.client_id != version.client_id
    result, _, non_working = prepare(
        session, version, content, persist_rates=True, new_client_check=new_client
    )
    before = content_from_version(version)
    _write_content(session, version, content, non_working)
    changed_header = {
        field: [str(getattr(before.header, field)), str(getattr(content.header, field))]
        for field in type(content.header).model_fields
        if field != "business_unit"  # obsoleto: lo ricava il server
        and getattr(before.header, field) != getattr(content.header, field)
    }
    _apply_header(version, content.header)
    version.summary = build_summary(result)
    _bump(version)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "save",
        {
            "version": version.version_number,
            "revision": version.revision,
            "header": changed_header,
            "phases": len(content.phases),
            "lines": sum(len(p.lines) for p in content.phases),
        },
    )
    if commit:
        session.commit()
    else:
        session.flush()


# ======= workflow
def _calculate_version(session: Session, version: CEVersion) -> CEResult:
    session.refresh(version)
    content = content_from_version(version)
    rates = version_rates(session, version)
    non_working = {m.month: m.non_working_days for m in version.months}
    ce_input = to_engine_input(content, rates, non_working)
    try:
        return engine.calculate(ce_input)
    except CalculationError as exc:
        raise unprocessable("Dati del CE non validi", exc.issues) from exc


def submit(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    require_owner(actor, ce)
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status not in ("draft", "rejected"):
        raise conflict(f"Un CE in stato '{version.status}' non può essere inviato in approvazione")
    result = _calculate_version(session, version)
    if issues := completeness_issues(result):
        raise unprocessable("CE incompleto", issues)
    declared = ce_business_units(session, [ce.id]).get(ce.id, [])
    if not declared:
        raise unprocessable("CE incompleto", ["Indica almeno una business unit coinvolta"])
    if missing := undeclared_business_units(session, version, declared):
        raise unprocessable(
            "Le business unit coinvolte non coincidono con i collaboratori delle righe",
            [
                f"«{name}» ha collaboratori nelle righe ma non è tra le business unit coinvolte"
                for _, name, _ in missing
            ],
        )
    version.status = "submitted"
    version.submitted_at = _now()
    version.rejected_by = version.rejected_at = version.rejection_reason = None
    version.summary = build_summary(result)
    _bump(version)
    notify_ce_submitted(session, actor, ce, version)
    audit.record(session, actor, "ce", ce.id, "submit", {"version": version.version_number})
    session.commit()


def withdraw(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    require_owner(actor, ce)
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status != "submitted":
        raise conflict("Solo un CE in approvazione può essere ritirato")
    version.status = "draft"
    version.submitted_at = None
    _bump(version)
    audit.record(session, actor, "ce", ce.id, "withdraw", {"version": version.version_number})
    session.commit()


def approve(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    """Solo admin, sempre: anche da bozza o da rifiutato."""
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status == "approved":
        raise conflict("Il CE è già approvato")
    result = _calculate_version(session, version)
    if issues := completeness_issues(result):
        raise unprocessable("CE incompleto", issues)
    summary = build_summary(result)
    version.status = "approved"
    version.approved_by = actor.id
    version.approved_at = _now()
    version.approved_totals = summary
    version.summary = summary
    version.rejected_by = version.rejected_at = version.rejection_reason = None
    _bump(version)
    notify_ce_approved(session, actor, ce, version)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "approve",
        {"version": version.version_number, "revenue": summary["revenue"], "cost": summary["cost"]},
    )
    session.commit()


def reject(session: Session, actor: User, ce: CE, version: CEVersion, reason: str) -> None:
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status != "submitted":
        raise conflict("Si può rifiutare solo un CE in approvazione")
    version.status = "rejected"
    version.rejected_by = actor.id
    version.rejected_at = _now()
    version.rejection_reason = reason
    _bump(version)
    notify_ce_rejected(session, actor, ce, version, reason)
    audit.record(
        session, actor, "ce", ce.id, "reject", {"version": version.version_number, "reason": reason}
    )
    session.commit()


# ======= versioni
def new_version(session: Session, actor: User, ce: CE) -> CEVersion:
    require_owner(actor, ce)
    if ce.outcome == "lost":
        raise conflict("Il CE è Close Lost: togli l'esito per creare una nuova versione")
    latest = get_latest_version(session, ce)
    lock_version(session, latest)
    if latest.status != "approved":
        raise conflict("Esiste già una versione in lavorazione")
    version = CEVersion(
        ce_id=ce.id,
        version_number=latest.version_number + 1,
        status="draft",
        rate_year=latest.rate_year,
        created_by=actor.id,
        client_id=latest.client_id,
        project_name=latest.project_name,
        start_date=latest.start_date,
        end_date=latest.end_date,
        planning_mode=latest.planning_mode,
        summary=latest.summary,
    )
    _apply_header(version, content_from_version(latest).header)
    version.business_unit = latest.business_unit  # il testo ricavato dalle business unit dichiarate
    session.add(version)
    session.flush()
    for rate in latest.rates:
        session.add(
            CEVersionRate(
                version_id=version.id,
                profile_id=rate.profile_id,
                daily_price=rate.daily_price,
                daily_cost=rate.daily_cost,
            )
        )
    content = content_from_version(latest)
    _write_content(session, version, content, {m.month: m.non_working_days for m in latest.months})
    notify_ce_new_version(session, actor, ce, version)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "new_version",
        {"version": version.version_number, "from": latest.version_number},
    )
    session.commit()
    return get_latest_version(session, ce)


def discard_open_version(session: Session, actor: User, ce: CE) -> int:
    require_owner(actor, ce)
    latest = get_latest_version(session, ce)
    lock_version(session, latest)
    if latest.status not in OPEN_STATUSES:
        raise conflict("Non c'è nessuna versione in lavorazione da scartare")
    if latest.version_number == 1:
        raise conflict("È la prima versione: per eliminare il CE serve un amministratore")
    if latest.status == "submitted" and actor.role != "admin":
        raise conflict("Il CE è in approvazione: ritiralo prima di scartarlo")
    number = latest.version_number
    session.delete(latest)
    audit.record(session, actor, "ce", ce.id, "discard_version", {"version": number})
    session.commit()
    return number


# ======= riallineamento, duplicazione
def realign(
    session: Session, actor: User, ce: CE, version: CEVersion, *, rates: bool, calendar_: bool
) -> None:
    lock_version(session, version)
    require_latest(session, ce, version)
    if version.status not in OPEN_STATUSES:
        raise conflict("Un CE approvato non si riallinea: crea una nuova versione")
    changes: dict[str, Any] = {"version": version.version_number}
    if rates:
        listino = {
            r.profile_id: r
            for r in session.scalars(
                select(ProfileRate).where(ProfileRate.year == version.rate_year)
            )
        }
        present = {r.profile_id: r for r in version.rates}
        updated = added = 0
        for pid, rate in present.items():
            fresh = listino.get(pid)
            if fresh and (
                rate.daily_price != fresh.daily_price or rate.daily_cost != fresh.daily_cost
            ):
                rate.daily_price, rate.daily_cost = fresh.daily_price, fresh.daily_cost
                updated += 1
        active = {p.id for p in session.scalars(select(Profile).where(Profile.is_active))}
        for pid, fresh in listino.items():
            if pid in active and pid not in present:
                session.add(
                    CEVersionRate(
                        version_id=version.id,
                        profile_id=pid,
                        daily_price=fresh.daily_price,
                        daily_cost=fresh.daily_cost,
                    )
                )
                added += 1
        changes["rates"] = {"updated": updated, "added": added}
    if calendar_:
        months = [m.month for m in version.months]
        suggestion = suggested_non_working(session, months)
        changed = 0
        for row in version.months:
            if row.non_working_days != suggestion[row.month]:
                row.non_working_days = suggestion[row.month]
                changed += 1
        changes["calendar"] = {"months_changed": changed}
    session.flush()
    session.expire(version, ["rates", "months"])
    result = _calculate_version(session, version)
    version.summary = build_summary(result)
    _bump(version)
    audit.record(session, actor, "ce", ce.id, "realign", changes)
    session.commit()


def duplicate(
    session: Session, actor: User, source_ce: CE, source: CEVersion, data: DuplicateIn
) -> CEVersion:
    source_units = ce_business_units(session, [source_ce.id]).get(source_ce.id, [])
    units = _validate_business_units(
        session,
        data.business_unit_ids or [u[0] for u in source_units],
        keep=frozenset(u[0] for u in source_units),
    )
    old_months = months_between(source.start_date, source.end_date)
    new_header = HeaderIn(
        client_id=data.client_id or source.client_id,
        project_name=data.project_name or source.project_name,
        start_date=data.start_date,
        end_date=data.end_date,
        planning_mode=source.planning_mode,
        business_unit=source.business_unit,
    )
    validate_header(new_header)
    try:
        new_months = (
            months_between(data.start_date, data.end_date)
            if data.end_date >= data.start_date
            else []
        )
    except ValueError:  # pragma: no cover
        new_months = []
    month_map = dict(zip(old_months, new_months, strict=False))

    def remap(allocs):
        return [
            AllocationIn(month=month_map[a.month], pct=a.pct)
            for a in allocs
            if a.month in month_map
        ]

    source_content = content_from_version(source)
    content = ContentIn(
        header=new_header,
        phases=[
            PhaseIn(
                name=phase.name,
                contingency_pct=phase.contingency_pct,
                lines=[
                    line.model_copy(update={"allocations": remap(line.allocations)})
                    for line in phase.lines
                ],
            )
            for phase in source_content.phases
        ],
        milestones=[
            MilestoneIn(month=month_map[m.month], label=m.label)
            for m in source_content.milestones
            if m.month in month_map
        ],
    )
    _check_references(session, content, new_client_check=True)
    ce, version = _new_ce_with_version(session, actor, data.code, new_header)
    _attach_business_units(session, ce, version, units)
    session.refresh(version)
    result, _, non_working = prepare(
        session, version, content, persist_rates=True, allow_inactive=True
    )
    _write_content(session, version, content, non_working)
    version.summary = build_summary(result)
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "duplicate",
        {"code": ce.code, "from_ce": str(source_ce.id), "from_version": source.version_number},
    )
    session.commit()
    return get_latest_version(session, ce)


def set_deleted(session: Session, actor: User, ce: CE, deleted: bool) -> None:
    if deleted:
        if ce.deleted_at is not None:
            raise conflict("Il CE è già eliminato")
        if ce.outcome:
            raise conflict(
                f"Il CE ha l'esito «{OUTCOME_LABEL[ce.outcome]}»: toglilo prima di eliminarlo"
            )
        ce.deleted_at, ce.deleted_by = _now(), actor.id
    else:
        if ce.deleted_at is None:
            raise conflict("Il CE non è eliminato")
        ce.deleted_at = ce.deleted_by = None
    audit.record(session, actor, "ce", ce.id, "delete" if deleted else "restore", {"code": ce.code})
    session.commit()


# ======= esito della trattativa
def set_outcome(
    session: Session, actor: User, ce: CE, outcome: Outcome | None, note: str | None
) -> None:
    """Imposta, cambia o toglie l'esito («Close Won» / «Close Lost»).

    Lo fanno l'admin, il responsabile di una business unit coinvolta e l'autore, e solo quando
    l'**ultima versione è approvata**. Valore, data e autore si registrano da soli; la nota
    (il motivo, per Close Lost) è facoltativa. Ogni cambio finisce nello storico.
    """
    latest = get_latest_version(session, ce)
    lock_version(session, latest)
    involved = [u[0] for u in ce_business_units(session, [ce.id]).get(ce.id, [])]
    author = actor.role in EDITOR_ROLES and ce.created_by == actor.id
    if not (actor.role == "admin" or is_involved_manager(actor, involved) or author):
        raise HTTPException(
            403,
            "L'esito lo imposta l'amministratore, il responsabile di una business unit "
            "coinvolta o l'autore del CE",
        )
    if latest.status != "approved":
        raise conflict("L'esito si imposta solo quando l'ultima versione è approvata")
    note = (note or "").strip() or None
    if outcome is None and note:
        raise unprocessable("La nota serve solo insieme a un esito")
    if (outcome, note) == (ce.outcome, ce.outcome_note):
        return
    before = ce.outcome
    if outcome is None:
        ce.outcome = ce.outcome_at = ce.outcome_by = ce.outcome_note = None
    else:
        ce.outcome, ce.outcome_at, ce.outcome_by, ce.outcome_note = outcome, _now(), actor.id, note
    audit.record(
        session, actor, "ce", ce.id, "set_outcome", {"from": before, "to": outcome, "note": note}
    )
    session.commit()


def outcome_out(session: Session, ce: CE) -> OutcomeOut | None:
    if ce.outcome is None:
        return None
    by = session.get(User, ce.outcome_by)
    return OutcomeOut(
        value=ce.outcome,
        at=ce.outcome_at,
        by=UserRef(id=by.id, full_name=by.full_name, is_service=by.is_service),
        note=ce.outcome_note,
    )


# ======= lettura: dettaglio
def assign_owner(session: Session, actor: User, ce: CE, target: User) -> None:
    """Un amministratore assegna a un presale un CE creato da un'integrazione.

    Da quel momento il presale può modificarlo e inviarlo in approvazione, e l'integrazione che
    l'aveva creato non può più modificarlo (resta leggibile).
    """
    if actor.role != "admin":
        raise HTTPException(403, "Solo un amministratore può assegnare un CE")
    current = session.get(User, ce.created_by)
    if current is None or not current.is_service:
        raise conflict("Si possono assegnare solo i CE creati da un'integrazione")
    if target.role != "presale" or target.is_service or not target.is_active:
        raise unprocessable(
            "Destinatario non valido", ["Scegli un utente presale attivo (non di servizio)"]
        )
    ce.created_by = target.id
    audit.record(
        session,
        actor,
        "ce",
        ce.id,
        "assign",
        {"from": current.full_name, "to": target.full_name, "to_user_id": str(target.id)},
    )
    session.commit()


def serialize_calculation(result: CEResult, names: dict[str, str]) -> CalculationOut:
    data = dataclasses.asdict(result)
    for row in data["lines"] + data["profiles"]:
        key = row.pop("profile")
        row["profile_id"] = key
        row["profile_name"] = names.get(key, "?")
    return CalculationOut.model_validate(data)


def _user_ref(session: Session, user_id: uuid.UUID | None) -> UserRef | None:
    if user_id is None:
        return None
    user = session.get(User, user_id)
    return (
        UserRef(id=user.id, full_name=user.full_name, is_service=user.is_service) if user else None
    )


def build_detail(session: Session, user: User, ce: CE, version: CEVersion) -> CEDetail:
    session.refresh(version)
    content = content_from_version(version)
    rates = version_rates(session, version)
    non_working = {m.month: m.non_working_days for m in version.months}
    result = engine.calculate(to_engine_input(content, rates, non_working))
    names = {str(pid): r.name for pid, r in rates.items()}
    client = session.get(Client, version.client_id)
    latest = latest_number(session, ce)
    owner = session.get(User, ce.created_by)
    declared_units = ce_business_units(session, [ce.id]).get(ce.id, [])
    employee_ids = {
        line.employee_id for phase in version.phases for line in phase.lines if line.employee_id
    }
    employee_names = (
        {
            e.id: f"{e.first_name} {e.last_name}"
            for e in session.scalars(select(Employee).where(Employee.id.in_(employee_ids)))
        }
        if employee_ids
        else {}
    )
    return CEDetail(
        ce=CEMeta(
            id=ce.id,
            code=ce.code,
            owner=UserRef(id=owner.id, full_name=owner.full_name, is_service=owner.is_service),
            created_at=ce.created_at,
            versions_count=latest,
            requested_by=ce.requested_by,
        ),
        version=VersionMeta(
            number=version.version_number,
            status=version.status,
            revision=version.revision,
            rate_year=version.rate_year,
            created_at=version.created_at,
            updated_at=version.updated_at,
            submitted_at=version.submitted_at,
            approved_at=version.approved_at,
            approved_by=_user_ref(session, version.approved_by),
            rejected_at=version.rejected_at,
            rejected_by=_user_ref(session, version.rejected_by),
            rejection_reason=version.rejection_reason,
        ),
        header=HeaderOut(
            client=ClientRef.model_validate(client),
            project_name=version.project_name,
            start_date=version.start_date,
            end_date=version.end_date,
            planning_mode=version.planning_mode,
            sf_opportunity=version.sf_opportunity,
            business_unit=version.business_unit,
            notes=version.notes,
            max_discount_pct=version.max_discount_pct,
            signed_price=version.signed_price,
        ),
        phases=[
            PhaseOut(
                id=phase.id,
                name=phase.name,
                contingency_pct=phase.contingency_pct,
                lines=[
                    LineOut(
                        id=line.id,
                        activity=line.activity,
                        profile_id=line.profile_id,
                        profile_name=names.get(str(line.profile_id), "?"),
                        employee_id=line.employee_id,
                        employee_name=employee_names.get(line.employee_id),
                        is_project_management=line.is_project_management,
                        hours=line.hours,
                        allocations=[
                            AllocationOut(month=a.month, pct=a.allocation_pct)
                            for a in line.allocations
                        ],
                    )
                    for line in phase.lines
                ],
            )
            for phase in version.phases
        ],
        rates=[
            RateOut(
                profile_id=r.profile_id,
                profile_name=r.name,
                is_external=r.is_external,
                daily_price=r.daily_price,
                daily_cost=r.daily_cost,
            )
            for r in rates.values()
        ],
        milestones=[MilestoneOut(month=m.month, label=m.label) for m in version.milestones],
        calculation=serialize_calculation(result, names),
        actions=compute_actions(
            user,
            ce,
            version,
            latest,
            owner.is_service,
            has_business_units=bool(declared_units),
            manager_involved=is_involved_manager(user, [u[0] for u in declared_units]),
        ),
        outcome=outcome_out(session, ce),
        business_units=[BusinessUnitRef(id=i, name=n, is_active=a) for i, n, a in declared_units],
        undeclared_business_units=[
            BusinessUnitRef(id=i, name=n, is_active=a)
            for i, n, a in undeclared_business_units(session, version, declared_units)
        ],
    )


def preview(session: Session, ce: CE, version: CEVersion, content: ContentIn) -> CalculationOut:
    """Calcolo di anteprima: non salva nulla (nemmeno le tariffe dei profili nuovi)."""
    result, rates, _ = prepare(session, version, content, persist_rates=False)
    return serialize_calculation(result, {str(pid): r.name for pid, r in rates.items()})


def history(session: Session, ce: CE, limit: int = 200) -> list[tuple[AuditLog, User | None]]:
    rows = session.execute(
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.entity_type == "ce", AuditLog.entity_id == ce.id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()
    return [(entry, user) for entry, user in rows]
