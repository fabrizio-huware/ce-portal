"""PDF: contenuto estratto dal file vero; il riepilogo non deve contenere costi né margini."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.exports.pdf_export import ce_full_pdf, ce_summary_pdf, pdf_text
from app.exports.reduced import reduced_from_detail
from app.schemas.ce import CEDetail
from tests.ce_helpers import create, real_ce_content, save, simple_content

URL = "/api/v1/ce"
NOW = datetime(2026, 10, 6, 12, 30, tzinfo=UTC)


def text_of(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def detail_of(api, env, ce_id) -> CEDetail:
    return CEDetail.model_validate(api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json())


@pytest.fixture
def real(api, env):
    created = create(api, env, code="PS-PDF-REAL", client_id=str(env.client.id))
    save(api, env, created["ce"]["id"], real_ce_content(env, 1))
    return detail_of(api, env, created["ce"]["id"])


def test_full_pdf_is_a_landscape_document_with_the_whole_ce(real):
    pdf = ce_full_pdf(real, NOW)
    reader = PdfReader(BytesIO(pdf))
    first = reader.pages[0]
    assert float(first.mediabox.width) > float(first.mediabox.height)  # A4 orizzontale
    text = text_of(pdf)
    for expected in (
        "PS-PDF-REAL", "Cliente di prova", "Progetto di prova", "20/01/2026 - 20/04/2026", "Bozza",
        "47.162,50 €", "20.200,00 €", "26.962,50 €", "57,17%", "42,83%", "58,50", "10,00", "48,50", "806,20 €",
        "Servizi interni", "Servizi esterni", "Contingency", "Specialist", "Sprint", "Totale PM", "Staffing mensile",
        "01/2026", "04/2026",
    ):  # fmt: skip
        assert expected in text, expected


def test_full_pdf_has_page_numbers_metadata_and_confidentiality_footer(real):
    pdf = ce_full_pdf(real, NOW)
    reader = PdfReader(BytesIO(pdf))
    pages = len(reader.pages)
    assert pages >= 2  # 40+ righe: più pagine
    assert f"Pagina 1 di {pages}" in reader.pages[0].extract_text()
    assert f"Pagina {pages} di {pages}" in reader.pages[-1].extract_text()
    assert "Riservato - uso interno" in reader.pages[0].extract_text()
    assert "06/10/2026 14:30" in reader.pages[0].extract_text()  # 12:30 UTC = ora legale italiana
    meta = reader.metadata
    assert meta.author == "Portale Conti Economici" and meta.title == "CE PS-PDF-REAL v1"


def test_summary_pdf_is_portrait_and_shows_only_days_and_revenue_per_phase(real):
    pdf = ce_summary_pdf(reduced_from_detail(real), "draft", NOW)
    reader = PdfReader(BytesIO(pdf))
    page = reader.pages[0]
    assert float(page.mediabox.height) > float(page.mediabox.width)  # A4 verticale
    text = text_of(pdf)
    for expected in ("Riepilogo PS-PDF-REAL", "Project management", "10,00", "Delivery", "48,50", "58,50",
                     "Ricavi per fase", "10.375,00", "20.200,00", "47.162,50", "Totale generale", "Versione non approvata"):  # fmt: skip
        assert expected in text, expected


def test_summary_pdf_contains_no_costs_margins_rates_or_activity_details(real):
    text = text_of(ce_summary_pdf(reduced_from_detail(real), "approved", NOW))
    assert "Versione non approvata" not in text  # per un CE approvato non compare
    for forbidden in (
        "Costi", "Costo", "Margine", "margine", "C/R", "Tariff", "Prezzo", "Sprint", "Presales", "Specialist",
        "Senior", "Manager", "Practice", "26.962", "10.220", "4.620", "57,17", "806,2", "Collaboratore",
    ):  # fmt: skip
        assert forbidden not in text, forbidden


def test_unapproved_summary_says_so_and_approved_one_does_not(real):
    ce = reduced_from_detail(real)
    assert "Bozza" in text_of(ce_summary_pdf(ce, "draft", NOW))
    approved = text_of(ce_summary_pdf(ce, "approved", NOW))
    assert "Approvato" in approved and "Bozza" not in approved


def test_hostile_and_exotic_text_is_rendered_literally_and_never_breaks_the_pdf(api, env):
    created = create(api, env, code="PS-PDF-HOSTILE")
    content = simple_content(
        env, 1, project_name="<b>Grassetto</b> & <font size=40>enorme</font> łódź 😀"
    )
    content["phases"][0]["lines"][0]["activity"] = "<img src=x/> <a href='http://evil'>clic</a>"
    save(api, env, created["ce"]["id"], content)
    detail = detail_of(api, env, created["ce"]["id"])
    for pdf in (
        ce_full_pdf(detail, NOW),
        ce_summary_pdf(reduced_from_detail(detail), "draft", NOW),
    ):
        text = text_of(pdf)
        assert (
            "<b>Grassetto</b>" in text and "<font size=40>enorme</font>" in text
        )  # il markup non viene interpretato
        assert "&" in text
    assert "<img src=x/>" in text_of(ce_full_pdf(detail, NOW))


def test_pdf_text_helper_neutralises_markup_and_unsupported_characters():
    assert pdf_text("<b>x</b> & y") == "&lt;b&gt;x&lt;/b&gt; &amp; y"
    assert pdf_text("a\n\tb") == "a b"
    assert pdf_text("€ è à – Sì") == "€ è à – Sì"  # supportati dai font standard
    assert pdf_text("ł😀") == "??"  # non supportati: segnalati, non rotti


def test_logo_is_used_when_available_and_the_title_falls_back_otherwise(real, tmp_path):
    from PIL import Image

    logo = tmp_path / "logo.png"
    Image.new("RGB", (240, 80), (29, 78, 216)).save(logo)
    with_logo = PdfReader(BytesIO(ce_full_pdf(real, NOW, logo_path=logo)))
    assert len(with_logo.pages[0].images) == 1
    without = PdfReader(BytesIO(ce_full_pdf(real, NOW, logo_path=tmp_path / "non-esiste.png")))
    assert len(without.pages[0].images) == 0
    assert "Portale Conti Economici" in without.pages[0].extract_text()
    summary = PdfReader(
        BytesIO(ce_summary_pdf(reduced_from_detail(real), "approved", NOW, logo_path=logo))
    )
    assert len(summary.pages[0].images) == 1


def test_contingency_is_shown_per_phase(api, env):
    created = create(api, env, code="PS-PDF-CONT")
    content = simple_content(env, 1, hours="40")
    content["phases"][0]["contingency_pct"] = "10"
    save(api, env, created["ce"]["id"], content)
    text = text_of(ce_full_pdf(detail_of(api, env, created["ce"]["id"]), NOW))
    assert (
        "contingency 10,00%" in text
        and "Ricavo da contingency 10,00% (senza costi)" in text
        and "425,00" in text
    )


def test_pdf_of_an_empty_ce_does_not_fail(api, env):
    created = create(api, env, code="PS-PDF-EMPTY")
    detail = detail_of(api, env, created["ce"]["id"])
    text = text_of(ce_full_pdf(detail, NOW))
    assert (
        "PS-PDF-EMPTY" in text and "n/d" in text
    )  # margini e fee non calcolabili: n/d, nessun errore
    assert "PS-PDF-EMPTY" in text_of(ce_summary_pdf(reduced_from_detail(detail), "draft", NOW))
