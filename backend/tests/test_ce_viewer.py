"""Il viewer vede solo l'ultima versione approvata e solo i dati riassuntivi: mai costi o righe."""

import json

import pytest

from tests.ce_helpers import (
    approved_ce,
    create,
    create_filled,
    real_ce_content,
    save,
    simple_content,
)

URL = "/api/v1/ce"

# Dati che il viewer non deve MAI ricevere, né come chiave né come valore.
FORBIDDEN_KEYS = {
    "cost",
    "margin",
    "margin_pct",
    "cost_ratio",
    "hours",
    "rates",
    "daily_cost",
    "daily_price",
    "activity",
    "lines",
    "profile_id",
    "profile_name",
    "employee_id",
    "signed_price",
    "price_min",
    "max_discount_pct",
    "notes",
    "sf_opportunity",
    "business_unit",
    "owner",
    "fee_media_min",
    "calculation",
    "monthly",
    "months",
    "allocations",
    "summary",
    "approved_totals",
}
LIST_KEYS = {
    "ce_id",
    "code",
    "client_name",
    "project_name",
    "start_date",
    "end_date",
    "version_number",
    "approved_at",
    "price",
}
DETAIL_KEYS = LIST_KEYS - {"price"} | {
    "days_project_management",
    "days_delivery",
    "days_total",
    "phases",
    "total_revenue",
}


def all_keys(node) -> set[str]:
    if isinstance(node, dict):
        return set(node) | set().union(*(all_keys(v) for v in node.values()), set())
    if isinstance(node, list):
        return set().union(*(all_keys(v) for v in node), set())
    return set()


def viewer(env):
    return env.h(env.viewer)


@pytest.fixture
def real(api, env):
    """Il CE reale, approvato: 47.162,50 di ricavi, 20.200,00 di costi."""
    return approved_ce(
        api,
        env,
        "PS-REAL-1",
        content=real_ce_content(
            env, 1, sf_opportunity="006SECRET", notes="Nota interna", max_discount_pct="5"
        ),
    )


def test_viewer_list_has_only_the_allowed_fields(api, env, real):
    resp = api.get(f"{URL}/summaries", headers=viewer(env))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert set(body["items"][0]) == LIST_KEYS
    assert (
        body["items"][0]["price"] == "47162.50"
        and body["items"][0]["client_name"] == "Cliente di prova"
    )


def test_viewer_detail_shows_management_delivery_days_phase_revenue_and_total(api, env, real):
    detail = api.get(f"{URL}/summaries/{real['ce']['id']}", headers=viewer(env)).json()
    assert set(detail) == DETAIL_KEYS
    assert detail["days_project_management"] == "10.00000"
    assert detail["days_delivery"] == "48.50000" and detail["days_total"] == "58.50000"
    assert detail["total_revenue"] == "47162.50"
    phases = {p["name"]: p["revenue"] for p in detail["phases"]}
    assert phases["PM"] == "10375.00" and phases["TA"] == "20200.00"
    assert [p["name"] for p in detail["phases"]][:3] == ["PM", "AN", "SD"]
    from decimal import Decimal

    assert sum(Decimal(p["revenue"]) for p in detail["phases"]) == Decimal(detail["total_revenue"])


@pytest.mark.parametrize("path", ["list", "detail"])
def test_viewer_responses_never_contain_costs_margins_or_rows(api, env, real, path):
    url = f"{URL}/summaries" if path == "list" else f"{URL}/summaries/{real['ce']['id']}"
    resp = api.get(url, headers=viewer(env))
    body = resp.json()
    assert all_keys(body).isdisjoint(FORBIDDEN_KEYS), all_keys(body) & FORBIDDEN_KEYS
    text = json.dumps(body)
    # valori che non possono coincidere con un ricavo: margine, costi per profilo, percentuali
    # (il costo totale 20.200 coincide per caso con il ricavo della fase TA: non è un buon indicatore)
    for secret in (
        "10220",
        "4620",
        "2160",
        "0.5716",
        "0.4283",
        "26962",
        "Sprint",
        "Specialist",
        "Senior",
        "Manager",
        "006SECRET",
        "Nota interna",
        "806.2",
    ):
        assert secret not in text, secret


