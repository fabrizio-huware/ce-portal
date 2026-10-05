from sqlalchemy import select

from app.models import AuditLog, User
from tests.factories import make_user
from tests.helpers import auth


def _admin(session):
    admin = make_user(session, role="admin")
    return admin, auth(admin)


def _audit(session, entity="user"):
    return list(session.scalars(select(AuditLog).where(AuditLog.entity_type == entity)))


def test_admin_creates_user_with_normalized_email_and_audit(api, session):
    admin, h = _admin(session)
    resp = api.post(
        "/api/v1/users",
        headers=h,
        json={
            "email": "  Nuovo.Utente@Huware.COM ",
            "full_name": "  Nuovo Utente ",
            "role": "presale",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "nuovo.utente@huware.com"
    assert body["full_name"] == "Nuovo Utente"
    assert body["is_active"] is True and body["last_login_at"] is None
    entries = [a for a in _audit(session) if a.action == "create"]
    assert len(entries) == 1 and entries[0].user_id == admin.id


def test_create_user_validations(api, session):
    _, h = _admin(session)
    make_user(session, email="esiste@huware.com")
    url = "/api/v1/users"
    ok = {"email": "x@huware.com", "full_name": "X", "role": "viewer"}
    assert api.post(url, headers=h, json={**ok, "email": "ESISTE@huware.com"}).status_code == 409
    assert api.post(url, headers=h, json={**ok, "email": "x@gmail.com"}).status_code == 422
    assert api.post(url, headers=h, json={**ok, "email": "non-una-email"}).status_code == 422
    assert api.post(url, headers=h, json={**ok, "role": "boss"}).status_code == 422
    assert api.post(url, headers=h, json={**ok, "full_name": "  "}).status_code == 422
    assert (
        api.post(url, headers=h, json={**ok, "is_active": False}).status_code == 422
    )  # campo ignoto


def test_list_users_filters_search_and_pagination(api, session):
    _, h = _admin(session)
    make_user(session, role="presale", email="anna.verdi@huware.com", full_name="Anna Verdi")
    make_user(session, role="viewer", email="bruno.neri@huware.com", full_name="Bruno Neri")
    make_user(
        session, role="viewer", email="carla.blu@huware.com", full_name="Carla Blu", is_active=False
    )

    body = api.get("/api/v1/users", headers=h).json()
    assert body["total"] == 4 and body["limit"] == 50 and body["offset"] == 0

    assert api.get("/api/v1/users?role=viewer", headers=h).json()["total"] == 2
    assert api.get("/api/v1/users?is_active=false", headers=h).json()["total"] == 1
    assert [
        u["full_name"] for u in api.get("/api/v1/users?q=verdi", headers=h).json()["items"]
    ] == ["Anna Verdi"]
    assert api.get("/api/v1/users?q=NERI@huware", headers=h).json()["total"] == 1

    page = api.get("/api/v1/users?limit=2&offset=1", headers=h).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["offset"] == 1
    assert api.get("/api/v1/users?limit=0", headers=h).status_code == 422
    assert api.get("/api/v1/users?limit=500", headers=h).status_code == 422


def test_search_treats_wildcards_literally(api, session):
    _, h = _admin(session)
    make_user(session, email="a@huware.com", full_name="Cento%Per_Cento")
    assert api.get("/api/v1/users?q=%25", headers=h).json()["total"] == 1
    assert api.get("/api/v1/users?q=_", headers=h).json()["total"] == 1


def test_update_user_and_audit(api, session):
    admin, h = _admin(session)
    target = make_user(session, role="viewer", full_name="Vecchio Nome")
    resp = api.patch(
        f"/api/v1/users/{target.id}", headers=h, json={"role": "presale", "full_name": "Nuovo Nome"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "presale" and resp.json()["full_name"] == "Nuovo Nome"
    update = [a for a in _audit(session) if a.action == "update"][0]
    assert update.changes["role"] == ["viewer", "presale"]


def test_update_without_changes_writes_no_audit(api, session):
    _, h = _admin(session)
    target = make_user(session, role="viewer")
    assert (
        api.patch(f"/api/v1/users/{target.id}", headers=h, json={"role": "viewer"}).status_code
        == 200
    )
    assert [a for a in _audit(session) if a.action == "update"] == []


def test_update_rejects_nulls_and_unknown_user(api, session):
    _, h = _admin(session)
    target = make_user(session)
    assert (
        api.patch(f"/api/v1/users/{target.id}", headers=h, json={"role": None}).status_code == 422
    )
    assert (
        api.patch(
            f"/api/v1/users/{target.id}", headers=h, json={"email": "x@huware.com"}
        ).status_code
        == 422
    )
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        api.patch(f"/api/v1/users/{missing}", headers=h, json={"role": "viewer"}).status_code == 404
    )
    assert api.get(f"/api/v1/users/{missing}", headers=h).status_code == 404


def test_last_active_admin_cannot_be_demoted_or_deactivated(api, session):
    admin, h = _admin(session)
    url = f"/api/v1/users/{admin.id}"
    assert api.patch(url, headers=h, json={"role": "presale"}).status_code == 409
    assert api.patch(url, headers=h, json={"is_active": False}).status_code == 409
    session.refresh(admin)
    assert admin.role == "admin" and admin.is_active


def test_admin_can_step_down_when_another_active_admin_exists(api, session):
    admin, h = _admin(session)
    other = make_user(session, role="admin")
    assert (
        api.patch(f"/api/v1/users/{admin.id}", headers=h, json={"role": "presale"}).status_code
        == 200
    )
    # ora other è l'unico admin attivo: non può essere toccato
    h2 = auth(other)
    assert (
        api.patch(f"/api/v1/users/{other.id}", headers=h2, json={"is_active": False}).status_code
        == 409
    )


def test_inactive_admins_do_not_count_as_other_admins(api, session):
    admin, h = _admin(session)
    make_user(session, role="admin", is_active=False)
    assert (
        api.patch(f"/api/v1/users/{admin.id}", headers=h, json={"role": "viewer"}).status_code
        == 409
    )


def test_deactivating_non_admin_users_is_always_allowed(api, session):
    _, h = _admin(session)
    target = make_user(session, role="presale")
    assert (
        api.patch(f"/api/v1/users/{target.id}", headers=h, json={"is_active": False}).status_code
        == 200
    )
    assert session.get(User, target.id).is_active is False
