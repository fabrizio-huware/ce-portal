"""Coda delle email: preparazione (nella stessa transazione dell'evento) e invio con ritentativi."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import CE, CEVersion, Client, EmailOutbox, User
from app.notifications.mailer import Mailer, OutgoingEmail, SendOutcome
from app.notifications.templates import render

logger = logging.getLogger("ce_portal.mail")

# Attesa prima di ogni ritentativo: 1 minuto, 5, 30, 2 ore, 6 ore.
BACKOFF_SECONDS = (60, 300, 1800, 7200, 21600)


def _now() -> datetime:
    return datetime.now(UTC)


# ====================================================================== preparazione
def enqueue(
    session: Session,
    *,
    type_: str,
    recipient_email: str,
    payload: dict[str, Any],
    dedupe_key: str | None = None,
) -> bool:
    """Mette l'email in coda. Restituisce False se esisteva già (stessa chiave anti-doppione).

    Non fa commit: l'email nasce o muore insieme all'evento che l'ha generata.
    """
    result = session.execute(
        pg_insert(EmailOutbox)
        .values(type=type_, recipient=recipient_email, payload=payload, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(EmailOutbox.id)
    )
    return result.scalar_one_or_none() is not None


def _active_admins(session: Session, exclude: User | None) -> list[User]:
    stmt = select(User).where(User.role == "admin", User.is_active).order_by(User.email)
    return [u for u in session.scalars(stmt) if exclude is None or u.id != exclude.id]


def _ce_payload(
    session: Session, ce: CE, version: CEVersion, actor: User, recipient: User
) -> dict[str, Any]:
    client = session.get(Client, version.client_id)
    return {
        "recipient_name": recipient.full_name,
        "actor_name": actor.full_name,
        "ce_id": str(ce.id),
        "code": ce.code,
        "version": version.version_number,
        "client_name": client.name if client else "",
        "project_name": version.project_name,
        "start_date": version.start_date.isoformat(),
        "end_date": version.end_date.isoformat(),
        # Solo il prezzo: costi e margini non escono mai dal portale via email.
        "price": (version.summary or {}).get("revenue"),
    }


def notify_ce_submitted(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    for admin in _active_admins(session, exclude=actor):
        enqueue(
            session,
            type_="ce_submitted",
            recipient_email=admin.email,
            payload=_ce_payload(session, ce, version, actor, admin),
            dedupe_key=f"ce_submitted:{version.id}:{version.revision}:{admin.id}",
        )


def _owner_if_notifiable(session: Session, ce: CE, actor: User) -> User | None:
    owner = session.get(User, ce.created_by)
    if owner is None or not owner.is_active or owner.id == actor.id:
        return None
    return owner


def notify_ce_approved(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    if owner := _owner_if_notifiable(session, ce, actor):
        enqueue(
            session,
            type_="ce_approved",
            recipient_email=owner.email,
            payload=_ce_payload(session, ce, version, actor, owner),
            dedupe_key=f"ce_approved:{version.id}:{owner.id}",
        )


def notify_ce_rejected(
    session: Session, actor: User, ce: CE, version: CEVersion, reason: str
) -> None:
    if owner := _owner_if_notifiable(session, ce, actor):
        enqueue(
            session,
            type_="ce_rejected",
            recipient_email=owner.email,
            payload={**_ce_payload(session, ce, version, actor, owner), "reason": reason},
            dedupe_key=f"ce_rejected:{version.id}:{version.revision}:{owner.id}",
        )


def notify_ce_new_version(session: Session, actor: User, ce: CE, version: CEVersion) -> None:
    for admin in _active_admins(session, exclude=actor):
        enqueue(
            session,
            type_="ce_new_version",
            recipient_email=admin.email,
            payload=_ce_payload(session, ce, version, actor, admin),
            dedupe_key=f"ce_new_version:{version.id}:{admin.id}",
        )


def notify_user_enabled(session: Session, actor: User, user: User) -> None:
    enqueue(
        session,
        type_="user_enabled",
        recipient_email=user.email,
        payload={
            "recipient_name": user.full_name,
            "actor_name": actor.full_name,
            "role": user.role,
        },
        dedupe_key=f"user_enabled:{user.id}",
    )


# ====================================================================== invio
@dataclass
class DispatchReport:
    processed: int = 0
    sent: int = 0
    deferred: int = 0  # errore temporaneo: resta in coda
    failed: int = 0  # errore definitivo o tentativi esauriti
    remaining: int = 0  # ancora in attesa (anche non ancora scadute)


def _settle(
    row: EmailOutbox,
    outcome: SendOutcome,
    settings: Settings,
    now: datetime,
    report: DispatchReport,
) -> None:
    row.attempts += 1
    row.last_attempt_at = now
    if outcome.ok:
        row.status, row.sent_at, row.error = "sent", now, None
        row.provider_message_id = outcome.provider_id
        report.sent += 1
    elif outcome.retry and row.attempts < settings.mail_max_attempts:
        wait = BACKOFF_SECONDS[min(row.attempts - 1, len(BACKOFF_SECONDS) - 1)]
        row.next_attempt_at = now + timedelta(seconds=wait)
        row.error = outcome.error
        report.deferred += 1
    else:
        row.status, row.error = "failed", outcome.error
        report.failed += 1


def dispatch(
    session: Session,
    mailer: Mailer,
    settings: Settings,
    *,
    limit: int = 50,
    ids: list[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> DispatchReport:
    """Invia le email in coda scadute. Due invii contemporanei non si pestano i piedi
    (le righe in lavorazione sono bloccate con SKIP LOCKED)."""
    now = now or _now()
    stmt = select(EmailOutbox).where(
        EmailOutbox.status == "pending", EmailOutbox.next_attempt_at <= now
    )
    if ids:
        stmt = stmt.where(EmailOutbox.id.in_(ids))
    rows = session.scalars(
        stmt.order_by(EmailOutbox.next_attempt_at, EmailOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()

    report = DispatchReport(processed=len(rows))
    emails: list[OutgoingEmail] = []
    to_send: list[EmailOutbox] = []
    for row in rows:
        try:
            rendered = render(row.type, row.payload, settings.public_base_url)
        except Exception as exc:  # contenuto non valido: ritentare non servirebbe
            _settle(
                row,
                SendOutcome(False, error=f"Email non preparabile: {exc}"),
                settings,
                now,
                report,
            )
            continue
        emails.append(
            OutgoingEmail(
                id=str(row.id),
                to_email=row.recipient,
                to_name=str(row.payload.get("recipient_name") or ""),
                subject=rendered.subject,
                text=rendered.text,
                html=rendered.html,
            )
        )
        to_send.append(row)

    if emails:
        try:
            outcomes = mailer.send(emails)
        except Exception as exc:  # errore imprevisto del client: tratta come temporaneo
            logger.exception("Errore imprevisto nell'invio delle email")
            outcomes = [
                SendOutcome(False, retry=True, error=f"Errore imprevisto ({type(exc).__name__})")
            ] * len(emails)
        for row, outcome in zip(to_send, outcomes, strict=True):
            _settle(row, outcome, settings, now, report)

    session.commit()
    report.remaining = (
        session.scalar(
            select(func.count()).select_from(EmailOutbox).where(EmailOutbox.status == "pending")
        )
        or 0
    )
    return report


def retry_failed(session: Session, row: EmailOutbox) -> None:
    """Rimette in coda un'email fallita: partirà al prossimo giro di invio."""
    row.status = "pending"
    row.attempts = 0
    row.next_attempt_at = _now()
    row.error = None


class Notifier:
    """Usato dalle API dopo il commit: invia subito, senza mai far fallire la richiesta."""

    def __init__(self, mailer: Mailer, settings: Settings) -> None:
        self.mailer = mailer
        self.settings = settings

    def flush(self, session: Session) -> DispatchReport | None:
        try:
            return dispatch(session, self.mailer, self.settings)
        except Exception:
            logger.exception("Invio immediato delle email non riuscito: restano in coda")
            session.rollback()
            return None
