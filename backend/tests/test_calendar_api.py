from datetime import date

from sqlalchemy import func, select

from app.models import AuditLog, NonWorkingDay
from tests.factories import make_user
from tests.helpers import auth


def _admin(session):
    return auth(make_user(session, role="admin"))


def test_create_list_update_delete_day(api, session):
    h = _admin(session)
    created = api.post(
        "/api/v1/calendar",
        headers=h,
        json={"day": "2026-12-24", "kind": "company_closure", "description": "Chiusura natalizia"},
    )
    assert created.status_code == 201
    did = created.json()["id"]

    assert (
        api.post(
            "/api/v1/calendar",
            headers=h,
            json={"day": "2026-12-24", "kind": "holiday", "description": "x"},
        ).status_code
        == 409
    )
    assert (
        api.post(
            "/api/v1/calendar",
            headers=h,
            json={"day": "2026-12-31", "kind": "ponte", "description": "x"},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/v1/calendar",
            headers=h,
            json={"day": "1900-01-01", "kind": "holiday", "description": "x"},
        ).status_code
        == 422
    )

    patched = api.patch(
        f"/api/v1/calendar/{did}", headers=h, json={"description": "Natale", "kind": "holiday"}
    )
    assert patched.json()["description"] == "Natale" and patched.json()["kind"] == "holiday"
    assert api.patch(f"/api/v1/calendar/{did}", headers=h, json={"kind": None}).status_code == 422

    assert api.delete(f"/api/v1/calendar/{did}", headers=h).status_code == 204
    assert api.delete(f"/api/v1/calendar/{did}", headers=h).status_code == 404
    actions = session.scalars(
        select(AuditLog.action).where(AuditLog.entity_type == "non_working_day")
    ).all()
    assert sorted(actions) == ["create", "delete", "update"]


def test_list_filters_by_year_and_sorts_by_date(api, session):
    h = auth(make_user(session, role="presale"))
    session.add_all(
        [
            NonWorkingDay(day=date(2027, 1, 1), kind="holiday", description="b"),
            NonWorkingDay(day=date(2026, 12, 25), kind="holiday", description="a"),
            NonWorkingDay(day=date(2026, 1, 6), kind="holiday", description="c"),
        ]
    )
    session.flush()
    all_days = [d["day"] for d in api.get("/api/v1/calendar", headers=h).json()]
    assert all_days == ["2026-01-06", "2026-12-25", "2027-01-01"]
    assert [d["day"] for d in api.get("/api/v1/calendar?year=2026", headers=h).json()] == [
        "2026-01-06",
        "2026-12-25",
    ]
    assert api.get("/api/v1/calendar?year=1800", headers=h).status_code == 422


def test_generate_holidays_is_idempotent_and_keeps_existing_days(api, session):
    h = _admin(session)
    session.add(
        NonWorkingDay(day=date(2028, 12, 7), kind="company_closure", description="Già presente")
    )
    session.flush()

    first = api.post("/api/v1/calendar/generate-holidays", headers=h, json={"year": 2028})
    assert first.status_code == 200 and first.json() == {
        "year": 2028,
        "created": 12,
    }  # 13 meno quello esistente
    second = api.post("/api/v1/calendar/generate-holidays", headers=h, json={"year": 2028})
    assert second.json()["created"] == 0

    count = session.scalar(select(func.count()).select_from(NonWorkingDay))
    assert count == 13
    kept = session.scalar(select(NonWorkingDay).where(NonWorkingDay.day == date(2028, 12, 7)))
    assert kept.description == "Già presente"  # non sovrascritto
    assert (
        api.post("/api/v1/calendar/generate-holidays", headers=h, json={"year": 1500}).status_code
        == 422
    )
