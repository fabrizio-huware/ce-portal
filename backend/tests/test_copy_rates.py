"""Copia delle tariffe di un anno su altri anni, con adeguamento facoltativo."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, ProfileRate
from tests.factories import make_profile, make_user
from tests.helpers import auth

URL = "/api/v1/profiles/copy-rates"
D = Decimal


@pytest.fixture
def setup(session):
    admin = auth(make_user(session, role="admin"))
    senior = make_profile(session, name="Senior")
    junior = make_profile(session, name="Junior")
    vuoto = make_profile(session, name="Senza tariffe")
    session.add_all(
        [
            ProfileRate(profile_id=senior.id, year=2026, daily_price=D("850"), daily_cost=D("330")),
            ProfileRate(profile_id=junior.id, year=2026, daily_price=D("600"), daily_cost=D("250")),
        ]
    )
    session.commit()
    return admin, senior, junior, vuoto


def rate(session, profile, year):
    session.expire_all()
    return session.get(ProfileRate, (profile.id, year))


def post(api, admin, body, dry_run=None):
    params = {} if dry_run is None else {"dry_run": str(dry_run).lower()}
    return api.post(URL, headers=admin, params=params, json=body)


def test_the_default_is_a_preview_and_changes_nothing(api, session, setup):
    admin, senior, *_ = setup
    resp = post(api, admin, {"from_year": 2026, "to_years": [2027]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True and body["applied"] is False
    assert (body["created"], body["updated"], body["unchanged"]) == (2, 0, 0)
    assert rate(session, senior, 2027) is None


def test_it_copies_the_rates_to_one_or_more_years(api, session, setup):
    admin, senior, junior, vuoto = setup
    resp = post(api, admin, {"from_year": 2026, "to_years": [2027, 2028]}, dry_run=False)
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied"] is True and resp.json()["created"] == 4
    for year in (2027, 2028):
        assert rate(session, senior, year).daily_price == D("850.00")
        assert rate(session, senior, year).daily_cost == D("330.00")
        assert rate(session, junior, year).daily_price == D("600.00")
        assert rate(session, vuoto, year) is None  # senza tariffa di partenza: non si crea nulla
    assert rate(session, senior, 2026).daily_price == D("850.00")  # l'anno di partenza non cambia


def test_existing_rates_of_the_target_year_are_overwritten(api, session, setup):
    admin, senior, junior, _ = setup
    session.add(ProfileRate(profile_id=senior.id, year=2027, daily_price=D("1"), daily_cost=D("1")))
    session.add(
        ProfileRate(profile_id=junior.id, year=2027, daily_price=D("600"), daily_cost=D("250"))
    )
    session.commit()
    resp = post(api, admin, {"from_year": 2026, "to_years": [2027]}, dry_run=False)
    assert (resp.json()["created"], resp.json()["updated"], resp.json()["unchanged"]) == (0, 1, 1)
    assert rate(session, senior, 2027).daily_price == D("850.00")
    items = {i["profile_name"]: i for i in resp.json()["items"]}
    assert items["Senior"]["action"] == "updated" and items["Senior"]["old_price"] == "1.00"
    assert items["Junior"]["action"] == "unchanged"


def test_the_adjustment_applies_to_price_and_cost_and_rounds_to_the_cent(api, session, setup):
    admin, senior, junior, _ = setup
    body = {
        "from_year": 2026,
        "to_years": [2027],
        "price_adjust_pct": "3",
        "cost_adjust_pct": "2.5",
    }
    assert post(api, admin, body, dry_run=False).status_code == 200
    assert rate(session, senior, 2027).daily_price == D("875.50")  # 850 x 1,03
    assert rate(session, senior, 2027).daily_cost == D("338.25")  # 330 x 1,025
    assert rate(session, junior, 2027).daily_price == D("618.00")
    assert rate(session, junior, 2027).daily_cost == D("256.25")


def test_a_negative_adjustment_and_the_preview_values(api, setup):
    admin, *_ = setup
    body = {"from_year": 2026, "to_years": [2027], "price_adjust_pct": "-10"}
    items = {i["profile_name"]: i for i in post(api, admin, body).json()["items"]}
    assert items["Senior"]["new_price"] == "765.00" and items["Senior"]["new_cost"] == "330.00"


def test_the_copy_is_audited_with_its_origin(api, session, setup):
    admin, senior, *_ = setup
    post(api, admin, {"from_year": 2026, "to_years": [2027]}, dry_run=False)
    entry = session.scalars(
        select(AuditLog).where(AuditLog.entity_id == senior.id, AuditLog.action == "create_rate")
    ).one()
    assert entry.changes["copied_from"] == 2026 and entry.changes["year"] == 2027


@pytest.mark.parametrize(
    "body",
    [
        {"from_year": 2026, "to_years": []},
        {"from_year": 2026, "to_years": [2026]},
        {"from_year": 2026, "to_years": [2027, 2027]},
        {"from_year": 2026, "to_years": [1999]},
        {"from_year": 2026, "to_years": list(range(2027, 2038))},
        {"from_year": 2026, "to_years": [2027], "price_adjust_pct": "-91"},
        {"from_year": 2026, "to_years": [2027], "cost_adjust_pct": "101"},
        {"from_year": 2026, "to_years": [2027], "price_adjust_pct": "1.234"},
        {"from_year": 1999, "to_years": [2027]},
        {"to_years": [2027]},
    ],
)
def test_invalid_requests_are_rejected_and_change_nothing(api, session, setup, body):
    admin, senior, *_ = setup
    assert post(api, admin, body, dry_run=False).status_code == 422
    assert rate(session, senior, 2027) is None


def test_a_source_year_without_rates_is_a_clear_422(api, setup):
    admin, *_ = setup
    resp = post(api, admin, {"from_year": 2030, "to_years": [2031]}, dry_run=False)
    assert resp.status_code == 422 and "2030" in resp.json()["detail"]


def test_only_admins_can_copy_rates(api, session, setup):
    for role in ("presale", "viewer"):
        h = auth(make_user(session, role=role))
        assert (
            post(api, h, {"from_year": 2026, "to_years": [2027]}, dry_run=False).status_code == 403
        )
