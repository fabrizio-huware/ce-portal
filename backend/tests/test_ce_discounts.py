"""Sconti sul CE: salvataggio, versioni, duplicato, viewer, integrazioni e vincoli del database."""

import pytest
from sqlalchemy import func, select

from app.models import CEDiscount, CEVersion
from tests.ce_helpers import approved_ce, create, save, simple_content
from tests.factories import assert_rejected, make_ce, make_client, make_user
from tests.test_constraints import make_version

URL = "/api/v1/ce"

DISCOUNTS = [
    {"description": "Sconto cliente storico", "kind": "amount", "value": "200.00"},
    {"description": "Sconto volume", "kind": "percent", "value": "10.00"},
]  # su 1.700 di servizi: 200 + 170 = 370


def with_discounts(env, revision, discounts=DISCOUNTS, **kw):
    content = simple_content(env, revision, **kw)  # 16 ore di Senior: 1.700 di ricavi, 660 di costi
    content["discounts"] = discounts
    return content


def owner(env):
    return env.h(env.presale)


def test_discounts_are_saved_returned_and_taken_off_the_price(api, env):
    created = create(api, env)
    saved = save(api, env, created["ce"]["id"], with_discounts(env, 1))
    assert saved.status_code == 200, saved.text
    detail = saved.json()
    assert detail["discounts"] == DISCOUNTS
    calc = detail["calculation"]
    assert [d["amount"] for d in calc["discount_items"]] == ["200.00", "170.00"]
    assert calc["discounts"]["revenue"] == "-370.00" and calc["discounts"]["cost"] == "0.00"
    assert calc["total"]["revenue"] == "1330.00" and calc["total"]["cost"] == "660.00"
    assert calc["kpis"]["price_project"] == "1330.00"
    again = api.get(f"{URL}/{created['ce']['id']}", headers=owner(env)).json()
    assert again["discounts"] == DISCOUNTS and again["calculation"] == calc


def test_a_ce_without_discounts_is_unchanged(api, env):
    created = create(api, env)
    detail = save(api, env, created["ce"]["id"], simple_content(env, 1)).json()
    assert detail["discounts"] == [] and detail["calculation"]["discount_items"] == []
    assert detail["calculation"]["total"]["revenue"] == "1700.00"


def test_saving_replaces_the_rows_and_an_empty_list_removes_them(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, with_discounts(env, 1))
    second = save(api, env, ce_id, with_discounts(env, 2, DISCOUNTS[:1]))
    assert [d["description"] for d in second.json()["discounts"]] == ["Sconto cliente storico"]
    third = save(api, env, ce_id, with_discounts(env, 3, []))
    assert third.json()["discounts"] == []
    assert session.scalar(select(func.count()).select_from(CEDiscount)) == 0


@pytest.mark.parametrize(
    "row",
    [
        {"description": "X", "kind": "amount", "value": "-1"},
        {"description": "X", "kind": "amount", "value": "1.001"},
        {"description": "X", "kind": "amount", "value": "10000000000"},
        {"description": "X", "kind": "percent", "value": "100.01"},
        {"description": "X", "kind": "percent", "value": "-1"},
        {"description": "X", "kind": "fixed", "value": "1"},
        {"description": "", "kind": "amount", "value": "1"},
        {"description": "   ", "kind": "amount", "value": "1"},
        {"description": "X", "value": "1"},
        {"description": "X", "kind": "amount"},
    ],
)
def test_invalid_rows_are_rejected_and_nothing_is_saved(api, env, session, row):
    created = create(api, env)
    resp = save(api, env, created["ce"]["id"], with_discounts(env, 1, [row]))
    assert resp.status_code == 422, resp.text
    assert session.scalar(select(func.count()).select_from(CEDiscount)) == 0


def test_more_than_one_hundred_rows_are_rejected(api, env):
    created = create(api, env)
    row = {"description": "X", "kind": "amount", "value": "1"}
    assert (
        save(api, env, created["ce"]["id"], with_discounts(env, 1, [row] * 101)).status_code == 422
    )


