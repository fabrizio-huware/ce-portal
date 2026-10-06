import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import (
    AdminUser,
    PageDep,
    SessionDep,
    SettingsDep,
    get_or_404,
    like_pattern,
    paginate,
)
from app.models import EmailOutbox
from app.notifications import dispatch, enqueue, retry_failed
from app.notifications.deps import NotifierDep
from app.notifications.templates import render
from app.schemas.common import Page
from app.schemas.notifications import DispatchOut, NotificationOut, NotificationStatus
from app.services import audit

router = APIRouter(prefix="/notifications", tags=["Notifiche email"])


def _out(row: EmailOutbox, base_url: str) -> NotificationOut:
    try:
        subject = render(row.type, row.payload, base_url).subject
    except Exception:
        subject = None
    return NotificationOut(
        id=row.id,
        type=row.type,
        recipient=row.recipient,
        subject=subject,
        status=row.status,
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        last_attempt_at=row.last_attempt_at,
        sent_at=row.sent_at,
        error=row.error,
        created_at=row.created_at,
    )


@router.get("", response_model=Page[NotificationOut], summary="Email preparate, inviate e fallite")
def list_notifications(
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
    params: PageDep,
    status: NotificationStatus | None = None,
    type: Annotated[str | None, Query(description="es. ce_submitted")] = None,
    recipient: Annotated[str | None, Query(description="testo contenuto nell'indirizzo")] = None,
) -> Page[NotificationOut]:
    """Per capire perché un'email non è arrivata: stato, tentativi ed errore di Mailjet."""
    stmt = select(EmailOutbox).order_by(EmailOutbox.created_at.desc())
    if status:
        stmt = stmt.where(EmailOutbox.status == status)
    if type:
        stmt = stmt.where(EmailOutbox.type == type)
    if recipient:
        stmt = stmt.where(EmailOutbox.recipient.ilike(like_pattern(recipient), escape="\\"))
    rows, total = paginate(session, stmt, params)
    return Page(
        items=[_out(r, settings.public_base_url) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("/dispatch", response_model=DispatchOut, summary="Invia subito le email in coda")
def dispatch_now(
    admin: AdminUser, session: SessionDep, settings: SettingsDep, notifier: NotifierDep
) -> DispatchOut:
    report = dispatch(session, notifier.mailer, settings)
    return DispatchOut(**vars(report))


@router.post("/test", response_model=NotificationOut, summary="Invia un'email di prova a te stesso")
def send_test(
    admin: AdminUser, session: SessionDep, settings: SettingsDep, notifier: NotifierDep
) -> NotificationOut:
    """Verifica le credenziali e il mittente di Mailjet senza toccare nessun CE."""
    key = f"test:{admin.id}:{uuid.uuid4()}"
    enqueue(
        session,
        type_="test",
        recipient_email=admin.email,
        payload={"recipient_name": admin.full_name},
        dedupe_key=key,
    )
    audit.record(session, admin, "email", None, "send_test", {"recipient": admin.email})
    session.commit()
    row = session.scalars(select(EmailOutbox).where(EmailOutbox.dedupe_key == key)).one()
    dispatch(session, notifier.mailer, settings, ids=[row.id])
    session.refresh(row)
    return _out(row, settings.public_base_url)


@router.post(
    "/{notification_id}/retry", response_model=NotificationOut, summary="Riprova un'email fallita"
)
def retry(
    notification_id: uuid.UUID,
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
    notifier: NotifierDep,
) -> NotificationOut:
    row = get_or_404(session, EmailOutbox, notification_id, "Email")
    if row.status != "failed":
        raise HTTPException(409, "Si possono riprovare solo le email fallite")
    retry_failed(session, row)
    audit.record(session, admin, "email", row.id, "retry", {"recipient": row.recipient})
    session.commit()
    dispatch(session, notifier.mailer, settings, ids=[row.id])
    session.refresh(row)
    return _out(row, settings.public_base_url)
