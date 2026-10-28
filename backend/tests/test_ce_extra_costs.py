"""Costi vari sul CE: salvataggio, anteprima, versioni, duplicato e vincoli del database."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import CEExtraCost, CEVersion
from tests.ce_helpers import approved_ce, create, save, simple_content
from tests.factories import assert_rejected, make_ce, make_client, make_user
from tests.test_constraints import make_version

URL = "/api/v1/ce"

EXTRAS = [
    {"description": "Viaggi e trasferte", "cost": "1000.00", "markup_pct": "20.00"},
    {"description": "Licenze", "cost": "333.33", "markup_pct": "15.50"},
]


def with_extras(env, revision, extras=EXTRAS, **kw):
    content = simple_content(env, revision, **kw)  # 16 ore di Senior: 1.700 di ricavi, 660 di costi
    content["extra_costs"] = extras
    return content


def owner(env):
    return env.h(env.presale)


def test_extra_costs_are_saved_returned_and_added_to_the_total(api, env):
    created = create(api, env)
    saved = save(api, env, created["ce"]["id"], with_extras(env, 1))
    assert saved.status_code == 200, saved.text
    detail = saved.json()
    assert detail["extra_costs"] == EXTRAS  # stesso ordine, stessi valori
    calc = detail["calculation"]
    assert [e["revenue"] for e in calc["extra_costs"]] == ["1200.00", "385.00"]
    assert calc["extras"]["revenue"] == "1585.00" and calc["extras"]["cost"] == "1333.33"
    assert calc["total"]["revenue"] == "3285.00"  # 1.700 + 1.585
    assert calc["total"]["cost"] == "1993.33"  # 660 + 1.333,33
    assert calc["kpis"]["price_project"] == "3285.00"
    # lo stesso CE riletto dal database
    again = api.get(f"{URL}/{created['ce']['id']}", headers=owner(env)).json()
    assert again["extra_costs"] == EXTRAS and again["calculation"] == calc


def test_a_ce_without_extra_costs_is_unchanged(api, env):
    created = create(api, env)
    detail = save(api, env, created["ce"]["id"], simple_content(env, 1)).json()
    assert detail["extra_costs"] == [] and detail["calculation"]["extra_costs"] == []
    assert detail["calculation"]["extras"]["revenue"] == "0.00"
    assert detail["calculation"]["total"]["revenue"] == "1700.00"


def test_preview_matches_saving_and_writes_nothing(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    content = with_extras(env, 1)
    preview = api.post(f"{URL}/{ce_id}/calculate", headers=owner(env), json=content)
    assert preview.status_code == 200, preview.text
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 0
    saved = save(api, env, ce_id, content).json()
    assert preview.json() == saved["calculation"]


def test_saving_replaces_the_rows_and_an_empty_list_removes_them(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, with_extras(env, 1))
    second = save(api, env, ce_id, with_extras(env, 2, EXTRAS[:1]))
    assert [e["description"] for e in second.json()["extra_costs"]] == ["Viaggi e trasferte"]
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 1
    third = save(api, env, ce_id, with_extras(env, 3, []))
    assert third.json()["extra_costs"] == []
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 0


def test_rows_keep_the_order_they_were_sent_in(api, env):
    created = create(api, env)
    reversed_rows = list(reversed(EXTRAS))
    detail = save(api, env, created["ce"]["id"], with_extras(env, 1, reversed_rows)).json()
    assert [e["description"] for e in detail["extra_costs"]] == ["Licenze", "Viaggi e trasferte"]


@pytest.mark.parametrize(
    "row",
    [
        {"description": "X", "cost": "-1", "markup_pct": "0"},
        {"description": "X", "cost": "1.001", "markup_pct": "0"},
        {"description": "X", "cost": "10000000000", "markup_pct": "0"},
        {"description": "X", "cost": "1", "markup_pct": "-1"},
        {"description": "X", "cost": "1", "markup_pct": "1000.01"},
        {"description": "X", "cost": "1", "markup_pct": "1.234"},
        {"description": "", "cost": "1", "markup_pct": "0"},
        {"description": "   ", "cost": "1", "markup_pct": "0"},
        {"description": "X" * 301, "cost": "1", "markup_pct": "0"},
        {"cost": "1", "markup_pct": "0"},
        {"description": "X", "markup_pct": "0"},
    ],
)
def test_invalid_rows_are_rejected_and_nothing_is_saved(api, env, session, row):
    created = create(api, env)
    resp = save(api, env, created["ce"]["id"], with_extras(env, 1, [row]))
    assert resp.status_code == 422, resp.text
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 0


def test_more_than_one_hundred_rows_are_rejected(api, env):
    created = create(api, env)
    row = {"description": "X", "cost": "1", "markup_pct": "0"}
    assert save(api, env, created["ce"]["id"], with_extras(env, 1, [row] * 101)).status_code == 422


def test_markup_defaults_to_zero(api, env):
    created = create(api, env)
    detail = save(
        api, env, created["ce"]["id"], with_extras(env, 1, [{"description": "X", "cost": "50"}])
    ).json()
    assert detail["extra_costs"][0]["markup_pct"] == "0.00"
    assert detail["calculation"]["extra_costs"][0]["revenue"] == "50.00"


def test_the_approved_totals_include_the_extra_costs(api, env, session):
    approved = approved_ce(api, env, "PS-EXTRA-1", content=with_extras(env, 1))
    version = session.scalar(select(CEVersion).where(CEVersion.ce_id == approved["ce"]["id"]))
    assert version.approved_totals["revenue"] == "3285.00"
    assert version.approved_totals["cost"] == "1993.33"


def test_a_new_version_copies_the_rows_and_changes_do_not_touch_the_approved_one(api, env, session):
    approved = approved_ce(api, env, "PS-EXTRA-2", content=with_extras(env, 1))
    ce_id = approved["ce"]["id"]
    v2 = api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    assert v2.status_code == 201, v2.text
    assert v2.json()["extra_costs"] == EXTRAS
    assert v2.json()["calculation"]["total"]["revenue"] == "3285.00"
    # modifico la versione 2: la 1 resta com'era
    changed = save(api, env, ce_id, with_extras(env, v2.json()["version"]["revision"], EXTRAS[:1]))
    assert changed.status_code == 200, changed.text
    first = api.get(f"{URL}/{ce_id}/versions/1", headers=owner(env)).json()
    assert first["extra_costs"] == EXTRAS
    assert first["calculation"]["total"]["revenue"] == "3285.00"
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 3  # 2 + 1


def test_a_duplicate_starts_with_the_same_rows(api, env):
    approved = approved_ce(api, env, "PS-EXTRA-3", content=with_extras(env, 1))
    copy = api.post(
        f"{URL}/{approved['ce']['id']}/duplicate",
        headers=owner(env),
        json={"code": "PS-EXTRA-3-COPIA", "start_date": "2026-02-02", "end_date": "2026-05-29"},
    )
    assert copy.status_code == 201, copy.text
    assert copy.json()["extra_costs"] == EXTRAS
    assert copy.json()["calculation"]["extras"]["revenue"] == "1585.00"


def test_extra_costs_are_removed_with_their_version_and_can_not_be_orphaned(session):
    user, client = make_user(session), make_client(session)
    version = make_version(session, make_ce(session, user), user, client)
    session.add(CEExtraCost(version_id=version.id, position=0, description="X", cost=1))
    session.flush()
    session.delete(version)
    session.flush()
    assert session.scalar(select(func.count()).select_from(CEExtraCost)) == 0


def test_the_database_rejects_negative_costs_and_out_of_range_markups(session):
    user, client = make_user(session), make_client(session)
    version = make_version(session, make_ce(session, user), user, client)
    ok = {"version_id": version.id, "position": 0, "description": "X"}
    assert_rejected(
        session, "ck_ce_extra_costs_cost_non_negative", CEExtraCost(**ok, cost=Decimal("-0.01"))
    )
    assert_rejected(
        session,
        "ck_ce_extra_costs_markup_range",
        CEExtraCost(**ok, cost=1, markup_pct=Decimal("-0.01")),
    )
    assert_rejected(
        session,
        "ck_ce_extra_costs_markup_range",
        CEExtraCost(**ok, cost=1, markup_pct=Decimal("1000.01")),
    )
    session.add(CEExtraCost(**ok, cost=0, markup_pct=Decimal("1000")))
    session.flush()  # i limiti stessi sono ammessi


def test_viewer_sees_the_total_price_but_never_the_rows_their_cost_or_markup(api, env):
    approved = approved_ce(api, env, "PS-EXTRA-4", content=with_extras(env, 1))
    ce_id = approved["ce"]["id"]
    listing = api.get(f"{URL}/summaries", headers=env.h(env.viewer)).json()
    detail = api.get(f"{URL}/summaries/{ce_id}", headers=env.h(env.viewer)).json()
    assert listing["items"][0]["price"] == "3285.00"  # 1.700 di servizi + 1.585 di costi vari
    assert detail["total_revenue"] == "3285.00"
    text = str(listing) + str(detail)
    for secret in ("Viaggi", "Licenze", "1000.00", "333.33", "extra", "markup", "1993.33"):
        assert secret not in text, secret