def test_a_discount_above_the_price_is_a_422_not_a_500(api, env, session):
    created = create(api, env)
    row = {"description": "Troppo", "kind": "amount", "value": "1700.01"}
    resp = save(api, env, created["ce"]["id"], with_discounts(env, 1, [row]))
    assert resp.status_code == 422, resp.text
    assert "supera il prezzo" in resp.text
    assert session.scalar(select(func.count()).select_from(CEDiscount)) == 0


def test_the_approved_totals_include_the_discounts(api, env, session):
    approved = approved_ce(api, env, "PS-DISC-1", content=with_discounts(env, 1))
    version = session.scalar(select(CEVersion).where(CEVersion.ce_id == approved["ce"]["id"]))
    assert version.approved_totals["revenue"] == "1330.00"
    assert version.approved_totals["cost"] == "660.00"


def test_a_new_version_copies_the_rows_and_changes_do_not_touch_the_approved_one(api, env, session):
    approved = approved_ce(api, env, "PS-DISC-2", content=with_discounts(env, 1))
    ce_id = approved["ce"]["id"]
    v2 = api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    assert v2.status_code == 201, v2.text
    assert v2.json()["discounts"] == DISCOUNTS
    assert v2.json()["calculation"]["total"]["revenue"] == "1330.00"
    changed = save(
        api, env, ce_id, with_discounts(env, v2.json()["version"]["revision"], DISCOUNTS[:1])
    )
    assert changed.status_code == 200, changed.text
    first = api.get(f"{URL}/{ce_id}/versions/1", headers=owner(env)).json()
    assert first["discounts"] == DISCOUNTS and first["calculation"]["total"]["revenue"] == "1330.00"
    assert session.scalar(select(func.count()).select_from(CEDiscount)) == 3  # 2 + 1


def test_a_duplicate_starts_with_the_same_rows(api, env):
    approved = approved_ce(api, env, "PS-DISC-3", content=with_discounts(env, 1))
    copy = api.post(
        f"{URL}/{approved['ce']['id']}/duplicate",
        headers=owner(env),
        json={"code": "PS-DISC-3-COPIA", "start_date": "2026-02-02", "end_date": "2026-05-29"},
    )
    assert copy.status_code == 201, copy.text
    assert copy.json()["discounts"] == DISCOUNTS
    assert copy.json()["calculation"]["discounts"]["revenue"] == "-370.00"


def test_viewer_sees_the_discounted_price_but_never_the_rows(api, env):
    approved = approved_ce(api, env, "PS-DISC-4", content=with_discounts(env, 1))
    ce_id = approved["ce"]["id"]
    listing = api.get(f"{URL}/summaries", headers=env.h(env.viewer)).json()
    detail = api.get(f"{URL}/summaries/{ce_id}", headers=env.h(env.viewer)).json()
    assert listing["items"][0]["price"] == "1330.00" and detail["total_revenue"] == "1330.00"
    assert {"name": "Sconti", "revenue": "-370.00"}.items() <= detail["phases"][-1].items()
    text = str(listing) + str(detail)
    for secret in ("storico", "volume", "200.00", "170.00", "percent", "discount"):
        assert secret not in text, secret


def test_discounts_are_removed_with_their_version(session):
    user, client = make_user(session), make_client(session)
    version = make_version(session, make_ce(session, user), user, client)
    session.add(
        CEDiscount(version_id=version.id, position=0, description="X", kind="amount", value=5)
    )
    session.flush()
    session.delete(version)
    session.flush()
    assert session.scalar(select(func.count()).select_from(CEDiscount)) == 0


def test_the_database_rejects_invalid_kinds_and_values(session):
    user, client = make_user(session), make_client(session)
    version = make_version(session, make_ce(session, user), user, client)
    ok = {"version_id": version.id, "position": 0, "description": "X"}
    assert_rejected(session, "ck_ce_discounts_kind_valid", CEDiscount(**ok, kind="fixed", value=1))
    assert_rejected(
        session, "ck_ce_discounts_value_non_negative", CEDiscount(**ok, kind="amount", value=-1)
    )
    assert_rejected(
        session, "ck_ce_discounts_percent_range", CEDiscount(**ok, kind="percent", value=101)
    )
    session.add(CEDiscount(**ok, kind="percent", value=100))
    session.add(
        CEDiscount(**{**ok, "position": 1}, kind="amount", value=500)
    )  # oltre 100 va bene in euro
    session.flush()
