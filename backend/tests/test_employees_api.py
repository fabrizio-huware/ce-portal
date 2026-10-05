from tests.factories import make_profile, make_user
from tests.helpers import auth


def _setup(session):
    admin_h = auth(make_user(session, role="admin"))
    profile = make_profile(session, name="Senior")
    return admin_h, profile


def _create(api, h, profile, **kw):
    body = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "default_profile_id": str(profile.id),
        **kw,
    }
    return api.post("/api/v1/employees", headers=h, json=body)


def test_admin_creates_employee_with_profile_name(api, session):
    h, profile = _setup(session)
    resp = _create(api, h, profile, netsuite_id="NS-1")
    assert resp.status_code == 201
    body = resp.json()
    assert (
        body["profile_name"] == "Senior"
        and body["is_active"] is True
        and body["netsuite_id"] == "NS-1"
    )


def test_create_employee_validations(api, session):
    h, profile = _setup(session)
    inactive = make_profile(session, name="Dismesso", is_active=False)
    assert _create(api, h, profile).status_code == 201
    assert _create(api, h, profile, first_name="MARIO", last_name="rossi").status_code == 409
    assert _create(api, h, inactive, first_name="Anna").status_code == 422
    unknown = api.post(
        "/api/v1/employees",
        headers=h,
        json={
            "first_name": "A",
            "last_name": "B",
            "default_profile_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert unknown.status_code == 422
    assert _create(api, h, profile, first_name="").status_code == 422


def test_update_employee(api, session):
    h, profile = _setup(session)
    other = make_profile(session, name="Consultant")
    eid = _create(api, h, profile).json()["id"]
    _create(api, h, profile, first_name="Luca", last_name="Bianchi")

    resp = api.patch(
        f"/api/v1/employees/{eid}",
        headers=h,
        json={"default_profile_id": str(other.id), "is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["profile_name"] == "Consultant" and resp.json()["is_active"] is False
    assert (
        api.patch(
            f"/api/v1/employees/{eid}",
            headers=h,
            json={"first_name": "Luca", "last_name": "Bianchi"},
        ).status_code
        == 409
    )
    assert (
        api.patch(f"/api/v1/employees/{eid}", headers=h, json={"is_active": None}).status_code
        == 422
    )


def test_employee_can_keep_an_inactive_profile_unless_changed_to_one(api, session):
    h, profile = _setup(session)
    eid = _create(api, h, profile).json()["id"]
    profile.is_active = False
    session.flush()
    # modificare altro non richiede che il profilo corrente sia attivo
    assert (
        api.patch(f"/api/v1/employees/{eid}", headers=h, json={"netsuite_id": "X"}).status_code
        == 200
    )


def test_presale_can_read_employees_but_not_change_them(api, session):
    admin_h, profile = _setup(session)
    eid = _create(api, admin_h, profile).json()["id"]
    h = auth(make_user(session, role="presale"))
    assert api.get(f"/api/v1/employees/{eid}", headers=h).status_code == 200
    assert (
        api.patch(f"/api/v1/employees/{eid}", headers=h, json={"is_active": False}).status_code
        == 403
    )


def test_list_employees_search_filters_and_order(api, session):
    h, profile = _setup(session)
    other = make_profile(session, name="Consultant")
    _create(api, h, profile, first_name="Mario", last_name="Rossi")
    _create(api, h, other, first_name="Anna", last_name="Bianchi")
    _create(api, h, profile, first_name="Zoe", last_name="Verdi", is_active=False)

    items = api.get("/api/v1/employees", headers=h).json()["items"]
    assert [i["last_name"] for i in items] == ["Bianchi", "Rossi", "Verdi"]
    assert api.get("/api/v1/employees?q=rossi", headers=h).json()["total"] == 1
    assert (
        api.get("/api/v1/employees?q=mario ros", headers=h).json()["total"] == 1
    )  # nome + cognome
    assert api.get("/api/v1/employees?is_active=false", headers=h).json()["total"] == 1
    assert api.get(f"/api/v1/employees?profile_id={other.id}", headers=h).json()["total"] == 1
    assert (
        api.get("/api/v1/employees?limit=1&offset=2", headers=h).json()["items"][0]["last_name"]
        == "Verdi"
    )
