"""Export dei CE: Excel, CSV, PDF. Il viewer ottiene solo la vista ridotta."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import CurrentUser, EditorUser, SessionDep
from app.exports import csv_export, pdf_export, xlsx_export
from app.exports.common import MAX_EXPORT_ROWS, file_response, safe_filename
from app.exports.reduced import reduced_from_detail
from app.schemas.ce import CEStatus, ViewerCE
from app.services import audit
from app.services import ce as svc
from app.services.ce_search import CEFilters, editor_items, viewer_ce, viewer_items

router = APIRouter(prefix="/ce", tags=["Export"])

Format = Annotated[
    Literal["xlsx", "csv", "pdf"], Query(alias="format", description="xlsx, csv o pdf")
]
ListFormat = Annotated[Literal["xlsx", "csv"], Query(alias="format", description="xlsx o csv")]
Variant = Annotated[
    Literal["full", "summary"],
    Query(description="full = completo (uso interno); summary = riepilogo senza costi né righe"),
]


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _reduced_file(ce: ViewerCE, fmt: str, status: str | None, now: datetime) -> bytes:
    if fmt == "xlsx":
        return xlsx_export.reduced_xlsx(ce)
    if fmt == "csv":
        return csv_export.reduced_csv(ce)
    return pdf_export.ce_summary_pdf(ce, status, now)


# ======= elenchi (dichiarati per primi: "export" non deve essere scambiato per un identificativo)
@router.get("/export", summary="Esporta i risultati di una ricerca (admin, presale)")
def export_list(
    user: EditorUser,
    session: SessionDep,
    fmt: ListFormat = "xlsx",
    client_id: uuid.UUID | None = None,
    project: str | None = None,
    code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: CEStatus | None = None,
    created_by: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> Response:
    """Stessi filtri della ricerca. Massimo 5000 righe."""
    if include_deleted and user.role != "admin":
        raise HTTPException(403, "Solo un amministratore può vedere i CE eliminati")
    filters = CEFilters(
        client_id, project, code, date_from, date_to, status, created_by, include_deleted
    )
    items, total = editor_items(session, filters, MAX_EXPORT_ROWS)
    if total > MAX_EXPORT_ROWS:
        raise HTTPException(
            422, f"Troppi risultati ({total}): restringi i filtri (massimo {MAX_EXPORT_ROWS})"
        )
    content = xlsx_export.ce_list_xlsx(items) if fmt == "xlsx" else csv_export.ce_list_csv(items)
    audit.record(
        session,
        user,
        "ce",
        None,
        "export_list",
        {"format": fmt, "rows": len(items), "filters": filters.as_audit()},
    )
    session.commit()
    return file_response(content, fmt, safe_filename("elenco_ce", _stamp(), ext=fmt))


@router.get("/summaries/export", summary="Esporta l'elenco ridotto (tutti i ruoli)")
def export_summaries(
    user: CurrentUser,
    session: SessionDep,
    fmt: ListFormat = "xlsx",
    client_id: uuid.UUID | None = None,
    project: str | None = None,
    code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    """Ultima versione approvata di ogni CE: solo codice, cliente, progetto, date e prezzo."""
    filters = CEFilters(client_id, project, code, date_from, date_to)
    items, total = viewer_items(session, filters, MAX_EXPORT_ROWS)
    if total > MAX_EXPORT_ROWS:
        raise HTTPException(
            422, f"Troppi risultati ({total}): restringi i filtri (massimo {MAX_EXPORT_ROWS})"
        )
    content = (
        xlsx_export.viewer_list_xlsx(items) if fmt == "xlsx" else csv_export.viewer_list_csv(items)
    )
    audit.record(
        session,
        user,
        "ce",
        None,
        "export_list",
        {"format": fmt, "variant": "summary", "rows": len(items), "filters": filters.as_audit()},
    )
    session.commit()
    return file_response(content, fmt, safe_filename("elenco_ce_approvati", _stamp(), ext=fmt))


# ======= singolo CE
@router.get(
    "/summaries/{ce_id}/export", summary="Esporta il riepilogo di un CE approvato (tutti i ruoli)"
)
def export_summary(
    ce_id: uuid.UUID, user: CurrentUser, session: SessionDep, fmt: Format = "pdf"
) -> Response:
    """Solo giornate di management e delivery, ricavi per fase e totale: nessun costo né riga."""
    ce = svc.get_ce(session, ce_id)
    reduced = viewer_ce(session, ce)
    if reduced is None:
        raise HTTPException(404, "CE non trovato")
    content = _reduced_file(reduced, fmt, "approved", datetime.now(UTC))
    audit.record(
        session,
        user,
        "ce",
        ce.id,
        "export",
        {"format": fmt, "variant": "summary", "version": reduced.version_number},
    )
    session.commit()
    return file_response(
        content, fmt, safe_filename(ce.code, f"v{reduced.version_number}", "riepilogo", ext=fmt)
    )


@router.get("/{ce_id}/export", summary="Esporta un CE (admin, presale)")
def export_ce(
    ce_id: uuid.UUID,
    user: EditorUser,
    session: SessionDep,
    fmt: Format = "xlsx",
    variant: Variant = "full",
    version: Annotated[
        int | None, Query(ge=1, description="Numero di versione (default: l'ultima)")
    ] = None,
) -> Response:
    """Excel con formule vive, CSV delle righe o PDF. `variant=summary`: riepilogo senza costi."""
    ce = svc.get_ce(session, ce_id)
    chosen = (
        svc.get_version(session, ce, version) if version else svc.get_latest_version(session, ce)
    )
    session.expire_all()
    detail = svc.build_detail(session, user, ce, chosen)
    now = datetime.now(UTC)
    if variant == "summary":
        content = _reduced_file(reduced_from_detail(detail), fmt, detail.version.status, now)
    elif fmt == "xlsx":
        content = xlsx_export.ce_full_xlsx(detail, now)
    elif fmt == "csv":
        content = csv_export.ce_lines_csv(detail)
    else:
        content = pdf_export.ce_full_pdf(detail, now)
    audit.record(
        session,
        user,
        "ce",
        ce.id,
        "export",
        {"format": fmt, "variant": variant, "version": detail.version.number},
    )
    session.commit()
    name = safe_filename(
        ce.code, f"v{detail.version.number}", "riepilogo" if variant == "summary" else None, ext=fmt
    )
    return file_response(content, fmt, name)
