import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import AdminUser, EditorUser, SessionDep, get_or_404
from app.models import DEFAULT_BUSINESS_UNIT, BusinessUnit, Employee, Practice, User
from app.models.accounts import AUTHOR_ROLES
from app.schemas.business_units import (
    ApplyToCEsResult,
    BusinessUnitCreate,
    BusinessUnitOut,
    BusinessUnitRef,
    BusinessUnitUpdate,
    CERefOut,
    VisibilityIn,
    VisibilityOut,
    VisibilityReport,
)
from app.services import audit, visibility
from app.services import ce as ce_service

router = APIRouter(prefix="/business-units", tags=["Business unit"])

SYSTEM_MESSAGE = (
    f"La business unit «{DEFAULT_BUSINESS_UNIT}» è di sistema: non si rinomina né si disattiva"
)


def _name_taken(session, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(BusinessUnit.id).where(func.lower(BusinessUnit.name) == name.lower())
    if exclude_id:
        stmt = stmt.where(BusinessUnit.id != exclude_id)
    return session.scalar(stmt) is not None


def _is_system(unit: BusinessUnit) -> bool:
    return unit.name.lower() == DEFAULT_BUSINESS_UNIT.lower()


def _out(session, units: list[BusinessUnit]) -> list[BusinessUnitOut]:
    practices = dict(
        session.execute(
            select(Practice.business_unit_id, func.count(Practice.id))
            .where(Practice.is_active.is_(True))
            .group_by(Practice.business_unit_id)
        ).all()
    )
    employees = dict(
        session.execute(
            select(Practice.business_unit_id, func.count(Employee.id))
            .join(Employee, Employee.practice_id == Practice.id)
            .where(Employee.is_active.is_(True))
            .group_by(Practice.business_unit_id)
        ).all()
    )
    users = dict(
        session.execute(
            select(User.business_unit_id, func.count(User.id))
            .where(
                User.is_active.is_(True), User.role.in_(AUTHOR_ROLES), User.is_service.is_(False)
            )
            .group_by(User.business_unit_id)
        ).all()
    )
    return [
        BusinessUnitOut(
            id=u.id,
            name=u.name,
            is_active=u.is_active,
            practices_count=practices.get(u.id, 0),
            employees_count=employees.get(u.id, 0),
            users_count=users.get(u.id, 0),
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in units
    ]


@router.get(
    "/lookup", response_model=list[BusinessUnitRef], summary="Elenco minimo per filtri e menu"
)
def lookup_business_units(user: EditorUser, session: SessionDep) -> list[BusinessUnit]:
    """Id, nome e stato di tutte le business unit (admin, presale e responsabili: serve ai menu)."""
    return list(session.scalars(select(BusinessUnit).order_by(func.lower(BusinessUnit.name))).all())


@router.get("", response_model=list[BusinessUnitOut], summary="Elenco business unit")
def list_business_units(admin: AdminUser, session: SessionDep) -> list[BusinessUnitOut]:
    units = list(
        session.scalars(select(BusinessUnit).order_by(func.lower(BusinessUnit.name))).all()
    )
    return _out(session, units)


@router.post("", response_model=BusinessUnitOut, status_code=201, summary="Crea una business unit")
def create_business_unit(
    body: BusinessUnitCreate, admin: AdminUser, session: SessionDep
) -> BusinessUnitOut:
    if _name_taken(session, body.name):
        raise HTTPException(409, "Esiste già una business unit con questo nome")
    unit = BusinessUnit(**body.model_dump())
    session.add(unit)
    session.flush()
    audit.record(session, admin, "business_unit", unit.id, "create", body.model_dump())
    session.commit()
    return _out(session, [unit])[0]


def _visibility_out(session) -> VisibilityOut:
    return VisibilityOut(
        enabled=visibility.is_enabled(session),
        report=VisibilityReport(**visibility.report(session)),
    )


@router.get(
    "/visibility",
    response_model=VisibilityOut,
    summary="Visibilità per business unit: stato e rapporto",
)
def get_visibility(admin: AdminUser, session: SessionDep) -> VisibilityOut:
    """Dice se la visibilità per business unit è accesa e che cosa manca prima di accenderla
    (CE senza business unit, presale senza business unit, practice ancora in «Da assegnare»)."""
    return _visibility_out(session)


@router.put(
    "/visibility",
    response_model=VisibilityOut,
    summary="Accende o spegne la visibilità per business unit",
)
def put_visibility(body: VisibilityIn, admin: AdminUser, session: SessionDep) -> VisibilityOut:
    """Acceso: un presale o un responsabile vede i CE della propria business unit e i propri, per
    intero; gli altri no (risposta «non trovato»). Spento: tutti vedono tutto, come prima. Ogni
    cambio è registrato nello storico. Si può accendere anche con il rapporto non a zero."""
    visibility.set_enabled(session, admin, body.enabled)
    return _visibility_out(session)


@router.post(
    "/apply-to-existing-ces",
    response_model=ApplyToCEsResult,
    summary="Assegna le business unit ai CE esistenti",
)
def apply_to_existing_ces(admin: AdminUser, session: SessionDep) -> ApplyToCEsResult:
    """Per ogni CE senza business unit le ricava dal testo libero della versione e dalle practice
    dei collaboratori delle righe. Idempotente: non tocca i CE che ne hanno già e non assegna mai
    «Da assegnare». Va lanciata dopo aver creato le business unit e assegnato le practice."""
    updated, without = ce_service.derive_business_units_for_existing(session, admin)
    return ApplyToCEsResult(
        updated=updated,
        without_business_units=[CERefOut(ce_id=i, code=code) for i, code in without[:500]],
    )


@router.patch(
    "/{business_unit_id}", response_model=BusinessUnitOut, summary="Modifica una business unit"
)
def update_business_unit(
    business_unit_id: uuid.UUID, body: BusinessUnitUpdate, admin: AdminUser, session: SessionDep
) -> BusinessUnitOut:
    unit = get_or_404(session, BusinessUnit, business_unit_id, "Business unit")
    values = body.model_dump(exclude_unset=True)
    if values.get("name", "x") is None or values.get("is_active", True) is None:
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    if _is_system(unit) and (
        ("name" in values and values["name"].lower() != unit.name.lower())
        or values.get("is_active") is False
    ):
        raise HTTPException(409, SYSTEM_MESSAGE)
    if "name" in values and _name_taken(session, values["name"], exclude_id=unit.id):
        raise HTTPException(409, "Esiste già una business unit con questo nome")
    changes = audit.apply_changes(unit, values)
    if changes:
        audit.record(session, admin, "business_unit", unit.id, "update", changes)
        session.commit()
    return _out(session, [unit])[0]
