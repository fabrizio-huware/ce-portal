"""Dipendenze comuni: sessione, utente corrente e controllo dei ruoli (sempre lato server)."""

from typing import Annotated

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_session
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False, description="Token ottenuto da /auth/google")

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Ruolo e stato attivo si leggono dal database a ogni richiesta, non dal token."""
    unauthorized = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise HTTPException(401, "Autenticazione richiesta", headers=unauthorized)
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError as exc:
        raise HTTPException(401, "Token non valido o scaduto", headers=unauthorized) from exc
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Utente non abilitato", headers=unauthorized)
    return user


def require_roles(*roles: str):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Permesso negato")
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
EditorUser = Annotated[User, Depends(require_roles("admin", "presale"))]  # chi può vedere i costi


class PageParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PageDep = Annotated[PageParams, Depends()]


def paginate(session: Session, stmt: Select, params: PageParams) -> tuple[list, int]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(session.scalars(stmt.limit(params.limit).offset(params.offset)).all())
    return rows, total


def like_pattern(text: str) -> str:
    """Pattern ILIKE con escape dei caratteri speciali (usare escape='\\\\')."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def get_or_404(session: Session, model: type, pk, what: str):
    obj = session.get(model, pk)
    if obj is None:
        raise HTTPException(404, f"{what} non trovato")
    return obj
