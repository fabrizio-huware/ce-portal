import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import and_, func, select

from app.api.deps import (
    AdminUser,
    CurrentUser,
    EditorUser,
    PageDep,
    PageParams,
    SessionDep,
    like_pattern,
)
from app.models import CE, CEVersion, Client, User
from app.notifications.deps import NotifierDep
from app.schemas.ce import (
    CalculationOut,
    CECreate,
    CEDetail,
    CEListItem,
    CEStatus,
    ContentIn,
    DiscardResult,
    DuplicateIn,
    HistoryItem,
    RealignIn,
    RejectIn,
    UserRef,
    VersionListItem,
    ViewerCE,
    ViewerListItem,
    ViewerPhase,
)
from app.schemas.clients import ClientRef
from app.schemas.common import Page
from app.services import ce as svc

router = APIRouter(prefix="/ce", tags=["Conti economici"])


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(value)


def _latest_subquery(*, only_approved: bool):
    query = select(CEVersion.ce_id.label("ce_id"), func.max(CEVersion.version_number).label("n"))
    if only_approved:
        query = query.where(CEVersion.status == "approved")
    return query.group_by(CEVersion.ce_id).subquery()


def _paginate_rows(session, stmt, params: PageParams):
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.execute(stmt.limit(params.limit).offset(params.offset)).all()
    return rows, total


def _filters(stmt, *, client_id, project, code, date_from, date_to):
    if client_id:
        stmt = stmt.where(CEVersion.client_id == client_id)
    if project:
        stmt = stmt.where(CEVersion.project_name.ilike(like_pattern(project), escape="\\"))
    if code:
        stmt = stmt.where(CE.code.ilike(like_pattern(code), escape="\\"))
    # "da - a": progetti attivi nel periodo, cioè con il periodo che si sovrappone
    if date_to:
        stmt = stmt.where(CEVersion.start_date <= date_to)
    if date_from:
        stmt = stmt.where(CEVersion.end_date >= date_from)
    return stmt


def _detail(session, user, ce: CE, version: CEVersion | None = None) -> CEDetail:
    session.expire_all()
    return svc.build_detail(session, user, ce, version or svc.get_latest_version(session, ce))


