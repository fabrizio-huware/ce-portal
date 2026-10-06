"""CSV: formato per Excel italiano, contenuto coerente con il motore, protezione dalle formule."""

import csv
import io

import pytest

from app.exports.csv_export import ce_lines_csv, reduced_csv, to_csv
from app.exports.reduced import reduced_from_detail
from app.schemas.ce import CEDetail
from tests.ce_helpers import create, real_ce_content, save, simple_content
from tests.engine_helpers import FIXTURE

URL = "/api/v1/ce"


def parse(data: bytes) -> list[list[str]]:
    assert data.startswith(b"\xef\xbb\xbf")  # BOM: Excel riconosce l'UTF-8
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))


def detail_of(api, env, ce_id) -> CEDetail:
    return CEDetail.model_validate(api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json())


@pytest.fixture
def real(api, env):
    created = create(api, env, code="PS-CSV-REAL")
    save(api, env, created["ce"]["id"], real_ce_content(env, 1))
    return detail_of(api, env, created["ce"]["id"])


def test_csv_format_is_italian_excel(real):
    raw = ce_lines_csv(real)
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw
    text = raw.decode("utf-8-sig")
    assert ";" in text.splitlines()[0] and "," in text.splitlines()[1]  # virgola decimale
    assert "Attività" in text.splitlines()[0]  # accenti conservati


def test_ce_lines_csv_has_one_row_per_line_with_the_engine_numbers(real):
    rows = parse(ce_lines_csv(real))
    header, body = rows[0], rows[1:]
    assert header[:5] == ["Codice", "Versione", "Fase", "Attività", "Profilo"]
    assert (
        len(body)
        == len(real.calculation.lines)
        == sum(len(t["hours"]) for p in FIXTURE["phases"] for t in p["tasks"])
    )
    col = {name: i for i, name in enumerate(header)}
    num = lambda s: float(s.replace(",", "."))  # noqa: E731
    assert sum(num(r[col["Ricavo"]]) for r in body) == pytest.approx(47162.50, abs=0.05)
    assert sum(num(r[col["Costo"]]) for r in body) == pytest.approx(20200.00, abs=0.05)
    assert sum(num(r[col["Ore"]]) for r in body) == pytest.approx(468)
    assert sum(num(r[col["Giorni"]]) for r in body) == pytest.approx(58.5)
    sprint = next(
        r for r in body if r[col["Attività"]] == "Sprint" and r[col["Profilo"]] == "Manager"
    )
    assert (
        sprint[col["Fase"]] == "PM"
        and sprint[col["Project Management"]] == "Sì"
        and sprint[col["Esterno"]] == "No"
    )
    assert sprint[col["Ore"]] == "16,00" and sprint[col["Giorni"]] == "2,0000"
    assert sprint[col["Prezzo/giorno"]] == "1200,00" and sprint[col["Costo/giorno"]] == "800,00"
    assert (
        sprint[col["Ricavo"]] == "2400,00"
        and sprint[col["Costo"]] == "1600,00"
        and sprint[col["Margine"]] == "800,00"
    )


def test_ce_lines_csv_carries_collaborator_and_contingency(api, env, session):
    from app.models import Employee

    emp = Employee(
        first_name="Ada", last_name="Lovelace", default_profile_id=env.profiles["Senior"].id
    )
    session.add(emp)
    session.flush()
    created = create(api, env, code="PS-CSV-EMP")
    content = simple_content(env, 1, hours="40")
    content["phases"][0]["lines"][0]["employee_id"] = str(emp.id)
    content["phases"][0]["contingency_pct"] = "10"
    save(api, env, created["ce"]["id"], content)
    rows = parse(ce_lines_csv(detail_of(api, env, created["ce"]["id"])))
    col = {name: i for i, name in enumerate(rows[0])}
    assert (
        rows[1][col["Collaboratore"]] == "Ada Lovelace"
        and rows[1][col["Contingency fase (%)"]] == "10,00"
    )


def test_formula_injection_in_activity_and_project_names_is_neutralised(api, env):
    created = create(api, env, code="PS-CSV-EVIL")
    content = simple_content(env, 1, project_name="=cmd|' /C calc'!A0")
    content["phases"][0]["lines"][0]["activity"] = '=HYPERLINK("http://evil","clic")'
    content["phases"][0]["name"] = "@SUM(1+1)"
    save(api, env, created["ce"]["id"], content)
    rows = parse(ce_lines_csv(detail_of(api, env, created["ce"]["id"])))
    body = rows[1]
    assert body[3] == '\'=HYPERLINK("http://evil","clic")' and body[2] == "'@SUM(1+1)"
    assert not any(
        cell.startswith(("=", "+", "-", "@"))
        for row in rows
        for cell in row
        if not cell.replace(",", "").replace("-", "").isdigit()
    )


def test_cells_with_separators_quotes_and_newlines_stay_in_their_cell(api, env):
    created = create(api, env, code="PS-CSV-QUOTE")
    content = simple_content(env, 1)
    content["phases"][0]["lines"][0]["activity"] = 'Analisi; "fase 1"\nseconda riga'
    save(api, env, created["ce"]["id"], content)
    rows = parse(ce_lines_csv(detail_of(api, env, created["ce"]["id"])))
    assert len(rows) == 2 and rows[1][3] == 'Analisi; "fase 1"\nseconda riga'
    assert all(len(r) == len(rows[0]) for r in rows)


def test_reduced_csv_contains_only_days_and_revenue(real):
    raw = reduced_csv(reduced_from_detail(real))
    rows = parse(raw)
    assert rows[0] == ["Codice", "Cliente", "Progetto", "Voce", "Valore"]
    values = {r[3]: r[4] for r in rows[1:]}
    assert values["Giornate management"] == "10,00" and values["Giornate delivery"] == "48,50"
    assert values["Giornate totali"] == "58,50" and values["Ricavi - PM"] == "10375,00"
    assert values["Ricavi totali"] == "47162,50" and values["Versione"] == "1"
    text = raw.decode("utf-8-sig")
    for forbidden in (
        "Costo",
        "Margine",
        "Prezzo/giorno",
        "Sprint",
        "Specialist",
        "26962",
        "10220",
        "4620",
        "0,5716",
    ):  # (20.200 è il ricavo della fase TA: non è un indicatore dei costi)
        assert forbidden not in text, forbidden


def test_to_csv_helpers_directly():
    raw = to_csv(["A", "B"], [["=x", 1], [None, True]])
    rows = parse(raw)
    assert rows == [["A", "B"], ["'=x", "1"], ["", "Sì"]]
    assert parse(to_csv(["A"], [])) == [["A"]]
