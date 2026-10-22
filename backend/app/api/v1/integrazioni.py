"""Contratto per i programmi esterni (account di servizio Google).

Percorso dedicato e stabile.

Ogni richiesta porta `Authorization: Bearer <ID token Google dell'account di servizio>`,
con audience uguale all'indirizzo del portale. Si può fare al massimo una richiesta al secondo.
Nessuna risposta contiene costi, margini o tariffe: solo giornate e ricavi.
"""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Response

from app.api.deps import PageDep, SessionDep
from app.api.s2s_deps import CanCreate, CanEdit, CanExport, CanRead
from app.exports import pdf_export
from app.exports.common import file_response, safe_filename
from app.exports.reduced import reduced_from_detail
from app.schemas.ce import CEStatus, ContentIn
from app.schemas.common import Page
from app.schemas.integrations import (
    IntegrationCE,
    IntegrationCECreate,
    IntegrationCEItem,
    IntegrationCEResult,
    IntegrationContent,
    LookupItem,
)
from app.services import audit
from app.services import ce as svc
from app.services import integrations as isvc
from app.services.ce_search import CEFilters

router = APIRouter(
    prefix="/integrazioni",
    tags=["Integrazioni"],
    responses={
        401: {
            "description": "Token mancante, non valido o scaduto, o integrazione non autorizzata"
        },
        403: {"description": "L'integrazione non ha il permesso richiesto"},
        429: {"description": "Troppe richieste: al massimo una al secondo (vedi `Retry-After`)"},
    },
)


# ======= elenchi di supporto
@router.get("/anagrafiche/clienti", response_model=list[LookupItem], summary="Clienti attivi")
def list_clients(principal: CanRead, session: SessionDep) -> list[LookupItem]:
    """Identificativo e nome: servono a indicare il cliente quando si crea un CE."""
    return isvc.clients(session)


@router.get(
    "/anagrafiche/business-unit",
    response_model=list[LookupItem],
    summary="Business unit attive",
)
def list_business_units(principal: CanRead, session: SessionDep) -> list[LookupItem]:
    """Identificativo e nome: servono a indicare le business unit coinvolte quando si crea un CE."""
    return isvc.business_units(session)


@router.get("/anagrafiche/profili", response_model=list[LookupItem], summary="Profili attivi")
def list_profiles(principal: CanRead, session: SessionDep) -> list[LookupItem]:
    """Identificativo e nome dei profili: mai tariffe né costi."""
    return isvc.profiles(session)


@router.get(
    "/anagrafiche/collaboratori", response_model=list[LookupItem], summary="Collaboratori attivi"
)
def list_employees(principal: CanRead, session: SessionDep) -> list[LookupItem]:
    return isvc.employees(session)


# ======= CE
@router.get("/ce", response_model=Page[IntegrationCEItem], summary="Elenco dei CE")
def list_ce(
    principal: CanRead,
    session: SessionDep,
    params: PageDep,
    client_id: uuid.UUID | None = None,
    project: str | None = None,
    code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: CEStatus | None = None,
    external_ref: str | None = None,
) -> Page[IntegrationCEItem]:
    """Ultima versione di ogni CE non eliminato, di qualunque stato. Con `external_ref` si ritrova
    un CE creato da questa integrazione (utile se la risposta alla creazione si è persa)."""
    filters = CEFilters(client_id, project, code, date_from, date_to)
    items, total = isvc.list_ce(
        session,
        principal,
        filters,
        status=status,
        external_ref=external_ref,
        limit=params.limit,
        offset=params.offset,
    )
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@router.post(
    "/ce",
    response_model=IntegrationCEResult,
    status_code=201,
    summary="Crea un CE con tutto il suo contenuto",
    responses={
        200: {"description": "Esisteva già un CE con lo stesso `external_ref`: nessun duplicato"}
    },
)
def create_ce(
    body: IntegrationCECreate, principal: CanCreate, session: SessionDep, response: Response
) -> IntegrationCEResult:
    """Crea il CE in bozza, tutto o niente. Autore: l'utente di servizio dell'integrazione.
    `external_ref` è il vostro identificativo: se ripetete la richiesta ottenete lo stesso CE
    (`200`, `created: false`) invece di un duplicato. `requested_by` è la persona per conto della
    quale lo create (solo annotazione). L'invio in approvazione e l'approvazione restano umani."""
    ce, created = isvc.create_ce(session, principal, body)
    if not created:
        response.status_code = 200
    return IntegrationCEResult(
        created=created,
        ce=isvc.summary(session, principal, ce),
        revision=isvc.revision_if_mine(session, principal, ce),
    )


@router.get("/ce/{ce_id}", response_model=IntegrationCE, summary="Riepilogo di un CE")
def get_ce(ce_id: uuid.UUID, principal: CanRead, session: SessionDep) -> IntegrationCE:
    """Giornate e ricavi dell'ultima versione, di qualunque stato. Se non è approvata, `notice`
    lo dice."""
    return isvc.summary(session, principal, svc.get_ce(session, ce_id))


@router.get(
    "/ce/{ce_id}/content", response_model=IntegrationContent, summary="Contenuto di un proprio CE"
)
def get_content(ce_id: uuid.UUID, principal: CanRead, session: SessionDep) -> IntegrationContent:
    """Ciò che l'integrazione ha inviato, per poterlo correggere. Solo per i CE di questa
    integrazione non ancora assegnati a un presale (`403` altrimenti). Contiene `revision`."""
    return isvc.own_content(session, principal, svc.get_ce(session, ce_id))


@router.put(
    "/ce/{ce_id}/content",
    response_model=IntegrationCEResult,
    summary="Sostituisce il contenuto di una propria bozza",
)
def put_content(
    ce_id: uuid.UUID, content: ContentIn, principal: CanEdit, session: SessionDep
) -> IntegrationCEResult:
    """Sostituisce l'intero contenuto. `expected_revision` è quello dell'ultima lettura: se nel
    frattempo qualcuno ha modificato la bozza si ottiene `409`. `403` se il CE non è (più)
    dell'integrazione, `409` se è approvato o in approvazione."""
    ce = svc.get_ce(session, ce_id)
    svc.save_content(session, principal.user, ce, svc.get_latest_version(session, ce), content)
    return IntegrationCEResult(
        created=False,
        ce=isvc.summary(session, principal, ce),
        revision=isvc.revision_if_mine(session, principal, ce),
    )


@router.get(
    "/ce/{ce_id}/pdf",
    summary="PDF di riepilogo di un CE",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_pdf(ce_id: uuid.UUID, principal: CanExport, session: SessionDep) -> Response:
    """Giornate e ricavi per fase, mai costi né margini. Di qualunque stato: se la versione non è
    approvata il documento riporta «Versione non approvata»."""
    ce = svc.get_ce(session, ce_id)
    version = svc.get_latest_version(session, ce)
    detail = svc.build_detail(session, principal.user, ce, version)
    content = pdf_export.ce_summary_pdf(
        reduced_from_detail(detail), version.status, datetime.now(UTC)
    )
    audit.record(
        session,
        principal.user,
        "ce",
        ce.id,
        "export",
        {
            "format": "pdf",
            "variant": "summary",
            "version": version.version_number,
            "via": "integration",
        },
    )
    session.commit()
    return file_response(
        content, "pdf", safe_filename(ce.code, f"v{version.version_number}", "riepilogo", ext="pdf")
    )
