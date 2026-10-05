"""Salvataggio del contenuto: il CE reale caricato dall'API deve dare i totali del foglio."""

from decimal import Decimal

from sqlalchemy import select

from app.models import AuditLog, CEVersion, CEVersionRate
from tests.ce_helpers import create, percent_ce_content, real_ce_content, save, simple_content
from tests.engine_helpers import FIXTURE, cents

URL = "/api/v1/ce"


def test_real_ce_through_the_api_matches_the_sheet(api, env):
    created = create(api, env)
    resp = save(api, env, created["ce"]["id"], real_ce_content(env, created["version"]["revision"]))
    assert resp.status_code == 200, resp.text
    calc = resp.json()["calculation"]
    exp = FIXTURE["expected"]
    assert calc["total"]["revenue"] == "47162.50" == f"{cents(exp['revenue_total'])}"
    assert calc["total"]["cost"] == "20200.00"
    assert calc["total"]["margin"] == "26962.50"
    assert calc["total"]["margin_pct"] == "0.571694" and calc["total"]["cost_ratio"] == "0.428306"
    k = calc["kpis"]
    assert (
        Decimal(k["days_total"]) == Decimal("58.5") and Decimal(k["days_project_management"]) == 10
    )
    assert Decimal(k["days_delivery"]) == Decimal("48.5")
    assert k["fee_media_min"] == "806.20" and k["price_min"] == "47162.50"
    by_profile = {p["profile_name"]: p for p in calc["profiles"]}
    assert {n: p["revenue"] for n, p in by_profile.items()} == {
        "Manager": "4800.00",
        "Practice": "4000.00",
        "Senior": "11900.00",
        "Specialist": "26462.50",
    }
    assert [m["work_days"] for m in calc["months"]] == [17, 20, 22, 22]


def test_saving_bumps_the_revision_and_updates_the_list_totals(api, env):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    assert created["version"]["revision"] == 1
    saved = save(api, env, ce_id, real_ce_content(env, 1)).json()
    assert saved["version"]["revision"] == 2
    row = api.get(URL, headers=env.h(env.presale)).json()["items"][0]
    assert (row["price"], row["days_total"], row["margin_pct"]) == (
        "47162.50",
        "58.50000",
        "0.571694",
    )


def test_saved_content_is_returned_in_order_with_all_fields(api, env):
    created = create(api, env)
    saved = save(api, env, created["ce"]["id"], real_ce_content(env, 1)).json()
    assert [p["name"] for p in saved["phases"]][:3] == ["PM", "AN", "SD"]
    first = saved["phases"][0]["lines"][0]
    assert first["activity"] == "Sprint" and first["is_project_management"] is True
    assert first["profile_name"] == "Manager" and first["hours"] == "16.00"
    assert saved["milestones"] == [{"month": "2026-04-01", "label": "GoLive"}]
    assert saved["header"]["project_name"] == "Progetto di prova"


def test_percent_mode_through_the_api_matches_the_sheet(api, env):
    created = create(api, env, planning_mode="percent")
    saved = save(api, env, created["ce"]["id"], percent_ce_content(env, 1)).json()
    t = saved["calculation"]["total"]
    assert (t["days"], t["revenue"], t["cost"]) == ("148.85000", "125762.50", "56714.00")
    assert [m["fte"] for m in saved["calculation"]["monthly"]] == [
        "1.850000",
        "2.350000",
        "1.850000",
        "1.350000",
    ]


def test_a_second_save_replaces_the_content_completely(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, real_ce_content(env, 1))
    second = save(api, env, ce_id, simple_content(env, 2)).json()
    assert len(second["phases"]) == 1 and second["milestones"] == []
    assert second["calculation"]["total"]["revenue"] == "1700.00"  # 16 h di Senior
    from app.models import CELine

    assert len(session.scalars(select(CELine)).all()) == 1  # nessuna riga orfana


def test_header_changes_are_saved_and_audited(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    content = simple_content(
        env, 1, project_name="Nome nuovo", max_discount_pct="10", signed_price="1500"
    )
    saved = save(api, env, ce_id, content).json()
    k = saved["calculation"]["kpis"]
    assert saved["header"]["project_name"] == "Nome nuovo"
    assert (k["price_min"], k["fee_media_min"]) == ("1530.00", "765.00")
    assert (k["margin_signed"], k["margin_pct_signed"]) == ("840.00", "0.560000")
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "save")).one()
    assert entry.changes["header"]["project_name"][1] == "Nome nuovo"
    assert entry.changes["lines"] == 1


# ------------------------------------------------------------------ salvataggio sicuro
def test_stale_revision_is_rejected_without_overwriting(api, env):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    assert save(api, env, ce_id, simple_content(env, 1, hours="8")).status_code == 200
    stale = save(api, env, ce_id, simple_content(env, 1, hours="99"), user=env.admin)
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_revision"] == 2
    current = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    assert current["phases"][0]["lines"][0]["hours"] == "8.00"  # la modifica obsoleta non ha vinto


