"""Ricerca e filtri sui CE (cliente, progetto, codice, date da-a, stato, autore)."""

import pytest

from tests.ce_helpers import approved_ce, create, create_filled, simple_content
from tests.factories import make_client

URL = "/api/v1/ce"


@pytest.fixture
def world(api, env, session):
    """Tre CE: A approvato (Alfa), B bozza di un altro autore (Beta), C in approvazione (Alfa)."""
    other_client = make_client(session, name="Beta Srl")
    a = approved_ce(api, env, "PS-ALFA-1")  # 20/1 - 20/4/2026, progetto "Progetto di prova"
    api.put(
        f"{URL}/{a['ce']['id']}/content", headers=env.h(env.admin), json=simple_content(env, 2)
    )  # (approvato: rifiutato, serve solo a non lasciare dubbi)
    b = create(
        api,
        env,
        user=env.other,
        code="PS-BETA-2",
        client_id=str(other_client.id),
        project_name="AI assistant",
        start_date="2026-06-01",
        end_date="2026-09-30",
    )
    c = create_filled(
        api,
        env,
        "PS-GAMMA-3",
        content=simple_content(
            env, 1, project_name="Dashboard BI", start_date="2026-03-01", end_date="2026-05-31"
        ),
    )
    api.post(f"{URL}/{c['ce']['id']}/submit", headers=env.h(env.presale))
    return {
        "a": a["ce"]["id"],
        "b": b["ce"]["id"],
        "c": c["ce"]["id"],
        "beta": str(other_client.id),
    }


def codes(api, env, query="", user=None) -> list[str]:
    resp = api.get(f"{URL}?{query}", headers=env.h(user or env.presale))
    assert resp.status_code == 200, resp.text
    return sorted(i["code"] for i in resp.json()["items"])


def test_unfiltered_list_shows_all_with_summary_columns(api, env, world):
    resp = api.get(URL, headers=env.h(env.presale)).json()
    assert resp["total"] == 3
    row = next(i for i in resp["items"] if i["code"] == "PS-ALFA-1")
    assert (row["status"], row["version_number"], row["price"]) == ("approved", 1, "1700.00")
    assert row["client"]["name"] == "Cliente di prova" and row["owner"]["id"] == str(env.presale.id)
    assert row["deleted"] is False and row["margin_pct"] == "0.611765"


def test_filter_by_client(api, env, world):
    assert codes(api, env, f"client_id={world['beta']}") == ["PS-BETA-2"]
    assert codes(api, env, f"client_id={env.client.id}") == ["PS-ALFA-1", "PS-GAMMA-3"]


def test_filter_by_project_and_code_is_partial_and_case_insensitive(api, env, world):
    assert codes(api, env, "project=ASSISTANT") == ["PS-BETA-2"]
    assert codes(api, env, "project=dash") == ["PS-GAMMA-3"]
    assert codes(api, env, "code=gam") == ["PS-GAMMA-3"]
    assert codes(api, env, "code=PS-") == ["PS-ALFA-1", "PS-BETA-2", "PS-GAMMA-3"]
    assert codes(api, env, "project=%25") == []  # il simbolo % è letterale
    assert codes(api, env, "project=nessuno") == []


def test_date_filter_finds_projects_active_in_the_period(api, env, world):
    # A: 20/1-20/4 · B: 1/6-30/9 · C: 1/3-31/5 (2026)
    assert codes(api, env, "date_from=2026-04-21&date_to=2026-05-15") == ["PS-GAMMA-3"]
    assert codes(api, env, "date_from=2026-02-01&date_to=2026-02-28") == ["PS-ALFA-1"]
    assert codes(api, env, "date_from=2026-10-01&date_to=2026-12-31") == []
    assert codes(api, env, "date_from=2026-09-01") == ["PS-BETA-2"]
    assert codes(api, env, "date_to=2026-02-01") == ["PS-ALFA-1"]


def test_date_filter_boundaries_are_inclusive(api, env, world):
    assert "PS-ALFA-1" in codes(api, env, "date_from=2026-04-20")  # il giorno di fine conta
    assert "PS-ALFA-1" not in codes(api, env, "date_from=2026-04-21")
    assert "PS-BETA-2" in codes(api, env, "date_to=2026-06-01")  # il giorno di inizio conta
    assert "PS-BETA-2" not in codes(api, env, "date_to=2026-05-31")


def test_filter_by_status_and_author(api, env, world):
    assert codes(api, env, "status=approved") == ["PS-ALFA-1"]
    assert codes(api, env, "status=draft") == ["PS-BETA-2"]
    assert codes(api, env, "status=submitted") == ["PS-GAMMA-3"]
    assert codes(api, env, f"created_by={env.other.id}") == ["PS-BETA-2"]
    assert api.get(f"{URL}?status=perso", headers=env.h(env.presale)).status_code == 422


def test_filters_combine(api, env, world):
    assert codes(api, env, f"client_id={env.client.id}&status=submitted") == ["PS-GAMMA-3"]
    assert codes(api, env, f"client_id={env.client.id}&date_from=2026-06-01") == []


def test_pagination_and_order_by_last_update(api, env, world):
    page = api.get(f"{URL}?limit=2&offset=0", headers=env.h(env.presale)).json()
    assert (page["total"], len(page["items"]), page["limit"]) == (3, 2, 2)
    second = api.get(f"{URL}?limit=2&offset=2", headers=env.h(env.presale)).json()
    assert len(second["items"]) == 1
    seen = [i["code"] for i in page["items"]] + [i["code"] for i in second["items"]]
    assert len(set(seen)) == 3
    assert api.get(f"{URL}?limit=0", headers=env.h(env.presale)).status_code == 422


def test_list_shows_the_latest_version_of_each_ce(api, env, world):
    api.post(f"{URL}/{world['a']}/versions", headers=env.h(env.presale))
    row = next(
        i
        for i in api.get(URL, headers=env.h(env.presale)).json()["items"]
        if i["code"] == "PS-ALFA-1"
    )
    assert (row["version_number"], row["status"]) == (2, "draft")
    assert codes(api, env, "status=approved") == []  # la v1 approvata non è più "l'ultima"
