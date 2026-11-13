"""Accesso da programma a programma: chi chiama è un'integrazione, riconosciuta dal token Google
del suo account di servizio. Ruolo, stato e permessi si leggono dal database a ogni richiesta."""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, literal_column, or_, select, update

from app.api.deps import SessionDep
from app.core.service_auth import (
    InvalidServiceTokenError,
    ServiceVerifier,
    ServiceVerifierUnavailableError,
    get_service_verifier,
)
from app.models import Integration, User
from app.services.integrations import Principal

service_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="TokenAccountDiServizio",
    description=(
        "ID token Google dell'account di servizio, con audience uguale all'indirizzo del portale"
    ),
)

NOT_AUTHORIZED = "Integrazione non autorizzata"


def get_principal(
    session: SessionDep,
    verifier: Annotated[ServiceVerifier, Depends(get_service_verifier)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(service_bearer)],
) -> Principal:
    unauthorized = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise HTTPException(401, "Autenticazione richiesta", headers=unauthorized)
    try:
        identity = verifier(credentials.credentials)
    except InvalidServiceTokenError as exc:
        raise HTTPException(401, "Token non valido o scaduto", headers=unauthorized) from exc
    except ServiceVerifierUnavailableError as exc:
        raise HTTPException(503, "Verifica del token momentaneamente non disponibile") from exc
    if not identity.email_verified or not identity.email:
        raise HTTPException(401, NOT_AUTHORIZED, headers=unauthorized)

    integration = session.scalar(
        select(Integration).where(Integration.service_account_email == identity.email)
    )
    if integration is None or not integration.is_active:
        raise HTTPException(401, NOT_AUTHORIZED, headers=unauthorized)
    if (
        integration.service_account_sub is None
    ):  # prima chiamata: si lega all'identificativo dell'account
        integration.service_account_sub = identity.sub
    elif integration.service_account_sub != identity.sub:  # stessa email ma account ricreato
        raise HTTPException(401, NOT_AUTHORIZED, headers=unauthorized)
    user = session.get(User, integration.user_id)
    if user is None or not user.is_active or not user.is_service:
        raise HTTPException(401, NOT_AUTHORIZED, headers=unauthorized)

    # Al massimo una richiesta al secondo per integrazione. L'aggiornamento è atomico sul database,
    # quindi vale anche con più copie del servizio in esecuzione.
    now = func.clock_timestamp()
    allowed = session.execute(
        update(Integration)
        .where(
            Integration.id == integration.id,
            or_(
                Integration.last_used_at.is_(None),
                Integration.last_used_at <= now - literal_column("interval '1 second'"),
            ),
        )
        .values(last_used_at=now)
        .returning(Integration.id)
        .execution_options(synchronize_session=False)
    ).first()
    if allowed is None:
        session.rollback()
        raise HTTPException(
            429, "Troppe richieste: al massimo una al secondo", headers={"Retry-After": "1"}
        )
    session.commit()
    session.refresh(integration)
    return Principal(integration=integration, user=user)


def require_permission(permission: str):
    def checker(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if permission not in principal.integration.permissions:
            raise HTTPException(403, "Questa integrazione non ha il permesso richiesto")
        return principal

    return checker


CanRead = Annotated[Principal, Depends(require_permission("read"))]
CanCreate = Annotated[Principal, Depends(require_permission("create"))]
CanEdit = Annotated[Principal, Depends(require_permission("edit"))]
CanExport = Annotated[Principal, Depends(require_permission("export"))]
