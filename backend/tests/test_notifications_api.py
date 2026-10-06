"""API admin delle email: elenco, invio immediato, nuovo tentativo, email di prova."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AuditLog, EmailOutbox
from app.notifications import dispatch, enqueue
from app.notifications.mailer import SendOutcome
from tests.ce_helpers import create_filled
from tests.helpers import TEST_SETTINGS

URL = "/api/v1/notifications"


def fail_all(retry: bool, error: str):
    return lambda emails: [SendOutcome(False, retry=retry, error=error) for _ in emails]


def add(session, email="a@huware.com", type_="test", **kw) -> EmailOutbox:
    enqueue(session, type_=type_, recipient_email=email, payload={"recipient_name": "A"}, **kw)
    session.flush()
    return session.scalars(select(EmailOutbox).where(EmailOutbox.recipient == email)).one()


def test_list_explains_what_happened_to_each_email(api, env, session, mailer):
    ce_id = create_filled(api, env, "PS-NOT-1")["ce"]["id"]
    api.post(f"/api/v1/ce/{ce_id}/approve", headers=env.h(env.admin))
    mailer.behavior = fail_all(retry=False, error="Mailjet ha rifiutato l'email (mj-0013)")
    row = add(session, "rotta@huware.com")
    dispatch(session, mailer, TEST_SETTINGS)
    body = api.get(URL, headers=env.h(env.admin)).json()
    assert body["total"] == 2
    sent = next(i for i in body["items"] if i["type"] == "ce_approved")
    assert sent["status"] == "sent" and sent["recipient"] == env.presale.email
    assert (
        sent["subject"] == "[CE] Approvato: PS-NOT-1 (v1)"
        and sent["sent_at"]
        and sent["error"] is None
    )
    broken = next(i for i in body["items"] if i["id"] == str(row.id))
    assert broken["status"] == "failed" and "mj-0013" in broken["error"] and broken["attempts"] == 1


def test_list_filters_and_pagination(api, env, session, mailer):
    a = add(session, "anna@huware.com", type_="test")
    add(session, "bruno@huware.com", type_="user_enabled")
    add(session, "carla@huware.com", type_="test")
    a.status = "failed"
    session.flush()
    h = env.h(env.admin)

    def emails(query):
        items = api.get(f"{URL}?{query}", headers=h).json()["items"]
        return sorted(item["recipient"] for item in items)

    assert emails("status=failed") == ["anna@huware.com"]
    assert emails("status=pending") == ["bruno@huware.com", "carla@huware.com"]
    assert emails("type=user_enabled") == ["bruno@huware.com"]
    assert emails("recipient=ARLA") == ["carla@huware.com"]
    assert emails("recipient=%25") == []  # il simbolo % è letterale
    page = api.get(f"{URL}?limit=2", headers=h).json()
    assert (page["total"], len(page["items"])) == (3, 2)
    assert api.get(f"{URL}?status=boh", headers=h).status_code == 422


def test_dispatch_now_sends_what_is_waiting(api, env, session, mailer):
    add(session, "uno@huware.com")
    add(session, "due@huware.com")
    resp = api.post(f"{URL}/dispatch", headers=env.h(env.admin))
    assert resp.status_code == 200
    assert resp.json() == {"processed": 2, "sent": 2, "deferred": 0, "failed": 0, "remaining": 0}
    assert sorted(e.to_email for e in mailer.sent) == ["due@huware.com", "uno@huware.com"]


def test_dispatch_reports_failures(api, env, session, mailer):
    mailer.behavior = fail_all(retry=True, error="giù")
    add(session)
    report = api.post(f"{URL}/dispatch", headers=env.h(env.admin)).json()
    assert (report["sent"], report["deferred"], report["remaining"]) == (0, 1, 1)


def test_retry_puts_a_failed_email_back_and_sends_it(api, env, session, mailer):
    row = add(session, "ritenta@huware.com")
    row.status, row.attempts, row.error = "failed", 5, "Configurazione Mailjet (send-0008)"
    session.flush()
    resp = api.post(f"{URL}/{row.id}/retry", headers=env.h(env.admin))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["attempts"], body["error"]) == ("sent", 1, None)
    assert [e.to_email for e in mailer.sent] == ["ritenta@huware.com"]
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "retry")).one()
    assert entry.user_id == env.admin.id and entry.entity_id == row.id


def test_retry_that_fails_again_shows_the_new_error(api, env, session, mailer):
    row = add(session)
    row.status = "failed"
    session.flush()
    mailer.behavior = fail_all(retry=True, error="ancora giù")
    body = api.post(f"{URL}/{row.id}/retry", headers=env.h(env.admin)).json()
    assert (body["status"], body["error"]) == ("pending", "ancora giù")


def test_only_failed_emails_can_be_retried(api, env, session, mailer):
    pending, sent = add(session, "p@huware.com"), add(session, "s@huware.com")
    sent.status = "sent"
    session.flush()
    for row in (pending, sent):
        assert api.post(f"{URL}/{row.id}/retry", headers=env.h(env.admin)).status_code == 409
    assert (
        api.post(
            f"{URL}/00000000-0000-0000-0000-000000000000/retry", headers=env.h(env.admin)
        ).status_code
        == 404
    )
    assert mailer.sent == []


def test_test_email_goes_to_the_admin_who_asks(api, env, session, mailer):
    resp = api.post(f"{URL}/test", headers=env.h(env.admin))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["type"], body["status"], body["recipient"]) == ("test", "sent", env.admin.email)
    (email,) = mailer.sent
    assert email.to_email == env.admin.email and "funziona" in email.text
    assert (
        session.scalars(select(AuditLog).where(AuditLog.action == "send_test")).one().user_id
        == env.admin.id
    )


def test_test_email_shows_why_it_did_not_arrive(api, env, mailer):
    mailer.behavior = fail_all(
        retry=True, error="Mailjet ha rifiutato le credenziali (verifica chiave e segreto)"
    )
    body = api.post(f"{URL}/test", headers=env.h(env.admin)).json()
    assert body["status"] == "pending" and "credenziali" in body["error"]


def test_each_test_request_sends_a_new_email(api, env, mailer):
    for _ in range(2):
        api.post(f"{URL}/test", headers=env.h(env.admin))
    assert len(mailer.sent) == 2


def test_a_waiting_email_is_not_sent_before_its_time(api, env, session, mailer):
    row = add(session)
    row.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
    session.flush()
    report = api.post(f"{URL}/dispatch", headers=env.h(env.admin)).json()
    assert report["processed"] == 0 and report["remaining"] == 1 and mailer.sent == []
