"""API di export: formati, intestazioni, permessi, storico, versioni, filtri, limiti."""

import csv
import io
import zipfile
from io import BytesIO

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import select

from app.models import AuditLog
from tests.ce_helpers import (
    approved_ce,
    create_filled,
    real_ce_content,
    save,
    simple_content,
)
from tests.dash_helpers import build_ce, world

URL = "/api/v1/ce"
MAGIC = {"xlsx": b"PK", "pdf": b"%PDF", "csv": b"\xef\xbb\xbf"}
MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}


def get(api, env, path, user=None, **params):
    return api.get(f"{URL}{path}", headers=env.h(user or env.presale), params=params)


def csv_rows(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig")), delimiter=";"))


def pdf_text(resp) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(resp.content)).pages)


@pytest.fixture
def real(api, env):
    return approved_ce(api, env, "PS-EXP-REAL", content=real_ce_content(env, 1))


# ------------------------------------------------------------------ singolo CE
@pytest.mark.parametrize("fmt", ["xlsx", "csv", "pdf"])
def test_full_export_headers_and_content_type(api, env, real, fmt):
    resp = get(api, env, f"/{real['ce']['id']}/export", format=fmt)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == MIME[fmt]
    assert resp.headers["content-disposition"] == f'attachment; filename="PS-EXP-REAL_v1.{fmt}"'
    assert (
        resp.headers["cache-control"] == "no-store"
        and resp.headers["x-content-type-options"] == "nosniff"
    )
    assert resp.content.startswith(MAGIC[fmt]) and len(resp.content) > 500


def test_default_format_is_excel_and_invalid_options_are_rejected(api, env, real):
    ce_id = real["ce"]["id"]
    resp = get(api, env, f"/{ce_id}/export")
    assert resp.headers["content-type"] == MIME["xlsx"]
    assert get(api, env, f"/{ce_id}/export", format="docx").status_code == 422
    assert get(api, env, f"/{ce_id}/export", variant="segreto").status_code == 422
    assert get(api, env, f"/{ce_id}/export", version=0).status_code == 422


def test_full_excel_export_has_the_real_totals(api, env, real):
    wb = load_workbook(BytesIO(get(api, env, f"/{real['ce']['id']}/export", format="xlsx").content))
    assert (
        wb["Riepilogo"]["B5"].value == "PS-EXP-REAL"
        and wb["Riepilogo"]["B22"].value == "=SUM(B19:B21)"
    )
    assert wb["Tariffe"]["B6"].value == 850  # Senior


def test_full_csv_and_pdf_export_have_the_real_numbers(api, env, real):
    rows = csv_rows(get(api, env, f"/{real['ce']['id']}/export", format="csv"))
    col = {n: i for i, n in enumerate(rows[0])}
    assert round(sum(float(r[col["Ricavo"]].replace(",", ".")) for r in rows[1:]), 1) == 47162.5
    text = pdf_text(get(api, env, f"/{real['ce']['id']}/export", format="pdf"))
    assert "47.162,50 €" in text and "Approvato" in text and "PS-EXP-REAL" in text


@pytest.mark.parametrize("fmt", ["xlsx", "csv", "pdf"])
def test_summary_variant_is_the_reduced_view(api, env, real, fmt):
    resp = get(api, env, f"/{real['ce']['id']}/export", format=fmt, variant="summary")
    assert resp.status_code == 200 and resp.headers["content-disposition"].endswith(
        f'_v1_riepilogo.{fmt}"'
    )
    if fmt == "pdf":
        text = pdf_text(resp)
        assert (
            "58,50" in text and "47.162,50" in text and "Costi" not in text and "Sprint" not in text
        )
    elif fmt == "csv":
        text = resp.content.decode("utf-8-sig")
        assert "Giornate management" in text and "Costo" not in text and "Sprint" not in text
    else:
        assert load_workbook(BytesIO(resp.content)).sheetnames == ["Riepilogo"]


def test_a_specific_version_can_be_exported(api, env):
    approved = approved_ce(api, env, "PS-EXP-VER")  # v1: 1.700
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=env.h(env.presale))
    save(api, env, ce_id, simple_content(env, 1, hours="80"))  # v2 in bozza: 8.500
    v1 = get(api, env, f"/{ce_id}/export", format="pdf", version=1)
    v2 = get(api, env, f"/{ce_id}/export", format="pdf")  # senza numero: l'ultima
    assert (
        "1.700,00 €" in pdf_text(v1)
        and "Approvato" in pdf_text(v1)
        and v1.headers["content-disposition"].endswith('v1.pdf"')
    )
    assert (
        "8.500,00 €" in pdf_text(v2)
        and "Bozza" in pdf_text(v2)
        and v2.headers["content-disposition"].endswith('v2.pdf"')
    )
    assert get(api, env, f"/{ce_id}/export", version=9).status_code == 404


