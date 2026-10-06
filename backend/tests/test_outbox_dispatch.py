"""La coda delle email: invio, ritentativi con attesa crescente, errori definitivi, anti-doppione."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import EmailOutbox
from app.notifications import Notifier, dispatch, enqueue, retry_failed
from app.notifications.mailer import SendOutcome
from app.notifications.outbox import BACKOFF_SECONDS
from tests.conftest import RecordingMailer
from tests.helpers import TEST_SETTINGS

T0 = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
PAYLOAD = {"recipient_name": "Mario"}


def queue(session, n=1, type_="test", **kw) -> list[EmailOutbox]:
    for i in range(n):
        enqueue(session, type_=type_, recipient_email=f"u{i}@huware.com", payload=PAYLOAD, **kw)
    session.flush()
    rows = list(session.scalars(select(EmailOutbox).order_by(EmailOutbox.recipient)))
    for row in rows:
        row.next_attempt_at = T0  # i test usano un'ora fissa: le email nascono "da inviare adesso"
    session.flush()
    return rows


def run(session, mailer, now=T0, **kw):
    return dispatch(session, mailer, TEST_SETTINGS, now=now, **kw)


def failing(retry: bool, error="boom"):
    return lambda emails: [SendOutcome(False, retry=retry, error=error) for _ in emails]


# ------------------------------------------------------------------ invio riuscito
def test_a_successful_send_marks_the_row_and_reports(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    report = run(session, mailer)
    assert (report.processed, report.sent, report.deferred, report.failed, report.remaining) == (
        1,
        1,
        0,
        0,
        0,
    )
    assert (row.status, row.attempts, row.error) == ("sent", 1, None)
    assert row.sent_at == T0 and row.last_attempt_at == T0 and row.provider_message_id == "rec-1"
    (email,) = mailer.sent
    assert (email.id, email.to_email, email.to_name) == (str(row.id), "u0@huware.com", "Mario")
    assert (
        email.subject.startswith("Email di prova")
        and "funziona" in email.text
        and "<html" in email.html
    )


def test_a_sent_email_is_never_sent_twice(session):
    queue(session, 2)
    mailer = RecordingMailer()
    run(session, mailer)
    again = run(session, mailer)
    assert again.processed == 0 and len(mailer.sent) == 2


def test_everything_due_goes_in_a_single_call_to_the_provider(session):
    queue(session, 5)
    mailer = RecordingMailer()
    run(session, mailer)
    assert len(mailer.calls) == 1 and len(mailer.calls[0]) == 5


# ------------------------------------------------------------------ errori temporanei
def test_temporary_errors_back_off_progressively_then_give_up(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=True, error="Mailjet non risponde")
    now = T0
    expected_waits = list(
        BACKOFF_SECONDS[:4]
    )  # al 5° tentativo fallito (max) l'email passa a "fallita"
    for attempt, wait in enumerate(expected_waits, start=1):
        report = run(session, mailer, now=now)
        assert (report.deferred, report.failed) == (1, 0)
        assert (row.status, row.attempts) == ("pending", attempt)
        assert row.next_attempt_at == now + timedelta(seconds=wait)
        assert row.error == "Mailjet non risponde"
        now = row.next_attempt_at
    final = run(session, mailer, now=now)
    assert final.failed == 1 and (row.status, row.attempts) == ("failed", 5)
    assert row.error == "Mailjet non risponde"
    assert run(session, mailer, now=now + timedelta(days=30)).processed == 0  # non si ritenta più


def test_the_wait_schedule_is_1m_5m_30m_2h_6h():
    assert BACKOFF_SECONDS == (60, 300, 1800, 7200, 21600)


def test_a_retry_that_finally_works_clears_the_error(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=True)
    run(session, mailer)
    assert row.status == "pending" and row.error == "boom"
    mailer.behavior = None
    run(session, mailer, now=T0 + timedelta(minutes=2))
    assert (row.status, row.attempts, row.error) == ("sent", 2, None)


def test_emails_not_yet_due_are_left_alone(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=True)
    run(session, mailer)
    mailer.calls.clear()
    soon = run(session, mailer, now=T0 + timedelta(seconds=59))
    assert soon.processed == 0 and soon.remaining == 1 and mailer.calls == []
    assert run(session, mailer, now=T0 + timedelta(seconds=60)).processed == 1
    assert row.attempts == 2


# ------------------------------------------------------------------ errori definitivi
def test_a_permanent_error_fails_immediately_and_is_not_retried(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=False, error="indirizzo non valido")
    report = run(session, mailer)
    assert (report.failed, report.deferred, report.remaining) == (1, 0, 0)
    assert (row.status, row.attempts, row.error) == ("failed", 1, "indirizzo non valido")
    mailer.calls.clear()
    run(session, mailer, now=T0 + timedelta(days=1))
    assert mailer.calls == []


def test_outcomes_are_matched_to_the_right_rows_in_a_mixed_batch(session):
    rows = queue(session, 4)
    mailer = RecordingMailer()
    outcome_for = {
        "u0@huware.com": SendOutcome(True, provider_id="ok-a"),
        "u1@huware.com": SendOutcome(False, retry=False, error="rifiutata"),
        "u2@huware.com": SendOutcome(False, retry=True, error="temporanea"),
        "u3@huware.com": SendOutcome(True, provider_id="ok-b"),
    }
    mailer.behavior = lambda emails: [outcome_for[e.to_email] for e in emails]
    report = run(session, mailer)
    assert (report.sent, report.failed, report.deferred) == (2, 1, 1)
    by_email = {r.recipient: r for r in rows}
    assert [by_email[f"u{i}@huware.com"].status for i in range(4)] == [
        "sent",
        "failed",
        "pending",
        "sent",
    ]
    assert by_email["u0@huware.com"].provider_message_id == "ok-a"
    assert by_email["u3@huware.com"].provider_message_id == "ok-b"
    assert (
        by_email["u1@huware.com"].error == "rifiutata"
        and by_email["u2@huware.com"].error == "temporanea"
    )


def test_an_unexpected_exception_in_the_client_is_treated_as_temporary(session):
    (row,) = queue(session)
    mailer = RecordingMailer()

    def explode(emails):
        raise RuntimeError("bug nel client")

    mailer.behavior = explode
    report = run(session, mailer)  # non propaga
    assert (report.deferred, row.status, row.attempts) == (1, "pending", 1)
    assert (
        "RuntimeError" in row.error and "bug nel client" not in row.error
    )  # nessun dettaglio interno


def test_an_email_that_cannot_be_rendered_fails_without_blocking_the_others(session):
    bad = EmailOutbox(
        type="tipo-inesistente", recipient="x@huware.com", payload={}, next_attempt_at=T0
    )
    session.add(bad)
    queue(session, 2)
    mailer = RecordingMailer()
    report = run(session, mailer)
    assert (report.sent, report.failed) == (2, 1)
    assert bad.status == "failed" and "non preparabile" in bad.error
    assert len(mailer.sent) == 2


# ------------------------------------------------------------------ selezione
def test_limit_takes_the_oldest_first(session):
    rows = queue(session, 5)
    base = T0 - timedelta(hours=1)
    for i, row in enumerate(rows):
        row.next_attempt_at = base + timedelta(minutes=i)
    session.flush()
    mailer = RecordingMailer()
    report = run(session, mailer, limit=2)
    assert report.processed == 2 and report.remaining == 3
    assert [e.to_email for e in mailer.sent] == ["u0@huware.com", "u1@huware.com"]


def test_dispatch_can_target_specific_rows(session):
    rows = queue(session, 3)
    mailer = RecordingMailer()
    run(session, mailer, ids=[rows[1].id])
    assert [e.to_email for e in mailer.sent] == ["u1@huware.com"]
    assert [r.status for r in rows] == ["pending", "sent", "pending"]


# ------------------------------------------------------------------ anti-doppione e nuovo tentativo
def test_the_same_event_cannot_queue_the_same_email_twice(session):
    first = enqueue(
        session,
        type_="test",
        recipient_email="a@huware.com",
        payload=PAYLOAD,
        dedupe_key="evento-1",
    )
    second = enqueue(
        session,
        type_="test",
        recipient_email="a@huware.com",
        payload=PAYLOAD,
        dedupe_key="evento-1",
    )
    other = enqueue(
        session,
        type_="test",
        recipient_email="a@huware.com",
        payload=PAYLOAD,
        dedupe_key="evento-2",
    )
    assert (first, second, other) == (True, False, True)
    assert len(session.scalars(select(EmailOutbox)).all()) == 2


def test_emails_without_a_key_are_never_considered_duplicates(session):
    for _ in range(2):
        assert enqueue(session, type_="test", recipient_email="a@huware.com", payload=PAYLOAD)
    assert len(session.scalars(select(EmailOutbox)).all()) == 2


def test_retrying_a_failed_email_puts_it_back_in_the_queue(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=False, error="rifiutata")
    run(session, mailer)
    assert row.status == "failed"
    retry_failed(session, row)
    assert (row.status, row.attempts, row.error) == ("pending", 0, None)
    mailer.behavior = None
    run(
        session, mailer, now=datetime.now(UTC) + timedelta(hours=1)
    )  # il nuovo tentativo parte "adesso"
    assert row.status == "sent"


# ------------------------------------------------------------------ Notifier
def test_notifier_never_raises_and_leaves_the_session_usable(session):
    class Broken:
        def send(self, emails):
            raise MemoryError

    queue(session)
    notifier = Notifier(Broken(), TEST_SETTINGS)
    assert (
        notifier.flush(session) is not None
    )  # l'errore è assorbito dal dispatch come errore temporaneo
    assert session.scalar(select(EmailOutbox.attempts)) == 1


def test_notifier_swallows_even_failures_of_the_database_layer(session, monkeypatch):
    import app.notifications.outbox as outbox

    def boom(*args, **kwargs):
        raise RuntimeError("database giù")

    monkeypatch.setattr(outbox, "dispatch", boom)
    assert Notifier(RecordingMailer(), TEST_SETTINGS).flush(session) is None
    assert session.scalar(select(EmailOutbox.id)) is None  # e la sessione è ancora utilizzabile


def test_max_attempts_comes_from_the_settings(session):
    (row,) = queue(session)
    mailer = RecordingMailer()
    mailer.behavior = failing(retry=True)
    strict = TEST_SETTINGS.model_copy(update={"mail_max_attempts": 2})
    dispatch(session, mailer, strict, now=T0)
    dispatch(session, mailer, strict, now=T0 + timedelta(minutes=2))
    assert (row.status, row.attempts) == ("failed", 2)
