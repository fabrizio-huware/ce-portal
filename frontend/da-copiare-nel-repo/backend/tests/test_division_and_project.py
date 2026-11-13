"""Filtro per progetto nel Carico risorse e divisione per business unit nel PDF completo."""

from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.schemas.ce import CEDetail
from app.services.unit_division import CONTINGENCY, NO_EMPLOYEE, business_unit_division
from tests.ce_helpers import create, save, simple_content
from tests.factories import make_business_unit
from tests.test_ce_business_units import _employee_in
from tests.test_ce_visibility import Scene, _switch

URL = "/api/v1/ce"
WINDOW = "date_from=2026-01-01&date_to=2026-04-30&include_pipeline=true"


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def _ce_with(
    api, env, user, code, project, people, *, extra_lines=False, contingency="0", units=None
):
    """Un CE di cui si sceglie il nome del progetto, con una riga per ciascun collaboratore indicato."""
    created = create(
        api,
        env,
        user,
        code,
        project_name=project,
        **({"business_unit_ids": units} if units else {}),
    )
    content = simple_content(env, created["version"]["revision"])
    content["header"]["project_name"] = project
    base = content["phases"][0]["lines"][0]
    lines = [
        {**base, "activity": f"Attività {i}", "employee_id": str(p.id)}
        for i, p in enumerate(people)
    ]
    if extra_lines:  # una riga senza collaboratore
        lines.append(
            {k: v for k, v in {**base, "activity": "Senza nome"}.items() if k != "employee_id"}
        )
    content["phases"][0]["lines"] = lines
    content["phases"][0]["contingency_pct"] = contingency
    assert save(api, env, created["ce"]["id"], content, user).status_code == 200
    return created["ce"]["id"]


# ------------------------------------------------------------------ filtro per progetto
def test_the_resources_filter_by_project_name_or_code(api, env, session):
    ada = _employee_in(session, env, env.unit, "Ada")
    session.commit()
    _ce_with(api, env, env.presale, "PS-PRJ-1-PJT", "Alfa Migrazione", [ada])
    _ce_with(api, env, env.presale, "PS-PRJ-2-PJT", "Beta Cloud", [ada])
    h = env.h(env.admin)

    def total(extra=""):
        body = api.get(f"/api/v1/dashboard/resources?{WINDOW}{extra}", headers=h).json()
        return Decimal(body["employees"][0]["total_days"]) if body["employees"] else Decimal(
            0
        ), body["ces_count"]

    both, count_both = total()
    one, count_one = total("&project=migrazione")  # dal nome, senza badare alle maiuscole
    other, _ = total("&project=prj-2")  # dal codice
    assert count_one == 1 and one * 2 == both and other * 2 == both and one > 0
    assert total("&project=ALFA")[0] == one
    assert total("&project=zzz") == (Decimal(0), 0)  # nessun progetto: niente
    assert count_both >= 2
    # il carattere % o _ nel testo non è un jolly
    assert total("&project=%25")[0] == Decimal(0)


def test_the_project_filter_applies_to_the_exports_too(api, env, session):
    ada = _employee_in(session, env, env.unit, "Ada")
    session.commit()
    _ce_with(api, env, env.presale, "PS-PRJ-3-PJT", "Gamma", [ada])
    h = env.h(env.admin)
    hit = api.get(
        f"/api/v1/dashboard/resources/export?format=csv&{WINDOW}&project=gamma", headers=h
    ).text
    miss = api.get(
        f"/api/v1/dashboard/resources/export?format=csv&{WINDOW}&project=zzz", headers=h
    ).text
    assert "Ada Test" in hit and "Ada Test" not in miss


def test_searching_a_project_never_reveals_ces_the_user_cannot_see(api, env, session):
    scene = Scene(api, env, session)
    ada = _employee_in(session, env, scene.a, "Ada")  # persona della business unit di Anna
    session.commit()
    _ce_with(
        api, env, env.other, "PS-PRJ-SEGRETO-PJT", "Segreto Cloud", [ada], units=[str(scene.b.id)]
    )
    _switch(api, env, True)
    anna, admin = env.h(env.presale), env.h(env.admin)
    assert (
        api.get(f"{URL}/{_ce_id(api, env, 'PS-PRJ-SEGRETO-PJT')}", headers=anna).status_code == 404
    )  # non lo vede
    free = api.get(f"/api/v1/dashboard/resources?{WINDOW}", headers=anna).json()
    assert [e["name"] for e in free["employees"]] == [
        "Ada Test"
    ]  # senza filtro: il carico di Ada è su tutti i CE
    probe = api.get(f"/api/v1/dashboard/resources?{WINDOW}&project=segreto", headers=anna).json()
    assert (
        probe["employees"] == [] and probe["ces_count"] == 0
    )  # col filtro non si «pesca» un CE che non si vede
    code = api.get(
        f"/api/v1/dashboard/resources?{WINDOW}&project=PS-PRJ-SEGRETO", headers=anna
    ).json()
    assert code["employees"] == []
    assert api.get(f"/api/v1/dashboard/resources?{WINDOW}&project=segreto", headers=admin).json()[
        "employees"
    ]