def test_expected_revision_is_required(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    del body["expected_revision"]
    resp = save(api, env, created["ce"]["id"], body)
    assert resp.status_code == 422 and "expected_revision" in resp.text


# ------------------------------------------------------------------ tariffe dei profili nuovi
def test_a_profile_added_after_creation_gets_its_rate_from_the_price_list(api, env, session):
    from app.models import Profile, ProfileRate

    created = create(api, env)
    late = Profile(name="Nuovo ruolo", sort_order=500)
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
    saved = save(api, env, created["ce"]["id"], body).json()
    assert saved["calculation"]["total"]["revenue"] == "400.00"
    assert "Nuovo ruolo" in {r["profile_name"] for r in saved["rates"]}


def test_new_profiles_must_be_active_and_priced(api, env, session):
    from app.models import Profile

    created = create(api, env)
    no_rate = Profile(name="Senza listino")
    off = Profile(name="Spento", is_active=False)
    session.add_all([no_rate, off])
    session.flush()
    for profile in (no_rate, off):
        body = simple_content(env, 1)
        body["phases"][0]["lines"][0]["profile_id"] = str(profile.id)
        resp = save(api, env, created["ce"]["id"], body)
        assert resp.status_code == 422, profile.name
    assert (
        session.scalar(
            select(CEVersionRate.profile_id).where(
                CEVersionRate.profile_id.in_([no_rate.id, off.id])
            )
        )
        is None
    )


# ------------------------------------------------------------------ validazione
def test_malformed_content_is_rejected_and_changes_nothing(api, env, session):
    created = create(api, env)
    ce_id = created["ce"]["id"]
    save(api, env, ce_id, simple_content(env, 1, hours="8"))
    bad = simple_content(env, 2)
    bad["phases"][0]["contingency_pct"] = "50"
    bad["phases"][0]["lines"].append(
        {
            "activity": "Ore con troppi decimali",
            "profile_id": str(env.profiles["Senior"].id),
            "hours": "7.555",
        }
    )
    resp = save(api, env, ce_id, bad)
    assert resp.status_code == 422
    assert resp.json()[
        "detail"
    ]  # errori di formato (es. più di 2 decimali) segnalati campo per campo
    ok = api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()
    assert ok["version"]["revision"] == 2  # il salvataggio rifiutato non ha cambiato nulla
    assert ok["phases"][0]["lines"][0]["hours"] == "8.00"


def test_engine_issues_come_back_as_a_list(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    body["non_working_days"] = [
        {"month": "2026-01-01", "non_working_days": 23}
    ]  # più dei feriali di gennaio
    body["phases"][0]["lines"][0]["allocations"] = [{"month": "2026-09-01", "pct": "50"}]
    resp = save(
        api,
        env,
        created["ce"]["id"],
        {**body, "header": {**body["header"], "planning_mode": "percent"}},
    )
    assert resp.status_code == 422
    issues = resp.json()["detail"]["issues"]
    assert any("devono essere tra 0 e 22" in i for i in issues)
    assert any("fuori dal periodo" in i for i in issues)


def test_months_outside_the_project_and_repeated_months_are_rejected(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    body["non_working_days"] = [
        {"month": "2026-09-01", "non_working_days": 1},
        {"month": "2026-01-01", "non_working_days": 1},
        {"month": "2026-01-01", "non_working_days": 2},
        {"month": "2026-02-15", "non_working_days": 1},
    ]
    issues = save(api, env, created["ce"]["id"], body).json()["detail"]["issues"]
    assert len(issues) == 3
    pct = simple_content(env, 1, planning_mode="percent")
    pct["phases"][0]["lines"][0]["allocations"] = [
        {"month": "2026-01-01", "pct": "50"},
        {"month": "2026-01-01", "pct": "60"},
    ]
    assert "ripetuti" in str(save(api, env, created["ce"]["id"], pct).json()["detail"]["issues"])


def test_unknown_references_are_rejected(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    body["phases"][0]["lines"][0]["profile_id"] = "00000000-0000-0000-0000-000000000000"
    assert save(api, env, created["ce"]["id"], body).status_code == 422
    body = simple_content(env, 1)
    body["phases"][0]["lines"][0]["employee_id"] = "00000000-0000-0000-0000-000000000000"
    assert save(api, env, created["ce"]["id"], body).status_code == 422
    body = simple_content(env, 1, client_id="00000000-0000-0000-0000-000000000000")
    assert save(api, env, created["ce"]["id"], body).status_code == 422


def test_missing_months_are_filled_from_the_calendar(api, env, session):
    from datetime import date

    from tests.ce_helpers import add_closures

    add_closures(session, date(2026, 3, 2))
    created = create(api, env)
    saved = save(
        api, env, created["ce"]["id"], simple_content(env, 1)
    ).json()  # nessun giorno indicato
    assert {m["month"]: m["non_working"] for m in saved["calculation"]["months"]}["2026-03-01"] == 1


def test_size_limits_are_enforced(api, env):
    created = create(api, env)
    body = simple_content(env, 1)
    body["phases"] = [{"name": f"F{i}", "lines": []} for i in range(61)]
    assert save(api, env, created["ce"]["id"], body).status_code == 422


def test_changing_the_period_changes_the_months(api, env):
    created = create(api, env)
    saved = save(
        api, env, created["ce"]["id"], simple_content(env, 1, end_date="2026-06-30")
    ).json()
    assert len(saved["calculation"]["months"]) == 6
    assert len(saved["calculation"]["monthly"]) == 6


def test_version_row_matches_the_api_view(api, env, session):
    created = create(api, env)
    save(api, env, created["ce"]["id"], real_ce_content(env, 1))
    version = session.scalars(select(CEVersion)).one()
    assert version.summary["revenue"] == "47162.50" and version.summary["cost"] == "20200.00"
    assert version.approved_totals is None