# ======= vista ridotta (tutti i ruoli)
# Percorsi dichiarati per primi: "summaries" non deve essere scambiato per un identificativo.
@router.get(
    "/summaries",
    response_model=Page[ViewerListItem],
    summary="Elenco ridotto: ultima versione approvata di ogni CE",
)
def list_summaries(
    user: CurrentUser,
    session: SessionDep,
    params: PageDep,
    client_id: uuid.UUID | None = None,
    project: str | None = None,
    code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[ViewerListItem]:
    """Per il viewer è l'unico elenco disponibile. Mostra solo codice, cliente, progetto,
    date e prezzo: nessun costo, margine, ora o riga."""
    latest = _latest_subquery(only_approved=True)
    stmt = (
        select(CE, CEVersion, Client)
        .join(latest, latest.c.ce_id == CE.id)
        .join(
            CEVersion,
            and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n),
        )
        .join(Client, Client.id == CEVersion.client_id)
        .where(CE.deleted_at.is_(None))
        .order_by(func.lower(CE.code))
    )
    stmt = _filters(
        stmt, client_id=client_id, project=project, code=code, date_from=date_from, date_to=date_to
    )
    rows, total = _paginate_rows(session, stmt, params)
    items = [
        ViewerListItem(
            ce_id=ce.id,
            code=ce.code,
            client_name=client.name,
            project_name=v.project_name,
            start_date=v.start_date,
            end_date=v.end_date,
            version_number=v.version_number,
            approved_at=v.approved_at,
            price=_dec((v.approved_totals or {}).get("revenue")),
        )
        for ce, v, client in rows
    ]
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@router.get(
    "/summaries/{ce_id}",
    response_model=ViewerCE,
    summary="Dettaglio ridotto: giornate di management e delivery, ricavi per fase",
)
def get_summary(ce_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ViewerCE:
    ce = svc.get_ce(session, ce_id)
    version = svc.get_latest_approved(session, ce)
    if version is None:
        raise HTTPException(
            404, "CE non trovato"
        )  # nessuna versione approvata: per il viewer non esiste
    totals = version.approved_totals or {}
    client = session.get(Client, version.client_id)
    return ViewerCE(
        ce_id=ce.id,
        code=ce.code,
        client_name=client.name,
        project_name=version.project_name,
        start_date=version.start_date,
        end_date=version.end_date,
        version_number=version.version_number,
        approved_at=version.approved_at,
        days_project_management=Decimal(totals["days_project_management"]),
        days_delivery=Decimal(totals["days_delivery"]),
        days_total=Decimal(totals["days_total"]),
        phases=[
            ViewerPhase(name=p["name"], revenue=Decimal(p["revenue"])) for p in totals["phases"]
        ],
        total_revenue=Decimal(totals["revenue"]),
    )


# ======= creazione ed elenco
@router.post("", response_model=CEDetail, status_code=201, summary="Crea un CE")
def create_ce(data: CECreate, user: EditorUser, session: SessionDep) -> CEDetail:
    """Crea il CE e la versione 1 in bozza. Le tariffe si copiano dal listino dell'anno di inizio
    e i giorni non lavorativi dal calendario generale; poi si compila con `PUT /ce/{id}/content`."""
    version = svc.create_ce(session, user, data)
    return _detail(session, user, session.get(CE, version.ce_id), version)


@router.get("", response_model=Page[CEListItem], summary="Cerca i CE (ultima versione di ciascuno)")
def list_ce(
    user: EditorUser,
    session: SessionDep,
    params: PageDep,
    client_id: uuid.UUID | None = None,
    project: Annotated[
        str | None, Query(description="Testo contenuto nel nome del progetto")
    ] = None,
    code: Annotated[str | None, Query(description="Testo contenuto nel codice")] = None,
    date_from: Annotated[date | None, Query(description="Progetti attivi dal...")] = None,
    date_to: Annotated[
        date | None, Query(description="...fino al (periodo che si sovrappone)")
    ] = None,
    status: CEStatus | None = None,
    created_by: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> Page[CEListItem]:
    if include_deleted and user.role != "admin":
        raise HTTPException(403, "Solo un amministratore può vedere i CE eliminati")
    latest = _latest_subquery(only_approved=False)
    stmt = (
        select(CE, CEVersion, Client, User)
        .join(latest, latest.c.ce_id == CE.id)
        .join(
            CEVersion,
            and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n),
        )
        .join(Client, Client.id == CEVersion.client_id)
        .join(User, User.id == CE.created_by)
        .order_by(CEVersion.updated_at.desc(), func.lower(CE.code))
    )
    if not include_deleted:
        stmt = stmt.where(CE.deleted_at.is_(None))
    stmt = _filters(
        stmt, client_id=client_id, project=project, code=code, date_from=date_from, date_to=date_to
    )
    if status:
        stmt = stmt.where(CEVersion.status == status)
    if created_by:
        stmt = stmt.where(CE.created_by == created_by)
    rows, total = _paginate_rows(session, stmt, params)
    items = []
    for ce, v, client, owner in rows:
        summary = v.summary or {}
        items.append(
            CEListItem(
                ce_id=ce.id,
                code=ce.code,
                client=ClientRef.model_validate(client),
                project_name=v.project_name,
                start_date=v.start_date,
                end_date=v.end_date,
                planning_mode=v.planning_mode,
                version_number=v.version_number,
                status=v.status,
                owner=UserRef(id=owner.id, full_name=owner.full_name),
                updated_at=v.updated_at,
                deleted=ce.deleted_at is not None,
                price=_dec(summary.get("revenue")),
                margin_pct=_dec(summary.get("margin_pct")),
                days_total=_dec(summary.get("days_total")),
            )
        )
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


# ======= lettura
@router.get("/{ce_id}", response_model=CEDetail, summary="Dettaglio completo dell'ultima versione")
def get_ce(ce_id: uuid.UUID, user: EditorUser, session: SessionDep) -> CEDetail:
    return _detail(session, user, svc.get_ce(session, ce_id))


@router.get("/{ce_id}/versions", response_model=list[VersionListItem], summary="Versioni del CE")
def list_versions(ce_id: uuid.UUID, user: EditorUser, session: SessionDep) -> list[VersionListItem]:
    ce = svc.get_ce(session, ce_id)
    versions = session.scalars(
        select(CEVersion).where(CEVersion.ce_id == ce.id).order_by(CEVersion.version_number.desc())
    ).all()
    out = []
    for v in versions:
        author = session.get(User, v.created_by)
        out.append(
            VersionListItem(
                number=v.version_number,
                status=v.status,
                revision=v.revision,
                created_by=UserRef(id=author.id, full_name=author.full_name),
                created_at=v.created_at,
                updated_at=v.updated_at,
                approved_at=v.approved_at,
                price=_dec((v.summary or {}).get("revenue")),
            )
        )
    return out


@router.get(
    "/{ce_id}/versions/{number}", response_model=CEDetail, summary="Dettaglio di una versione"
)
def get_ce_version(
    ce_id: uuid.UUID, number: int, user: EditorUser, session: SessionDep
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    return _detail(session, user, ce, svc.get_version(session, ce, number))


@router.get("/{ce_id}/history", response_model=list[HistoryItem], summary="Storico delle modifiche")
def get_history(ce_id: uuid.UUID, user: EditorUser, session: SessionDep) -> list[HistoryItem]:
    ce = svc.get_ce(session, ce_id)
    return [
        HistoryItem(
            id=entry.id,
            occurred_at=entry.occurred_at,
            user=UserRef(id=author.id, full_name=author.full_name) if author else None,
            action=entry.action,
            changes=entry.changes,
        )
        for entry, author in svc.history(session, ce)
    ]


# ======= modifica e calcolo
@router.put("/{ce_id}/content", response_model=CEDetail, summary="Salva l'intero contenuto")
def save_content(
    ce_id: uuid.UUID, content: ContentIn, user: EditorUser, session: SessionDep
) -> CEDetail:
    """Sostituisce testata, fasi, righe, % mensili, giorni non lavorativi e milestone.
    `expected_revision` deve essere quello dell'ultima lettura, altrimenti `409`."""
    ce = svc.get_ce(session, ce_id)
    svc.save_content(session, user, ce, svc.get_latest_version(session, ce), content)
    return _detail(session, user, ce)


@router.post(
    "/{ce_id}/calculate", response_model=CalculationOut, summary="Calcolo di anteprima (non salva)"
)
def calculate_preview(
    ce_id: uuid.UUID, content: ContentIn, user: EditorUser, session: SessionDep
) -> CalculationOut:
    ce = svc.get_ce(session, ce_id)
    return svc.preview(session, ce, svc.get_latest_version(session, ce), content)


# ======= workflow
@router.post("/{ce_id}/submit", response_model=CEDetail, summary="Invia in approvazione")
def submit_ce(
    ce_id: uuid.UUID, user: EditorUser, session: SessionDep, notifier: NotifierDep
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    svc.submit(session, user, ce, svc.get_latest_version(session, ce))
    notifier.flush(session)
    return _detail(session, user, ce)


@router.post("/{ce_id}/withdraw", response_model=CEDetail, summary="Ritira dall'approvazione")
def withdraw_ce(ce_id: uuid.UUID, user: EditorUser, session: SessionDep) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    svc.withdraw(session, user, ce, svc.get_latest_version(session, ce))
    return _detail(session, user, ce)


@router.post("/{ce_id}/approve", response_model=CEDetail, summary="Approva (solo admin, sempre)")
def approve_ce(
    ce_id: uuid.UUID, admin: AdminUser, session: SessionDep, notifier: NotifierDep
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    svc.approve(session, admin, ce, svc.get_latest_version(session, ce))
    notifier.flush(session)
    return _detail(session, admin, ce)


@router.post("/{ce_id}/reject", response_model=CEDetail, summary="Rifiuta con motivo (solo admin)")
def reject_ce(
    ce_id: uuid.UUID,
    body: RejectIn,
    admin: AdminUser,
    session: SessionDep,
    notifier: NotifierDep,
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    svc.reject(session, admin, ce, svc.get_latest_version(session, ce), body.reason)
    notifier.flush(session)
    return _detail(session, admin, ce)


# ======= versioni
@router.post(
    "/{ce_id}/versions",
    response_model=CEDetail,
    status_code=201,
    summary="Nuova versione da un CE approvato",
)
def create_version(
    ce_id: uuid.UUID, user: EditorUser, session: SessionDep, notifier: NotifierDep
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    version = svc.new_version(session, user, ce)
    notifier.flush(session)
    return _detail(session, user, ce, version)


@router.delete(
    "/{ce_id}/open-version",
    response_model=DiscardResult,
    summary="Scarta la versione in lavorazione",
)
def discard_version(ce_id: uuid.UUID, user: EditorUser, session: SessionDep) -> DiscardResult:
    ce = svc.get_ce(session, ce_id)
    return DiscardResult(discarded_version=svc.discard_open_version(session, user, ce))


@router.post(
    "/{ce_id}/realign",
    response_model=CEDetail,
    summary="Riallinea tariffe e calendario ai valori correnti (solo admin)",
)
def realign_ce(
    ce_id: uuid.UUID, body: RealignIn, admin: AdminUser, session: SessionDep
) -> CEDetail:
    ce = svc.get_ce(session, ce_id)
    svc.realign(
        session,
        admin,
        ce,
        svc.get_latest_version(session, ce),
        rates=body.rates,
        calendar_=body.calendar,
    )
    return _detail(session, admin, ce)


@router.post(
    "/{ce_id}/duplicate",
    response_model=CEDetail,
    status_code=201,
    summary="Crea un nuovo CE copiando struttura e righe",
)
def duplicate_ce(
    ce_id: uuid.UUID, body: DuplicateIn, user: EditorUser, session: SessionDep
) -> CEDetail:
    """Il nuovo CE parte in bozza, con tariffe e calendario correnti. Non si copiano
    max sconto, prezzo firmato, opportunità Salesforce e note."""
    source = svc.get_ce(session, ce_id)
    version = svc.duplicate(session, user, source, svc.get_latest_version(session, source), body)
    return _detail(session, user, session.get(CE, version.ce_id), version)


# ======= eliminazione
@router.delete(
    "/{ce_id}", status_code=204, summary="Elimina il CE (cancellazione logica, solo admin)"
)
def delete_ce(ce_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> Response:
    svc.set_deleted(session, admin, svc.get_ce(session, ce_id), True)
    return Response(status_code=204)


@router.post("/{ce_id}/restore", response_model=CEDetail, summary="Ripristina un CE eliminato")
def restore_ce(ce_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> CEDetail:
    ce = svc.get_ce(session, ce_id, include_deleted=True)
    svc.set_deleted(session, admin, ce, False)
    return _detail(session, admin, ce)