def test_exporting_does_not_change_the_ce(api, env, real):
    ce_id = real["ce"]["id"]
    before = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    for fmt in ("xlsx", "csv", "pdf"):
        get(api, env, f"/{ce_id}/export", format=fmt)
    assert api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json() == before


def test_unknown_and_deleted_ces_cannot_be_exported(api, env, real):
    assert get(api, env, "/00000000-0000-0000-0000-000000000000/export").status_code == 404
    api.delete(f"{URL}/{real['ce']['id']}", headers=env.h(env.admin))
    assert get(api, env, f"/{real['ce']['id']}/export").status_code == 404


def test_every_export_is_recorded_in_the_history(api, env, real, session):
    ce_id = real["ce"]["id"]
    get(api, env, f"/{ce_id}/export", format="pdf")
    get(api, env, f"/{ce_id}/export", format="xlsx", variant="summary", user=env.admin)
    api.get(f"{URL}/summaries/{ce_id}/export", headers=env.h(env.viewer), params={"format": "csv"})
    entries = session.scalars(
        select(AuditLog).where(AuditLog.action == "export").order_by(AuditLog.id)
    ).all()
    assert [(e.user_id, e.changes["format"], e.changes["variant"], e.changes["version"]) for e in entries] == [
        (env.presale.id, "pdf", "full", 1), (env.admin.id, "xlsx", "summary", 1), (env.viewer.id, "csv", "summary", 1),
    ]  # fmt: skip
    history = api.get(f"{URL}/{ce_id}/history", headers=env.h(env.presale)).json()
    assert [h["action"] for h in history].count("export") == 3


# ------------------------------------------------------------------ vista del viewer
@pytest.mark.parametrize("fmt", ["pdf", "xlsx", "csv"])
def test_viewer_can_export_the_summary_of_an_approved_ce(api, env, real, fmt):
    resp = api.get(
        f"{URL}/summaries/{real['ce']['id']}/export",
        headers=env.h(env.viewer),
        params={"format": fmt},
    )
    assert resp.status_code == 200 and resp.headers["content-type"] == MIME[fmt]
    assert (
        resp.headers["content-disposition"]
        == f'attachment; filename="PS-EXP-REAL_v1_riepilogo.{fmt}"'
    )
    assert resp.headers["cache-control"] == "no-store"


def test_viewer_default_format_is_pdf(api, env, real):
    resp = api.get(f"{URL}/summaries/{real['ce']['id']}/export", headers=env.h(env.viewer))
    assert resp.headers["content-type"] == MIME["pdf"]


def test_viewer_cannot_export_unapproved_or_deleted_ces_or_the_full_version(api, env, real):
    draft = create_filled(api, env, "PS-EXP-DRAFT")
    assert (
        api.get(
            f"{URL}/summaries/{draft['ce']['id']}/export", headers=env.h(env.viewer)
        ).status_code
        == 404
    )
    assert api.get(f"{URL}/{real['ce']['id']}/export", headers=env.h(env.viewer)).status_code == 403
    assert api.get(f"{URL}/export", headers=env.h(env.viewer)).status_code == 403
    api.delete(f"{URL}/{real['ce']['id']}", headers=env.h(env.admin))
    assert (
        api.get(f"{URL}/summaries/{real['ce']['id']}/export", headers=env.h(env.viewer)).status_code
        == 404
    )


def test_viewer_export_shows_the_approved_version_while_a_new_one_is_in_progress(api, env):
    approved = approved_ce(api, env, "PS-EXP-V2")
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=env.h(env.presale))
    save(api, env, ce_id, simple_content(env, 1, hours="80"))
    resp = api.get(
        f"{URL}/summaries/{ce_id}/export", headers=env.h(env.viewer), params={"format": "pdf"}
    )
    assert "1.700,00" in pdf_text(resp) and "8.500,00" not in pdf_text(resp)


