"""Export dei CE: Excel, CSV, PDF. Il viewer ottiene solo la vista ridotta."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import CurrentUser, EditorUser, SessionDep, SettingsDep, enforce_ce_visibility
from app.exports import csv_export, pdf_export, xlsx_export
from app.exports.common import MAX_EXPORT_ROWS, MIME, file_response, safe_filename
from app.exports.reduced import reduced_from_detail
from app.models import AuditLog, Client, EmailOutbox
from app.notifications import enqueue
from app.notifications.deps import NotifierDep
from app.notifications.mailer import Attachment
from app.schemas.ce import CEStatus, ViewerCE
from app.schemas.exports import ExportEmailIn, ExportEmailOut
from app.services import audit, unit_division, visibility
from app.services import ce as svc
from app.services.ce_search import CEFilters, editor_items, viewer_ce, viewer_items

router = APIRouter(prefix="/ce", tags=["Export"], dependencies=[Depends(enforce_ce_visibility)])

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


def _reduced_file(
    ce: ViewerCE,
    fmt: str,
    status: str | None,
    now: datetime,
    units: list[unit_division.RevenueRow] | None = None,
) -> bytes:
    if fmt == "xlsx":
        return xlsx_export.reduced_xlsx(ce)
    if fmt == "csv":
        return csv_export.reduced_csv(ce)
    return pdf_export.ce_summary_pdf(ce, status, now, units=units)


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
    business_unit_id: uuid.UUID | None = None,
    outcome: Literal["none", "won", "lost"] | None = None,
) -> Response:
    """Stessi filtri della ricerca. Massimo 5000 righe."""
    if include_deleted and user.role != "admin":
        raise HTTPException(403, "Solo un amministratore può vedere i CE eliminati")
    filters = CEFilters(
        client_id,
        project,
        code,
        date_from,
        date_to,
        status,
        created_by,
        include_deleted,
        business_unit_id,
        outcome,
    )
    items, total = editor_items(
        session, filters, MAX_EXPORT_ROWS, visible=visibility.visible_condition(session, user)
    )
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
    # i ricavi per business unit vengono dal calcolo dell'ultima versione approvata (congelata)
    approved = svc.get_latest_approved(session, ce)
    units = unit_division.business_unit_revenue(
        session, svc.build_detail(session, user, ce, approved)
    )
    content = _reduced_file(reduced, fmt, "approved", datetime.now(UTC), units)
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


def _build_export(
    session, user, ce, fmt: str, variant: str, version: int | None
) -> tuple[bytes, str, int]:
    """Genera il file di un CE (completo o riepilogo). Restituisce contenuto, nome e versione."""
    chosen = (
        svc.get_version(session, ce, version) if version else svc.get_latest_version(session, ce)
    )
    session.expire_all()
    detail = svc.build_detail(session, user, ce, chosen)
    now = datetime.now(UTC)
    if variant == "summary":
        content = _reduced_file(
            reduced_from_detail(detail),
            fmt,
            detail.version.status,
            now,
            unit_division.business_unit_revenue(session, detail),
        )
    elif fmt == "xlsx":
        content = xlsx_export.ce_full_xlsx(detail, now)
    elif fmt == "csv":
        content = csv_export.ce_lines_csv(detail)
    else:
        content = pdf_export.ce_full_pdf(
            detail, now, division=unit_division.business_unit_division(session, detail)
        )
    name = safe_filename(
        ce.code, f"v{detail.version.number}", "riepilogo" if variant == "summary" else None, ext=fmt
    )
    return content, name, detail.version.number


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
    content, name, number = _build_export(session, user, ce, fmt, variant, version)
    audit.record(
        session, user, "ce", ce.id, "export", {"format": fmt, "variant": variant, "version": number}
    )
    session.commit()
    return file_response(content, fmt, name)


REPORT_LABELS = {
    ("summary", "pdf"): "Riepilogo PDF",
    ("summary", "xlsx"): "Riepilogo Excel",
    ("full", "pdf"): "PDF completo",
    ("full", "xlsx"): "Excel completo",
}
EMAIL_LIMIT_PER_HOUR = 20  # invii per utente: argina errori e abusi
MAX_ATTACHMENT_BYTES = 8_000_000


@router.post(
    "/{ce_id}/export/email",
    response_model=ExportEmailOut,
    summary="Invia per email il report di un CE (admin, presale)",
)
def email_export(
    ce_id: uuid.UUID,
    body: ExportEmailIn,
    user: EditorUser,
    session: SessionDep,
    settings: SettingsDep,
    notifier: NotifierDep,
) -> ExportEmailOut:
    """Il file è quello dell'export, allegato a un'email a un solo destinatario.

    I report completi (costi e margini) partono solo verso indirizzi dei domini aziendali;
    i riepiloghi (senza costi né righe) si possono inviare a chiunque.
    """
    domain = body.recipient.rsplit("@", 1)[1]
    if body.variant == "full" and domain not in settings.allowed_email_domains:
        raise HTTPException(
            403,
            "Il report completo contiene costi e margini: si può inviare solo a indirizzi "
            f"aziendali ({', '.join(settings.allowed_email_domains)}). Scegli un riepilogo.",
        )
    recent = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.user_id == user.id,
            AuditLog.action == "export_email",
            AuditLog.occurred_at >= datetime.now(UTC) - timedelta(hours=1),
        )
    )
    if (recent or 0) >= EMAIL_LIMIT_PER_HOUR:
        raise HTTPException(
            429,
            f"Hai raggiunto il limite di {EMAIL_LIMIT_PER_HOUR} invii all'ora: riprova più tardi",
        )

    ce = svc.get_ce(session, ce_id)
    content, name, number = _build_export(
        session, user, ce, body.format, body.variant, body.version
    )
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Il file è troppo grande per essere allegato a un'email")
    label = REPORT_LABELS[(body.variant, body.format)]
    version = svc.get_version(session, ce, number)
    client = session.get(Client, version.client_id)
    key = f"report:{user.id}:{uuid.uuid4()}"
    enqueue(
        session,
        type_="ce_report",
        recipient_email=body.recipient,
        payload={
            "recipient_name": "",
            "actor_name": user.full_name,
            "ce_id": str(ce.id),
            "code": ce.code,
            "version": number,
            "client_name": client.name if client else "",
            "project_name": version.project_name,
            "start_date": version.start_date.isoformat(),
            "end_date": version.end_date.isoformat(),
            "report_label": label,
            "filename": name,
            "message": body.message,
        },
        dedupe_key=key,
        attachment=Attachment(name=name, mime=MIME[body.format], content=content),
    )
    audit.record(
        session,
        user,
        "ce",
        ce.id,
        "export_email",
        {
            "recipient": body.recipient,
            "format": body.format,
            "variant": body.variant,
            "version": number,
        },
    )
    session.commit()
    row = session.scalars(select(EmailOutbox).where(EmailOutbox.dedupe_key == key)).one()
    notifier.flush(session)
    session.refresh(row)
    status = {"sent": "sent", "pending": "queued"}.get(row.status, "failed")
    return ExportEmailOut(recipient=body.recipient, filename=name, status=status, error=row.error)
