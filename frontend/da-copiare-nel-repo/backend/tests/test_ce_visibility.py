"""Visibilità per business unit: chi vede quali CE, su ogni percorso, con l'interruttore spento e acceso."""

import uuid

import pytest
from sqlalchemy import delete, select

from app.core.config import Settings
from app.main import create_app
from app.models import AuditLog, CEBusinessUnit
from tests.ce_helpers import create, save, simple_content
from tests.factories import make_business_unit, make_practice, make_user
from tests.test_ce_business_units import _employee_in
from tests.test_permissions_matrix import MATRIX, _fill

URL = "/api/v1/ce"
SWITCH = "/api/v1/business-units/visibility"
PREFIX = "PS-VIS"


def _make(api, env, user, code, units):
    created = create(api, env, user, code, business_unit_ids=[str(u.id) for u in units])
    ce_id = created["ce"]["id"]
    assert (
        save(api, env, ce_id, simple_content(env, created["version"]["revision"]), user).status_code
        == 200
    )
    return ce_id


def _switch(api, env, on):
    resp = api.put(SWITCH, headers=env.h(env.admin), json={"enabled": on})
    assert resp.status_code == 200 and resp.json()["enabled"] is on
    return resp.json()


class Scene:
    """Tre business unit, tre presale (A, B e senza), tre responsabili (A, B, C) e cinque CE incrociati."""

    def __init__(self, api, env, session):
        self.a, self.b = env.unit, make_business_unit(session, name="Cloud")
        self.c = make_business_unit(session, name="Digital")
        env.presale.business_unit_id = self.a.id
        env.other.business_unit_id = self.b.id
        self.none = make_user(session, role="presale")
        self.ma = make_user(session, role="bu_manager", business_unit_id=self.a.id)
        self.mb = make_user(session, role="bu_manager", business_unit_id=self.b.id)
        self.mc = make_user(session, role="bu_manager", business_unit_id=self.c.id)
        session.commit()
        self.users = {
            "presale A": env.presale, "presale B": env.other, "presale senza": self.none,
            "responsabile A": self.ma, "responsabile B": self.mb, "responsabile C": self.mc,
        }  # fmt: skip
        self.ce = {
            "a": _make(api, env, env.presale, f"{PREFIX}-A-PJT", [self.a]),
            "b": _make(api, env, env.other, f"{PREFIX}-B-PJT", [self.b]),
            "ab": _make(api, env, env.other, f"{PREFIX}-AB-PJT", [self.a, self.b]),
            "na": _make(api, env, self.none, f"{PREFIX}-NA-PJT", [self.a]),
            "nb": _make(api, env, self.none, f"{PREFIX}-NB-PJT", [self.b]),
        }  # fmt: skip
        # chi vede cosa con l'interruttore acceso: la propria business unit coinvolta, oppure i propri CE
        self.expected = {
            "presale A": {"a", "ab", "na"},
            "presale B": {"b", "ab", "nb"},
            "presale senza": {"na", "nb"},
            "responsabile A": {"a", "ab", "na"},
            "responsabile B": {"b", "ab", "nb"},
            "responsabile C": set(),
        }  # fmt: skip

    def code(self, key):
        return {"a": "A", "b": "B", "ab": "AB", "na": "NA", "nb": "NB"}[key]

    def ids(self, env, ce_key):
        return {
            "ce_id": self.ce[ce_key], "number": 1, "user_id": str(env.presale.id),
            "client_id": str(env.client.id), "business_unit_id": str(self.a.id),
        }  # fmt: skip


