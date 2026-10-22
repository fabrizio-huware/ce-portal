"""Business unit coinvolte in un CE: dichiarazione, modifica con registro, coerenza con le righe, duplicazione."""

import uuid

from sqlalchemy import delete, select, update

from app.models import AuditLog, CEBusinessUnit, CEVersion, Employee
from tests.ce_helpers import approved_ce, create, create_filled, save, simple_content
from tests.factories import make_business_unit, make_practice, make_user, system_business_unit

URL = "/api/v1/ce"


def _employee_in(session, env, unit, first="Ada"):
    """Un collaboratore la cui practice sta nella business unit indicata."""
    practice = make_practice(session, name=f"Practice di {unit.name}", business_unit_id=unit.id)
    employee = Employee(
        first_name=first,
        last_name="Test",
        default_profile_id=env.profiles["Senior"].id,
        practice_id=practice.id,
    )
    session.add(employee)
    session.flush()
    return employee


def _content(env, revision, employee=None):
    content = simple_content(env, revision)
    if employee is not None:
        content["phases"][0]["lines"][0]["employee_id"] = str(employee.id)
    return content


def _put(api, env, ce_id, units, user=None):
    return api.put(
        f"{URL}/{ce_id}/business-units",
        headers=env.h(user or env.presale),
        json={"business_unit_ids": [str(u.id if hasattr(u, "id") else u) for u in units]},
    )


def _names(detail):
    return [u["name"] for u in detail["business_units"]]


def _audit(session, ce_id, action):
    session.expire_all()
    return list(
        session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "ce",
                AuditLog.entity_id == uuid.UUID(ce_id),
                AuditLog.action == action,
            )
        )
    )


# ------------------------------------------------------------------ creazione
def test_creation_requires_at_least_one_valid_business_unit(api, env, session):
    system = system_business_unit(session)
    off = make_business_unit(session, name="Spenta", is_active=False)
    session.commit()
    post = lambda ids, code: api.post(  # noqa: E731
        URL,
        headers=env.h(env.presale),
        json={
            **{k: v for k, v in create_body_of(env, code).items() if k != "business_unit_ids"},
            **({} if ids is None else {"business_unit_ids": ids}),
        },
    )
    assert post(None, "PS-BU-1").status_code == 422  # manca
    assert post([], "PS-BU-2").status_code == 422  # vuota
    assert post([str(uuid.uuid4())], "PS-BU-3").status_code == 422  # inesistente
    assert (
        post([str(system.id)], "PS-BU-4").status_code == 422
    )  # «Da assegnare» non è coinvolgibile
    refused = post([str(off.id)], "PS-BU-5")
    assert refused.status_code == 422 and "disattivata" in str(refused.json())
    twice = post([str(env.unit.id), str(env.unit.id)], "PS-BU-6")  # i doppioni si ignorano
    assert twice.status_code == 201 and _names(twice.json()) == [env.unit.name]


def create_body_of(env, code):
    from tests.ce_helpers import create_body

    return create_body(env, code)


def test_the_business_units_are_shown_and_give_the_text_label(api, env, session):
    a, b = make_business_unit(session, name="Data & AI"), make_business_unit(session, name="Cloud")
    session.commit()
    created = create(api, env, code="PS-BU-7", business_unit_ids=[str(a.id), str(b.id)])
    assert _names(created) == ["Cloud", "Data & AI"]  # in ordine alfabetico
    assert created["header"]["business_unit"] == "Cloud · Data & AI"  # per dashboard, Excel e PDF
    assert created["undeclared_business_units"] == []
    item = next(
        i
        for i in api.get(URL, headers=env.h(env.presale)).json()["items"]
        if i["code"] == "PS-BU-7"
    )
    assert item["business_units"] == ["Cloud", "Data & AI"]
    assert [
        e.changes["business_units"] for e in _audit(session, created["ce"]["id"], "create")
    ] == [["Cloud", "Data & AI"]]


def test_the_free_text_business_unit_is_ignored(api, env):
    created = create(api, env, code="PS-BU-8", business_unit="Testo qualsiasi")
    assert created["header"]["business_unit"] == env.unit.name  # lo ricava il server
    ce_id, rev = created["ce"]["id"], created["version"]["revision"]
    resp = save(api, env, ce_id, simple_content(env, rev, business_unit="Altro testo"))
    assert resp.status_code == 200 and resp.json()["header"]["business_unit"] == env.unit.name
    assert resp.json()["business_units"][0]["name"] == env.unit.name