# ------------------------------------------------------------------ elenchi
@pytest.fixture
def listed(api, env, session):
    return world(api, env, session)


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_list_export_matches_the_search(api, env, listed, fmt):
    resp = get(api, env, "/export", format=fmt)
    assert resp.status_code == 200 and resp.headers["content-type"] == MIME[fmt]
    assert resp.headers["content-disposition"].startswith('attachment; filename="elenco_ce_')
    if fmt == "csv":
        rows = csv_rows(resp)
        assert rows[0][:3] == ["Codice", "Cliente", "Progetto"] and len(rows) == 1 + 5
    else:
        ws = load_workbook(BytesIO(resp.content))["Elenco CE"]
        assert ws.max_row == 6 and ws["A1"].value == "Codice"


def test_list_export_respects_the_same_filters(api, env, listed):
    rows = csv_rows(get(api, env, "/export", format="csv", status="approved"))
    # D ha una v2 in bozza: nell'elenco compare l'ultima versione, quindi non è "approvato"
    assert sorted(r[0] for r in rows[1:]) == ["PS-DASH-A", "PS-DASH-B"]
    rows = csv_rows(get(api, env, "/export", format="csv", code="dash-c"))
    assert [r[0] for r in rows[1:]] == ["PS-DASH-C"]
    rows = csv_rows(
        get(
            api,
            env,
            "/export",
            format="csv",
            client_id=str(listed["alfa"].id),
            date_from="2026-04-01",
        )
    )
    assert sorted(r[0] for r in rows[1:]) == ["PS-DASH-A"]  # C finisce a marzo
    assert csv_rows(get(api, env, "/export", format="csv", project="inesistente")) == [
        csv_rows(get(api, env, "/export", format="csv"))[0]
    ]


def test_list_export_columns_for_editors(api, env, listed):
    rows = csv_rows(get(api, env, "/export", format="csv", code="dash-a"))
    col = {n: i for i, n in enumerate(rows[0])}
    r = rows[1]
    assert (
        r[col["Stato"]] == "Approvato"
        and r[col["Modalità"]] == "Ore"
        and r[col["Prezzo"]] == "23000,00"
    )
    assert (
        r[col["Margine (%)"]] == "61,30"
        and r[col["Giornate"]] == "30,00"
        and r[col["Inizio"]] == "20/01/2026"
    )


def test_list_export_pdf_is_not_available_and_deleted_ces_are_admin_only(api, env, listed):
    assert get(api, env, "/export", format="pdf").status_code == 422
    assert get(api, env, "/export", include_deleted="true").status_code == 403
    api.delete(f"{URL}/{listed['ids']['A']}", headers=env.h(env.admin))
    assert len(csv_rows(get(api, env, "/export", format="csv"))) == 1 + 4
    assert (
        len(
            csv_rows(get(api, env, "/export", format="csv", include_deleted="true", user=env.admin))
        )
        == 1 + 5
    )


def test_list_export_has_a_row_limit(api, env, listed, monkeypatch):
    import app.api.v1.exports as exports

    monkeypatch.setattr(exports, "MAX_EXPORT_ROWS", 3)
    resp = get(api, env, "/export", format="csv")
    assert resp.status_code == 422 and "restringi i filtri" in resp.json()["detail"]
    assert (
        get(api, env, "/export", format="csv", status="approved").status_code == 200
    )  # 3 risultati: entro il limite


def test_viewer_list_export_has_only_approved_ces_and_the_reduced_columns(api, env, listed):
    resp = api.get(f"{URL}/summaries/export", headers=env.h(env.viewer), params={"format": "csv"})
    rows = csv_rows(resp)
    assert rows[0] == [
        "Codice",
        "Cliente",
        "Progetto",
        "Inizio",
        "Fine",
        "Versione",
        "Approvato il",
        "Prezzo",
    ]
    assert sorted(r[0] for r in rows[1:]) == ["PS-DASH-A", "PS-DASH-B", "PS-DASH-D"]
    prices = {r[0]: r[7] for r in rows[1:]}
    assert prices["PS-DASH-A"] == "23000,00" and prices["PS-DASH-D"] == "3625,00"
    wb = load_workbook(
        BytesIO(api.get(f"{URL}/summaries/export", headers=env.h(env.viewer)).content)
    )
    assert wb.sheetnames == ["Elenco CE approvati"] and wb.active["H1"].value == "Prezzo (€)"
    assert (
        api.get(
            f"{URL}/summaries/export", headers=env.h(env.viewer), params={"format": "pdf"}
        ).status_code
        == 422
    )