def _listed(api, env, user):
    resp = api.get(f"{URL}?limit=200&code={PREFIX}", headers=env.h(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(body["items"])
    return {i["code"].removeprefix(f"{PREFIX}-").removesuffix("-PJT") for i in body["items"]}


# ------------------------------------------------------------------ interruttore spento
def test_with_the_switch_off_everyone_sees_everything_as_before(api, env, session):
    scene = Scene(api, env, session)
    everything = {"A", "B", "AB", "NA", "NB"}
    for who, user in scene.users.items():
        assert _listed(api, env, user) == everything, who
        assert api.get(f"{URL}/{scene.ce['b']}", headers=env.h(user)).status_code == 200, who


# ------------------------------------------------------------------ interruttore acceso
def test_the_list_follows_the_rule_with_the_switch_on(api, env, session):
    scene = Scene(api, env, session)
    _switch(api, env, True)
    for who, user in scene.users.items():
        assert _listed(api, env, user) == {scene.code(k) for k in scene.expected[who]}, who
    assert _listed(api, env, env.admin) == {"A", "B", "AB", "NA", "NB"}  # l'admin vede tutto


def test_a_ce_that_cannot_be_seen_is_not_found_on_every_route_with_a_ce_id(api, env, session):
    """Percorre da sola ogni rotta dei CE con un identificativo: chi non vede il CE riceve sempre 404."""
    scene = Scene(api, env, session)
    _switch(api, env, True)
    rows = [r for r in MATRIX if "{ce_id}" in r[1] and r[1].startswith(URL)]
    assert len(rows) >= 20  # la matrice dei permessi copre le rotte
    checked = 0
    for who, user in scene.users.items():
        for key in scene.ce:
            if key in scene.expected[who]:
                continue
            ids = scene.ids(env, key)
            for method, path, kwargs, _allowed in rows:
                resp = api.request(
                    method, _fill(path, ids), headers=env.h(user), **_fill(kwargs, ids)
                )
                assert resp.status_code == 404, (
                    who,
                    key,
                    method,
                    path,
                    resp.status_code,
                    resp.text[:120],
                )
                assert (
                    resp.json()["detail"] == "CE non trovato"
                )  # lo stesso di un CE che non esiste
                checked += 1
    assert checked > 300


def test_every_ce_route_in_the_api_is_covered_by_that_check(api):
    """Una rotta nuova con `{ce_id}` che non è nella matrice dei permessi fa fallire questo test."""
    spec = create_app(Settings()).openapi()["paths"]
    in_api = {
        (m.upper(), p)
        for p, ops in spec.items()
        if "{ce_id}" in p and p.startswith(URL)
        for m in ops
        if m in ("get", "post", "put", "patch", "delete")
    }
    in_matrix = {(m, p) for m, p, _k, _a in MATRIX if "{ce_id}" in p and p.startswith(URL)}
    assert in_api <= in_matrix, sorted(in_api - in_matrix)


def test_who_can_see_a_ce_reaches_its_routes(api, env, session):
    scene = Scene(api, env, session)
    _switch(api, env, True)
    reads = [r for r in MATRIX if r[0] == "GET" and "{ce_id}" in r[1] and "summaries" not in r[1]]
    for who, user in scene.users.items():
        for key in scene.expected[who]:
            for method, path, kwargs, _allowed in reads:
                ids = scene.ids(env, key)
                resp = api.request(
                    method, _fill(path, ids), headers=env.h(user), **_fill(kwargs, ids)
                )
                assert resp.status_code != 404, (who, key, path, resp.text[:120])


def test_the_exports_of_the_list_hold_only_visible_ces(api, env, session):
    scene = Scene(api, env, session)
    _switch(api, env, True)
    resp = api.get(f"{URL}/export?format=csv&code={PREFIX}", headers=env.h(env.presale))
    assert resp.status_code == 200
    for key in scene.ce:
        assert (f"{PREFIX}-{scene.code(key)}-PJT" in resp.text) is (
            key in scene.expected["presale A"]
        ), key
    everything = api.get(f"{URL}/export?format=csv&code={PREFIX}", headers=env.h(env.admin)).text
    assert all(f"{PREFIX}-{scene.code(k)}-PJT" in everything for k in scene.ce)


def test_the_portfolio_counts_only_the_ces_the_user_sees(api, env, session):
    scene = Scene(api, env, session)
    _switch(api, env, True)
    seen = api.get("/api/v1/dashboard/portfolio", headers=env.h(env.presale))
    assert seen.status_code == 200
    for key in scene.ce:
        assert (f"{PREFIX}-{scene.code(key)}-PJT" in seen.text) is (
            key in scene.expected["presale A"]
        ), key
    admin = api.get("/api/v1/dashboard/portfolio", headers=env.h(env.admin)).text
    assert all(f"{PREFIX}-{scene.code(k)}-PJT" in admin for k in scene.ce)
    export = api.get("/api/v1/dashboard/portfolio/export?format=csv", headers=env.h(env.presale))
    assert export.status_code == 200 and f"{PREFIX}-B-PJT" not in export.text


def test_the_resources_show_only_the_people_of_the_own_business_unit_but_count_every_ce(
    api, env, session
):
    scene = Scene(api, env, session)
    ada, bruno = (
        _employee_in(session, env, scene.a, "Ada"),
        _employee_in(session, env, scene.b, "Bruno"),
    )
    session.commit()
    # Ada lavora sul CE «a» (visibile al presale A) e sul CE «b» (che lui non vede); Bruno solo sul «b»
    for key, who, people in (("a", env.presale, [ada]), ("b", env.other, [ada, bruno])):
        detail = api.get(f"{URL}/{scene.ce[key]}", headers=env.h(who)).json()
        content = simple_content(env, detail["version"]["revision"])
        line = content["phases"][0]["lines"][0]
        content["phases"][0]["lines"] = [{**line, "employee_id": str(e.id)} for e in people]
        assert save(api, env, scene.ce[key], content, who).status_code == 200
    window = "date_from=2026-01-01&date_to=2026-04-30&include_pipeline=true"
    everyone = api.get(f"/api/v1/dashboard/resources?{window}", headers=env.h(env.admin)).json()
    assert {e["name"] for e in everyone["employees"]} == {"Ada Test", "Bruno Test"}
    _switch(api, env, True)
    mine = api.get(f"/api/v1/dashboard/resources?{window}", headers=env.h(env.presale)).json()
    assert [e["name"] for e in mine["employees"]] == [
        "Ada Test"
    ]  # Bruno è di un'altra business unit
    ada_all = next(e for e in everyone["employees"] if e["name"] == "Ada Test")["total_days"]
    assert (
        mine["employees"][0]["total_days"] == ada_all
    )  # il carico di Ada è su tutti i CE, anche quelli non visibili
    assert mine["ces_count"] == 2  # i CE con righe di quelle persone (solo il numero, mai i codici)
    assert everyone["ces_count"] == 5  # l'admin conta tutti i CE del periodo
    assert [p["name"] for p in mine["practices"]] == [
        "Practice di Business unit di prova"
    ]  # solo la sua
    assert "Bruno" not in str(mine) and f"{PREFIX}-B-PJT" not in str(mine)
    nobody = api.get(f"/api/v1/dashboard/resources?{window}", headers=env.h(scene.none)).json()
    assert (
        nobody["employees"] == [] and nobody["profiles"] == []
    )  # senza business unit non vede persone


def test_viewer_and_the_other_roles_are_not_affected_by_the_switch(api, env, session):
    scene = Scene(api, env, session)
    for key in ("a", "b"):
        assert (
            api.post(f"{URL}/{scene.ce[key]}/approve", headers=env.h(env.admin)).status_code == 200
        )
    _switch(api, env, True)
    listed = api.get(f"{URL}/summaries?limit=200", headers=env.h(env.viewer)).json()["items"]
    codes = {i["code"] for i in listed if i["code"].startswith(PREFIX)}
    assert codes == {
        f"{PREFIX}-A-PJT",
        f"{PREFIX}-B-PJT",
    }  # il viewer vede i riepiloghi approvati di tutti
    assert api.get(f"{URL}/summaries/{scene.ce['b']}", headers=env.h(env.viewer)).status_code == 200


# ------------------------------------------------------------------ responsabile: approvazione
def _submit(api, env, scene, key):
    owner = {"a": env.presale, "b": env.other, "ab": env.other, "na": scene.none, "nb": scene.none}[
        key
    ]
    assert api.post(f"{URL}/{scene.ce[key]}/submit", headers=env.h(owner)).status_code == 200


def test_the_manager_of_an_involved_business_unit_approves_and_rejects(api, env, session):
    scene = Scene(api, env, session)
    _submit(api, env, scene, "ab")
    seen = api.get(f"{URL}/{scene.ce['ab']}", headers=env.h(scene.mb)).json()
    assert (seen["actions"]["approve"], seen["actions"]["reject"]) == (True, True)
    assert (
        api.post(
            f"{URL}/{scene.ce['ab']}/reject", headers=env.h(scene.ma), json={"reason": "No"}
        ).status_code
        == 200
    )
    _submit(api, env, scene, "ab")
    done = api.post(
        f"{URL}/{scene.ce['ab']}/approve", headers=env.h(scene.mb)
    )  # basta il responsabile di una
    assert done.status_code == 200 and done.json()["version"]["status"] == "approved"
    assert done.json()["version"]["approved_by"]["id"] == str(scene.mb.id)


def test_the_manager_of_another_business_unit_cannot_approve(api, env, session):
    scene = Scene(api, env, session)
    _submit(api, env, scene, "a")
    assert (
        api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(scene.mc)).status_code == 403
    )  # interruttore spento
    assert (
        api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(scene.mb)).status_code == 403
    )  # non coinvolto
    _switch(api, env, True)
    assert (
        api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(scene.mc)).status_code == 404
    )  # e non lo vede
    assert (
        api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(env.presale)).status_code == 403
    )  # un presale mai
    seen = api.get(f"{URL}/{scene.ce['a']}", headers=env.h(scene.ma)).json()
    assert seen["actions"]["approve"] is True