# ------------------------------------------------------------------ modifica
def test_author_and_admin_change_them_and_it_is_recorded(api, env, session):
    a = make_business_unit(session, name="Alfa")
    session.commit()
    ce = create(api, env, code="PS-BU-9")["ce"]["id"]
    resp = _put(api, env, ce, [env.unit, a])
    assert resp.status_code == 200
    assert _names(resp.json()) == sorted([env.unit.name, "Alfa"], key=str.lower)
    assert resp.json()["header"]["business_unit"] == " · ".join(
        sorted([env.unit.name, "Alfa"], key=str.lower)
    )
    admin = _put(api, env, ce, [a], user=env.admin)
    assert admin.status_code == 200 and _names(admin.json()) == ["Alfa"]
    entries = _audit(session, ce, "set_business_units")
    assert [e.changes for e in entries] == [
        {"from": [env.unit.name], "to": sorted([env.unit.name, "Alfa"], key=str.lower)},
        {"from": sorted([env.unit.name, "Alfa"], key=str.lower), "to": ["Alfa"]},
    ]


def test_only_the_author_or_an_admin_can_change_them(api, env, session):
    ce = create(api, env, code="PS-BU-10")["ce"]["id"]
    manager = make_user(session, role="bu_manager", business_unit_id=env.unit.id)
    session.commit()
    assert _put(api, env, ce, [env.unit], user=env.other).status_code == 403
    assert _put(api, env, ce, [env.unit], user=manager).status_code == 403
    assert _put(api, env, ce, [env.unit], user=env.viewer).status_code == 403


def test_they_change_only_while_draft_or_rejected(api, env, session):
    other = make_business_unit(session, name="Altra")
    session.commit()
    ce = create_filled(api, env, code="PS-BU-11")["ce"]["id"]
    assert _put(api, env, ce, [env.unit, other]).status_code == 200  # bozza
    assert api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale)).status_code == 200
    assert _put(api, env, ce, [other]).status_code == 409  # in approvazione
    assert _put(api, env, ce, [other], user=env.admin).status_code == 409  # nemmeno l'admin
    api.post(f"{URL}/{ce}/reject", headers=env.h(env.admin), json={"reason": "Da rivedere"})
    assert _put(api, env, ce, [other]).status_code == 200  # rifiutato
    approved = approved_ce(api, env, code="PS-BU-12")["ce"]["id"]
    assert _put(api, env, approved, [other]).status_code == 409  # approvato


def test_changes_are_validated_and_a_no_op_leaves_no_trace(api, env, session):
    system = system_business_unit(session)
    off = make_business_unit(session, name="Spenta")
    ce = create(api, env, code="PS-BU-13", business_unit_ids=[str(off.id)])["ce"]["id"]
    session.execute(update(type(off)).where(type(off).id == off.id).values(is_active=False))
    session.commit()
    assert _put(api, env, ce, []).status_code == 422
    assert _put(api, env, ce, [system]).status_code == 422
    assert _put(api, env, ce, [uuid.uuid4()]).status_code == 422
    other_off = make_business_unit(session, name="Altra spenta", is_active=False)
    session.commit()
    assert (
        _put(api, env, ce, [off, other_off]).status_code == 422
    )  # una disattivata nuova non si aggiunge
    assert (
        _put(api, env, ce, [off, env.unit]).status_code == 200
    )  # quella già coinvolta si può tenere
    before = len(_audit(session, ce, "set_business_units"))
    assert (
        _put(api, env, ce, [env.unit, off]).status_code == 200
    )  # stesso elenco: niente da registrare
    assert len(_audit(session, ce, "set_business_units")) == before


def test_the_action_flag_follows_status_and_ownership(api, env):
    created = create_filled(api, env, code="PS-BU-14")
    ce = created["ce"]["id"]
    assert created["actions"]["set_business_units"] is True
    seen_by_other = api.get(f"{URL}/{ce}", headers=env.h(env.other)).json()
    assert seen_by_other["actions"]["set_business_units"] is False
    assert (
        api.get(f"{URL}/{ce}", headers=env.h(env.admin)).json()["actions"]["set_business_units"]
        is True
    )
    api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale))
    assert (
        api.get(f"{URL}/{ce}", headers=env.h(env.presale)).json()["actions"]["set_business_units"]
        is False
    )


