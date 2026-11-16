"""Sconti negli export: Excel con formule vive, CSV, PDF, vista ridotta e divisione per business unit."""

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from app.exports.pdf_export import ce_full_pdf
from app.exports.xlsx_export import ce_full_xlsx
from app.schemas.ce import CEDetail
from app.services.unit_division import DISCOUNTS, business_unit_division, business_unit_revenue
from tests.ce_helpers import approved_ce, create, save, simple_content
from tests.test_extra_costs_exports import export
from tests.xlsx_helpers import formula_errors, needs_libreoffice, recalculated

URL = "/api/v1/ce"
NOW = datetime(2026, 10, 6, 12, 30, tzinfo=UTC)
SECRET = "RISERVATO-SCONTO"
EXTRAS_IN = [{"description": "Licenze", "cost": "1000.00", "markup_pct": "20.00"}]
DISCOUNTS_IN = [
    {"description": f"Sconto {SECRET}", "kind": "amount", "value": "200.00"},
    {"description": "Sconto volume", "kind": "percent", "value": "10.00"},
]  # prima degli sconti 1.700 + 1.200 = 2.900; sconti 200 + 290 = 490; prezzo 2.410; costi 1.660


def content(env, revision, with_extras=True):
    body = simple_content(env, revision)  # 16 ore di Senior: ricavi 1.700, costi 660
    body["discounts"] = DISCOUNTS_IN
    if with_extras:
        body["extra_costs"] = EXTRAS_IN
    return body


