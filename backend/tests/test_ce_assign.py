"""Un amministratore assegna a un presale un CE creato da un'integrazione."""

import uuid

import pytest

from tests.ce_helpers import create_filled, save
from tests.s2s_helpers import Caller, new_ce_body, register


@pytest.fixture
def call(api, env, session, service) -> Caller:
    register(api, env)
    return Caller(api, session, service)


@pytest.fixture
def ext(call, env) -> str:
    """Un CE creato dall'integrazione, ancora suo."""
    response = call.post("/ce", json=new_ce_body(env))
    assert response.status_code == 201, response.text
    return response.json()["ce"]["ce_id"]


def assign(api, env, ce_id, user, by=None):
    return api.post(
        f"/api/v1/ce/{ce_id}/assign",
        json={"user_id": str(user.id) if hasattr(user, "id") else user},
        headers=env.h(by or env.admin),
    )


def detail(api, env, ce_id, user=None) -> dict:
    return api.get(f"/api/v1/ce/{ce_id}", headers=env.h(user or env.admin)).json()


def test_the_admin_assigns_it_and_the_presale_takes_over(api, env, ext):
    before = detail(api, env, ext)
    assert before["actions"]["assign"] is True and before["ce"]["owner"]["is_service"] is True
    assert (
        detail(api, env, ext, env.presale)["actions"]["edit"] is False
    )  # un presale non può toccarlo...

    response = assign(api, env, ext, env.presale)
    assert response.status_code == 200, response.text
    after = response.json()
    assert (
        after["ce"]["owner"]["id"] == str(env.presale.id)
        and after["ce"]["owner"]["is_service"] is False
    )
    assert after["actions"]["assign"] is False  # non più assegnabile: ormai ha un autore umano
    assert after["ce"]["requested_by"] == "anna.rossi@huware.com"  # l'annotazione resta

    mine = detail(api, env, ext, env.presale)  # ...ora sì
    assert mine["actions"]["edit"] is True and mine["actions"]["submit"] is True
    content = {
        "expected_revision": mine["version"]["revision"],
        "header": new_ce_body(env)["content"]["header"],
        "phases": new_ce_body(env, hours="24")["content"]["phases"],
    }
    assert save(api, env, ext, content).status_code == 200  # il presale lo modifica
    assert (
        api.post(f"/api/v1/ce/{ext}/submit", headers=env.h(env.presale)).status_code == 200
    )  # e lo invia


def test_after_the_assignment_the_integration_can_only_read_it(call, api, env, ext):
    assert assign(api, env, ext, env.presale).status_code == 200
    content = {"expected_revision": 2, **new_ce_body(env)["content"]}
    assert call.put(f"/ce/{ext}/content", json=content).status_code == 403
    assert call.get(f"/ce/{ext}/content").status_code == 403  # nemmeno il contenuto si rilegge
    seen = call.get(f"/ce/{ext}").json()
    assert (
        seen["mine"] is False and seen["external_ref"] == "EXT-001"
    )  # il riepilogo resta leggibile
    assert call.get(f"/ce/{ext}/pdf").status_code == 200
    listed = call.get("/ce?external_ref=EXT-001").json()["items"]
    assert listed[0]["mine"] is False and listed[0]["external_ref"] == "EXT-001"


def test_repeating_the_creation_after_the_assignment_does_not_duplicate(call, api, env, ext):
    assign(api, env, ext, env.presale)
    again = call.post("/ce", json=new_ce_body(env))
    assert again.status_code == 200 and again.json()["created"] is False
    assert (
        again.json()["ce"]["ce_id"] == ext and again.json()["revision"] is None
    )  # non è più suo: niente da correggere


def test_the_assignment_is_recorded_in_the_history(api, env, ext):
    assign(api, env, ext, env.other)
    history = api.get(f"/api/v1/ce/{ext}/history", headers=env.h(env.admin)).json()
    entry = next(h for h in history if h["action"] == "assign")
    assert (
        entry["changes"]["from"] == "Portale esterno (servizio)"
        and entry["changes"]["to"] == env.other.full_name
    )
    assert entry["user"]["id"] == str(env.admin.id)  # chi ha assegnato


def test_only_admins_can_assign(api, env, ext):
    assert assign(api, env, ext, env.presale, by=env.presale).status_code == 403
    assert assign(api, env, ext, env.presale, by=env.viewer).status_code == 403
    assert (
        api.post(f"/api/v1/ce/{ext}/assign", json={"user_id": str(env.presale.id)}).status_code
        == 401
    )
    assert detail(api, env, ext)["ce"]["owner"]["is_service"] is True  # nessuno ha cambiato nulla


def test_only_ces_created_by_an_integration_can_be_assigned(api, env):
    human = create_filled(api, env, "PS-UMANO-001-PJT")["ce"]["id"]
    assert assign(api, env, human, env.other).status_code == 409
    assert detail(api, env, human)["ce"]["owner"]["id"] == str(env.presale.id)
    assert detail(api, env, human)["actions"]["assign"] is False


def test_it_cannot_be_assigned_twice(api, env, ext):
    assert assign(api, env, ext, env.presale).status_code == 200
    assert assign(api, env, ext, env.other).status_code == 409  # ora ha un autore umano


def test_the_recipient_must_be_an_active_presale_person(api, env, ext, session):
    for bad in (env.viewer, env.admin):
        assert assign(api, env, ext, bad).status_code == 422, bad.role
    assert detail(api, env, ext)["ce"]["owner"]["is_service"] is True
    env.other.is_active = False
    session.commit()
    assert assign(api, env, ext, env.other).status_code == 422  # disattivato
    service_user = detail(api, env, ext)["ce"]["owner"]["id"]
    assert assign(api, env, ext, service_user).status_code == 422  # nemmeno a un utente di servizio
    assert assign(api, env, ext, str(uuid.uuid4())).status_code == 404
    assert assign(api, env, str(uuid.uuid4()), env.presale).status_code == 404


def test_the_integration_cannot_assign_anything_by_any_means(call, ext):
    response = call.post(f"/ce/{ext}/assign", json={"user_id": str(uuid.uuid4())})
    assert response.status_code in (404, 405)  # non esiste nel contratto per i programmi esterni
