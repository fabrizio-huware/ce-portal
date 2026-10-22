import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, or_, select

from app.api.deps import (
    AdminUser,
    PageDep,
    SessionDep,
    SettingsDep,
    get_or_404,
    like_pattern,
    paginate,
)
from app.models import DEFAULT_BUSINESS_UNIT, BusinessUnit, User
from app.models.accounts import AUTHOR_ROLES
from app.notifications import notify_user_enabled
from app.notifications.deps import NotifierDep
from app.schemas.common import Page, Role
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(prefix="/users", tags=["Utenti"])


def _person_or_404(session, user_id: uuid.UUID) -> User:
    """Una persona: gli utenti di servizio non si leggono né si modificano da qui."""
    user = get_or_404(session, User, user_id, "Utente")
    if user.is_service:
        raise HTTPException(404, "Utente non trovato")
    return user


def _user_out(session, users: list[User]) -> list[UserOut]:
    names = dict(session.execute(select(BusinessUnit.id, BusinessUnit.name)).all())
    return [
        UserOut.model_validate(u).model_copy(
            update={"business_unit_name": names.get(u.business_unit_id)}
        )
        for u in users
    ]


def _check_business_unit(
    session, role: str, unit_id: uuid.UUID | None, current: uuid.UUID | None = None
) -> None:
    """Solo presale e responsabili hanno una business unit; il responsabile deve averla."""
    if role not in AUTHOR_ROLES:
        if unit_id is not None:
            raise HTTPException(
                422, "Solo presale e responsabili di business unit hanno una business unit"
            )
        return
    if unit_id is None:
        if role == "bu_manager":
            raise HTTPException(
                422, "Il responsabile di business unit deve avere una business unit"
            )
        return
    unit = session.get(BusinessUnit, unit_id)
    if unit is None:
        raise HTTPException(422, "Business unit non trovata")
    if unit.name.lower() == DEFAULT_BUSINESS_UNIT.lower():
        raise HTTPException(
            422,
            f"«{DEFAULT_BUSINESS_UNIT}» non si assegna a una persona: scegline una vera",
        )
    if not unit.is_active and unit.id != current:
        raise HTTPException(422, "La business unit è disattivata: scegline un'altra")


def _ensure_not_last_admin(session, target: User, new_role: str, new_active: bool) -> None:
    """Deve restare almeno un amministratore attivo."""
    if target.role == "admin" and target.is_active and (new_role != "admin" or not new_active):
        other_admins = session.scalars(
            select(User.id)
            .where(User.role == "admin", User.is_active, User.id != target.id)
            .with_for_update()
        ).all()
        if not other_admins:
            raise HTTPException(409, "Deve restare almeno un amministratore attivo")


@router.get("", response_model=Page[UserOut], summary="Elenco utenti")
def list_users(
    admin: AdminUser,
    session: SessionDep,
    params: PageDep,
    q: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    # Gli utenti di servizio delle integrazioni si gestiscono solo dalla scheda Integrazioni.
    stmt = (
        select(User)
        .where(User.is_service.is_(False))
        .order_by(func.lower(User.full_name), User.email)
    )
    if q:
        pattern = like_pattern(q)
        stmt = stmt.where(
            or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"))
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    rows, total = paginate(session, stmt, params)
    return Page(
        items=_user_out(session, list(rows)),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("", response_model=UserOut, status_code=201, summary="Registra un utente")
def create_user(
    body: UserCreate,
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
    notifier: NotifierDep,
) -> User:
    if body.email.rpartition("@")[2] not in settings.allowed_email_domains:
        allowed = ", ".join(settings.allowed_email_domains)
        raise HTTPException(422, f"Dominio email non consentito (ammessi: {allowed})")
    if session.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Esiste già un utente con questa email")
    _check_business_unit(session, body.role, body.business_unit_id)
    user = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        business_unit_id=body.business_unit_id,
    )
    session.add(user)
    session.flush()
    audit.record(
        session,
        admin,
        "user",
        user.id,
        "create",
        {
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "business_unit_id": str(user.business_unit_id) if user.business_unit_id else None,
        },
    )
    notify_user_enabled(session, admin, user)
    session.commit()
    notifier.flush(session)
    return _user_out(session, [user])[0]


@router.get("/{user_id}", response_model=UserOut, summary="Dettaglio utente")
def get_user(user_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> UserOut:
    return _user_out(session, [_person_or_404(session, user_id)])[0]


@router.patch("/{user_id}", response_model=UserOut, summary="Modifica ruolo, nome o stato")
def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, session: SessionDep
) -> UserOut:
    user = _person_or_404(session, user_id)
    values = body.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k != "business_unit_id"):
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    role = values.get("role", user.role)
    if role not in AUTHOR_ROLES and "business_unit_id" not in values:
        # chi non è più presale né responsabile perde la business unit
        values["business_unit_id"] = None
    unit_id = values["business_unit_id"] if "business_unit_id" in values else user.business_unit_id
    _check_business_unit(session, role, unit_id, current=user.business_unit_id)
    _ensure_not_last_admin(
        session, user, values.get("role", user.role), values.get("is_active", user.is_active)
    )
    changes = audit.apply_changes(user, values)
    if changes:
        audit.record(session, admin, "user", user.id, "update", changes)
        session.commit()
    return _user_out(session, [user])[0]
