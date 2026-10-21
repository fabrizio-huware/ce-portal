"""Verifica degli ID token Google degli account di servizio (accesso da programma a programma).

Il programma esterno si fa firmare da Google un token per l'indirizzo del portale (audience) e lo
manda in ogni richiesta. Il portale non conserva segreti: controlla firma, scadenza, issuer e
audience con i certificati pubblici di Google.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from google.auth.exceptions import TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings, get_settings

CLOCK_SKEW_SECONDS = (
    10  # tolleranza tra gli orologi: un token appena emesso non deve risultare «dal futuro»
)


class InvalidServiceTokenError(Exception):
    """Token non valido: firma, scadenza, issuer o audience non corretti."""


class ServiceVerifierUnavailableError(Exception):
    """Non si riescono a ottenere i certificati di Google: non è colpa di chi chiama."""


@dataclass(frozen=True)
class ServiceIdentity:
    email: str
    sub: str
    email_verified: bool


ServiceVerifier = Callable[[str], ServiceIdentity]


def expand_audiences(audiences: list[str]) -> list[str]:
    """Ogni indirizzo vale con e senza «/» finale: il token riporta ciò che il chiamante scrive."""
    out: list[str] = []
    for audience in audiences:
        base = audience.strip().rstrip("/")
        if base:
            out += [base, base + "/"]
    return out


def verify_service_token(token: str, audiences: list[str], request=None) -> ServiceIdentity:
    """Controlla firma, scadenza, issuer e audience.

    Senza audience configurate non verifica nulla: la libreria, con audience assente, salterebbe
    quel controllo e accetterebbe un token emesso per chiunque.
    """
    expected = expand_audiences(audiences)
    if not expected:
        raise InvalidServiceTokenError("Nessuna audience configurata")
    try:
        info = id_token.verify_oauth2_token(
            token,
            request or google_requests.Request(),
            expected,
            clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
        )
    except TransportError as exc:
        raise ServiceVerifierUnavailableError(str(exc)) from exc
    except Exception as exc:
        # Firma, scadenza, issuer, formato: qualunque errore nel decodificare significa «rifiutato».
        raise InvalidServiceTokenError(str(exc)) from exc
    sub = str(info.get("sub", "")).strip()
    if not sub:
        raise InvalidServiceTokenError("Token senza identificativo")
    return ServiceIdentity(
        email=str(info.get("email", "")).strip().lower(),
        sub=sub,
        email_verified=bool(info.get("email_verified", False)),
    )


def get_service_verifier(settings: Annotated[Settings, Depends(get_settings)]) -> ServiceVerifier:
    """Dependency FastAPI: nei test viene sostituita con un verificatore simulato."""
    audiences = settings.s2s_audiences
    if not audiences:
        raise HTTPException(status_code=503, detail="Accesso per integrazioni non configurato")
    return lambda token: verify_service_token(token, audiences)
