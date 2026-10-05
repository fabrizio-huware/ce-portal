from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.core.google import GoogleVerifier, InvalidGoogleTokenError, get_google_verifier
from app.core.security import create_access_token
from app.models import User
from app.schemas.users import DevLoginRequest, GoogleLoginRequest, TokenResponse, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["Autenticazione"])
# Registrato solo se APP_ENV=local (vedi create_app): non esiste in test e prod.
dev_router = APIRouter(prefix="/auth", tags=["Autenticazione (solo sviluppo locale)"])

NOT_ENABLED = "Utente non abilitato. Contatta un amministratore."


def _token_response(user: User, settings) -> TokenResponse:
    token, expires_in = create_access_token(user.id, settings)
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )


@router.post("/google", response_model=TokenResponse, summary="Login con token Google")
def login_google(
    body: GoogleLoginRequest,
    session: SessionDep,
    settings: SettingsDep,
    verifier: Annotated[GoogleVerifier, Depends(get_google_verifier)],
) -> TokenResponse:
    """Verifica l'ID token Google e, se l'utente è stato registrato da un admin, emette il token."""
    try:
        identity = verifier(body.id_token)
    except InvalidGoogleTokenError as exc:
        raise HTTPException(401, "Token Google non valido") from exc

    if not identity.email_verified:
        raise HTTPException(403, "Email Google non verificata")
    if identity.email.rpartition("@")[2] not in settings.allowed_email_domains:
        raise HTTPException(403, "Dominio email non autorizzato")

    user = session.scalar(select(User).where(User.email == identity.email))
    if user is None or not user.is_active:
        raise HTTPException(403, NOT_ENABLED)

    if user.google_sub is None:
        user.google_sub = identity.sub
        audit.record(session, user, "user", user.id, "link_google")
    elif user.google_sub != identity.sub:
        raise HTTPException(403, "Account Google non corrispondente all'utente registrato")

    user.last_login_at = datetime.now(UTC)
    session.commit()
    return _token_response(user, settings)


@router.get("/me", response_model=UserOut, summary="Utente corrente")
def me(user: CurrentUser) -> User:
    return user


@dev_router.post("/dev-login", response_model=TokenResponse, summary="Login simulato (solo locale)")
def dev_login(body: DevLoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active:
        raise HTTPException(403, NOT_ENABLED)
    return _token_response(user, settings)