def test_list_exports_are_audited_with_their_filters(api, env, listed, session):
    get(api, env, "/export", format="csv", status="approved", code="dash")
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "export_list")).one()
    assert (
        entry.user_id == env.presale.id
        and entry.changes["rows"] == 2
        and entry.changes["filters"]["status"] == "approved"
    )


def test_route_order_export_is_not_taken_for_an_identifier(api, env, listed):
    assert get(api, env, "/export", format="csv").status_code == 200  # non 422 "uuid non valido"
    assert (
        api.get(
            f"{URL}/summaries/export", headers=env.h(env.viewer), params={"format": "csv"}
        ).status_code
        == 200
    )


# ------------------------------------------------------------------ dashboard
def test_portfolio_export_formats(api, env, session):
    world(api, env, session)
    base = "/api/v1/dashboard/portfolio/export"
    xlsx = api.get(base, headers=env.h(env.presale))
    wb = load_workbook(BytesIO(xlsx.content))
    assert wb.sheetnames == [
        "Riepilogo",
        "Per cliente",
        "Per business unit",
        "Per stato",
        "Per mese",
        "Elenco CE",
    ]
    assert wb["Riepilogo"]["C5"].value == pytest.approx(30875) and wb["Riepilogo"][
        "C6"
    ].value == pytest.approx(8100)
    assert xlsx.headers["content-disposition"].startswith('attachment; filename="portfolio_ce_')
    rows = csv_rows(api.get(base, headers=env.h(env.presale), params={"format": "csv"}))
    assert len(rows) == 1 + 5 and rows[0][5] == "Ambito"
    assert {r[5] for r in rows[1:]} == {"Approvato", "Pipeline"}
    assert api.get(base, headers=env.h(env.presale), params={"format": "pdf"}).status_code == 422
    assert (
        api.get(
            base,
            headers=env.h(env.presale),
            params={"date_from": "2026-05-01", "date_to": "2026-04-01"},
        ).status_code
        == 422
    )


def test_resources_export_formats_and_overload_highlight(api, env, session):
    from tests.dash_helpers import make_employee

    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api,
        env,
        "PS-EXP-BIG",
        start="2026-09-01",
        end="2026-09-30",
        lines=[("Senior", 400, ada)],
        state="approved",
    )
    base = "/api/v1/dashboard/resources/export"
    q = {"date_from": "2026-09-01", "date_to": "2026-09-30"}
    wb = load_workbook(BytesIO(api.get(base, headers=env.h(env.presale), params=q).content))
    assert wb.sheetnames == ["Collaboratori", "Profili", "Dati"]
    ws = wb["Collaboratori"]
    assert ws["A2"].value == "Ada L" and ws["C2"].value == pytest.approx(
        50 / 22, abs=1e-5
    )  # FTE 227%
    assert ws["C2"].fill.fgColor.rgb.endswith("FDE2E1")  # evidenziato
    rows = csv_rows(api.get(base, headers=env.h(env.presale), params={**q, "format": "csv"}))
    col = {n: i for i, n in enumerate(rows[0])}
    emp = next(r for r in rows[1:] if r[col["Tipo"]] == "Collaboratore")
    assert (
        emp[col["Nome"]],
        emp[col["Mese"]],
        emp[col["Giorni totali"]],
        emp[col["Sovraccarico"]],
    ) == ("Ada L", "09/2026", "50,00", "Sì")
    assert emp[col["FTE (%)"]] == "227,27" and emp[col["Capacità (giorni)"]] == "22"


def test_dashboard_exports_are_audited(api, env, session):
    world(api, env, session)
    api.get("/api/v1/dashboard/portfolio/export", headers=env.h(env.presale))
    api.get(
        "/api/v1/dashboard/resources/export",
        headers=env.h(env.admin),
        params={"date_from": "2026-01-01", "date_to": "2026-03-31"},
    )
    entries = session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "report").order_by(AuditLog.id)
    ).all()
    assert [e.changes["report"] for e in entries] == ["portfolio", "resources"]


def test_zip_of_the_excel_contains_only_expected_parts(api, env, real):
    resp = get(api, env, f"/{real['ce']['id']}/export", format="xlsx")
    names = zipfile.ZipFile(BytesIO(resp.content)).namelist()
    assert not any(
        n.startswith(("xl/externalLinks", "xl/vbaProject", "customXml"))
        or n.endswith("comments1.xml")
        for n in names
    )
