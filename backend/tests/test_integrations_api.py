"""Contratto per i programmi esterni: creare, rileggere, modificare ed esportare, sempre senza costi né margini."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select

from app.models import CE
from tests.ce_helpers import approved_ce, create_filled
from tests.dash_helpers import make_employee
from tests.s2s_helpers import Caller, keys_of, new_ce_body, register

NOTICE = "Versione non approvata: i valori possono cambiare."
# Nomi di campo che non devono mai comparire in ciò che esce verso l'esterno.
SECRET_KEYS = ("cost", "margin", "rate", "fee", "price", "discount", "billab")


@pytest.fixture
def call(api, env, session, service) -> Caller:
    register(api, env)
    return Caller(api, session, service)


def make(call, env, **kw) -> dict:
    response = call.post("/ce", json=new_ce_body(env, **kw))
    assert response.status_code == 201, response.text
    return response.json()


def admin_detail(api, env, ce_id) -> dict:
    return api.get(f"/api/v1/ce/{ce_id}", headers=env.h(env.admin)).json()


# ------------------------------------------------------------------ elenchi di supporto
def test_lookups_give_only_ids_and_names(call, env, session):
    make_employee(session, env, "Ada", "Lovelace", "Senior")
    session.commit()
    for path in ("/anagrafiche/clienti", "/anagrafiche/profili", "/anagrafiche/collaboratori"):
        data = call.get(path).json()
        assert data, path
        assert all(set(item) == {"id", "name"} for item in data), (
            path
        )  # niente tariffe, costi, email, note
    assert "Senior" in {p["name"] for p in call.get("/anagrafiche/profili").json()}
    assert env.client.name in {c["name"] for c in call.get("/anagrafiche/clienti").json()}
    assert "Ada Lovelace" in {e["name"] for e in call.get("/anagrafiche/collaboratori").json()}


def test_inactive_entries_are_not_offered(call, env, session):
    employee = make_employee(session, env, "Bruno", "Inattivo", "Senior")
    employee.is_active = False
    env.profiles["Senior"].is_active = False
    env.client.is_active = False
    session.commit()
    assert "Bruno Inattivo" not in {
        e["name"] for e in call.get("/anagrafiche/collaboratori").json()
    }
    assert "Senior" not in {p["name"] for p in call.get("/anagrafiche/profili").json()}
    assert env.client.name not in {c["name"] for c in call.get("/anagrafiche/clienti").json()}


# ------------------------------------------------------------------ creazione
def test_create_builds_the_whole_ce_in_one_call_with_the_service_user_as_author(call, env, api):
    out = make(call, env)
    ce = out["ce"]
    assert out["created"] is True and out["revision"] >= 2
    assert (ce["code"], ce["status"], ce["mine"], ce["external_ref"], ce["requested_by"]) == (
        "PS-EXT-001-PJT", "draft", True, "EXT-001", "anna.rossi@huware.com")  # fmt: skip
    assert Decimal(ce["total_revenue"]) == Decimal("1700.00") and Decimal(ce["days_total"]) == 2
    assert ce["notice"] == NOTICE and ce["approved_at"] is None

    detail = admin_detail(api, env, ce["ce_id"])
    assert detail["ce"]["owner"] == {
        "id": detail["ce"]["owner"]["id"], "full_name": "Portale esterno (servizio)", "is_service": True}  # fmt: skip
    assert detail["ce"]["requested_by"] == "anna.rossi@huware.com"
    assert detail["actions"]["assign"] is True  # l'amministratore può assegnarlo a un presale
    assert Decimal(detail["calculation"]["kpis"]["price_project"]) == Decimal(ce["total_revenue"])


def test_requested_by_is_optional(call, env):
    body = new_ce_body(env)
    body["requested_by"] = None
    out = call.post("/ce", json=body).json()
    assert out["ce"]["requested_by"] is None


def test_a_ce_that_fails_validation_is_not_created_at_all(call, env, session):
    body = new_ce_body(env, code="PS-FALLITO-001-PJT", ref="F-1")
    body["content"]["phases"][0]["lines"][0]["profile_id"] = str(
        uuid.uuid4()
    )  # profilo inesistente
    response = call.post("/ce", json=body)
    assert response.status_code == 422
    session.expire_all()
    assert (
        session.scalar(select(CE).where(CE.code == "PS-FALLITO-001-PJT")) is None
    )  # tutto o niente
    good = new_ce_body(env, code="PS-FALLITO-001-PJT", ref="F-1")
    assert (
        call.post("/ce", json=good).status_code == 201
    )  # e l'identificativo non è rimasto «bruciato»


@pytest.mark.parametrize(
    "change",
    [
        {"code": "xx"},
        {"code": "con spazi"},
        {"external_ref": ""},
        {"external_ref": None},
        {"requested_by": "x" * 400},
        {"inventato": True},
        {"content": {}},
    ],
)
def test_invalid_bodies_are_refused(call, env, session, change):
    body = {**new_ce_body(env), **change}
    assert call.post("/ce", json=body).status_code == 422
    assert session.scalar(select(func.count()).select_from(CE)) == 0


def test_repeating_the_request_gives_the_same_ce_and_never_a_duplicate(call, env, session):
    first = make(call, env)
    again = call.post("/ce", json=new_ce_body(env))
    assert again.status_code == 200 and again.json()["created"] is False
    assert again.json()["ce"]["ce_id"] == first["ce"]["ce_id"]
    renamed = call.post(
        "/ce", json=new_ce_body(env, code="PS-EXT-999-PJT")
    )  # stesso identificativo, altro codice
    assert renamed.status_code == 200 and renamed.json()["ce"]["ce_id"] == first["ce"]["ce_id"]
    assert session.scalar(select(func.count()).select_from(CE)) == 1


def test_the_same_code_with_another_reference_is_a_conflict(call, env):
    make(call, env)
    assert call.post("/ce", json=new_ce_body(env, ref="EXT-002")).status_code == 409


def test_two_integrations_can_use_the_same_reference(api, env, session, service):
    register(api, env)
    register(api, env, name="Altro", email="altro@p.iam.gserviceaccount.com")
    one = Caller(api, session, service)
    two = Caller(api, session, service, email="altro@p.iam.gserviceaccount.com", sub="sa-2")
    first = one.post("/ce", json=new_ce_body(env, code="PS-UNO-001-PJT", ref="R-1"))
    second = two.post("/ce", json=new_ce_body(env, code="PS-DUE-001-PJT", ref="R-1"))
    assert first.status_code == second.status_code == 201
    assert first.json()["ce"]["ce_id"] != second.json()["ce"]["ce_id"]


# ------------------------------------------------------------------ elenco e riepilogo
def test_list_shows_every_ce_of_any_status_with_ownership_flags(call, env, api, session):
    mine = make(call, env)["ce"]
    human = create_filled(api, env, "PS-UMANO-001-PJT")["ce"]
    approved = approved_ce(api, env, "PS-APPROV-001-PJT")["ce"]
    page = call.get("/ce").json()
    by_code = {i["code"]: i for i in page["items"]}
    assert (
        set(by_code) == {"PS-EXT-001-PJT", "PS-UMANO-001-PJT", "PS-APPROV-001-PJT"}
        and page["total"] == 3
    )
    assert (by_code["PS-EXT-001-PJT"]["mine"], by_code["PS-EXT-001-PJT"]["external_ref"]) == (
        True,
        "EXT-001",
    )
    assert (by_code["PS-UMANO-001-PJT"]["mine"], by_code["PS-UMANO-001-PJT"]["external_ref"]) == (
        False,
        None,
    )
    assert by_code["PS-APPROV-001-PJT"]["status"] == "approved"
    assert {mine["ce_id"], human["id"], approved["id"]} == {i["ce_id"] for i in page["items"]}
    assert call.get("/ce?status=approved").json()["total"] == 1
    assert call.get("/ce?external_ref=EXT-001").json()["items"][0]["code"] == "PS-EXT-001-PJT"
    assert call.get("/ce?external_ref=NON-ESISTE").json()["total"] == 0
    assert call.get("/ce?code=umano").json()["total"] == 1
    one = call.get("/ce?limit=1&offset=1").json()
    assert (one["total"], one["limit"], one["offset"], len(one["items"])) == (3, 1, 1, 1)


def test_the_reference_of_another_integration_is_not_visible_or_searchable(
    api, env, session, service
):
    register(api, env)
    register(api, env, name="Altro", email="altro@p.iam.gserviceaccount.com")
    one = Caller(api, session, service)
    two = Caller(api, session, service, email="altro@p.iam.gserviceaccount.com", sub="sa-2")
    created = one.post("/ce", json=new_ce_body(env)).json()["ce"]
    seen = two.get(f"/ce/{created['ce_id']}").json()
    assert (seen["mine"], seen["external_ref"], seen["requested_by"]) == (False, None, None)
    assert two.get("/ce?external_ref=EXT-001").json()["total"] == 0
    assert two.get(f"/ce/{created['ce_id']}/content").status_code == 403


def test_deleted_ces_do_not_exist_for_integrations(call, env, session):
    ce_id = make(call, env)["ce"]["ce_id"]
    session.execute(
        CE.__table__.update().where(CE.id == ce_id).values(deleted_at=datetime.now(UTC))
    )
    session.commit()
    assert call.get("/ce").json()["total"] == 0
    for path in (f"/ce/{ce_id}", f"/ce/{ce_id}/content", f"/ce/{ce_id}/pdf"):
        assert call.get(path).status_code == 404, path


def test_summary_of_a_human_ce_and_of_an_approved_one(call, env, api):
    human = create_filled(api, env, "PS-UMANO-001-PJT")["ce"]["id"]
    seen = call.get(f"/ce/{human}").json()
    assert (seen["mine"], seen["status"], seen["notice"]) == (False, "draft", NOTICE)
    approved = approved_ce(api, env, "PS-APPROV-001-PJT")["ce"]["id"]
    seen = call.get(f"/ce/{approved}").json()
    assert seen["status"] == "approved" and seen["notice"] is None and seen["approved_at"]
    assert Decimal(seen["total_revenue"]) == Decimal("1700.00")
    assert [p["name"] for p in seen["phases"]] == ["Fase"]
    assert call.get(f"/ce/{uuid.uuid4()}").status_code == 404


# ------------------------------------------------------------------ contenuto: rilettura e modifica
def test_the_integration_can_reread_and_correct_its_own_draft(call, env, api):
    created = make(call, env)
    ce_id = created["ce"]["ce_id"]
    got = call.get(f"/ce/{ce_id}/content").json()
    assert got["revision"] == created["revision"] and got["status"] == "draft"
    content = got["content"]
    assert content["expected_revision"] == got["revision"]
    content["phases"][0]["lines"][0]["hours"] = "32"
    saved = call.put(f"/ce/{ce_id}/content", json=content)
    assert saved.status_code == 200, saved.text
    out = saved.json()
    assert out["created"] is False and out["revision"] == got["revision"] + 1
    assert Decimal(out["ce"]["days_total"]) == 4 and Decimal(out["ce"]["total_revenue"]) == Decimal(
        "3400.00"
    )
    assert Decimal(
        admin_detail(api, env, ce_id)["calculation"]["kpis"]["price_project"]
    ) == Decimal("3400.00")


def test_a_stale_revision_is_a_conflict_and_changes_nothing(call, env):
    created = make(call, env)
    ce_id = created["ce"]["ce_id"]
    content = call.get(f"/ce/{ce_id}/content").json()["content"]
    content["phases"][0]["lines"][0]["hours"] = "24"
    assert call.put(f"/ce/{ce_id}/content", json=content).status_code == 200
    content["phases"][0]["lines"][0]["hours"] = "8"
    stale = call.put(
        f"/ce/{ce_id}/content", json=content
    )  # stessa revisione di prima: nel frattempo è cambiata
    assert (
        stale.status_code == 409
        and stale.json()["detail"]["current_revision"] == created["revision"] + 1
    )
    assert Decimal(call.get(f"/ce/{ce_id}").json()["days_total"]) == 3
    content.pop("expected_revision")
    assert (
        call.put(f"/ce/{ce_id}/content", json=content).status_code == 422
    )  # senza revisione non si salva


def test_it_cannot_touch_the_ces_of_other_authors(call, env, api):
    human = create_filled(api, env, "PS-UMANO-001-PJT")
    ce_id = human["ce"]["id"]
    assert call.get(f"/ce/{ce_id}/content").status_code == 403
    body = new_ce_body(env)["content"]
    body["expected_revision"] = human["version"]["revision"]
    assert call.put(f"/ce/{ce_id}/content", json=body).status_code == 403


def test_approved_and_submitted_ces_cannot_be_modified(call, env, api):
    ce_id = make(call, env)["ce"]["ce_id"]
    content = call.get(f"/ce/{ce_id}/content").json()
    assert (
        api.post(f"/api/v1/ce/{ce_id}/submit", headers=env.h(env.admin)).status_code == 200
    )  # lo invia una persona
    assert (
        call.put(f"/ce/{ce_id}/content", json=content["content"]).status_code == 409
    )  # in approvazione
    assert api.post(f"/api/v1/ce/{ce_id}/approve", headers=env.h(env.admin)).status_code == 200
    fresh = call.get(f"/ce/{ce_id}/content").json()
    assert fresh["status"] == "approved"
    assert (
        call.put(f"/ce/{ce_id}/content", json=fresh["content"]).status_code == 409
    )  # approvato: nuova versione, non qui


def test_a_rejected_ce_can_be_corrected_like_any_author_would(call, env, api):
    ce_id = make(call, env)["ce"]["ce_id"]
    api.post(f"/api/v1/ce/{ce_id}/submit", headers=env.h(env.admin))
    rejected = api.post(
        f"/api/v1/ce/{ce_id}/reject", json={"reason": "Mancano le fasi"}, headers=env.h(env.admin)
    )
    assert rejected.status_code == 200
    got = call.get(f"/ce/{ce_id}/content").json()
    assert got["status"] == "rejected"
    got["content"]["phases"][0]["lines"][0]["hours"] = "40"
    assert call.put(f"/ce/{ce_id}/content", json=got["content"]).status_code == 200


# ------------------------------------------------------------------ PDF
def pdf_text(response) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)


def test_pdf_of_any_ce_with_the_notice_when_not_approved(call, env, api):
    mine = make(call, env)["ce"]["ce_id"]
    approved = approved_ce(api, env, "PS-APPROV-001-PJT")["ce"]["id"]
    draft = call.get(f"/ce/{mine}/pdf")
    assert draft.status_code == 200 and draft.headers["content-type"] == "application/pdf"
    assert "PS-EXT-001-PJT" in draft.headers["content-disposition"] and draft.content.startswith(
        b"%PDF"
    )
    text = pdf_text(draft)
    assert (
        "Versione non approvata" in text
        and "1.700,00" in text
        and "Riepilogo PS-EXT-001-PJT" in text
    )
    final = pdf_text(call.get(f"/ce/{approved}/pdf"))
    assert "Versione non approvata" not in final and "Approvato" in final
    human = create_filled(api, env, "PS-UMANO-001-PJT")["ce"]["id"]
    assert (
        call.get(f"/ce/{human}/pdf").status_code == 200
    )  # «tutti i CE», anche quelli delle persone


def test_the_pdf_never_mentions_costs_margins_or_rates(call, env):
    ce_id = make(call, env)["ce"]["ce_id"]
    text = pdf_text(call.get(f"/ce/{ce_id}/pdf"))
    for forbidden in (
        "Costi",
        "Costo",
        "Margine",
        "Prezzo",
        "Tariffa",
        "Fee",
        "C/R",
        "Senior",
    ):
        assert forbidden not in text, forbidden


# ------------------------------------------------------------------ riservatezza e registro
def test_no_response_ever_contains_cost_margin_or_rate_fields(call, env, api):
    ce_id = make(call, env)["ce"]["ce_id"]
    approved = approved_ce(api, env, "PS-APPROV-001-PJT")["ce"]["id"]
    responses = {
        "lista": call.get("/ce"),
        "riepilogo": call.get(f"/ce/{ce_id}"),
        "riepilogo approvato": call.get(f"/ce/{approved}"),
        "clienti": call.get("/anagrafiche/clienti"),
        "profili": call.get("/anagrafiche/profili"),
        "collaboratori": call.get("/anagrafiche/collaboratori"),
        "creazione ripetuta": call.post("/ce", json=new_ce_body(env)),
    }
    for name, response in responses.items():
        assert response.status_code in (200, 201), name
        names = {k.lower() for k in keys_of(response.json())}
        leaked = {
            k for k in names if any(secret in k for secret in SECRET_KEYS) and k != "total_revenue"
        }
        assert not leaked, (name, leaked)
    content = call.get(
        f"/ce/{ce_id}/content"
    ).json()  # ciò che l'integrazione ha inviato: i suoi dati, senza costi
    assert not {
        k
        for k in keys_of(content)
        if any(s in k.lower() for s in ("cost", "margin", "rate", "fee"))
    }


def test_errors_do_not_reveal_costs_either(call, env):
    body = new_ce_body(env)
    body["content"]["phases"][0]["lines"][0]["profile_id"] = str(uuid.uuid4())
    text = call.post("/ce", json=body).text.lower()
    for forbidden in ("daily_cost", "daily_price", "margin"):
        assert forbidden not in text


def test_writes_and_exports_are_recorded_with_the_service_user_as_actor(call, env, api):
    ce_id = make(call, env)["ce"]["ce_id"]
    content = call.get(f"/ce/{ce_id}/content").json()["content"]
    call.put(f"/ce/{ce_id}/content", json=content)
    call.get(f"/ce/{ce_id}/pdf")
    history = api.get(f"/api/v1/ce/{ce_id}/history", headers=env.h(env.admin)).json()
    actions = [h["action"] for h in history]
    for expected in ("create", "create_by_integration", "save", "export"):
        assert expected in actions, (expected, actions)
    created = next(h for h in history if h["action"] == "create_by_integration")
    assert (
        created["changes"]["external_ref"] == "EXT-001"
        and created["changes"]["integration"] == "Portale esterno"
    )
    assert (
        created["user"]["full_name"] == "Portale esterno (servizio)"
        and created["user"]["is_service"] is True
    )
    export = next(h for h in history if h["action"] == "export")
    assert export["changes"]["via"] == "integration"


# ------------------------------------------------------------------ business unit coinvolte
def test_creation_needs_the_business_units_and_they_are_stored(call, env, session, api):
    from tests.factories import make_business_unit, system_business_unit

    off = make_business_unit(session, name="Spenta", is_active=False)
    system = system_business_unit(session)
    session.commit()
    body = new_ce_body(env, code="PS-EXT-BU-1", ref="BU-1")
    without = {k: v for k, v in body.items() if k != "business_unit_ids"}
    assert call.post("/ce", json=without).status_code == 422
    assert call.post("/ce", json={**body, "business_unit_ids": []}).status_code == 422
    for bad in (
        str(uuid.uuid4()),
        str(off.id),
        str(system.id),
    ):  # inesistente, disattivata, di sistema
        assert call.post("/ce", json={**body, "business_unit_ids": [bad]}).status_code == 422, bad
    assert (
        session.scalar(select(func.count()).select_from(CE).where(CE.code == "PS-EXT-BU-1")) == 0
    )  # nulla creato
    created = call.post("/ce", json=body)
    assert created.status_code == 201
    detail = admin_detail(api, env, created.json()["ce"]["ce_id"])
    assert [u["name"] for u in detail["business_units"]] == [env.unit.name]
    assert detail["header"]["business_unit"] == env.unit.name


def test_a_repeated_creation_does_not_change_the_business_units(call, env, session):
    from tests.factories import make_business_unit

    other = make_business_unit(session, name="Altra")
    session.commit()
    first = call.post("/ce", json=new_ce_body(env, code="PS-EXT-BU-2", ref="BU-2"))
    assert first.status_code == 201
    again = call.post(
        "/ce",
        json={
            **new_ce_body(env, code="PS-EXT-BU-2", ref="BU-2"),
            "business_unit_ids": [str(other.id)],
        },
    )
    assert again.status_code == 200 and again.json()["created"] is False
    assert again.json()["ce"]["ce_id"] == first.json()["ce"]["ce_id"]


def test_the_business_unit_lookup_gives_only_active_real_ones_with_id_and_name(call, env, session):
    from tests.factories import make_business_unit, system_business_unit

    make_business_unit(session, name="Attiva")
    make_business_unit(session, name="Spenta", is_active=False)
    system_business_unit(session)
    session.commit()
    response = call.get("/anagrafiche/business-unit")
    assert response.status_code == 200
    names = [u["name"] for u in response.json()]
    assert "Attiva" in names and env.unit.name in names
    assert "Spenta" not in names and "Da assegnare" not in names
    assert {k for u in response.json() for k in u} == {"id", "name"}