def test_a_new_version_keeps_the_business_units(api, env, session):
    other = make_business_unit(session, name="Altra")
    session.commit()
    approved = approved_ce(api, env, code="PS-BU-15", content=None)
    ce = approved["ce"]["id"]
    resp = api.post(f"{URL}/{ce}/versions", headers=env.h(env.presale))
    assert resp.status_code == 201
    assert (
        _names(resp.json()) == [env.unit.name]
        and resp.json()["header"]["business_unit"] == env.unit.name
    )
    assert other  # il CE conserva le sue business unit per tutte le versioni


# ------------------------------------------------------------------ coerenza con le righe
def test_lines_with_collaborators_of_other_business_units_block_the_submission(api, env, session):
    cloud = make_business_unit(session, name="Cloud")
    ada = _employee_in(session, env, cloud)
    session.commit()
    created = create(api, env, code="PS-BU-16")
    ce, rev = created["ce"]["id"], created["version"]["revision"]
    saved = save(api, env, ce, _content(env, rev, ada))
    assert saved.status_code == 200
    assert [u["name"] for u in saved.json()["undeclared_business_units"]] == ["Cloud"]
    blocked = api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale))
    assert blocked.status_code == 422
    assert "«Cloud» ha collaboratori nelle righe ma non è tra le business unit coinvolte" in str(
        blocked.json()
    )
    assert _put(api, env, ce, [env.unit, cloud]).status_code == 200
    detail = api.get(f"{URL}/{ce}", headers=env.h(env.presale)).json()
    assert detail["undeclared_business_units"] == []
    assert api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale)).status_code == 200


def test_collaborators_without_a_real_business_unit_do_not_conflict(api, env, session):
    from tests.dash_helpers import make_employee

    unassigned = make_employee(session, env, "Ugo", "Senzaarea")  # practice «Da assegnare»
    session.commit()
    created = create(api, env, code="PS-BU-17")
    ce, rev = created["ce"]["id"], created["version"]["revision"]
    saved = save(api, env, ce, _content(env, rev, unassigned))
    assert saved.status_code == 200 and saved.json()["undeclared_business_units"] == []
    assert api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale)).status_code == 200


def test_the_submission_needs_at_least_one_business_unit(api, env, session):
    ce = create_filled(api, env, code="PS-BU-18")["ce"]["id"]
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id == uuid.UUID(ce)))
    session.commit()
    blocked = api.post(f"{URL}/{ce}/submit", headers=env.h(env.presale))
    assert blocked.status_code == 422 and "almeno una business unit" in str(blocked.json())


# ------------------------------------------------------------------ duplicazione
def test_a_duplicate_has_the_same_business_units_unless_told_otherwise(api, env, session):
    a = make_business_unit(session, name="Alfa")
    session.commit()
    source = create_filled(api, env, code="PS-BU-19")["ce"]["id"]
    _put(api, env, source, [env.unit, a])
    body = {"code": "PS-BU-19-BIS", "start_date": "2026-01-20", "end_date": "2026-04-20"}
    same = api.post(f"{URL}/{source}/duplicate", headers=env.h(env.presale), json=body)
    assert same.status_code == 201
    assert _names(same.json()) == sorted([env.unit.name, "Alfa"], key=str.lower)
    other = api.post(
        f"{URL}/{source}/duplicate",
        headers=env.h(env.presale),
        json={**body, "code": "PS-BU-19-TER", "business_unit_ids": [str(a.id)]},
    )
    assert other.status_code == 201 and _names(other.json()) == ["Alfa"]


def test_duplicating_a_ce_without_business_units_needs_them_in_the_request(api, env, session):
    source = create_filled(api, env, code="PS-BU-20")["ce"]["id"]
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id == uuid.UUID(source)))
    session.commit()
    body = {"code": "PS-BU-20-BIS", "start_date": "2026-01-20", "end_date": "2026-04-20"}
    assert (
        api.post(f"{URL}/{source}/duplicate", headers=env.h(env.presale), json=body).status_code
        == 422
    )
    ok = api.post(
        f"{URL}/{source}/duplicate",
        headers=env.h(env.presale),
        json={**body, "business_unit_ids": [str(env.unit.id)]},
    )
    assert ok.status_code == 201 and _names(ok.json()) == [env.unit.name]


