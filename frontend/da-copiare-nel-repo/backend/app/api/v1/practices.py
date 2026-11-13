import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import AdminUser, EditorUser, SessionDep, get_or_404
from app.models import DEFAULT_PRACTICE, BusinessUnit, Employee, Practice
from app.schemas.practices import PracticeCreate, PracticeOut, PracticeRef, PracticeUpdate
from app.services import audit

router = APIRouter(prefix="/practices", tags=["Practice"])

SYSTEM_MESSAGE = f"La practice «{DEFAULT_PRACTICE}» è di sistema: non si rinomina né si disattiva"


def _name_taken(session, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Practice.id).where(func.lower(Practice.name) == name.lower())
    if exclude_id:
        stmt = stmt.where(Practice.id != exclude_id)
    return session.scalar(stmt) is not None


def _is_system(practice: Practice) -> bool:
    return practice.name.lower() == DEFAULT_PRACTICE.lower()


def _require_business_unit(session, unit_id: uuid.UUID, current: uuid.UUID | None = None) -> None:
    """Deve esistere ed essere attiva, a meno che sia quella che la practice ha già."""
    unit = session.get(BusinessUnit, unit_id)
    if unit is None:
        raise HTTPException(422, "Business unit non trovata")
    if not unit.is_active and unit.id != current:
        raise HTTPException(422, "La business unit è disattivata: scegline un'altra")


def _out(session, practices: list[Practice]) -> list[PracticeOut]:
    unit_names = dict(session.execute(select(BusinessUnit.id, BusinessUnit.name)).all())
    counts = dict(
        session.execute(
            select(Employee.practice_id, func.count(Employee.id))
            .where(Employee.is_active.is_(True))
            .group_by(Employee.practice_id)
        ).all()
    )
    return [
        PracticeOut(
            id=p.id,
            name=p.name,
            is_active=p.is_active,
            employees_count=counts.get(p.id, 0),
            business_unit_id=p.business_unit_id,
            business_unit_name=unit_names[p.business_unit_id],
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in practices
    ]


@router.get("/lookup", response_model=list[PracticeRef], summary="Elenco minimo per filtri e menu")
def lookup_practices(user: EditorUser, session: SessionDep) -> list[Practice]:
    """Id, nome e stato di tutte le practice (admin e presale: serve ai filtri e ai menu)."""
    return list(session.scalars(select(Practice).order_by(func.lower(Practice.name))).all())


@router.get("", response_model=list[PracticeOut], summary="Elenco practice")
def list_practices(admin: AdminUser, session: SessionDep) -> list[PracticeOut]:
    practices = list(session.scalars(select(Practice).order_by(func.lower(Practice.name))).all())
    return _out(session, practices)


@router.post("", response_model=PracticeOut, status_code=201, summary="Crea una practice")
def create_practice(body: PracticeCreate, admin: AdminUser, session: SessionDep) -> PracticeOut:
    if _name_taken(session, body.name):
        raise HTTPException(409, "Esiste già una practice con questo nome")
    values = body.model_dump()
    if values["business_unit_id"] is not None:
        _require_business_unit(session, values["business_unit_id"])
    else:
        values.pop("business_unit_id")  # lo assegna il modello: «Da assegnare»
    practice = Practice(**values)
    session.add(practice)
    session.flush()
    audit.record(
        session,
        admin,
        "practice",
        practice.id,
        "create",
        {**values, "business_unit_id": str(practice.business_unit_id)},
    )
    session.commit()
    return _out(session, [practice])[0]


@router.patch("/{practice_id}", response_model=PracticeOut, summary="Modifica una practice")
def update_practice(
    practice_id: uuid.UUID, body: PracticeUpdate, admin: AdminUser, session: SessionDep
) -> PracticeOut:
    practice = get_or_404(session, Practice, practice_id, "Practice")
    values = body.model_dump(exclude_unset=True)
    if any(values.get(k, "x") is None for k in ("name", "is_active", "business_unit_id")):
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    if "business_unit_id" in values:
        _require_business_unit(
            session, values["business_unit_id"], current=practice.business_unit_id
        )
    if _is_system(practice) and (
        ("name" in values and values["name"].lower() != practice.name.lower())
        or values.get("is_active") is False
    ):
        raise HTTPException(409, SYSTEM_MESSAGE)
    if "name" in values and _name_taken(session, values["name"], exclude_id=practice.id):
        raise HTTPException(409, "Esiste già una practice con questo nome")
    changes = audit.apply_changes(practice, values)
    if changes:
        audit.record(session, admin, "practice", practice.id, "update", changes)
        session.commit()
    return _out(session, [practice])[0]