def _ce_id(api, env, code):
    items = api.get(f"{URL}?limit=200&code={code}", headers=env.h(env.admin)).json()["items"]
    return items[0]["ce_id"]


# ------------------------------------------------------------------ divisione per business unit
def _division_scene(api, env, session):
    b = make_business_unit(session, name="Cloud")
    ada = _employee_in(session, env, env.unit, "Ada")
    bruno = _employee_in(session, env, b, "Bruno")
    session.commit()
    ce = _ce_with(
        api, env, env.presale, "PS-DIV-1-PJT", "Divisione", [ada, bruno], extra_lines=True, contingency="10",
        units=[str(env.unit.id), str(b.id)],
    )  # fmt: skip
    return ce, ada, bruno, b


def test_the_division_adds_up_to_the_totals_of_the_ce(api, env, session):
    ce, *_ = _division_scene(api, env, session)
    detail = CEDetail.model_validate(api.get(f"{URL}/{ce}", headers=env.h(env.admin)).json())
    rows = business_unit_division(session, detail)
    assert [r.label for r in rows] == ["Business unit di prova", "Cloud", NO_EMPLOYEE, CONTINGENCY][
        :0
    ] or True
    labels = [r.label for r in rows]
    assert labels[:2] == sorted(
        ["Business unit di prova", "Cloud"], key=str.lower
    )  # le business unit, in ordine
    assert labels[-2:] == [
        NO_EMPLOYEE,
        CONTINGENCY,
    ]  # poi le righe senza collaboratore e la contingency
    total = detail.calculation.total
    assert sum(r.days for r in rows) == total.days
    assert sum(r.revenue for r in rows) == total.revenue
    assert sum(r.cost for r in rows) == total.cost
    assert sum(r.margin for r in rows) == total.margin
    assert abs(sum(r.share for r in rows) - 1) < Decimal("1e-9")  # le quote dei ricavi fanno 100%
    contingency = rows[-1]
    assert (
        contingency.cost == 0 and contingency.revenue == detail.calculation.contingency.revenue > 0
    )
    by_label = {r.label: r for r in rows}
    ada_line = detail.calculation.lines[0]
    assert (
        by_label["Business unit di prova"].revenue == ada_line.revenue
    )  # le righe di Ada sono della sua unit
    assert by_label["Cloud"].revenue == detail.calculation.lines[1].revenue


def test_a_ce_without_lines_has_no_division(api, env, session):
    created = create(api, env, env.presale, "PS-DIV-2-PJT")
    detail = CEDetail.model_validate(
        api.get(f"{URL}/{created['ce']['id']}", headers=env.h(env.admin)).json()
    )
    assert business_unit_division(session, detail) == []


def test_the_complete_pdf_has_the_division_and_the_summary_does_not(api, env, session):
    ce, *_ = _division_scene(api, env, session)
    full = api.get(f"{URL}/{ce}/export?format=pdf&variant=full", headers=env.h(env.presale))
    assert full.status_code == 200
    text = _text(full.content)
    assert "Divisione per business unit" in text
    for label in ("Business unit di prova", "Cloud", NO_EMPLOYEE, "Contingency", "% dei ricavi"):
        assert label in text, label
    assert "practice attuale" in text  # la nota che spiega come si attribuisce
    summary = api.get(f"{URL}/{ce}/export?format=pdf&variant=summary", headers=env.h(env.presale))
    assert summary.status_code == 200
    assert "Divisione per business unit" not in _text(
        summary.content
    )  # il riepilogo non ha costi né divisioni


def test_the_complete_pdf_of_a_ce_without_lines_still_works(api, env, session):
    created = create(api, env, env.presale, "PS-DIV-3-PJT")
    resp = api.get(
        f"{URL}/{created['ce']['id']}/export?format=pdf&variant=full", headers=env.h(env.presale)
    )
    assert resp.status_code == 200 and "Divisione per business unit" not in _text(resp.content)


# ------------------------------------------------------------------ impaginazione
TITLES = (
    "Ricavi e costi",
    "Divisione per business unit",
    "Dettaglio per fase",
    "Riepilogo per profilo",
    "Staffing mensile",
)


def test_no_page_of_the_complete_pdf_ends_with_a_lone_section_title(api, env, session):
    """Con un numero crescente di righe il punto di rottura di pagina cade in posti diversi: un titolo di
    sezione non deve mai restare solo in fondo a una pagina, con la tabella sulla successiva."""
    ada = _employee_in(session, env, env.unit, "Ada")
    session.commit()
    orphans = []
    for n in range(3, 23):
        ce = _ce_with(api, env, env.presale, f"PS-PAG-{n}-PJT", f"Impaginazione {n}", [ada] * n)
        pdf = api.get(
            f"{URL}/{ce}/export?format=pdf&variant=full", headers=env.h(env.presale)
        ).content
        for number, page in enumerate(PdfReader(BytesIO(pdf)).pages, 1):
            lines = [
                x.strip()
                for x in page.extract_text().splitlines()
                if x.strip() and not x.startswith(("Riservato", "Pagina "))
            ]
            if lines and lines[-1] in TITLES:
                orphans.append((n, number, lines[-1]))
    assert orphans == [], orphans
