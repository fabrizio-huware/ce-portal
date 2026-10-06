import re

import pytest

from app.notifications.templates import TYPES, fmt_date, money, oneline, render

BASE = "https://portale.example.it"

CE_PAYLOAD = {
    "recipient_name": "Fabrizio Clerici",
    "actor_name": "Anna Rossi",
    "ce_id": "11111111-2222-3333-4444-555555555555",
    "code": "PS-BONGA-AI-PJT",
    "version": 2,
    "client_name": "Bonga Spa",
    "project_name": "Bonga - AI",
    "start_date": "2026-01-20",
    "end_date": "2026-04-20",
    "price": "47162.50",
}


def test_money_and_date_use_italian_format():
    assert money("47162.50") == "47.162,50 €"
    assert (
        money("0.00") == "0,00 €"
        and money("1234567.89") == "1.234.567,89 €"
        and money(None) is None
    )
    assert fmt_date("2026-01-05") == "05/01/2026"


def test_submitted_email_has_everything_the_approver_needs():
    mail = render("ce_submitted", CE_PAYLOAD, BASE)
    assert mail.subject == "[CE] Da approvare: PS-BONGA-AI-PJT (v2) – Bonga Spa"
    for expected in (
        "Ciao Fabrizio Clerici,",
        "Anna Rossi ha inviato in approvazione il CE PS-BONGA-AI-PJT (versione 2).",
        "Cliente: Bonga Spa",
        "Progetto: Bonga - AI",
        "Periodo: 20/01/2026 – 20/04/2026",
        "Prezzo: 47.162,50 €",
        f"Apri il CE: {BASE}/ce/{CE_PAYLOAD['ce_id']}",
    ):
        assert expected in mail.text, expected
    assert f'href="{BASE}/ce/{CE_PAYLOAD["ce_id"]}"' in mail.html and "47.162,50 €" in mail.html


def test_approved_rejected_and_new_version_texts():
    approved = render("ce_approved", CE_PAYLOAD, BASE)
    assert approved.subject == "[CE] Approvato: PS-BONGA-AI-PJT (v2)"
    assert (
        "è stato approvato da Anna Rossi" in approved.text and "visibile ai viewer" in approved.text
    )

    rejected = render("ce_rejected", {**CE_PAYLOAD, "reason": "Servono più ore di test"}, BASE)
    assert rejected.subject == "[CE] Rifiutato: PS-BONGA-AI-PJT (v2)"
    assert (
        "Motivo: Servono più ore di test" in rejected.text and "inviarlo di nuovo" in rejected.text
    )

    new = render("ce_new_version", CE_PAYLOAD, BASE)
    assert new.subject == "[CE] Nuova versione: PS-BONGA-AI-PJT (v2)"
    assert (
        "versione 2" in new.text and "versione 1 approvata" in new.text and "in bozza" in new.text
    )


def test_user_enabled_and_test_emails():
    enabled = render(
        "user_enabled",
        {"recipient_name": "Mario Rossi", "actor_name": "Fabrizio", "role": "presale"},
        BASE,
    )
    assert enabled.subject == "Accesso al portale Conti Economici"
    assert "ruolo Presale" in enabled.text and f"Apri il portale: {BASE}" in enabled.text
    assert (
        "ruolo Amministratore"
        in render("user_enabled", {"recipient_name": "A", "role": "admin"}, BASE).text
    )
    assert (
        "ruolo Viewer"
        in render("user_enabled", {"recipient_name": "A", "role": "viewer"}, BASE).text
    )
    test = render("test", {"recipient_name": "Fabrizio"}, BASE)
    assert "funziona" in test.text and test.subject.startswith("Email di prova")


def test_price_is_omitted_when_unknown():
    mail = render("ce_submitted", {**CE_PAYLOAD, "price": None}, BASE)
    assert "Prezzo" not in mail.text and "Cliente: Bonga Spa" in mail.text


def test_emails_never_carry_costs_or_margins():
    for type_ in ("ce_submitted", "ce_approved", "ce_new_version", "ce_rejected"):
        mail = render(type_, {**CE_PAYLOAD, "reason": "ok"}, BASE)
        visible_html = re.sub(r"<[^>]*>", " ", mail.html)  # solo il testo che legge una persona
        for word in ("margin", "Margin", "costo", "Costo", "costi", "Costi", "C/R"):
            assert word not in mail.text and word not in visible_html, (type_, word)


def test_user_text_cannot_inject_html():
    hostile = {
        **CE_PAYLOAD,
        "project_name": "<script>alert(1)</script>",
        "client_name": '"><img src=x onerror=alert(1)>',
        "actor_name": "<b>Eve</b>",
        "recipient_name": "<i>Mario</i>",
        "reason": "<a href='http://evil'>clicca</a>",
    }
    mail = render("ce_rejected", hostile, BASE)
    for raw in ("<script>", "<img", "<b>Eve", "<i>Mario", "<a href='http://evil'"):
        assert raw not in mail.html, raw
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in mail.html
    assert mail.html.count("<a ") == 1  # l'unico link è il nostro pulsante


def test_newlines_cannot_inject_email_headers_into_the_subject():
    mail = render(
        "ce_submitted",
        {**CE_PAYLOAD, "client_name": "Cliente\r\nBcc: spia@evil.com", "code": "A\nB"},
        BASE,
    )
    assert "\n" not in mail.subject and "\r" not in mail.subject
    assert mail.subject == "[CE] Da approvare: A B (v2) – Cliente Bcc: spia@evil.com"
    assert oneline("a \n\t b") == "a b"


def test_unknown_type_is_rejected():
    with pytest.raises(ValueError):
        render("sconosciuto", {}, BASE)
    assert set(TYPES) >= {
        "ce_submitted",
        "ce_approved",
        "ce_rejected",
        "ce_new_version",
        "user_enabled",
    }


def test_html_is_a_complete_responsive_document():
    html = render("ce_submitted", CE_PAYLOAD, BASE).html
    assert html.startswith("<!doctype html>") and 'lang="it"' in html and "max-width:560px" in html
    assert "messaggio automatico" in html
