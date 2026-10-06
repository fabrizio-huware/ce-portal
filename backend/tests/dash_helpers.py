"""Un piccolo "mondo" di CE per provare dashboard ed export."""

from app.models import Employee
from tests.ce_helpers import create, header, save
from tests.factories import make_client

URL = "/api/v1/ce"


def make_employee(session, env, first, last, profile="Senior") -> Employee:
    emp = Employee(first_name=first, last_name=last, default_profile_id=env.profiles[profile].id)
    session.add(emp)
    session.flush()
    return emp


def build_ce(api, env, code, *, lines, client=None, bu=None, start="2026-01-20", end="2026-04-20",
             contingency="0", state="draft", project="Progetto", notes=None, sf=None, planning_mode="hours"):  # fmt: skip
    """Crea e compila un CE. `lines` = [(profilo, ore, collaboratore|None, [attività])].

    state: draft | submitted | rejected | approved.
    """
    client = client or env.client
    created = create(api, env, code=code, client_id=str(client.id), start_date=start, end_date=end,
                     business_unit=bu, project_name=project, planning_mode=planning_mode)  # fmt: skip
    ce_id = created["ce"]["id"]
    content = {
        "expected_revision": 1,
        "header": header(env, client_id=str(client.id), start_date=start, end_date=end, business_unit=bu,
                         project_name=project, notes=notes, sf_opportunity=sf, planning_mode=planning_mode),
        "phases": [{
            "name": "Fase",
            "contingency_pct": contingency,
            "lines": [
                {"activity": (spec[3] if len(spec) > 3 else f"Attività {i}"), "profile_id": str(env.profiles[spec[0]].id),
                 "hours": str(spec[1]), **({"employee_id": str(spec[2].id)} if spec[2] else {})}
                for i, spec in enumerate(lines)
            ],
        }],
    }  # fmt: skip
    resp = save(api, env, ce_id, content)
    assert resp.status_code == 200, resp.text
    if state in ("submitted", "rejected", "approved"):
        assert api.post(f"{URL}/{ce_id}/submit", headers=env.h(env.presale)).status_code == 200
    if state == "rejected":
        r = api.post(
            f"{URL}/{ce_id}/reject", headers=env.h(env.admin), json={"reason": "Da rivedere"}
        )
        assert r.status_code == 200
    if state == "approved":
        assert api.post(f"{URL}/{ce_id}/approve", headers=env.h(env.admin)).status_code == 200
    return ce_id


def world(api, env, session):
    """Quattro CE approvati/aperti con collaboratori e due clienti.

    A  (Alfa, AI)   approvato  Senior 80 h (Ada) + Specialist 160 h (Bruno)   -> 23.000 / 8.900 / 30 g
    B  (Beta, Data) approvato  Senior 40 h (Ada), mar-giu                      ->  4.250 / 1.650 /  5 g
    D  (Beta, -)    approvato  Specialist 40 h (Bruno) + v2 in bozza           ->  3.625 / 1.400 /  5 g
    C  (Alfa, AI)   bozza      Specialist 80 h (Bruno)  [pipeline]             ->  7.250 / 2.800 / 10 g
    F  (Beta, Data) rifiutato  Senior 8 h               [pipeline]             ->    850 /   330 /  1 g
    """
    alfa = env.client
    beta = make_client(session, name="Beta Srl")
    ada = make_employee(session, env, "Ada", "Lovelace", "Senior")
    bruno = make_employee(session, env, "Bruno", "Neri", "Specialist")
    ids = {
        "A": build_ce(api, env, "PS-DASH-A", client=alfa, bu="AI", lines=[("Senior", 80, ada), ("Specialist", 160, bruno)], state="approved"),
        "B": build_ce(api, env, "PS-DASH-B", client=beta, bu="Data", start="2026-03-01", end="2026-06-30", lines=[("Senior", 40, ada)], state="approved"),
        "D": build_ce(api, env, "PS-DASH-D", client=beta, lines=[("Specialist", 40, bruno)], state="approved"),
        "C": build_ce(api, env, "PS-DASH-C", client=alfa, bu="AI", start="2026-02-01", end="2026-03-31", lines=[("Specialist", 80, bruno)]),
        "F": build_ce(api, env, "PS-DASH-F", client=beta, bu="Data", start="2026-03-01", end="2026-04-30", lines=[("Senior", 8, None)], state="rejected"),
    }  # fmt: skip
    api.post(
        f"{URL}/{ids['D']}/versions", headers=env.h(env.presale)
    )  # revisione in corso di un CE approvato
    return {"ids": ids, "alfa": alfa, "beta": beta, "ada": ada, "bruno": bruno}
