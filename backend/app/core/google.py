"""Verifica degli ID token emessi da Google Identity Services."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings, get_settings


class InvalidGoogleTokenError(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    sub: str
    name: str
    email_verified: bool


GoogleVerifier = Callable[[str], GoogleIdentity]


def verify_google_id_token(token: str, client_id: str) -> GoogleIdentity:
    """Controlla firma, scadenza, issuer e audience (client id) del token."""
    try:
        info = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except ValueError as exc:
        raise InvalidGoogleTokenError(str(exc)) from exc
    return GoogleIdentity(
        email=str(info.get("email", "")).strip().lower(),
        sub=str(info["sub"]),
        name=str(info.get("name", "")),
        email_verified=bool(info.get("email_verified", False)),
    )


def get_google_verifier(settings: Annotated[Settings, Depends(get_settings)]) -> GoogleVerifier:
    """Dependency FastAPI: nei test viene sostituita con un verificatore simulato."""
    client_id = settings.google_oauth_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Login Google non configurato")
    return lambda token: verify_google_id_token(token, client_id)
