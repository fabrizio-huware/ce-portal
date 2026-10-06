"""Dashboard carico risorse: giorni, ore e FTE per mese; sovraccarico sopra il 100%."""

from datetime import date
from decimal import Decimal

from app.services.dashboards import default_window
from tests.ce_helpers import add_closures, save, simple_content
from tests.dash_helpers import build_ce, make_employee, world

URL = "/api/v1/dashboard/resources"
D = Decimal
WINDOW = "date_from=2026-01-01&date_to=2026-06-30"


def get(api, env, query=WINDOW, user=None):
    resp = api.get(f"{URL}?{query}", headers=env.h(user or env.presale))
    assert resp.status_code == 200, resp.text
    return resp.json()


def row(body, kind, name):
    return next(r for r in body[kind] if r["name"] == name)


def days(r):
    return [D(c["days"]) for c in r["cells"]]


def test_default_window_is_this_month_plus_eleven():
    assert default_window(date(2026, 10, 6)) == (date(2026, 10, 1), date(2027, 9, 1))
    assert default_window(date(2026, 1, 31)) == (date(2026, 1, 1), date(2026, 12, 1))
    assert default_window(date(2026, 12, 15)) == (date(2026, 12, 1), date(2027, 11, 1))


def test_months_and_capacity_come_from_the_general_calendar(api, env, session):
    add_closures(
        session, date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 21)
    )  # lun, mar, sab (non conta)
    world(api, env, session)
    body = get(api, env)
    assert [m["month"] for m in body["months"]] == [f"2026-0{i}-01" for i in range(1, 7)]
    assert [m["capacity_days"] for m in body["months"]] == [
        22,
        18,
        22,
        22,
        21,
        22,
    ]  # febbraio: 20 - 2 giorni feriali
    assert body["overload_threshold_fte"] == "1" and body["include_pipeline"] is False


