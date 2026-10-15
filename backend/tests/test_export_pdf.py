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


# ------------------------------------------------------------------ stile moderno (CL-036)
def base_fonts(reader: PdfReader) -> set[str]:
    names = set()
    for page in reader.pages:
        for ref in page["/Resources"].get("/Font", {}).values():
            names.add(str(ref.get_object().get("/BaseFont")))
    return names


def test_the_brand_font_is_embedded_and_the_fallback_works_without_the_font_files(real, tmp_path):
    from app.exports.pdf_export import FONT_DIR, load_fonts

    assert any("DMSans" in n for n in base_fonts(PdfReader(BytesIO(ce_full_pdf(real, NOW)))))
    assert load_fonts(FONT_DIR).embedded is True
    fallback = load_fonts(tmp_path)  # cartella senza i font: si ripiega sui font standard
    assert (fallback.embedded, fallback.regular, fallback.bold) == (
        False,
        "Helvetica",
        "Helvetica-Bold",
    )
    (tmp_path / "DMSans-Light.ttf").write_bytes(b"non e' un font")
    assert load_fonts(tmp_path).embedded is False  # anche un file rovinato: nessun errore


def test_font_license_is_shipped_with_the_font_files():
    from app.exports.pdf_export import FONT_DIR

    assert "SIL Open Font License" in (FONT_DIR / "OFL.txt").read_text(encoding="utf-8")


def test_first_page_has_cards_donut_bars_and_a_label_that_does_not_wrap(real):
    text = text_of(ce_full_pdf(real, NOW))
    for expected in ("PREZZO PROGETTO", "COSTI", "MARGINE", "COME SI DIVIDE IL PREZZO", "Margine 57,17%", "Costi 42,83%",
                     "57%", "GIORNATE PER PROFILO", " gg", "Opportunità SF"):  # fmt: skip
        assert expected in text, expected


def test_later_pages_have_the_slim_band_and_every_phase_table_has_its_header(real):
    reader = PdfReader(BytesIO(ce_full_pdf(real, NOW)))
    assert len(reader.pages) >= 3
    for page in reader.pages[1:]:
        assert "Conto economico PS-PDF-REAL · Cliente di prova · v1" in page.extract_text()
    assert (
        reader.pages[1].extract_text().count("Attività") >= 2
    )  # più fasi su questa pagina, ciascuna con la sua intestazione


def test_default_logo_pair_gives_one_image_per_page_and_custom_logo_goes_on_a_light_plate(
    real, tmp_path
):
    from reportlab.lib.units import mm

    from app.exports.pdf_export import LOGO_PATH, _band_logo

    reader = PdfReader(BytesIO(ce_full_pdf(real, NOW)))
    assert all(len(page.images) == 1 for page in reader.pages)  # fascia grande poi fascia sottile
    path, _, plate = _band_logo(None, 10 * mm)
    assert path.endswith("logo-white.png") and plate is False  # sulla fascia nera va il logo bianco
    assert _band_logo(tmp_path / "non-esiste.png", 10 * mm) is None
    from PIL import Image

    custom = tmp_path / "mio.png"
    Image.new("RGB", (240, 80), (29, 78, 216)).save(custom)
    assert _band_logo(custom, 10 * mm)[2] is True  # senza versione bianca: piastra chiara
    pair = tmp_path / "logo.png"
    Image.new("RGB", (240, 80), (0, 0, 0)).save(pair)
    Image.new("RGB", (240, 80), (255, 255, 255)).save(tmp_path / "logo-white.png")
    assert _band_logo(pair, 10 * mm)[0].endswith("logo-white.png") and LOGO_PATH.exists()


def test_donut_data_for_missing_zero_negative_and_over_100_percent_margins():
    from decimal import Decimal

    from app.exports.pdf_export import ALERT, TEAL, _donut_for

    missing = _donut_for(None, None)
    assert (missing["share"], missing["center"]) == (None, "n/d")
    negative = _donut_for(Decimal("-0.5"), Decimal("1.5"))
    assert (negative["color"], negative["center"], negative["share"]) == (ALERT, "-50%", 1.0)
    assert "negativo" in negative["legend"][0][1]
    zero = _donut_for(Decimal("0"), Decimal("1"))
    assert (zero["share"], zero["center"], zero["color"]) == (0.0, "0%", TEAL)
    assert (
        _donut_for(Decimal("1.2"), Decimal("-0.2"))["share"] == 1.0
    )  # oltre il 100%: l'anello non esce dal cerchio


def test_fit_text_shortens_with_dots_and_never_exceeds_the_width():
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from app.exports.pdf_export import F, fit_text

    out = fit_text("x" * 200, F.regular, 8, 100)
    assert out.endswith("...") and stringWidth(out, F.regular, 8) <= 100
    assert fit_text("breve", F.regular, 8, 100) == "breve"
    assert fit_text("", F.regular, 8, 100) == ""


def test_very_long_texts_and_huge_numbers_do_not_break_the_pdf(api, env):
    created = create(
        api, env, code="PS-CODICE-MOLTO-LUNGO-PER-VEDERE-COME-SI-COMPORTA-IL-TITOLO-NELLA-FASCIA"
    )
    long_name = "Progetto di migrazione dei dati storici e consolidamento dei sistemi legacy verso la nuova piattaforma"
    save(
        api, env, created["ce"]["id"], simple_content(env, 1, project_name=long_name, hours="9999")
    )
    detail = detail_of(api, env, created["ce"]["id"])
    pdf = ce_full_pdf(detail, NOW)
    text = text_of(pdf)
    assert (
        "PS-CODICE-MOLTO-LUNGO-PER-VEDERE-COME-SI-COMPORTA-IL-TITOLO-NELLA-FASCIA" in text
    )  # per intero nel piè di pagina
    assert (
        "..." in PdfReader(BytesIO(pdf)).pages[0].extract_text()
    )  # nella fascia il titolo si accorcia
    assert "9.999,00" in text and long_name in text.replace("\n", " ")
    assert (
        len(PdfReader(BytesIO(ce_summary_pdf(reduced_from_detail(detail), "approved", NOW))).pages)
        == 1
    )


def test_summary_has_cards_and_bars_but_no_price_cost_or_margin_wording(real):
    text = text_of(ce_summary_pdf(reduced_from_detail(real), "approved", NOW))
    for expected in ("GIORNATE TOTALI", "RICAVI TOTALI", "RICAVI PER FASE", "Totale generale"):
        assert expected in text, expected
    for forbidden in ("PREZZO", "COSTI", "MARGINE", "COME SI DIVIDE", "Margine", "Prezzo", "%"):
        assert forbidden not in text, forbidden