def test_contingency_is_included_in_phase_revenue_so_phases_add_up(api, env):
    content = real_ce_content(env, 1)
    content["phases"][0]["contingency_pct"] = "20"  # PM
    approved = approved_ce(api, env, "PS-CONT-1", content=content)
    detail = api.get(f"{URL}/summaries/{approved['ce']['id']}", headers=viewer(env)).json()
    from decimal import Decimal

    assert {p["name"]: p["revenue"] for p in detail["phases"]}["PM"] == "12450.00"  # 10.375 + 20%
    assert detail["total_revenue"] == "49237.50"
    assert sum(Decimal(p["revenue"]) for p in detail["phases"]) == Decimal(detail["total_revenue"])


def test_unapproved_ces_do_not_exist_for_the_viewer(api, env):
    draft = create_filled(api, env, "PS-DRAFT-1")
    submitted = create_filled(api, env, "PS-SUBM-1")
    api.post(f"{URL}/{submitted['ce']['id']}/submit", headers=env.h(env.presale))
    empty = create(api, env, code="PS-EMPTY-1")
    assert api.get(f"{URL}/summaries", headers=viewer(env)).json()["total"] == 0
    for ce in (draft, submitted, empty):
        assert api.get(f"{URL}/summaries/{ce['ce']['id']}", headers=viewer(env)).status_code == 404
    assert (
        api.get(
            f"{URL}/summaries/00000000-0000-0000-0000-000000000000", headers=viewer(env)
        ).status_code
        == 404
    )


def test_viewer_keeps_seeing_the_approved_version_while_a_new_one_is_in_progress(api, env):
    approved = approved_ce(api, env, "PS-NEWV-1")  # 1.700
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=env.h(env.presale))
    save(api, env, ce_id, simple_content(env, 1, hours="80"))  # v2 in bozza: 8.500
    seen = api.get(f"{URL}/summaries/{ce_id}", headers=viewer(env)).json()
    assert (seen["version_number"], seen["total_revenue"]) == (1, "1700.00")
    api.post(f"{URL}/{ce_id}/approve", headers=env.h(env.admin))
    seen = api.get(f"{URL}/summaries/{ce_id}", headers=viewer(env)).json()
    assert (seen["version_number"], seen["total_revenue"]) == (2, "8500.00")
    assert (
        api.get(f"{URL}/summaries", headers=viewer(env)).json()["items"][0]["version_number"] == 2
    )


def test_viewer_search_filters(api, env, real):
    assert api.get(f"{URL}/summaries?code=real", headers=viewer(env)).json()["total"] == 1
    assert api.get(f"{URL}/summaries?project=nessuno", headers=viewer(env)).json()["total"] == 0
    assert (
        api.get(f"{URL}/summaries?client_id={env.client.id}", headers=viewer(env)).json()["total"]
        == 1
    )
    assert (
        api.get(f"{URL}/summaries?date_from=2026-04-20", headers=viewer(env)).json()["total"] == 1
    )
    assert (
        api.get(f"{URL}/summaries?date_from=2026-04-21", headers=viewer(env)).json()["total"] == 0
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", ""),
        ("get", "/{id}"),
        ("get", "/{id}/versions"),
        ("get", "/{id}/versions/1"),
        ("get", "/{id}/history"),
        ("post", "/{id}/calculate"),
        ("put", "/{id}/content"),
    ],
)
def test_viewer_cannot_reach_any_full_endpoint(api, env, real, method, path):
    url = URL + path.format(id=real["ce"]["id"])
    resp = getattr(api, method)(
        url, headers=viewer(env), **({"json": {}} if method in ("post", "put") else {})
    )
    assert resp.status_code == 403


def test_editors_can_use_the_reduced_view_too(api, env, real):
    assert api.get(f"{URL}/summaries", headers=env.h(env.presale)).json()["total"] == 1
    assert (
        api.get(f"{URL}/summaries/{real['ce']['id']}", headers=env.h(env.admin)).status_code == 200
    )
