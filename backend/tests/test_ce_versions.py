"""Versioni, riallineamento, duplicazione, eliminazione."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models import AuditLog, CELine, CEVersion, Profile, ProfileRate
from tests.ce_helpers import (
    add_closures,
    approved_ce,
    create,
    create_filled,
    percent_ce_content,
    real_ce_content,
    save,
    simple_content,
)

URL = "/api/v1/ce"


def owner(env):
    return env.h(env.presale)


def admin(env):
    return env.h(env.admin)


def revenue(detail) -> str:
    return detail["calculation"]["total"]["revenue"]


# ------------------------------------------------------------------ nuova versione
def test_new_version_copies_everything_and_leaves_the_approved_one_untouched(api, env):
    approved = approved_ce(api, env, "PS-VER-1", content=real_ce_content(env, 1))
    ce_id = approved["ce"]["id"]
    v2 = api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    assert v2.status_code == 201
    body = v2.json()
    assert body["version"]["number"] == 2 and body["version"]["status"] == "draft"
    assert body["version"]["revision"] == 1 and body["version"]["approved_by"] is None
    assert body["ce"]["versions_count"] == 2
    assert revenue(body) == revenue(approved) == "47162.50"
    assert body["phases"][0]["name"] == approved["phases"][0]["name"]
    assert [len(p["lines"]) for p in body["phases"]] == [
        len(p["lines"]) for p in approved["phases"]
    ]
    assert body["milestones"] == approved["milestones"]
    assert body["rates"] == approved["rates"]  # tariffe ereditate, non riprese dal listino
    assert body["calculation"]["months"] == approved["calculation"]["months"]

    # si modifica la v2: la v1 non cambia
    changed = save(api, env, ce_id, simple_content(env, 1, hours="8"))
    assert revenue(changed.json()) == "850.00"
    v1 = api.get(f"{URL}/{ce_id}/versions/1", headers=owner(env)).json()
    assert revenue(v1) == "47162.50" and v1["version"]["status"] == "approved"


def test_only_one_open_version_at_a_time(api, env):
    approved = approved_ce(api, env, "PS-VER-2")
    ce_id = approved["ce"]["id"]
    assert api.post(f"{URL}/{ce_id}/versions", headers=owner(env)).status_code == 201
    again = api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    assert again.status_code == 409 and "in lavorazione" in again.json()["detail"]


def test_versions_list_and_lookup(api, env):
    approved = approved_ce(api, env, "PS-VER-3")
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    versions = api.get(f"{URL}/{ce_id}/versions", headers=owner(env)).json()
    assert [(v["number"], v["status"]) for v in versions] == [(2, "draft"), (1, "approved")]
    assert versions[1]["price"] == "1700.00" and versions[1]["approved_at"]
    assert api.get(f"{URL}/{ce_id}/versions/3", headers=owner(env)).status_code == 404
    # senza numero si legge l'ultima
    assert api.get(f"{URL}/{ce_id}", headers=owner(env)).json()["version"]["number"] == 2


def test_approving_a_second_version_keeps_the_history(api, env):
    approved = approved_ce(api, env, "PS-VER-4")
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    save(api, env, ce_id, simple_content(env, 1, hours="40"))
    v2 = api.post(f"{URL}/{ce_id}/approve", headers=admin(env)).json()
    assert v2["version"]["number"] == 2 and revenue(v2) == "4250.00"
    assert revenue(api.get(f"{URL}/{ce_id}/versions/1", headers=owner(env)).json()) == "1700.00"
    # e si può aprire la v3
    assert api.post(f"{URL}/{ce_id}/versions", headers=owner(env)).json()["version"]["number"] == 3


def test_discarding_an_open_version_returns_to_the_approved_one(api, env, session):
    approved = approved_ce(api, env, "PS-DISC-1")
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    save(api, env, ce_id, simple_content(env, 1, hours="99"))
    resp = api.delete(f"{URL}/{ce_id}/open-version", headers=owner(env))
    assert resp.status_code == 200 and resp.json() == {"discarded_version": 2}
    now = api.get(f"{URL}/{ce_id}", headers=owner(env)).json()
    assert now["version"]["number"] == 1 and now["version"]["status"] == "approved"
    assert session.scalar(select(func.count()).select_from(CEVersion)) == 1
    assert session.scalar(select(func.count()).select_from(CELine)) == 1  # nessuna riga orfana
    assert "discard_version" in session.scalars(select(AuditLog.action)).all()
    assert (
        api.post(f"{URL}/{ce_id}/versions", headers=owner(env)).status_code == 201
    )  # se ne può aprire un'altra


def test_a_submitted_second_version_can_only_be_discarded_by_an_admin(api, env):
    approved = approved_ce(api, env, "PS-DISC-2")
    ce_id = approved["ce"]["id"]
    api.post(f"{URL}/{ce_id}/versions", headers=owner(env))
    api.post(f"{URL}/{ce_id}/submit", headers=owner(env))
    assert api.delete(f"{URL}/{ce_id}/open-version", headers=owner(env)).status_code == 409
    assert api.delete(f"{URL}/{ce_id}/open-version", headers=admin(env)).status_code == 200


# ------------------------------------------------------------------ riallineamento
def test_realign_updates_rates_from_the_current_price_list_but_only_for_admins(api, env, session):
    created = create_filled(api, env, "PS-RA-1")  # 16 h di Senior a 850 -> 1.700
    ce_id = created["ce"]["id"]
    session.get(ProfileRate, (env.profiles["Senior"].id, 2026)).daily_price = Decimal("1000")
    session.flush()
    assert revenue(api.get(f"{URL}/{ce_id}", headers=owner(env)).json()) == "1700.00"  # congelato

    assert api.post(f"{URL}/{ce_id}/realign", headers=owner(env), json={}).status_code == 403
    done = api.post(f"{URL}/{ce_id}/realign", headers=admin(env), json={"calendar": False})
    assert done.status_code == 200
    assert revenue(done.json()) == "2000.00"  # 2 giornate x 1.000
    assert done.json()["version"]["revision"] > created["version"]["revision"]
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "realign")).one()
    assert entry.changes["rates"]["updated"] == 1


def test_realign_adds_missing_active_profiles(api, env, session):
    created = create(api, env)
    new = Profile(name="Arrivato dopo", sort_order=900)
    session.add(new)
    session.flush()
    session.add(
        ProfileRate(
            profile_id=new.id, year=2026, daily_price=Decimal("500"), daily_cost=Decimal("200")
        )
    )
    session.flush()
    done = api.post(
        f"{URL}/{created['ce']['id']}/realign", headers=admin(env), json={"calendar": False}
    ).json()
    assert "Arrivato dopo" in {r["profile_name"] for r in done["rates"]}


def test_realign_calendar_recomputes_the_months(api, env, session):
    created = create_filled(api, env, "PS-RA-2")
    ce_id = created["ce"]["id"]
    add_closures(session, date(2026, 2, 16), date(2026, 2, 17))
    before = {
        m["month"]: m["non_working"]
        for m in api.get(f"{URL}/{ce_id}", headers=owner(env)).json()["calculation"]["months"]
    }
    assert before["2026-02-01"] == 0  # il calendario generale è cambiato dopo la creazione
    done = api.post(f"{URL}/{ce_id}/realign", headers=admin(env), json={"rates": False}).json()
    after = {m["month"]: m["non_working"] for m in done["calculation"]["months"]}
    assert after["2026-02-01"] == 2 and after["2026-01-01"] == 0


def test_realign_is_refused_on_approved_versions(api, env):
    approved = approved_ce(api, env, "PS-RA-3")
    resp = api.post(f"{URL}/{approved['ce']['id']}/realign", headers=admin(env), json={})
    assert resp.status_code == 409


# ------------------------------------------------------------------ duplicazione
def test_duplicate_copies_structure_but_starts_fresh(api, env, session):
    source = approved_ce(
        api,
        env,
        "PS-SRC-1",
        content=real_ce_content(
            env,
            1,
            sf_opportunity="006AAA",
            notes="Nota",
            max_discount_pct="10",
            signed_price="40000",
        ),
    )
    new = api.post(
        f"{URL}/{source['ce']['id']}/duplicate",
        headers=env.h(env.other),
        json={
            "code": "ps-copia-1",
            "start_date": "2026-02-02",
            "end_date": "2026-05-29",
            "project_name": "Copia",
        },
    )
    assert new.status_code == 201, new.text
    body = new.json()
    assert body["ce"]["code"] == "PS-COPIA-1" and body["ce"]["owner"]["id"] == str(env.other.id)
    assert body["version"]["number"] == 1 and body["version"]["status"] == "draft"
    assert body["header"]["project_name"] == "Copia"
    assert (body["header"]["sf_opportunity"], body["header"]["notes"]) == (None, None)
    assert (body["header"]["max_discount_pct"], body["header"]["signed_price"]) == ("0.00", None)
    assert revenue(body) == "47162.50"  # stessa struttura e stesse ore
    assert [len(p["lines"]) for p in body["phases"]] == [len(p["lines"]) for p in source["phases"]]
    # la sorgente è intatta
    again = api.get(f"{URL}/{source['ce']['id']}", headers=owner(env)).json()
    assert (
        again["version"]["status"] == "approved" and again["header"]["signed_price"] == "40000.00"
    )


def test_duplicate_uses_the_current_price_list_and_calendar(api, env, session):
    source = approved_ce(api, env, "PS-SRC-2")  # 16 h Senior a 850
    session.get(ProfileRate, (env.profiles["Senior"].id, 2026)).daily_price = Decimal("900")
    add_closures(session, date(2026, 3, 2))
    new = api.post(
        f"{URL}/{source['ce']['id']}/duplicate",
        headers=owner(env),
        json={"code": "PS-COPIA-2", "start_date": "2026-01-20", "end_date": "2026-04-20"},
    ).json()
    assert revenue(new) == "1800.00"  # tariffa nuova
    assert {m["month"]: m["non_working"] for m in new["calculation"]["months"]}["2026-03-01"] == 1


def test_duplicate_remaps_percent_allocations_to_the_new_months(api, env):
    created = create(api, env, code="PS-PCT-SRC", planning_mode="percent")
    save(api, env, created["ce"]["id"], percent_ce_content(env, 1))
    new = api.post(
        f"{URL}/{created['ce']['id']}/duplicate",
        headers=owner(env),
        json={
            "code": "PS-PCT-COPIA",
            "start_date": "2026-06-10",
            "end_date": "2026-08-31",
        },  # 3 mesi: giu-ago
    ).json()
    manager = next(
        line for p in new["phases"] for line in p["lines"] if line["profile_name"] == "Manager"
    )
    assert [a["month"] for a in manager["allocations"]] == [
        "2026-06-01",
        "2026-07-01",
        "2026-08-01",
    ]
    senior = next(
        line for p in new["phases"] for line in p["lines"] if line["profile_name"] == "Senior"
    )
    assert [a["pct"] for a in senior["allocations"]] == [
        "100.00",
        "100.00",
        "50.00",
    ]  # il 4° mese cade


def test_duplicate_validations(api, env):
    source = approved_ce(api, env, "PS-SRC-3")
    url = f"{URL}/{source['ce']['id']}/duplicate"
    base = {"code": "PS-NUOVO-9", "start_date": "2026-01-20", "end_date": "2026-04-20"}
    assert api.post(url, headers=owner(env), json={**base, "code": "ps-src-3"}).status_code == 409
    assert (
        api.post(url, headers=owner(env), json={**base, "end_date": "2025-01-01"}).status_code
        == 422
    )
    assert (
        api.post(
            url,
            headers=owner(env),
            json={**base, "start_date": "2027-01-10", "end_date": "2027-02-10"},
        ).status_code
        == 422
    )
    assert (
        api.post(
            url,
            headers=owner(env),
            json={**base, "client_id": "00000000-0000-0000-0000-000000000000"},
        ).status_code
        == 422
    )
    assert (
        api.get(URL, headers=owner(env)).json()["total"] == 1
    )  # i rifiuti non hanno lasciato CE a metà


# ------------------------------------------------------------------ eliminazione
def test_delete_hides_the_ce_everywhere_and_restore_brings_it_back(api, env):
    approved = approved_ce(api, env, "PS-DEL-1")
    ce_id = approved["ce"]["id"]
    assert api.delete(f"{URL}/{ce_id}", headers=admin(env)).status_code == 204
    assert api.get(URL, headers=owner(env)).json()["total"] == 0
    assert api.get(f"{URL}/{ce_id}", headers=owner(env)).status_code == 404
    assert api.get(f"{URL}/summaries", headers=env.h(env.viewer)).json()["total"] == 0
    assert api.get(f"{URL}/summaries/{ce_id}", headers=env.h(env.viewer)).status_code == 404

    seen = api.get(f"{URL}?include_deleted=true", headers=admin(env)).json()
    assert seen["total"] == 1 and seen["items"][0]["deleted"] is True
    assert api.get(f"{URL}?include_deleted=true", headers=owner(env)).status_code == 403
    assert api.delete(f"{URL}/{ce_id}", headers=admin(env)).status_code == 404  # già eliminato

    restored = api.post(f"{URL}/{ce_id}/restore", headers=admin(env))
    assert restored.status_code == 200 and restored.json()["version"]["status"] == "approved"
    assert api.get(URL, headers=owner(env)).json()["total"] == 1
    assert (
        api.post(f"{URL}/{ce_id}/restore", headers=admin(env)).status_code == 409
    )  # non era eliminato


def test_only_admins_delete(api, env):
    ce = create_filled(api, env, "PS-DEL-2")
    assert api.delete(f"{URL}/{ce['ce']['id']}", headers=owner(env)).status_code == 403
