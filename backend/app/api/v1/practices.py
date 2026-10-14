import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import AdminUser, EditorUser, SessionDep, get_or_404
from app.models import DEFAULT_PRACTICE, Employee, Practice
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


def _out(session, practices: list[Practice]) -> list[PracticeOut]:
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
    practice = Practice(**body.model_dump())
    session.add(practice)
    session.flush()
    audit.record(session, admin, "practice", practice.id, "create", body.model_dump())
    session.commit()
    return _out(session, [practice])[0]


@router.patch("/{practice_id}", response_model=PracticeOut, summary="Modifica una practice")
def update_practice(
    practice_id: uuid.UUID, body: PracticeUpdate, admin: AdminUser, session: SessionDep
) -> PracticeOut:
    practice = get_or_404(session, Practice, practice_id, "Practice")
    values = body.model_dump(exclude_unset=True)
    if values.get("name", "x") is None or values.get("is_active", True) is None:
        raise HTTPException(422, "I campi indicati non possono essere nulli")
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
