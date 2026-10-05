from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import CE, AuditLog, CEVersion, CEVersionRate
from tests.ce_helpers import PHASE_NAMES, add_closures, create, create_body
from tests.factories import make_client

URL = "/api/v1/ce"


def test_create_starts_a_draft_with_standard_phases_and_frozen_rates(api, env, session):
    body = create(api, env, code="ps-bonga-ai-pjt")
    assert body["ce"]["code"] == "PS-BONGA-AI-PJT"  # maiuscolo
    assert body["ce"]["owner"]["id"] == str(env.presale.id)
    assert body["version"]["number"] == 1 and body["version"]["status"] == "draft"
    assert body["version"]["revision"] == 1 and body["version"]["rate_year"] == 2026
    assert [p["name"] for p in body["phases"]] == PHASE_NAMES
    assert all(p["lines"] == [] for p in body["phases"])
    rates = {r["profile_name"]: r for r in body["rates"]}
    assert rates["Senior"]["daily_price"] == "850.00" and rates["Senior"]["daily_cost"] == "330.00"
    assert rates["Esterni"]["is_external"] is True and rates["Senior"]["is_external"] is False
    assert len(rates) == 9
    assert body["calculation"]["total"]["revenue"] == "0.00"
    assert body["calculation"]["kpis"]["fee_media_min"] is None


def test_create_can_start_empty(api, env):
    body = create(api, env, code="PS-VUOTO-1", standard_phases=False)
    assert body["phases"] == []


def test_create_precompiles_non_working_days_from_the_general_calendar(api, env, session):
    add_closures(
        session,
        date(2026, 1, 1),  # giovedì
        date(2026, 1, 6),  # martedì
        date(2026, 1, 3),  # sabato: non conta
        date(2026, 2, 16),  # lunedì
        date(2026, 6, 2),  # fuori dal progetto
    )
    body = create(api, env)
    months = {m["month"]: m for m in body["calculation"]["months"]}
    assert [
        months[m]["non_working"] for m in ("2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01")
    ] == [2, 1, 0, 0]
    assert months["2026-01-01"]["work_days"] == 20  # 22 feriali - 2
    assert months["2026-04-01"]["weekdays"] == 22


def test_rates_are_frozen_at_creation_and_listino_changes_do_not_alter_the_ce(api, env, session):
    body = create(api, env)
    senior = env.profiles["Senior"]
    from app.models import ProfileRate

    rate = session.get(ProfileRate, (senior.id, 2026))
    rate.daily_price = Decimal("999")
    session.flush()
    again = api.get(f"{URL}/{body['ce']['id']}", headers=env.h(env.presale)).json()
    assert {r["profile_name"]: r["daily_price"] for r in again["rates"]}["Senior"] == "850.00"


def test_only_active_profiles_are_copied(api, env, session):
    env.profiles["Stage"].is_active = False
    session.flush()
    names = {r["profile_name"] for r in create(api, env)["rates"]}
    assert "Stage" not in names and len(names) == 8


def test_create_writes_an_audit_entry(api, env, session):
    create(api, env)
    entry = session.scalar(
        select(AuditLog).where(AuditLog.action == "create", AuditLog.entity_type == "ce")
    )
    assert entry.user_id == env.presale.id and entry.changes["version"] == 1


def test_admin_can_create_too(api, env):
    assert create(api, env, user=env.admin, code="PS-ADMIN-1")["ce"]["owner"]["id"] == str(
        env.admin.id
    )


def test_codes_are_unique_ignoring_case_even_after_deletion(api, env):
    created = create(api, env, code="PS-UNICO-1")
    again = api.post(URL, headers=env.h(env.other), json=create_body(env, "ps-unico-1"))
    assert again.status_code == 409
    api.delete(f"{URL}/{created['ce']['id']}", headers=env.h(env.admin))
    assert (
        api.post(URL, headers=env.h(env.other), json=create_body(env, "PS-UNICO-1")).status_code
        == 409
    )


def test_invalid_codes_are_rejected(api, env):
    for bad in ("AB", "ha spazi", "con/slash", "", "-INIZIA", "X" * 101):
        resp = api.post(URL, headers=env.h(env.presale), json=create_body(env, bad))
        assert resp.status_code == 422, bad


def test_create_requires_the_price_list_of_the_start_year(api, env):
    resp = api.post(
        URL,
        headers=env.h(env.presale),
        json={**create_body(env), "start_date": "2027-01-10", "end_date": "2027-03-01"},
    )
    assert resp.status_code == 422
    assert "2027" in resp.json()["detail"]["message"]
    assert api.get(URL, headers=env.h(env.presale)).json()["total"] == 0  # nulla è stato creato


def test_create_validates_dates_client_and_fields(api, env, session):
    post = lambda **over: api.post(URL, headers=env.h(env.presale), json=create_body(env, **over))  # noqa: E731
    assert post(end_date="2025-12-31").status_code == 422
    assert post(start_date="2026-01-01", end_date="2027-01-31").status_code == 422  # oltre 12 mesi
    assert post(client_id="00000000-0000-0000-0000-000000000000").status_code == 422
    inactive = make_client(session, name="Cliente spento", is_active=False)
    assert post(client_id=str(inactive.id)).status_code == 422
    assert post(planning_mode="giorni").status_code == 422
    assert post(project_name="  ").status_code == 422
    assert post(max_discount_pct="101").status_code == 422
    assert post(signed_price="-1").status_code == 422
    assert post(extra_field=1).status_code == 422
    assert session.scalar(select(CE.id)) is None  # ogni rifiuto non ha lasciato nulla


def test_a_failed_creation_leaves_no_partial_data(api, env, session):
    api.post(URL, headers=env.h(env.presale), json=create_body(env, end_date="2025-01-01"))
    assert session.scalar(select(CEVersion.id)) is None
    assert session.scalar(select(CEVersionRate.version_id)) is None


def test_header_fields_are_stored(api, env):
    body = create(
        api,
        env,
        code="PS-HDR-1",
        sf_opportunity="006XX0001",
        business_unit="AI",
        notes="Note",
        max_discount_pct="7.5",
        signed_price="1000",
    )
    h = body["header"]
    assert (h["sf_opportunity"], h["business_unit"], h["notes"]) == ("006XX0001", "AI", "Note")
    assert (h["max_discount_pct"], h["signed_price"]) == ("7.50", "1000.00")
    assert h["client"]["name"] == "Cliente di prova"
