"""Invio per email del report di un CE: allegato, regole sui destinatari, audit, limiti."""

from io import BytesIO

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import select

from app.models import AuditLog, EmailOutbox
from tests.ce_helpers import approved_ce, real_ce_content

URL = "/api/v1/ce"


@pytest.fixture
def real(api, env):
    return approved_ce(api, env, "PS-MAIL-1", content=real_ce_content(env, 1))


def send(api, env, ce, user=None, **body):
    body.setdefault("recipient", "mario.rossi@cliente.it")
    return api.post(
        f"{URL}/{ce['ce']['id']}/export/email", headers=env.h(user or env.presale), json=body
    )


def test_a_summary_goes_to_an_external_address_with_the_file_attached(api, env, real, mailer):
    resp = send(api, env, real, message="In allegato il riepilogo.")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "recipient": "mario.rossi@cliente.it",
        "filename": "PS-MAIL-1_v1_riepilogo.pdf",
        "status": "sent",
        "error": None,
    }
    [mail] = mailer.sent
    assert mail.to_email == "mario.rossi@cliente.it" and "PS-MAIL-1" in mail.subject
    assert "In allegato il riepilogo." in mail.text and mail.text.startswith("Buongiorno,")
    assert mail.attachment.name == "PS-MAIL-1_v1_riepilogo.pdf"
    assert mail.attachment.mime == "application/pdf"
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(mail.attachment.content)).pages)
    assert "47.162,50" in text and "Sprint" not in text  # riepilogo: nessuna riga di costo


def test_the_email_has_no_link_to_the_portal_for_the_outsider(api, env, real, mailer):
    send(api, env, real)
    assert "/ce/" not in mailer.sent[0].text and "/ce/" not in mailer.sent[0].html


def test_summary_excel_is_attached_as_a_workbook(api, env, real, mailer):
    send(api, env, real, format="xlsx")
    [mail] = mailer.sent
    assert mail.attachment.name.endswith("_riepilogo.xlsx")
    assert load_workbook(BytesIO(mail.attachment.content)).sheetnames == ["Riepilogo"]


@pytest.mark.parametrize("fmt", ["pdf", "xlsx"])
def test_a_full_report_is_refused_to_an_external_address(api, env, real, mailer, fmt):
    resp = send(api, env, real, format=fmt, variant="full")
    assert resp.status_code == 403 and "costi e margini" in resp.json()["detail"]
    assert mailer.sent == []


def test_a_full_report_goes_to_a_company_address(api, env, real, mailer):
    resp = send(api, env, real, variant="full", format="xlsx", recipient="Collega@Huware.com")
    assert resp.status_code == 200 and resp.json()["recipient"] == "collega@huware.com"
    [mail] = mailer.sent
    assert mail.attachment.name == "PS-MAIL-1_v1.xlsx"
    assert load_workbook(BytesIO(mail.attachment.content))["Tariffe"]["B6"].value == 850


def test_a_lookalike_domain_is_not_a_company_address(api, env, real, mailer):
    for address in ("x@huware.com.evil.io", "x@evilhuware.com", "x@sub.huware.com"):
        assert send(api, env, real, variant="full", recipient=address).status_code == 403
    assert mailer.sent == []


@pytest.mark.parametrize(
    "address", ["", "senza-chiocciola", "a b@x.it", "a@b", "x@y.it\nBcc: z@w.it"]
)
def test_invalid_addresses_are_rejected(api, env, real, mailer, address):
    assert send(api, env, real, recipient=address).status_code == 422
    assert mailer.sent == []


def test_unknown_fields_formats_and_long_messages_are_rejected(api, env, real, mailer):
    assert send(api, env, real, cc="a@b.it").status_code == 422
    assert send(api, env, real, format="csv").status_code == 422
    assert send(api, env, real, variant="segreto").status_code == 422
    assert send(api, env, real, message="x" * 501).status_code == 422
    assert send(api, env, real, version=0).status_code == 422
    assert mailer.sent == []


