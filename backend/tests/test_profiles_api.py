from sqlalchemy import select

from app.models import AuditLog, ProfileRate
from tests.factories import make_profile, make_user
from tests.helpers import auth


def _admin(session):
    return auth(make_user(session, role="admin"))


def test_create_profile_and_unique_name(api, session):
    h = _admin(session)
    resp = api.post(
        "/api/v1/profiles",
        headers=h,
        json={"name": " Partner ", "sort_order": 10, "billability_target": "40"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Partner" and resp.json()["rates"] == []
    assert api.post("/api/v1/profiles", headers=h, json={"name": "PARTNER"}).status_code == 409
    assert (
        api.post(
            "/api/v1/profiles", headers=h, json={"name": "Altro", "billability_target": "101"}
        ).status_code
        == 422
    )
    assert api.post("/api/v1/profiles", headers=h, json={"name": ""}).status_code == 422


def test_rates_can_be_created_updated_and_deleted(api, session):
    h = _admin(session)
    pid = api.post("/api/v1/profiles", headers=h, json={"name": "Senior"}).json()["id"]
    url = f"/api/v1/profiles/{pid}/rates/2026"

    created = api.put(url, headers=h, json={"daily_price": "850", "daily_cost": "330.50"})
    assert created.status_code == 200
    assert created.json() == {"year": 2026, "daily_price": "850.00", "daily_cost": "330.50"}

    updated = api.put(url, headers=h, json={"daily_price": "900", "daily_cost": "330.50"})
    assert updated.json()["daily_price"] == "900.00"
    api.put(
        f"/api/v1/profiles/{pid}/rates/2027",
        headers=h,
        json={"daily_price": "950", "daily_cost": "350"},
    )

    detail = api.get(f"/api/v1/profiles/{pid}", headers=h).json()
    assert [r["year"] for r in detail["rates"]] == [2026, 2027]

    assert api.delete(url, headers=h).status_code == 204
    assert api.delete(url, headers=h).status_code == 404
    assert [r["year"] for r in api.get(f"/api/v1/profiles/{pid}", headers=h).json()["rates"]] == [
        2027
    ]

    actions = session.scalars(
        select(AuditLog.action).where(AuditLog.entity_type == "profile")
    ).all()
    assert {"create", "create_rate", "update_rate", "delete_rate"} <= set(actions)


def test_rate_validation(api, session):
    h = _admin(session)
    profile = make_profile(session)
    base = f"/api/v1/profiles/{profile.id}/rates"
    ok = {"daily_price": "100", "daily_cost": "50"}
    assert api.put(f"{base}/2026", headers=h, json={**ok, "daily_price": "-1"}).status_code == 422
    assert (
        api.put(f"{base}/2026", headers=h, json={**ok, "daily_cost": "10.123"}).status_code == 422
    )
    assert api.put(f"{base}/1999", headers=h, json=ok).status_code == 422
    assert api.put(f"{base}/2026", headers=h, json={"daily_price": "100"}).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert api.put(f"/api/v1/profiles/{missing}/rates/2026", headers=h, json=ok).status_code == 404
    assert session.scalar(select(ProfileRate.year)) is None


def test_update_profile(api, session):
    h = _admin(session)
    a = make_profile(session, name="Alfa")
    make_profile(session, name="Beta")
    assert (
        api.patch(f"/api/v1/profiles/{a.id}", headers=h, json={"name": "beta"}).status_code == 409
    )
    resp = api.patch(f"/api/v1/profiles/{a.id}", headers=h, json={"is_active": False, "band": "F"})
    assert (
        resp.status_code == 200 and resp.json()["is_active"] is False and resp.json()["band"] == "F"
    )
    assert api.patch(f"/api/v1/profiles/{a.id}", headers=h, json={"name": None}).status_code == 422


def test_list_profiles_orders_by_sort_order_and_filters_active(api, session):
    h = auth(make_user(session, role="presale"))  # il presale vede il listino
    make_profile(session, name="Zeta", sort_order=10)
    make_profile(session, name="Alfa", sort_order=20)
    make_profile(session, name="Spento", sort_order=5, is_active=False)
    assert [p["name"] for p in api.get("/api/v1/profiles", headers=h).json()] == [
        "Spento",
        "Zeta",
        "Alfa",
    ]
    assert [p["name"] for p in api.get("/api/v1/profiles?is_active=true", headers=h).json()] == [
        "Zeta",
        "Alfa",
    ]


def test_presale_cannot_change_the_price_list(api, session):
    profile = make_profile(session)
    h = auth(make_user(session, role="presale"))
    body = {"daily_price": "1", "daily_cost": "1"}
    assert (
        api.put(f"/api/v1/profiles/{profile.id}/rates/2026", headers=h, json=body).status_code
        == 403
    )
    assert api.post("/api/v1/profiles", headers=h, json={"name": "X"}).status_code == 403
