from sqlalchemy import select

from app.models import AuditLog
from tests.factories import make_client, make_user
from tests.helpers import auth


def test_presale_creates_and_updates_clients(api, session):
    presale = make_user(session, role="presale")
    h = auth(presale)
    created = api.post(
        "/api/v1/clients", headers=h, json={"name": " Menarini ", "address": "Via Roma 1, Firenze"}
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["name"] == "Menarini" and created.json()["is_active"] is True

    updated = api.patch(
        f"/api/v1/clients/{cid}",
        headers=h,
        json={"address": "Via Nuova 2", "external_ref": "NS-77"},
    )
    assert updated.status_code == 200 and updated.json()["external_ref"] == "NS-77"
    assert api.get(f"/api/v1/clients/{cid}", headers=h).json()["address"] == "Via Nuova 2"
    actions = session.scalars(select(AuditLog.action).where(AuditLog.entity_type == "client")).all()
    assert sorted(actions) == ["create", "update"]


def test_client_names_are_unique_ignoring_case(api, session):
    h = auth(make_user(session, role="presale"))
    make_client(session, name="Menarini")
    other = make_client(session, name="Altro")
    assert api.post("/api/v1/clients", headers=h, json={"name": "MENARINI"}).status_code == 409
    assert (
        api.patch(f"/api/v1/clients/{other.id}", headers=h, json={"name": "menarini"}).status_code
        == 409
    )
    # rinominare mantenendo lo stesso nome (cambio di maiuscole) è consentito
    assert (
        api.patch(f"/api/v1/clients/{other.id}", headers=h, json={"name": "ALTRO"}).status_code
        == 200
    )


def test_only_admin_can_activate_or_deactivate_clients(api, session):
    client = make_client(session)
    presale_h = auth(make_user(session, role="presale"))
    admin_h = auth(make_user(session, role="admin"))
    url = f"/api/v1/clients/{client.id}"
    assert api.patch(url, headers=presale_h, json={"is_active": False}).status_code == 403
    assert api.patch(url, headers=admin_h, json={"is_active": False}).json()["is_active"] is False
    # il presale può comunque modificare gli altri campi
    assert api.patch(url, headers=presale_h, json={"address": "x"}).status_code == 200


def test_client_validation(api, session):
    h = auth(make_user(session, role="presale"))
    client = make_client(session)
    assert api.post("/api/v1/clients", headers=h, json={"name": "  "}).status_code == 422
    assert api.post("/api/v1/clients", headers=h, json={}).status_code == 422
    assert (
        api.patch(f"/api/v1/clients/{client.id}", headers=h, json={"name": None}).status_code == 422
    )
    missing = "00000000-0000-0000-0000-000000000000"
    assert api.get(f"/api/v1/clients/{missing}", headers=h).status_code == 404


def test_viewer_gets_minimal_lookup_but_not_client_details(api, session):
    make_client(session, name="Menarini", address="Indirizzo riservato")
    make_client(session, name="Mediolanum")
    h = auth(make_user(session, role="viewer"))

    lookup = api.get("/api/v1/clients/lookup?q=men", headers=h)
    assert lookup.status_code == 200
    assert lookup.json() == [{"id": lookup.json()[0]["id"], "name": "Menarini", "is_active": True}]
    assert "Indirizzo" not in lookup.text
    assert api.get("/api/v1/clients", headers=h).status_code == 403


def test_client_list_search_filter_and_order(api, session):
    h = auth(make_user(session, role="presale"))
    make_client(session, name="beta")
    make_client(session, name="Alfa")
    make_client(session, name="Gamma", is_active=False)
    names = [c["name"] for c in api.get("/api/v1/clients", headers=h).json()["items"]]
    assert names == ["Alfa", "beta", "Gamma"]  # ordine alfabetico senza distinzione di maiuscole
    assert api.get("/api/v1/clients?is_active=false", headers=h).json()["total"] == 1
    assert api.get("/api/v1/clients?q=ALF", headers=h).json()["total"] == 1
    assert (
        api.get("/api/v1/clients?limit=1&offset=1", headers=h).json()["items"][0]["name"] == "beta"
    )