def test_each_ce_own_non_working_days_do_not_change_the_reference_capacity(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    ce_id = build_ce(api, env, "PS-RES-NW", lines=[("Senior", 80, ada)], state="approved")
    ce = api.get(f"/api/v1/ce/{ce_id}", headers=env.h(env.admin)).json()
    assert ce["calculation"]["months"][0]["non_working"] == 0
    body = get(api, env)
    assert body["months"][0]["capacity_days"] == 22  # il calendario generale non ha chiusure


def test_employee_rows_sum_the_days_of_their_ces(api, env, session):
    world(api, env, session)
    body = get(api, env)
    ada, bruno = row(body, "employees", "Ada Lovelace"), row(body, "employees", "Bruno Neri")
    assert ada["profile_name"] == "Senior" and bruno["profile_name"] == "Specialist"
    assert ada["total_days"] == "15.00000" or D(ada["total_days"]) == D("15")  # 10 (A) + 5 (B)
    assert D(bruno["total_days"]) == D("25")  # 20 (A) + 5 (D v1)
    assert sum(days(ada)) == D("15") and sum(days(bruno)) == D("25")
    assert [c["days_pipeline"] for c in ada["cells"]] == [
        "0"
    ] * 6  # la pipeline non è inclusa di default


def test_fte_is_days_over_capacity_and_hours_are_days_times_eight(api, env, session):
    world(api, env, session)
    body = get(api, env)
    ada = row(body, "employees", "Ada Lovelace")
    for cell, month in zip(ada["cells"], body["months"], strict=True):
        if D(cell["days"]) > 0:
            assert D(cell["hours"]) == D(cell["days"]) * 8
            assert D(cell["fte"]) == (D(cell["days"]) / D(month["capacity_days"])).quantize(
                D("0.000001")
            )
        else:
            assert cell["fte"] == "0.000000" or D(cell["fte"]) == 0
    assert all(not c["overloaded"] for c in ada["cells"]) and ada["overloaded_months"] == 0


def test_a_person_above_100_percent_is_flagged_overloaded(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api,
        env,
        "PS-RES-BIG",
        start="2026-09-01",
        end="2026-09-30",
        lines=[("Senior", 400, ada)],
        state="approved",
    )
    body = get(api, env, "date_from=2026-09-01&date_to=2026-09-30")
    r = row(body, "employees", "Ada L")
    cell = r["cells"][0]
    assert D(cell["days"]) == D("50") and D(cell["fte"]) > 1 and cell["overloaded"] is True
    assert r["overloaded_months"] == 1
    assert (
        row(body, "profiles", "Senior")["overloaded_months"] == 0
    )  # per i profili l'avviso non ha senso


def test_exactly_100_percent_is_not_overloaded_and_just_above_is(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    # settembre 2026: 22 giorni lavorativi = 176 ore
    build_ce(
        api,
        env,
        "PS-RES-100",
        start="2026-09-01",
        end="2026-09-30",
        lines=[("Senior", 176, ada)],
        state="approved",
    )
    cell = row(get(api, env, "date_from=2026-09-01&date_to=2026-09-30"), "employees", "Ada L")[
        "cells"
    ][0]
    assert D(cell["fte"]) == D("1.000000") and cell["overloaded"] is False
    build_ce(
        api,
        env,
        "PS-RES-101",
        start="2026-09-01",
        end="2026-09-30",
        lines=[("Senior", "0.08", ada)],
        state="approved",
    )
    cell = row(get(api, env, "date_from=2026-09-01&date_to=2026-09-30"), "employees", "Ada L")[
        "cells"
    ][0]
    assert D(cell["fte"]) > 1 and cell["overloaded"] is True  # 22,01 giorni su 22


def test_load_adds_up_across_ces_for_the_same_person(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    for code, hours in (("PS-RES-X1", 100), ("PS-RES-X2", 100)):
        build_ce(
            api,
            env,
            code,
            start="2026-09-01",
            end="2026-09-30",
            lines=[("Senior", hours, ada)],
            state="approved",
        )
    cell = row(get(api, env, "date_from=2026-09-01&date_to=2026-09-30"), "employees", "Ada L")[
        "cells"
    ][0]
    assert D(cell["days"]) == D("25") and cell["overloaded"] is True  # 12,5 + 12,5 giorni su 22


def test_lines_without_a_collaborator_count_on_the_profile_only(api, env, session):
    build_ce(
        api,
        env,
        "PS-RES-UN",
        lines=[("Senior", 80, None), ("Specialist", 40, None)],
        state="approved",
    )
    body = get(api, env)
    assert body["employees"] == []
    senior = row(body, "profiles", "Senior")
    assert D(senior["total_days"]) == D("10") and D(senior["unassigned_days"]) == D("10")
    assert D(row(body, "profiles", "Specialist")["unassigned_days"]) == D("5")


def test_profile_rows_include_assigned_and_unassigned_days(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api, env, "PS-RES-MIX", lines=[("Senior", 80, ada), ("Senior", 40, None)], state="approved"
    )
    senior = row(get(api, env), "profiles", "Senior")
    assert D(senior["total_days"]) == D("15") and D(senior["unassigned_days"]) == D("5")


def test_pipeline_is_kept_apart_and_counts_towards_overload_only_when_included(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api,
        env,
        "PS-RES-APP",
        start="2026-09-01",
        end="2026-09-30",
        lines=[("Senior", 120, ada)],
        state="approved",
    )
    build_ce(
        api, env, "PS-RES-PIPE", start="2026-09-01", end="2026-09-30", lines=[("Senior", 80, ada)]
    )  # bozza
    q = "date_from=2026-09-01&date_to=2026-09-30"
    without = row(get(api, env, q), "employees", "Ada L")["cells"][0]
    assert D(without["days"]) == D("15") and without["overloaded"] is False
    with_pipeline = get(api, env, q + "&include_pipeline=true")
    cell = row(with_pipeline, "employees", "Ada L")["cells"][0]
    assert (D(cell["days_approved"]), D(cell["days_pipeline"]), D(cell["days"])) == (
        D("15"),
        D("10"),
        D("25"),
    )
    assert (
        cell["overloaded"] is True
        and with_pipeline["include_pipeline"] is True
        and with_pipeline["ces_count"] == 2
    )


def test_only_the_latest_approved_version_counts(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    ce_id = build_ce(api, env, "PS-RES-V2", lines=[("Senior", 80, ada)], state="approved")
    api.post(f"/api/v1/ce/{ce_id}/versions", headers=env.h(env.presale))
    content = simple_content(env, 1, hours="40")
    content["phases"][0]["lines"][0]["employee_id"] = str(ada.id)
    content["header"].update(start_date="2026-01-20", end_date="2026-04-20")
    assert save(api, env, ce_id, content).status_code == 200
    assert D(row(get(api, env), "employees", "Ada L")["total_days"]) == D(
        "10"
    )  # la v2 in bozza non conta
    api.post(f"/api/v1/ce/{ce_id}/approve", headers=env.h(env.admin))
    assert D(row(get(api, env), "employees", "Ada L")["total_days"]) == D(
        "5"
    )  # ora conta solo la v2


def test_filters_by_profile_employee_and_client(api, env, session):
    w = world(api, env, session)
    by_profile = get(api, env, f"{WINDOW}&profile_id={env.profiles['Specialist'].id}")
    assert [r["name"] for r in by_profile["profiles"]] == ["Specialist"] and [
        r["name"] for r in by_profile["employees"]
    ] == ["Bruno Neri"]
    by_emp = get(api, env, f"{WINDOW}&employee_id={w['ada'].id}")
    assert [r["name"] for r in by_emp["employees"]] == ["Ada Lovelace"] and D(
        by_emp["employees"][0]["total_days"]
    ) == D("15")
    by_client = get(
        api, env, f"{WINDOW}&client_id={w['beta'].id}"
    )  # B (Ada 5 g) e D v1 (Bruno 5 g)
    assert {r["name"]: D(r["total_days"]) for r in by_client["employees"]} == {
        "Ada Lovelace": D("5"),
        "Bruno Neri": D("5"),
    }


def test_months_outside_the_ce_period_have_no_load(api, env, session):
    ada = make_employee(session, env, "Ada", "L")
    build_ce(
        api,
        env,
        "PS-RES-WIN",
        start="2026-03-02",
        end="2026-03-31",
        lines=[("Senior", 80, ada)],
        state="approved",
    )
    r = row(get(api, env), "employees", "Ada L")
    assert [D(c["days"]) for c in r["cells"]] == [0, 0, D("10"), 0, 0, 0]
    assert get(api, env, "date_from=2026-05-01&date_to=2026-06-30")["employees"] == []


def test_period_rules(api, env):
    assert (
        api.get(
            f"{URL}?date_from=2026-05-01&date_to=2026-04-01", headers=env.h(env.presale)
        ).status_code
        == 422
    )
    too_long = api.get(f"{URL}?date_from=2026-01-01&date_to=2029-12-01", headers=env.h(env.presale))
    assert too_long.status_code == 422 and "massimo" in too_long.json()["detail"]
    one_month = get(api, env, "date_from=2026-03-17&date_to=2026-03-20")
    assert [m["month"] for m in one_month["months"]] == ["2026-03-01"]
    assert [m["month"] for m in get(api, env, "date_from=2026-03-17")["months"]] == [
        "2026-03-01"
    ]  # senza data finale


def test_deleted_ces_and_empty_state(api, env, session):
    assert get(api, env)["employees"] == [] and get(api, env)["profiles"] == []
    ada = make_employee(session, env, "Ada", "L")
    ce_id = build_ce(api, env, "PS-RES-DEL", lines=[("Senior", 80, ada)], state="approved")
    api.delete(f"/api/v1/ce/{ce_id}", headers=env.h(env.admin))
    assert get(api, env)["employees"] == []
