"""Dashboard portfolio: approvati e, a parte, la pipeline."""

from decimal import Decimal

from tests.dash_helpers import build_ce, make_employee, world

URL = "/api/v1/dashboard/portfolio"
D = Decimal


def get(api, env, query="", user=None):
    resp = api.get(f"{URL}?{query}", headers=env.h(user or env.presale))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_approved_and_pipeline_are_separate_series(api, env, session):
    world(api, env, session)
    body = get(api, env)
    a, p = body["approved"], body["pipeline"]
    assert (a["count"], D(a["revenue"]), D(a["cost"]), D(a["margin"]), D(a["days"])) == (
        3,
        D("30875"),
        D("11950"),
        D("18925"),
        D("40"),
    )
    assert a["margin_pct"] == str((D("18925") / D("30875")).quantize(D("0.000001")))
    assert (p["count"], D(p["revenue"]), D(p["cost"]), D(p["days"])) == (
        2,
        D("8100"),
        D("3130"),
        D("11"),
    )


def test_a_revision_in_progress_is_not_added_on_top_of_the_approved_version(api, env, session):
    world(api, env, session)
    body = get(api, env)
    assert body["revisions_in_progress"] == 1  # D v2 in bozza
    codes = {i["code"]: i for i in body["items"]}
    assert codes["PS-DASH-D"]["scope"] == "approved" and codes["PS-DASH-D"]["version_number"] == 1
    assert D(codes["PS-DASH-D"]["revenue"]) == D("3625")
    assert [i["code"] for i in body["items"]].count("PS-DASH-D") == 1


def test_when_the_new_version_is_approved_only_it_counts(api, env, session):
    w = world(api, env, session)
    d = w["ids"]["D"]
    from tests.ce_helpers import save, simple_content

    save(api, env, d, simple_content(env, 1, hours="80", profile="Specialist"))
    api.post(f"/api/v1/ce/{d}/approve", headers=env.h(env.admin))
    body = get(api, env)
    item = next(i for i in body["items"] if i["code"] == "PS-DASH-D")
    assert item["version_number"] == 2 and D(item["revenue"]) == D(
        "7250"
    )  # 10 giornate di Specialist
    assert body["revisions_in_progress"] == 0 and body["approved"]["count"] == 3


def test_items_carry_status_scope_and_margin(api, env, session):
    world(api, env, session)
    items = {i["code"]: i for i in get(api, env)["items"]}
    assert set(items) == {"PS-DASH-A", "PS-DASH-B", "PS-DASH-D", "PS-DASH-C", "PS-DASH-F"}
    c, f = items["PS-DASH-C"], items["PS-DASH-F"]
    assert (c["status"], c["scope"], D(c["margin"])) == ("draft", "pipeline", D("4450"))
    assert (f["status"], f["scope"]) == ("rejected", "pipeline")
    a = items["PS-DASH-A"]
    assert (a["client_name"], a["business_unit"], a["margin_pct"]) == (
        "Cliente di prova",
        "AI",
        str((D("14100") / D("23000")).quantize(D("0.000001"))),
    )


def test_without_pipeline_only_approved_ces_are_listed(api, env, session):
    world(api, env, session)
    body = get(api, env, "include_pipeline=false")
    assert body["pipeline"]["count"] == 0 and D(body["pipeline"]["revenue"]) == 0
    assert {i["scope"] for i in body["items"]} == {"approved"} and len(body["items"]) == 3


def test_breakdown_by_client_and_business_unit(api, env, session):
    world(api, env, session)
    body = get(api, env)
    clients = {g["label"]: g for g in body["by_client"]}
    assert set(clients) == {"Beta Srl", "Cliente di prova"}
    alfa, beta = clients["Cliente di prova"], clients["Beta Srl"]
    assert (
        alfa["approved"]["count"],
        D(alfa["approved"]["revenue"]),
        alfa["pipeline"]["count"],
        D(alfa["pipeline"]["revenue"]),
    ) == (1, D("23000"), 1, D("7250"))
    assert (
        beta["approved"]["count"],
        D(beta["approved"]["revenue"]),
        beta["pipeline"]["count"],
        D(beta["pipeline"]["revenue"]),
    ) == (2, D("7875"), 1, D("850"))
    units = {g["label"]: g for g in body["by_business_unit"]}
    assert set(units) == {"AI", "Data", "Non indicata"}
    assert D(units["AI"]["approved"]["revenue"]) == D("23000") and D(
        units["AI"]["pipeline"]["revenue"]
    ) == D("7250")
    assert D(units["Non indicata"]["approved"]["revenue"]) == D("3625")
    # la somma dei gruppi è il totale
    assert sum(D(g["approved"]["revenue"]) for g in body["by_client"]) == D(
        body["approved"]["revenue"]
    )


