"""Quali email partono per ogni evento, a chi, e a chi non devono mai arrivare."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import EmailOutbox
from app.notifications import dispatch
from app.notifications.mailer import SendOutcome
from tests.ce_helpers import create, create_filled, real_ce_content, save, simple_content
from tests.factories import make_client, make_user
from tests.helpers import TEST_SETTINGS

URL = "/api/v1/ce"
BASE = TEST_SETTINGS.public_base_url


def recipients(mailer) -> list[str]:
    return sorted(e.to_email for e in mailer.sent)


def outbox(session) -> list[EmailOutbox]:
    return list(session.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at)))


@pytest.fixture
def team(env, session):
    """Un secondo admin attivo e uno disattivato, oltre agli utenti dell'ambiente."""
    return {
        "admin2": make_user(session, role="admin"),
        "ex_admin": make_user(session, role="admin", is_active=False),
    }


def post(api, env, ce_id, action, who, **kw):
    user = {"owner": env.presale, "admin": env.admin, "other": env.other}[who]
    return api.post(f"{URL}/{ce_id}/{action}", headers=env.h(user), **kw)


# ------------------------------------------------------------------ invio in approvazione
def test_submit_notifies_every_active_admin_but_nobody_else(api, env, team, mailer):
    ce = create_filled(api, env, "PS-MAIL-1")
    assert mailer.sent == []  # creare e salvare non genera email
    assert post(api, env, ce["ce"]["id"], "submit", "owner").status_code == 200
    assert recipients(mailer) == sorted([env.admin.email, team["admin2"].email])
    assert env.viewer.email not in recipients(mailer) and team["ex_admin"].email not in recipients(
        mailer
    )
    assert env.presale.email not in recipients(mailer) and env.other.email not in recipients(mailer)
    email = next(e for e in mailer.sent if e.to_email == env.admin.email)
    assert email.subject == "[CE] Da approvare: PS-MAIL-1 (v1) – Cliente di prova"
    assert email.to_name == env.admin.full_name
    assert f"{env.presale.full_name} ha inviato in approvazione il CE PS-MAIL-1" in email.text
    assert "Prezzo: 1.700,00 €" in email.text
    assert f"{BASE}/ce/{ce['ce']['id']}" in email.text


def test_an_admin_submitting_does_not_email_themselves(api, env, team, mailer):
    ce = create_filled(api, env, "PS-MAIL-2", user=env.admin)
    post(api, env, ce["ce"]["id"], "submit", "admin")
    assert recipients(mailer) == [team["admin2"].email]


