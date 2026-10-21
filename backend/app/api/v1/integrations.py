"""Gestione delle integrazioni (solo amministratori).

Chi può agire da programma esterno e con quali permessi.
"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep, get_or_404
from app.models import Integration, User
from app.schemas.integrations import IntegrationCreate, IntegrationOut, IntegrationUpdate
from app.services import audit

router = APIRouter(prefix="/integrations", tags=["Integrazioni (amministrazione)"])


def _service_name(name: str) -> str:
    return f"{name} (servizio)"


def _name_taken(session, name: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Integration.id).where(func.lower(Integration.name) == name.lower())
    if exclude:
        stmt = stmt.where(Integration.id != exclude)
    return session.scalar(stmt) is not None


@router.get("", response_model=list[IntegrationOut], summary="Elenco delle integrazioni")
def list_integrations(admin: AdminUser, session: SessionDep) -> list[Integration]:
    return list(session.scalars(select(Integration).order_by(func.lower(Integration.name))))


@router.post("", response_model=IntegrationOut, status_code=201, summary="Registra un'integrazione")
def create_integration(
    body: IntegrationCreate, admin: AdminUser, session: SessionDep
) -> Integration:
    """Registra l'account di servizio e crea l'utente di servizio che sarà l'autore dei suoi CE."""
    if session.scalar(
        select(Integration.id).where(
            Integration.service_account_email == body.service_account_email
        )
    ) or session.scalar(select(User.id).where(User.email == body.service_account_email)):
        raise HTTPException(409, "Esiste già un utente o un'integrazione con questo indirizzo")
    if _name_taken(session, body.name):
        raise HTTPException(409, "Esiste già un'integrazione con questo nome")
    user = User(
        email=body.service_account_email,
        full_name=_service_name(body.name),
        role="presale",
        is_active=True,
        is_service=True,
    )
    session.add(user)
    session.flush()
    integration = Integration(
        name=body.name,
        service_account_email=body.service_account_email,
        user_id=user.id,
        permissions=body.permissions,
        created_by=admin.id,
    )
    session.add(integration)
    session.flush()
    audit.record(
        session,
        admin,
        "integration",
        integration.id,
        "create",
        {
            "name": body.name,
            "service_account_email": body.service_account_email,
            "permissions": body.permissions,
        },
    )
    session.commit()
    return integration


@router.patch("/{integration_id}", response_model=IntegrationOut, summary="Modifica o disattiva")
def update_integration(
    integration_id: uuid.UUID, body: IntegrationUpdate, admin: AdminUser, session: SessionDep
) -> Integration:
    """Nome, permessi e stato. Un'integrazione disattivata smette di funzionare alla richiesta
    successiva. L'indirizzo dell'account di servizio non cambia: se ne registra una nuova."""
    integration = get_or_404(session, Integration, integration_id, "Integrazione")
    values = body.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()):
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    if "name" in values and _name_taken(session, values["name"], integration.id):
        raise HTTPException(409, "Esiste già un'integrazione con questo nome")
    user = session.get(User, integration.user_id)
    changes = audit.apply_changes(integration, values)
    if "name" in values:
        user.full_name = _service_name(values["name"])
    if "is_active" in values:
        user.is_active = values["is_active"]
    if changes:
        audit.record(session, admin, "integration", integration.id, "update", changes)
    session.commit()
    return integration
