"""Calcolo di anteprima: stesso risultato del salvataggio, ma senza salvare nulla."""

from decimal import Decimal

from sqlalchemy import func, select

from app.models import CELine, CEVersion, CEVersionRate, Profile, ProfileRate
from tests.ce_helpers import create, real_ce_content, save, simple_content

URL = "/api/v1/ce"


def test_preview_matches_what_saving_would_produce(api, env):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    content = real_ce_content(env, 1)
    preview = api.post(f"{URL}/{ce_id}/calculate", headers=env.h(env.presale), json=content)
    assert preview.status_code == 200
    saved = save(api, env, ce_id, content).json()
    assert preview.json() == saved["calculation"]


def test_preview_does_not_change_anything(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, simple_content(env, 1, hours="8"))
    before = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    api.post(f"{URL}/{ce_id}/calculate", headers=env.h(env.presale), json=real_ce_content(env, 2))
    after = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    assert before == after  # contenuto, revisione e totali identici
    assert session.scalar(select(func.count()).select_from(CELine)) == 1


def test_preview_works_without_the_revision_and_for_other_users(api, env):
    created = create(api, env)
    content = simple_content(env, 1)
    del content["expected_revision"]
    resp = api.post(
        f"{URL}/{created['ce']['id']}/calculate", headers=env.h(env.other), json=content
    )
    assert resp.status_code == 200 and resp.json()["total"]["revenue"] == "1700.00"


def test_preview_prices_new_profiles_from_the_price_list_without_saving_them(api, env, session):
    created = create(api, env)
    late = Profile(name="Solo anteprima", sort_order=700)
    session.add(late)
    session.flush()
    session.add(
        ProfileRate(
            profile_id=late.id, year=2026, daily_price=Decimal("400"), daily_cost=Decimal("150")
        )
    )
    session.flush()
    body = simple_content(env, 1, hours="8")
    body["phases"][0]["lines"][0]["profile_id"] = str(late.id)
    resp = api.post(f"{URL}/{created['ce']['id']}/calculate", headers=env.h(env.presale), json=body)
    assert resp.json()["total"]["revenue"] == "400.00"
    assert resp.json()["profiles"][0]["profile_name"] == "Solo anteprima"
    saved_rates = session.scalars(
        select(CEVersionRate.profile_id).where(CEVersionRate.profile_id == late.id)
    ).all()
    assert saved_rates == []  # nessuna tariffa è stata congelata


def test_preview_reports_invalid_content(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    body["header"]["end_date"] = "2025-01-01"
    resp = api.post(f"{URL}/{created['ce']['id']}/calculate", headers=env.h(env.presale), json=body)
    assert resp.status_code == 422 and resp.json()["detail"]["issues"]


def test_preview_is_available_on_approved_ces_as_a_what_if(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, simple_content(env, 1))
    api.post(f"{URL}/{ce_id}/approve", headers=env.h(env.admin))
    what_if = api.post(
        f"{URL}/{ce_id}/calculate",
        headers=env.h(env.presale),
        json=simple_content(env, 2, hours="80"),
    )
    assert what_if.status_code == 200 and what_if.json()["total"]["revenue"] == "8500.00"
    current = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    assert current["calculation"]["total"]["revenue"] == "1700.00"
    assert session.scalar(select(func.count()).select_from(CEVersion)) == 1