def test_a_message_cannot_inject_html_or_headers(api, env, real, mailer):
    send(api, env, real, message="<script>alert(1)</script>\nBcc: z@w.it")
    [mail] = mailer.sent
    assert "<script>" not in mail.html and "&lt;script&gt;" in mail.html
    assert "\n" not in mail.subject


def test_only_editors_can_send(api, env, real, mailer):
    assert send(api, env, real, user=env.viewer).status_code == 403
    assert (
        api.post(f"{URL}/{real['ce']['id']}/export/email", json={"recipient": "a@b.it"}).status_code
        == 401
    )
    assert mailer.sent == []


def test_a_missing_ce_or_version_is_a_404(api, env, real, mailer):
    ghost = {"ce": {"id": "00000000-0000-0000-0000-000000000000"}}
    assert send(api, env, ghost).status_code == 404
    assert send(api, env, real, version=9).status_code == 404
    assert mailer.sent == []


def test_a_chosen_version_is_the_one_attached(api, env, real, mailer):
    api.post(f"{URL}/{real['ce']['id']}/versions", headers=env.h(env.presale))
    send(api, env, real, version=1)
    assert mailer.sent[-1].attachment.name == "PS-MAIL-1_v1_riepilogo.pdf"


def test_every_send_is_in_the_audit_log_without_the_file(api, env, real, session, mailer):
    send(api, env, real, message="riservato")
    row = session.scalars(select(AuditLog).where(AuditLog.action == "export_email")).one()
    assert row.user_id == env.presale.id and str(row.entity_id) == real["ce"]["id"]
    assert row.changes == {
        "recipient": "mario.rossi@cliente.it",
        "format": "pdf",
        "variant": "summary",
        "version": 1,
    }


def test_the_report_does_not_stay_in_the_database_once_sent(api, env, real, session, mailer):
    send(api, env, real)
    row = session.scalars(select(EmailOutbox).where(EmailOutbox.type == "ce_report")).one()
    assert row.status == "sent" and row.attachment is None
    assert row.attachment_name == "PS-MAIL-1_v1_riepilogo.pdf"


def test_a_temporary_failure_keeps_the_file_and_retries(api, env, real, session, mailer):
    from app.notifications.mailer import SendOutcome

    mailer.behavior = lambda emails: (
        [SendOutcome(False, retry=True, error="Mailjet non raggiungibile")] * len(emails)
    )
    resp = send(api, env, real)
    assert resp.status_code == 200 and resp.json()["status"] == "queued"
    assert resp.json()["error"] == "Mailjet non raggiungibile"
    row = session.scalars(select(EmailOutbox).where(EmailOutbox.type == "ce_report")).one()
    assert row.status == "pending" and row.attachment  # il file aspetta il prossimo giro


def test_a_definitive_refusal_is_reported_as_failed(api, env, real, mailer):
    from app.notifications.mailer import SendOutcome

    mailer.behavior = lambda emails: (
        [SendOutcome(False, retry=False, error="indirizzo rifiutato")] * len(emails)
    )
    resp = send(api, env, real)
    assert resp.json()["status"] == "failed" and resp.json()["error"] == "indirizzo rifiutato"


def test_the_notifications_list_does_not_expose_the_file(api, env, real, mailer):
    send(api, env, real)
    resp = api.get("/api/v1/notifications", headers=env.h(env.admin))
    item = next(i for i in resp.json()["items"] if i["type"] == "ce_report")
    assert "attachment" not in item and item["subject"].startswith("[CE] Riepilogo PDF")


def test_twenty_sends_an_hour_are_the_limit(api, env, real, mailer):
    for _ in range(20):
        assert send(api, env, real).status_code == 200
    resp = send(api, env, real)
    assert resp.status_code == 429 and len(mailer.sent) == 20
    other = send(api, env, real, user=env.admin)  # il limite è per utente
    assert other.status_code == 200


def test_two_identical_requests_send_two_emails(api, env, real, mailer):
    send(api, env, real)
    send(api, env, real)
    assert len(mailer.sent) == 2
