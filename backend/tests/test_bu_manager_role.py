"""Responsabile di business unit: come un presale su ciò che è suo (l'approvazione arriva con la visibilità per business unit)."""

from app.models import ProfileRate
from tests.factories import make_business_unit, make_client, make_profile, make_user
from tests.helpers import auth

HEADER = {
    "project_name": "Progetto",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "planning_mode": "hours",
}


def _manager(session):
    unit = make_business_unit(session, name="Data & AI")
    return make_user(session, role="bu_manager", business_unit_id=unit.id)


def _create(api, session, user, code):
    client = make_client(session)
    session.add(
        ProfileRate(profile_id=make_profile(session).id, year=2026, daily_price=1, daily_cost=1)
    )  # il listino 2026
    session.commit()
    resp = api.post(
        "/api/v1/ce", headers=auth(user), json={"code": code, "client_id": str(client.id), **HEADER}
    )
    assert resp.status_code == 201, resp.text
    return resp.json(), client


def test_the_manager_reaches_what_editors_reach_and_not_what_only_admins_reach(api, session):
    h = auth(_manager(session))
    for path in (
        "/api/v1/ce",
        "/api/v1/dashboard/resources",
        "/api/v1/clients/lookup",
        "/api/v1/business-units/lookup",
        "/api/v1/practices/lookup",
    ):
        assert api.get(path, headers=h).status_code == 200, path
    for path in (
        "/api/v1/users",
        "/api/v1/integrations",
        "/api/v1/business-units",
        "/api/v1/practices",
    ):
        assert api.get(path, headers=h).status_code == 403, path


def test_the_manager_authors_edits_and_submits_own_ces(api, session):
    manager = _manager(session)
    h = auth(manager)
    detail, client = _create(api, session, manager, "PS-BUM-001-PJT")
    assert detail["ce"]["owner"]["id"] == str(manager.id)
    actions = detail["actions"]
    assert (actions["edit"], actions["submit"], actions["delete"], actions["assign"]) == (
        True,
        True,
        False,
        False,
    )
    content = {
        "expected_revision": detail["version"]["revision"],
        "header": {"client_id": str(client.id), **HEADER},
        "phases": [],
    }
    ce_id = detail["ce"]["id"]
    assert api.put(f"/api/v1/ce/{ce_id}/content", headers=h, json=content).status_code == 200
    # l'invio è permesso (un CE vuoto non è valido: 422, non 403)
    assert api.post(f"/api/v1/ce/{ce_id}/submit", headers=h).status_code == 422


def test_the_manager_cannot_edit_the_ces_of_others(api, session):
    presale = make_user(session, role="presale")
    detail, client = _create(api, session, presale, "PS-BUM-002-PJT")
    manager = _manager(session)
    h = auth(manager)
    ce_id = detail["ce"]["id"]
    seen = api.get(f"/api/v1/ce/{ce_id}", headers=h).json()
    assert (seen["actions"]["edit"], seen["actions"]["submit"]) == (
        False,
        False,
    )  # per ora li vede tutti, come il presale
    content = {
        "expected_revision": detail["version"]["revision"],
        "header": {"client_id": str(client.id), **HEADER},
        "phases": [],
    }
    assert api.put(f"/api/v1/ce/{ce_id}/content", headers=h, json=content).status_code == 403


def test_a_presale_cannot_edit_the_ces_of_a_manager(api, session):
    manager = _manager(session)
    detail, client = _create(api, session, manager, "PS-BUM-003-PJT")
    other = make_user(session, role="presale")
    content = {
        "expected_revision": detail["version"]["revision"],
        "header": {"client_id": str(client.id), **HEADER},
        "phases": [],
    }
    assert (
        api.put(
            f"/api/v1/ce/{detail['ce']['id']}/content", headers=auth(other), json=content
        ).status_code
        == 403
    )
