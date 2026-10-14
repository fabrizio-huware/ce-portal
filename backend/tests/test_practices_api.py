"""Anagrafica Practice: creazione, modifica, disattivazione, practice di sistema e conteggio dei collaboratori."""

from sqlalchemy import func, select

from app.models import DEFAULT_PRACTICE, AuditLog, Employee, Practice
from tests.factories import make_practice, make_profile, make_user
from tests.helpers import auth

URL = "/api/v1/practices"


def _admin(session):
    return auth(make_user(session, role="admin"))


def _system_practice(session) -> Practice:
    """La practice di sistema esiste già dopo la migrazione (o la crea la prima assegnazione): qui si prende o si crea."""
    found = session.scalar(
        select(Practice).where(func.lower(Practice.name) == DEFAULT_PRACTICE.lower())
    )
    return found or make_practice(session, name=DEFAULT_PRACTICE)


def test_admin_creates_a_practice_and_the_name_is_trimmed(api, session):
    resp = api.post(URL, headers=_admin(session), json={"name": "  Data & AI  "})
    assert resp.status_code == 201
    body = resp.json()
    assert (body["name"], body["is_active"], body["employees_count"]) == ("Data & AI", True, 0)


def test_names_are_unique_ignoring_case(api, session):
    h = _admin(session)
    assert api.post(URL, headers=h, json={"name": "Cloud"}).status_code == 201
    for name in ("Cloud", "cloud", "CLOUD"):
        resp = api.post(URL, headers=h, json={"name": name})
        assert resp.status_code == 409 and "Esiste già" in resp.json()["detail"]


def test_empty_or_too_long_names_are_rejected(api, session):
    h = _admin(session)
    assert api.post(URL, headers=h, json={"name": "   "}).status_code == 422
    assert api.post(URL, headers=h, json={"name": "x" * 101}).status_code == 422
    assert api.post(URL, headers=h, json={}).status_code == 422


def test_list_counts_only_active_employees(api, session):
    h = _admin(session)
    profile = make_profile(session)
    cloud = make_practice(session, name="Cloud")
    make_practice(session, name="Data")
    for first, active in (("Ada", True), ("Bruno", True), ("Carla", False)):
        session.add(
            Employee(first_name=first, last_name="T", default_profile_id=profile.id,
                     practice_id=cloud.id, is_active=active)
        )  # fmt: skip
    session.flush()
    body = api.get(URL, headers=h).json()
    counts = {p["name"]: p["employees_count"] for p in body}
    assert counts["Cloud"] == 2 and counts["Data"] == 0  # Carla è disattivata: non conta
    assert [p["name"] for p in body] == sorted((p["name"] for p in body), key=str.lower)


def test_rename_and_duplicate_rename(api, session):
    h = _admin(session)
    a = make_practice(session, name="Cloud")
    make_practice(session, name="Data")
    ok = api.patch(f"{URL}/{a.id}", headers=h, json={"name": "Cloud & Infra"})
    assert ok.status_code == 200 and ok.json()["name"] == "Cloud & Infra"
    clash = api.patch(f"{URL}/{a.id}", headers=h, json={"name": "data"})
    assert clash.status_code == 409
    own = api.patch(
        f"{URL}/{a.id}", headers=h, json={"name": "CLOUD & INFRA"}
    )  # solo le maiuscole, la stessa practice
    assert own.status_code == 200


def test_null_fields_are_rejected_and_unknown_practice_is_404(api, session):
    h = _admin(session)
    a = make_practice(session, name="Cloud")
    assert api.patch(f"{URL}/{a.id}", headers=h, json={"name": None}).status_code == 422
    assert api.patch(f"{URL}/{a.id}", headers=h, json={"is_active": None}).status_code == 422
    assert (
        api.patch(
            f"{URL}/00000000-0000-0000-0000-000000000000", headers=h, json={"name": "X"}
        ).status_code
        == 404
    )


def test_deactivating_keeps_the_employees_but_it_cannot_be_chosen_again(api, session):
    h = _admin(session)
    profile = make_profile(session)
    cloud = make_practice(session, name="Cloud")
    emp = Employee(
        first_name="Ada", last_name="T", default_profile_id=profile.id, practice_id=cloud.id
    )
    session.add(emp)
    session.flush()
    assert (
        api.patch(f"{URL}/{cloud.id}", headers=h, json={"is_active": False}).json()["is_active"]
        is False
    )
    session.refresh(emp)
    assert emp.practice_id == cloud.id  # resta assegnata
    again = api.post(
        "/api/v1/employees", headers=h,
        json={"first_name": "Bruno", "last_name": "T", "default_profile_id": str(profile.id), "practice_id": str(cloud.id)},
    )  # fmt: skip
    assert again.status_code == 422 and "non è attiva" in again.json()["detail"]
    assert (
        api.patch(f"{URL}/{cloud.id}", headers=h, json={"is_active": True}).json()["is_active"]
        is True
    )


def test_the_system_practice_cannot_be_renamed_or_deactivated(api, session):
    h = _admin(session)
    system = _system_practice(session)
    assert api.patch(f"{URL}/{system.id}", headers=h, json={"name": "Altro"}).status_code == 409
    resp = api.patch(f"{URL}/{system.id}", headers=h, json={"is_active": False})
    assert resp.status_code == 409 and "di sistema" in resp.json()["detail"]
    assert (
        api.patch(f"{URL}/{system.id}", headers=h, json={"is_active": True}).status_code == 200
    )  # nessun cambio
    assert (
        api.post(URL, headers=h, json={"name": DEFAULT_PRACTICE.upper()}).status_code == 409
    )  # non si duplica


def test_lookup_is_available_to_presale_and_lists_every_practice(api, session):
    make_practice(session, name="Cloud")
    inactive = make_practice(session, name="Vecchia", is_active=False)
    resp = api.get(f"{URL}/lookup", headers=auth(make_user(session, role="presale")))
    assert resp.status_code == 200
    by_name = {p["name"]: p["is_active"] for p in resp.json()}
    assert by_name["Cloud"] is True and by_name[inactive.name] is False
    assert set(resp.json()[0]) == {"id", "name", "is_active"}  # vista minima


def test_only_admins_manage_practices_and_the_viewer_sees_nothing(api, session):
    presale, viewer = (
        auth(make_user(session, role="presale")),
        auth(make_user(session, role="viewer")),
    )
    a = make_practice(session, name="Cloud")
    for h, status in ((presale, 403), (viewer, 403)):
        assert api.get(URL, headers=h).status_code == status
        assert api.post(URL, headers=h, json={"name": "Nuova"}).status_code == status
        assert api.patch(f"{URL}/{a.id}", headers=h, json={"name": "X"}).status_code == status
    assert api.get(f"{URL}/lookup", headers=viewer).status_code == 403


def test_writes_are_audited(api, session):
    h = _admin(session)
    created = api.post(URL, headers=h, json={"name": "Cloud"}).json()
    api.patch(f"{URL}/{created['id']}", headers=h, json={"name": "Cloud 2"})
    entries = session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "practice").order_by(AuditLog.id)
    ).all()
    assert [e.action for e in entries] == ["create", "update"]
    assert session.scalar(select(Practice.name).where(Practice.id == created["id"])) == "Cloud 2"