def test_breakdown_by_status(api, env, session):
    world(api, env, session)
    rows = {r["status"]: r for r in get(api, env)["by_status"]}
    assert (
        rows["approved"]["count"],
        rows["approved"]["scope"],
        D(rows["approved"]["revenue"]),
    ) == (3, "approved", D("30875"))
    assert (rows["draft"]["count"], rows["draft"]["scope"], D(rows["draft"]["revenue"])) == (
        1,
        "pipeline",
        D("7250"),
    )
    assert rows["rejected"]["label"] == "Rifiutato" and "submitted" not in rows


def test_monthly_view_adds_up_and_excludes_contingency(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api, env, "PS-DASH-CONT", lines=[("Senior", 80, ada)], contingency="10", state="approved"
    )  # 8.500 + 850
    body = get(api, env)
    months = body["by_month"]
    assert [m["month"] for m in months] == ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    monthly_revenue = sum(D(m["approved"]["revenue"]) for m in months)
    assert abs(monthly_revenue - D("8500")) < D("0.05")  # senza i 850 di contingency
    assert D(body["approved"]["revenue"]) == D("9350")  # i totali interi la includono
    assert sum(D(m["approved"]["days"]) for m in months) == D("10")
    assert (
        all(D(m["pipeline"]["revenue"]) == 0 for m in months)
        and body["monthly_excludes_contingency"] is True
    )


def test_period_filter_selects_overlapping_ces_and_limits_the_months(api, env, session):
    world(api, env, session)
    # A: 20/1-20/4 · B: 1/3-30/6 · D: 20/1-20/4 · C: 1/2-31/3 · F: 1/3-30/4
    only_june = get(api, env, "date_from=2026-06-01&date_to=2026-06-30")
    assert [i["code"] for i in only_june["items"]] == ["PS-DASH-B"]
    assert [m["month"] for m in only_june["by_month"]] == ["2026-06-01"]
    # il totale resta quello intero del CE, non solo il mese filtrato
    assert D(only_june["approved"]["revenue"]) == D("4250")
    assert (
        get(api, env, "date_from=2026-04-20&date_to=2026-04-20")["approved"]["count"] == 3
    )  # estremi inclusi
    assert (
        get(api, env, "date_from=2026-04-21&date_to=2026-05-31")["approved"]["count"] == 1
    )  # solo B
    assert get(api, env, "date_from=2027-01-01")["approved"]["count"] == 0


def test_client_and_business_unit_filters(api, env, session):
    w = world(api, env, session)
    assert {i["code"] for i in get(api, env, f"client_id={w['beta'].id}")["items"]} == {
        "PS-DASH-B",
        "PS-DASH-D",
        "PS-DASH-F",
    }
    assert {i["code"] for i in get(api, env, "business_unit=ai")["items"]} == {
        "PS-DASH-A",
        "PS-DASH-C",
    }  # senza maiuscole
    assert get(api, env, "business_unit=inesistente")["items"] == []


def test_deleted_ces_are_excluded(api, env, session):
    w = world(api, env, session)
    api.delete(f"/api/v1/ce/{w['ids']['A']}", headers=env.h(env.admin))
    body = get(api, env)
    assert "PS-DASH-A" not in {i["code"] for i in body["items"]} and body["approved"]["count"] == 2


def test_empty_portfolio_has_zero_totals_and_no_percentages(api, env):
    body = get(api, env)
    assert body["approved"] == {
        "count": 0,
        "revenue": "0",
        "cost": "0",
        "margin": "0",
        "margin_pct": None,
        "days": "0",
    }
    assert body["items"] == [] and body["by_month"] == [] and body["revisions_in_progress"] == 0


def test_invalid_period_is_rejected(api, env):
    assert (
        api.get(
            f"{URL}?date_from=2026-05-01&date_to=2026-04-01", headers=env.h(env.presale)
        ).status_code
        == 422
    )
    assert api.get(f"{URL}?date_from=ieri", headers=env.h(env.presale)).status_code == 422


def test_admin_sees_the_same_numbers(api, env, session):
    world(api, env, session)
    assert get(api, env, user=env.admin)["approved"] == get(api, env)["approved"]