def text_of(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def detail_of(api, env, ce_id) -> CEDetail:
    return CEDetail.model_validate(api.get(f"{URL}/{ce_id}", headers=env.h(env.admin)).json())


@pytest.fixture
def ce_id(api, env):
    created = create(api, env, code="PS-DISC-EXP")
    resp = save(api, env, created["ce"]["id"], content(env, 1))
    assert resp.status_code == 200, resp.text
    return created["ce"]["id"]


# ------------------------------------------------------------------ Excel
@needs_libreoffice
def test_the_excel_formulas_recalculate_to_the_engine_numbers(api, env, ce_id):
    wb = recalculated(ce_full_xlsx(detail_of(api, env, ce_id), NOW))
    assert formula_errors(wb) == []
    sc = wb["Sconti"]
    assert sc["D2"].value == pytest.approx(200.00) and sc["D3"].value == pytest.approx(290.00)
    assert sc["D4"].value == pytest.approx(490.00)
    s = wb["Riepilogo"]
    assert s["A22"].value == "Costi vari" and s["B22"].value == pytest.approx(1200.00)
    assert s["A23"].value == "Sconti" and s["B23"].value == pytest.approx(-490.00)
    assert s["C23"].value == 0
    assert s["B24"].value == pytest.approx(2410.00) and s["C24"].value == pytest.approx(1660.00)


@needs_libreoffice
def test_the_excel_without_extras_puts_the_discounts_right_after_the_contingency(api, env):
    created = create(api, env, code="PS-DISC-NOEX")
    assert (
        save(api, env, created["ce"]["id"], content(env, 1, with_extras=False)).status_code == 200
    )
    wb = recalculated(ce_full_xlsx(detail_of(api, env, created["ce"]["id"]), NOW))
    assert formula_errors(wb) == []
    s = wb["Riepilogo"]
    assert s["A22"].value == "Sconti" and s["B22"].value == pytest.approx(
        -370.00
    )  # 200 + 10% di 1.700
    assert s["B23"].value == pytest.approx(1330.00) and s["C23"].value == pytest.approx(660.00)


@needs_libreoffice
def test_changing_a_discount_in_excel_changes_the_totals(api, env, ce_id):
    def edit(wb):
        wb["Sconti"]["C2"] = 500

    wb = recalculated(ce_full_xlsx(detail_of(api, env, ce_id), NOW), edit)
    assert wb["Sconti"]["D2"].value == pytest.approx(500.00)
    assert wb["Riepilogo"]["B24"].value == pytest.approx(2110.00)


def test_a_ce_without_discounts_has_no_discount_sheet(api, env):
    created = create(api, env, code="PS-DISC-NONE")
    save(api, env, created["ce"]["id"], simple_content(env, 1))
    wb = load_workbook(BytesIO(ce_full_xlsx(detail_of(api, env, created["ce"]["id"]), NOW)))
    assert "Sconti" not in wb.sheetnames


# ------------------------------------------------------------------ CSV
def test_the_csv_has_one_negative_row_per_discount_with_no_cost(api, env, ce_id):
    raw = export(api, env, ce_id, "csv").decode("utf-8-sig")
    rows = [ln for ln in raw.strip().splitlines() if ";Sconti;" in ln or ",Sconti," in ln]
    assert len(rows) == 2
    assert "-200,00" in rows[0] and "-290,00" in rows[1]


# ------------------------------------------------------------------ PDF completo
def test_the_full_pdf_shows_the_discounts(api, env, ce_id):
    text = text_of(ce_full_pdf(detail_of(api, env, ce_id), NOW))
    for expected in (
        "Sconto " + SECRET,
        "Sconto volume",
        "Totale sconti",
        "Percentuale",
        "2.410,00",
    ):
        assert expected in text


# ------------------------------------------------------------------ vista ridotta
def test_the_reduced_views_show_one_sconti_row_and_never_the_details(api, env):
    approved = approved_ce(api, env, "PS-DISC-APP", content=content(env, 1))
    new_id = approved["ce"]["id"]
    for fmt in ("csv", "pdf", "xlsx"):
        viewer = api.get(f"{URL}/summaries/{new_id}/export?format={fmt}", headers=env.h(env.viewer))
        assert viewer.status_code == 200
        raw = viewer.content
        if fmt == "csv":
            blob = raw.decode("utf-8-sig")
        elif fmt == "pdf":
            blob = text_of(raw)
        else:
            wb = load_workbook(BytesIO(raw))
            blob = " ".join(str(c.value) for ws in wb for r in ws.iter_rows() for c in r if c.value)
        assert "Sconti" in blob and any(v in blob for v in ("-490,00", "-490.00", "-490"))
        for secret in (SECRET, "volume", "-200,00", "290,00", "Percentuale", "1.660,00", "1660,00"):
            assert secret not in blob, (fmt, secret)


def test_the_editor_summary_has_the_discounts_without_the_details(api, env, ce_id):
    for fmt in ("pdf", "csv"):
        raw = export(api, env, ce_id, fmt, variant="summary")
        blob = text_of(raw) if fmt == "pdf" else raw.decode("utf-8-sig")
        assert "Sconti" in blob and SECRET not in blob and "volume" not in blob


def test_the_viewer_json_has_the_discounts_as_one_negative_phase(api, env):
    approved = approved_ce(api, env, "PS-DISC-VJ", content=content(env, 1))
    resp = api.get(f"{URL}/summaries/{approved['ce']['id']}", headers=env.h(env.viewer))
    phases = {p["name"]: p["revenue"] for p in resp.json()["phases"]}
    assert Decimal(phases["Sconti"]) == Decimal("-490.00")
    assert SECRET not in resp.text and "percent" not in resp.text


# ------------------------------------------------------------------ divisione
def test_the_division_has_a_discounts_row_and_adds_up_to_the_totals(api, env, session, ce_id):
    detail = detail_of(api, env, ce_id)
    rows = business_unit_division(session, detail)
    assert rows[-1].label == DISCOUNTS and rows[-1].kind == "discounts"
    assert rows[-1].revenue == Decimal("-490.00") and rows[-1].cost == Decimal("0")
    total = detail.calculation.total
    assert sum(r.revenue for r in rows) == total.revenue
    assert sum(r.cost for r in rows) == total.cost


def test_the_revenue_by_unit_has_the_discounts_last_and_adds_up(api, env, session, ce_id):
    detail = detail_of(api, env, ce_id)
    rows = business_unit_revenue(session, detail)
    assert rows[-1].label == DISCOUNTS and rows[-1].revenue == Decimal("-490.00")
    assert sum(r.revenue for r in rows) == detail.calculation.total.revenue
    assert sum(r.share for r in rows) == pytest.approx(1)