def test_the_manager_approves_only_what_is_waiting_for_approval(api, env, session):
    scene = Scene(api, env, session)  # il CE «a» è in bozza
    seen = api.get(f"{URL}/{scene.ce['a']}", headers=env.h(scene.ma)).json()
    assert (seen["actions"]["approve"], seen["actions"]["reject"]) == (False, False)
    assert api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(scene.ma)).status_code == 403
    assert (
        api.post(f"{URL}/{scene.ce['a']}/approve", headers=env.h(env.admin)).status_code == 200
    )  # l'admin sempre


# ------------------------------------------------------------------ interruttore e rapporto
def test_only_an_admin_can_read_or_change_the_switch(api, env, session):
    scene = Scene(api, env, session)
    for user in (env.presale, scene.ma, env.viewer):
        assert api.get(SWITCH, headers=env.h(user)).status_code == 403
        assert api.put(SWITCH, headers=env.h(user), json={"enabled": True}).status_code == 403
    assert api.put(SWITCH, headers=env.h(env.admin), json={}).status_code == 422
    assert (
        api.get(SWITCH, headers=env.h(env.admin)).json()["enabled"] is False
    )  # spento alla pubblicazione


def test_the_switch_is_recorded_once_per_change(api, env, session):
    Scene(api, env, session)
    _switch(api, env, True)
    _switch(api, env, True)  # niente da registrare
    _switch(api, env, False)
    session.expire_all()
    entries = session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "setting").order_by(AuditLog.id)
    ).all()
    assert [e.changes["bu_visibility_enabled"] for e in entries] == [[False, True], [True, False]]


