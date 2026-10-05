import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import (
    CurrentUser,
    EditorUser,
    PageDep,
    SessionDep,
    get_or_404,
    like_pattern,
    paginate,
)
from app.models import Client
from app.schemas.clients import ClientCreate, ClientOut, ClientRef, ClientUpdate
from app.schemas.common import Page
from app.services import audit

router = APIRouter(prefix="/clients", tags=["Clienti"])


def _name_taken(session, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Client.id).where(func.lower(Client.name) == name.lower())
    if exclude_id:
        stmt = stmt.where(Client.id != exclude_id)
    return session.scalar(stmt) is not None


@router.get("/lookup", response_model=list[ClientRef], summary="Elenco minimo per filtri")
def lookup_clients(
    user: CurrentUser,
    session: SessionDep,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Client]:
    """Id e nome dei clienti: accessibile a tutti i ruoli (serve ai filtri di ricerca)."""
    stmt = select(Client).order_by(func.lower(Client.name)).limit(limit)
    if q:
        stmt = stmt.where(Client.name.ilike(like_pattern(q), escape="\\"))
    return list(session.scalars(stmt).all())


@router.get("", response_model=Page[ClientOut], summary="Elenco clienti")
def list_clients(
    user: EditorUser,
    session: SessionDep,
    params: PageDep,
    q: str | None = None,
    is_active: bool | None = None,
) -> Page[ClientOut]:
    stmt = select(Client).order_by(func.lower(Client.name))
    if q:
        stmt = stmt.where(Client.name.ilike(like_pattern(q), escape="\\"))
    if is_active is not None:
        stmt = stmt.where(Client.is_active == is_active)
    rows, total = paginate(session, stmt, params)
    return Page(
        items=[ClientOut.model_validate(c) for c in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("", response_model=ClientOut, status_code=201, summary="Crea un cliente")
def create_client(body: ClientCreate, user: EditorUser, session: SessionDep) -> Client:
    if _name_taken(session, body.name):
        raise HTTPException(409, "Esiste già un cliente con questo nome")
    client = Client(**body.model_dump())
    session.add(client)
    session.flush()
    audit.record(session, user, "client", client.id, "create", body.model_dump())
    session.commit()
    return client


@router.get("/{client_id}", response_model=ClientOut, summary="Dettaglio cliente")
def get_client(client_id: uuid.UUID, user: EditorUser, session: SessionDep) -> Client:
    return get_or_404(session, Client, client_id, "Cliente")


@router.patch("/{client_id}", response_model=ClientOut, summary="Modifica un cliente")
def update_client(
    client_id: uuid.UUID, body: ClientUpdate, user: EditorUser, session: SessionDep
) -> Client:
    client = get_or_404(session, Client, client_id, "Cliente")
    values = body.model_dump(exclude_unset=True)
    if values.get("name", "x") is None or values.get("is_active", True) is None:
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    if "is_active" in values and user.role != "admin":
        raise HTTPException(403, "Solo un amministratore può attivare o disattivare un cliente")
    if "name" in values and _name_taken(session, values["name"], exclude_id=client.id):
        raise HTTPException(409, "Esiste già un cliente con questo nome")
    changes = audit.apply_changes(client, values)
    if changes:
        audit.record(session, user, "client", client.id, "update", changes)
        session.commit()
    return client