# ------------------------------------------------------------------ CE esistenti
def test_apply_to_existing_ces_derives_from_the_text_and_from_the_lines(api, env, session):
    data = make_business_unit(session, name="Data & AI")
    cloud = make_business_unit(session, name="Cloud")
    system_business_unit(session)
    ada = _employee_in(session, env, cloud)
    session.commit()
    ids = {}
    for code in ("PS-OLD-1", "PS-OLD-2", "PS-OLD-3", "PS-OLD-4"):
        ids[code] = create(api, env, code=code)["ce"]["id"]
    save(api, env, ids["PS-OLD-2"], _content(env, 1, ada))
    keep = [uuid.UUID(ids["PS-OLD-4"])]
    wipe = [uuid.UUID(v) for k, v in ids.items() if k != "PS-OLD-4"]
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id.in_(wipe)))
    labels = {"PS-OLD-1": "data & ai", "PS-OLD-2": None, "PS-OLD-3": "Da assegnare"}
    for code, label in labels.items():
        session.execute(
            update(CEVersion)
            .where(CEVersion.ce_id == uuid.UUID(ids[code]))
            .values(business_unit=label)
        )
    session.commit()

    refused = api.post("/api/v1/business-units/apply-to-existing-ces", headers=env.h(env.presale))
    assert refused.status_code == 403
    resp = api.post("/api/v1/business-units/apply-to-existing-ces", headers=env.h(env.admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 2
    assert [c["code"] for c in body["without_business_units"]] == [
        "PS-OLD-3"
    ]  # «Da assegnare» non si assegna mai
    one = api.get(f"{URL}/{ids['PS-OLD-1']}", headers=env.h(env.admin)).json()
    two = api.get(f"{URL}/{ids['PS-OLD-2']}", headers=env.h(env.admin)).json()
    four = api.get(f"{URL}/{keep[0]}", headers=env.h(env.admin)).json()
    assert (
        _names(one) == ["Data & AI"] and one["header"]["business_unit"] == "Data & AI"
    )  # dal testo
    assert _names(two) == ["Cloud"]  # dalla practice del collaboratore
    assert _names(four) == [env.unit.name]  # chi le aveva già non si tocca
    entry = _audit(session, ids["PS-OLD-1"], "set_business_units")[0]
    assert entry.changes["from"] == [] and "esistenti" in entry.changes["origin"]
    again = api.post(
        "/api/v1/business-units/apply-to-existing-ces", headers=env.h(env.admin)
    ).json()
    assert again["updated"] == 0 and len(again["without_business_units"]) == 1  # idempotente
    assert data


def test_an_admin_can_repair_an_old_ce_without_business_units_in_any_status(api, env, session):
    approved = approved_ce(api, env, code="PS-BU-21")
    ce = approved["ce"]["id"]
    session.execute(delete(CEBusinessUnit).where(CEBusinessUnit.ce_id == uuid.UUID(ce)))
    session.commit()
    seen_by_admin = api.get(f"{URL}/{ce}", headers=env.h(env.admin)).json()
    assert (
        seen_by_admin["business_units"] == []
        and seen_by_admin["actions"]["set_business_units"] is True
    )
    assert (
        api.get(f"{URL}/{ce}", headers=env.h(env.presale)).json()["actions"]["set_business_units"]
        is False
    )
    assert (
        _put(api, env, ce, [env.unit], user=env.presale).status_code == 409
    )  # l'autore no: è approvato
    assert _put(api, env, ce, [env.unit], user=env.admin).status_code == 200  # l'admin ripara
    assert _names(api.get(f"{URL}/{ce}", headers=env.h(env.admin)).json()) == [env.unit.name]
    other = make_business_unit(session, name="Altra")
    session.commit()
    assert (
        _put(api, env, ce, [other], user=env.admin).status_code == 409
    )  # ora che ne ha, vale la regola di sempre
    assert len(_audit(session, ce, "set_business_units")) == 1