def test_the_report_says_what_is_missing_before_turning_it_on(api, env, session):
    scene = Scene(api, env, session)
    base = api.get(SWITCH, headers=env.h(env.admin)).json()["report"]
    assert base["ces_without_business_units"] == 0
    assert "Presale senza business unit" not in base["people_without_business_unit"]
    session.execute(
        delete(CEBusinessUnit).where(
            CEBusinessUnit.ce_id.in_([uuid.UUID(scene.ce["a"]), uuid.UUID(scene.ce["b"])])
        )
    )
    make_practice(session, name="Ancora senza area")  # finisce in «Da assegnare»
    make_user(session, role="presale", full_name="Presale senza business unit")
    session.commit()
    report = api.get(SWITCH, headers=env.h(env.admin)).json()["report"]
    assert report["ces_without_business_units"] == 2
    assert {c["code"] for c in report["ces_without_examples"]} == {
        f"{PREFIX}-A-PJT",
        f"{PREFIX}-B-PJT",
    }
    assert "Presale senza business unit" in report["people_without_business_unit"]
    assert report["practices_unassigned"] >= 1
    assert (
        api.put(SWITCH, headers=env.h(env.admin), json={"enabled": True}).status_code == 200
    )  # si accende comunque


def test_a_ce_without_business_units_is_seen_only_by_its_author_and_admins(api, env, session):
    scene = Scene(api, env, session)
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id == uuid.UUID(scene.ce["a"])))
    session.commit()
    _switch(api, env, True)
    assert (
        api.get(f"{URL}/{scene.ce['a']}", headers=env.h(env.presale)).status_code == 200
    )  # è l'autore
    assert api.get(f"{URL}/{scene.ce['a']}", headers=env.h(scene.ma)).status_code == 404
    assert api.get(f"{URL}/{scene.ce['a']}", headers=env.h(env.admin)).status_code == 200


@pytest.mark.parametrize("who", ["presale A", "responsabile A"])
def test_changing_the_business_units_changes_who_sees_the_ce(api, env, session, who):
    scene = Scene(api, env, session)
    _switch(api, env, True)
    user = scene.users[who]
    assert api.get(f"{URL}/{scene.ce['b']}", headers=env.h(user)).status_code == 404
    put = api.put(
        f"{URL}/{scene.ce['b']}/business-units",
        headers=env.h(env.other),
        json={"business_unit_ids": [str(scene.a.id), str(scene.b.id)]},
    )
    assert put.status_code == 200
    assert api.get(f"{URL}/{scene.ce['b']}", headers=env.h(user)).status_code == 200
