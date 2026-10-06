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
from app.models import User
from app.notifications import notify_user_enabled
from app.notifications.deps import NotifierDep
from app.schemas.common import Page, Role
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(prefix="/users", tags=["Utenti"])


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
    stmt = select(User).order_by(func.lower(User.full_name), User.email)
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
        items=[UserOut.model_validate(u) for u in rows],
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
    user = User(email=body.email, full_name=body.full_name, role=body.role)
    session.add(user)
    session.flush()
    audit.record(
        session,
        admin,
        "user",
        user.id,
        "create",
        {"email": user.email, "role": user.role, "full_name": user.full_name},
    )
    notify_user_enabled(session, admin, user)
    session.commit()
    notifier.flush(session)
    return user


@router.get("/{user_id}", response_model=UserOut, summary="Dettaglio utente")
def get_user(user_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> User:
    return get_or_404(session, User, user_id, "Utente")


@router.patch("/{user_id}", response_model=UserOut, summary="Modifica ruolo, nome o stato")
def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, session: SessionDep
) -> User:
    user = get_or_404(session, User, user_id, "Utente")
    values = body.model_dump(exclude_unset=True)
    if any(values.get(k) is None for k in values):
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    _ensure_not_last_admin(
        session, user, values.get("role", user.role), values.get("is_active", user.is_active)
    )
    changes = audit.apply_changes(user, values)
    if changes:
        audit.record(session, admin, "user", user.id, "update", changes)
        session.commit()
    return user