def test_resubmitting_after_a_withdrawal_notifies_again(api, env, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-3")["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    post(api, env, ce_id, "withdraw", "owner")
    assert len(mailer.sent) == 1  # il ritiro non genera email
    post(api, env, ce_id, "submit", "owner")
    assert [e.to_email for e in mailer.sent] == [env.admin.email] * 2


# ------------------------------------------------------------------ approvazione e rifiuto
def test_approval_notifies_the_author_only(api, env, team, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-4")["ce"]["id"]
    post(api, env, ce_id, "approve", "admin")
    assert recipients(mailer) == [env.presale.email]
    email = mailer.sent[0]
    assert email.subject == "[CE] Approvato: PS-MAIL-4 (v1)"
    assert f"approvato da {env.admin.full_name}" in email.text and "1.700,00 €" in email.text


def test_an_admin_approving_their_own_ce_is_not_emailed(api, env, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-5", user=env.admin)["ce"]["id"]
    assert post(api, env, ce_id, "approve", "admin").status_code == 200
    assert mailer.sent == []


def test_rejection_notifies_the_author_with_the_reason(api, env, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-6")["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    mailer.calls.clear()
    post(api, env, ce_id, "reject", "admin", json={"reason": "Mancano le ore di test"})
    assert recipients(mailer) == [env.presale.email]
    email = mailer.sent[0]
    assert email.subject == "[CE] Rifiutato: PS-MAIL-6 (v1)"
    assert "Motivo: Mancano le ore di test" in email.text and "inviarlo di nuovo" in email.text


def test_an_inactive_author_is_skipped_without_breaking_the_workflow(api, env, session, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-7")["ce"]["id"]
    env.presale.is_active = False
    session.flush()
    assert post(api, env, ce_id, "approve", "admin").status_code == 200
    assert mailer.sent == []


# ------------------------------------------------------------------ nuova versione
def test_a_new_version_notifies_the_admins_except_the_actor(api, env, team, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-8")["ce"]["id"]
    post(api, env, ce_id, "approve", "admin")
    mailer.calls.clear()
    assert post(api, env, ce_id, "versions", "owner").status_code == 201
    assert recipients(mailer) == sorted([env.admin.email, team["admin2"].email])
    email = mailer.sent[0]
    assert email.subject == "[CE] Nuova versione: PS-MAIL-8 (v2)"
    assert (
        f"{env.presale.full_name} ha creato la versione 2" in email.text
        and "versione 1 approvata" in email.text
    )


# ------------------------------------------------------------------ nuovo utente
def test_creating_a_user_emails_the_new_user(api, env, mailer):
    resp = api.post(
        "/api/v1/users",
        headers=env.h(env.admin),
        json={"email": "nuovo@huware.com", "full_name": "Nuovo Utente", "role": "presale"},
    )
    assert resp.status_code == 201
    (email,) = mailer.sent
    assert email.to_email == "nuovo@huware.com" and email.to_name == "Nuovo Utente"
    assert email.subject == "Accesso al portale Conti Economici"
    assert f"{env.admin.full_name} ti ha abilitato" in email.text and "ruolo Presale" in email.text
    assert f"Apri il portale: {BASE}" in email.text


def test_failed_user_creation_sends_nothing(api, env, mailer, session):
    h = env.h(env.admin)
    api.post(
        "/api/v1/users",
        headers=h,
        json={"email": "uno@huware.com", "full_name": "Uno", "role": "viewer"},
    )
    mailer.calls.clear()
    for body in (
        {"email": "UNO@huware.com", "full_name": "Doppio", "role": "viewer"},  # già esistente
        {"email": "x@gmail.com", "full_name": "X", "role": "viewer"},  # dominio non ammesso
        {"email": "non-valida", "full_name": "X", "role": "viewer"},
    ):
        assert api.post("/api/v1/users", headers=h, json=body).status_code in (409, 422)
    assert mailer.sent == [] and len(outbox(session)) == 1


# ------------------------------------------------------------------ nessuna email se l'operazione non riesce
def test_refused_operations_send_nothing_and_prepare_nothing(api, env, session, mailer):
    empty = create(api, env, code="PS-MAIL-9")["ce"]["id"]  # vuoto: non inviabile
    filled = create_filled(api, env, "PS-MAIL-10")["ce"]["id"]
    attempts = [
        post(api, env, empty, "submit", "owner"),  # 422 incompleto
        post(api, env, empty, "approve", "admin"),  # 422 incompleto
        post(api, env, filled, "submit", "other"),  # 403 non è l'autore
        post(api, env, filled, "approve", "owner"),  # 403 solo admin
        post(api, env, filled, "reject", "admin", json={"reason": "no"}),  # 409 non in approvazione
        post(api, env, filled, "versions", "owner"),  # 409 non approvato
    ]
    assert [a.status_code for a in attempts] == [422, 422, 403, 403, 409, 409]
    assert mailer.sent == [] and outbox(session) == []


def test_editing_and_discarding_do_not_send_emails(api, env, mailer):
    ce = create_filled(api, env, "PS-MAIL-11")
    ce_id = ce["ce"]["id"]
    save(api, env, ce_id, simple_content(env, ce["version"]["revision"] + 1, hours="24"))
    post(api, env, ce_id, "approve", "admin")
    mailer.calls.clear()
    api.post(f"{URL}/{ce_id}/versions", headers=env.h(env.presale))
    mailer.calls.clear()
    api.delete(f"{URL}/{ce_id}/open-version", headers=env.h(env.presale))
    assert mailer.sent == []


def test_the_viewer_never_receives_anything(api, env, team, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-12")["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    post(api, env, ce_id, "reject", "admin", json={"reason": "Motivo"})
    post(api, env, ce_id, "submit", "owner")
    post(api, env, ce_id, "approve", "admin")
    post(api, env, ce_id, "versions", "owner")
    assert len(mailer.sent) >= 5 and env.viewer.email not in recipients(mailer)


# ------------------------------------------------------------------ affidabilità
def test_a_mail_provider_outage_does_not_block_the_workflow(api, env, session, mailer):
    mailer.behavior = lambda emails: [
        SendOutcome(False, retry=True, error="Mailjet non risponde") for _ in emails
    ]
    ce_id = create_filled(api, env, "PS-MAIL-13")["ce"]["id"]
    resp = post(api, env, ce_id, "approve", "admin")
    assert resp.status_code == 200 and resp.json()["version"]["status"] == "approved"
    (row,) = outbox(session)
    assert (row.status, row.attempts, row.error) == ("pending", 1, "Mailjet non risponde")
    assert row.recipient == env.presale.email and row.next_attempt_at > datetime.now(UTC)

    mailer.behavior = None  # Mailjet torna disponibile: il giro successivo la consegna
    report = dispatch(session, mailer, TEST_SETTINGS, now=datetime.now(UTC) + timedelta(minutes=2))
    assert report.sent == 1 and row.status == "sent" and row.attempts == 2


def test_a_provider_that_crashes_does_not_block_the_workflow(api, env, session, mailer):
    def explode(emails):
        raise RuntimeError("giù")

    mailer.behavior = explode
    ce_id = create_filled(api, env, "PS-MAIL-14")["ce"]["id"]
    assert post(api, env, ce_id, "approve", "admin").status_code == 200
    assert outbox(session)[0].status == "pending"


def test_the_next_event_also_delivers_emails_that_were_waiting(api, env, session, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-15")["ce"]["id"]
    mailer.behavior = lambda emails: [SendOutcome(False, retry=True, error="x") for _ in emails]
    post(api, env, ce_id, "approve", "admin")  # l'email all'autore resta in coda
    row = outbox(session)[0]
    row.next_attempt_at = datetime.now(UTC) - timedelta(minutes=1)  # ora è scaduta
    session.flush()
    mailer.behavior = None
    mailer.calls.clear()
    other = create_filled(api, env, "PS-MAIL-16")["ce"]["id"]
    post(api, env, other, "approve", "admin")  # un nuovo evento
    assert sorted(e.to_email for e in mailer.sent) == [env.presale.email] * 2
    assert row.status == "sent"


def test_the_local_console_backend_marks_emails_as_sent(api, env, session):
    ce_id = create_filled(api, env, "PS-MAIL-17")["ce"][
        "id"
    ]  # nessun registratore: backend console
    post(api, env, ce_id, "approve", "admin")
    (row,) = outbox(session)
    assert (row.status, row.provider_message_id) == ("sent", "console")


# ------------------------------------------------------------------ riservatezza e sicurezza dei contenuti
def test_emails_carry_the_price_but_never_costs_or_margins(api, env, mailer):
    created = create(api, env, code="PS-MAIL-18")
    save(
        api, env, created["ce"]["id"], real_ce_content(env, 1)
    )  # ricavi 47.162,50 · costi 20.200,00
    ce_id = created["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    post(api, env, ce_id, "approve", "admin")
    assert len(mailer.sent) == 2
    for email in mailer.sent:
        assert "47.162,50 €" in email.text
        for forbidden in (
            "20.200",
            "26.962",
            "57,17",
            "0,5717",
            "margine",
            "Margine",
            "costi",
            "Costi",
        ):
            assert forbidden not in email.text, forbidden
            assert forbidden not in email.html, forbidden


def test_hostile_user_text_is_neutralised(api, env, session, mailer):
    evil_client = make_client(session, name="Cliente\r\nBcc: spia@evil.com")
    created = create(
        api,
        env,
        code="PS-MAIL-19",
        client_id=str(evil_client.id),
        project_name="<script>x</script>",
    )
    save(
        api,
        env,
        created["ce"]["id"],
        simple_content(env, 1, client_id=str(evil_client.id), project_name="<script>x</script>"),
    )
    ce_id = created["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    post(api, env, ce_id, "reject", "admin", json={"reason": "<img src=x onerror=alert(1)>"})
    for email in mailer.sent:
        assert "\n" not in email.subject and "\r" not in email.subject
        assert "<script>" not in email.html and "<img" not in email.html
    assert any("&lt;script&gt;" in e.html for e in mailer.sent)


def test_every_email_is_addressed_to_exactly_one_person(api, env, team, mailer):
    ce_id = create_filled(api, env, "PS-MAIL-20")["ce"]["id"]
    post(api, env, ce_id, "submit", "owner")
    assert (
        len(mailer.sent) == 2 and len({e.to_email for e in mailer.sent}) == 2
    )  # nessuno vede gli altri
