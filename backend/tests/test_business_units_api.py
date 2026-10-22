"""Anagrafica Business unit: gestione, business unit di sistema, collegamento con practice, utenti e collaboratori."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models import DEFAULT_BUSINESS_UNIT, AuditLog, BusinessUnit, Employee, Practice, User
from tests.factories import make_business_unit, make_practice, make_profile, make_user
from tests.helpers import auth

URL = "/api/v1/business-units"


def _admin(session):
    return auth(make_user(session, role="admin"))


def _system(session) -> BusinessUnit:
    found = session.scalar(
        select(BusinessUnit).where(func.lower(BusinessUnit.name) == DEFAULT_BUSINESS_UNIT.lower())
    )
    return found or make_business_unit(session, name=DEFAULT_BUSINESS_UNIT)


# ------------------------------------------------------------------ anagrafica
def test_admin_creates_a_business_unit_and_the_name_is_trimmed(api, session):
    resp = api.post(URL, headers=_admin(session), json={"name": "  Data & AI  "})
    assert resp.status_code == 201
    body = resp.json()
    assert (body["name"], body["is_active"]) == ("Data & AI", True)
    assert (body["practices_count"], body["employees_count"], body["users_count"]) == (0, 0, 0)


def test_the_name_is_unique_without_regard_to_case(api, session):
    h = _admin(session)
    assert api.post(URL, headers=h, json={"name": "Cloud"}).status_code == 201
    dup = api.post(URL, headers=h, json={"name": "CLOUD"})
    assert (
        dup.status_code == 409 and "business unit" in dup.json()["detail"]
    )  # il messaggio è quello dell'applicazione
    other = api.post(URL, headers=h, json={"name": "Digital"}).json()
    renamed = api.patch(f"{URL}/{other['id']}", headers=h, json={"name": "cloud"})
    assert renamed.status_code == 409 and "business unit" in renamed.json()["detail"]


@pytest.mark.parametrize(
    "body", [{"name": ""}, {"name": "   "}, {"name": "x" * 101}, {}, {"inventato": 1, "name": "A"}]
)
def test_invalid_bodies_are_refused(api, session, body):
    assert api.post(URL, headers=_admin(session), json=body).status_code == 422


def test_rename_and_deactivate_and_nulls_are_refused(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Vecchio")
    session.commit()
    done = api.patch(f"{URL}/{unit.id}", headers=h, json={"name": "Nuovo", "is_active": False})
    assert done.status_code == 200 and (done.json()["name"], done.json()["is_active"]) == (
        "Nuovo",
        False,
    )
    assert api.patch(f"{URL}/{unit.id}", headers=h, json={"name": None}).status_code == 422
    assert api.patch(f"{URL}/{unit.id}", headers=h, json={"is_active": None}).status_code == 422
    assert api.patch(f"{URL}/{uuid.uuid4()}", headers=h, json={"name": "X"}).status_code == 404


def test_the_system_business_unit_cannot_be_renamed_or_deactivated(api, session):
    h = _admin(session)
    system = _system(session)
    session.commit()
    assert api.patch(f"{URL}/{system.id}", headers=h, json={"name": "Altro"}).status_code == 409
    assert api.patch(f"{URL}/{system.id}", headers=h, json={"is_active": False}).status_code == 409
    assert (
        api.patch(f"{URL}/{system.id}", headers=h, json={"name": system.name.upper()}).status_code
        == 200
    )


def test_counts_cover_practices_employees_and_people(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Data & AI")
    other = make_business_unit(session, name="Cloud")
    practice = make_practice(session, name="Data", business_unit_id=unit.id)
    make_practice(session, name="Inattiva", business_unit_id=unit.id, is_active=False)
    profile = make_profile(session)
    session.add_all(
        [
            Employee(
                first_name="A",
                last_name="Uno",
                default_profile_id=profile.id,
                practice_id=practice.id,
            ),
            Employee(
                first_name="B",
                last_name="Due",
                default_profile_id=profile.id,
                practice_id=practice.id,
                is_active=False,
            ),
        ]
    )
    make_user(session, role="presale", business_unit_id=unit.id)
    make_user(session, role="bu_manager", business_unit_id=unit.id)
    make_user(session, role="presale", business_unit_id=unit.id, is_active=False)
    make_user(session, role="presale", business_unit_id=other.id)
    session.commit()
    rows = {r["name"]: r for r in api.get(URL, headers=h).json()}
    assert (
        rows["Data & AI"]["practices_count"],
        rows["Data & AI"]["employees_count"],
        rows["Data & AI"]["users_count"],
    ) == (1, 1, 2)
    assert (rows["Cloud"]["practices_count"], rows["Cloud"]["users_count"]) == (0, 1)


def test_changes_are_recorded_in_the_audit_log(api, session):
    h = _admin(session)
    created = api.post(URL, headers=h, json={"name": "Audit"}).json()
    api.patch(f"{URL}/{created['id']}", headers=h, json={"is_active": False})
    session.expire_all()
    actions = session.scalars(
        select(AuditLog.action).where(AuditLog.entity_type == "business_unit").order_by(AuditLog.id)
    ).all()
    assert actions == ["create", "update"]


def test_lookup_is_for_admin_presale_and_manager_not_viewer(api, session):
    make_business_unit(session, name="Una")
    make_business_unit(session, name="Spenta", is_active=False)
    session.commit()
    for role in ("admin", "presale", "bu_manager"):
        resp = api.get(f"{URL}/lookup", headers=auth(make_user(session, role=role)))
        assert resp.status_code == 200, role
        assert {"Una", "Spenta"} <= {
            u["name"] for u in resp.json()
        }  # anche le disattivate: servono ai filtri
        assert set(resp.json()[0]) == {"id", "name", "is_active"}
    assert (
        api.get(f"{URL}/lookup", headers=auth(make_user(session, role="viewer"))).status_code == 403
    )


# ------------------------------------------------------------------ business unit di default
def test_a_practice_created_without_a_business_unit_goes_to_the_system_one(session):
    practice = make_practice(session, name="Orfana")
    session.commit()
    unit = session.get(BusinessUnit, practice.business_unit_id)
    assert unit.name == DEFAULT_BUSINESS_UNIT


def test_the_default_practice_of_an_employee_also_gets_the_default_business_unit(session):
    profile = make_profile(session)
    session.add(Employee(first_name="Z", last_name="Zeta", default_profile_id=profile.id))
    session.commit()
    practice = session.scalar(select(Practice).where(func.lower(Practice.name) == "da assegnare"))
    assert session.get(BusinessUnit, practice.business_unit_id).name == DEFAULT_BUSINESS_UNIT


# ------------------------------------------------------------------ practice
def test_practice_api_shows_and_changes_the_business_unit(api, session):
    h = _admin(session)
    a, b = make_business_unit(session, name="Alfa"), make_business_unit(session, name="Beta")
    session.commit()
    made = api.post(
        "/api/v1/practices", headers=h, json={"name": "Data", "business_unit_id": str(a.id)}
    ).json()
    assert (made["business_unit_id"], made["business_unit_name"]) == (str(a.id), "Alfa")
    moved = api.patch(
        f"/api/v1/practices/{made['id']}", headers=h, json={"business_unit_id": str(b.id)}
    ).json()
    assert moved["business_unit_name"] == "Beta"
    default = api.post("/api/v1/practices", headers=h, json={"name": "Senza"}).json()
    assert default["business_unit_name"] == DEFAULT_BUSINESS_UNIT  # facoltativa: «Da assegnare»


def test_practice_refuses_unknown_inactive_or_null_business_units(api, session):
    h = _admin(session)
    off = make_business_unit(session, name="Spenta", is_active=False)
    live = make_business_unit(session, name="Viva")
    practice = make_practice(session, name="P", business_unit_id=off.id)
    session.commit()
    p = f"/api/v1/practices/{practice.id}"
    assert (
        api.post(
            "/api/v1/practices",
            headers=h,
            json={"name": "X", "business_unit_id": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/v1/practices", headers=h, json={"name": "Y", "business_unit_id": str(off.id)}
        ).status_code
        == 422
    )
    assert api.patch(p, headers=h, json={"business_unit_id": None}).status_code == 422
    assert api.patch(p, headers=h, json={"business_unit_id": str(uuid.uuid4())}).status_code == 422
    assert (
        api.patch(p, headers=h, json={"name": "Rinominata"}).status_code == 200
    )  # la sua business unit spenta non blocca
    assert (
        api.patch(p, headers=h, json={"business_unit_id": str(off.id)}).status_code == 200
    )  # confermare quella che ha è ammesso
    assert api.patch(p, headers=h, json={"business_unit_id": str(live.id)}).status_code == 200


def test_employees_show_the_business_unit_of_their_practice(api, session):
    h = _admin(session)
    a, b = make_business_unit(session, name="Alfa"), make_business_unit(session, name="Beta")
    pa = make_practice(session, name="PA", business_unit_id=a.id)
    pb = make_practice(session, name="PB", business_unit_id=b.id)
    profile = make_profile(session)
    session.commit()
    made = api.post(
        "/api/v1/employees",
        headers=h,
        json={
            "first_name": "Ada",
            "last_name": "Test",
            "default_profile_id": str(profile.id),
            "practice_id": str(pa.id),
        },
    ).json()
    assert made["business_unit_name"] == "Alfa"
    moved = api.patch(
        f"/api/v1/employees/{made['id']}", headers=h, json={"practice_id": str(pb.id)}
    ).json()
    assert (moved["business_unit_id"], moved["business_unit_name"]) == (
        str(b.id),
        "Beta",
    )  # segue la practice
    listed = api.get("/api/v1/employees", headers=h).json()["items"]
    assert {e["business_unit_name"] for e in listed if e["id"] == made["id"]} == {"Beta"}


# ------------------------------------------------------------------ utenti
def _new_user(api, h, **over):
    body = {
        "email": f"nuovo{uuid.uuid4().hex[:6]}@huware.com",
        "full_name": "Nuovo",
        "role": "presale",
        **over,
    }
    return api.post("/api/v1/users", headers=h, json=body)


def test_a_presale_has_a_business_unit_and_it_is_shown(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Data & AI")
    session.commit()
    made = _new_user(api, h, business_unit_id=str(unit.id)).json()
    assert (made["business_unit_id"], made["business_unit_name"]) == (str(unit.id), "Data & AI")
    listed = api.get("/api/v1/users", headers=h).json()["items"]
    assert {u["business_unit_name"] for u in listed if u["id"] == made["id"]} == {"Data & AI"}
    assert (
        api.get(f"/api/v1/users/{made['id']}", headers=h).json()["business_unit_name"]
        == "Data & AI"
    )
    assert (
        _new_user(api, h).json()["business_unit_id"] is None
    )  # per i presale è facoltativa: serve a migrare


def test_a_business_unit_manager_must_have_one(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Cloud")
    session.commit()
    assert _new_user(api, h, role="bu_manager").status_code == 422
    ok = _new_user(api, h, role="bu_manager", business_unit_id=str(unit.id))
    assert ok.status_code == 201 and ok.json()["role"] == "bu_manager"
    uid = ok.json()["id"]
    assert (
        api.patch(f"/api/v1/users/{uid}", headers=h, json={"business_unit_id": None}).status_code
        == 422
    )
    assert (
        api.patch(f"/api/v1/users/{uid}", headers=h, json={"role": "presale"}).status_code == 200
    )  # il presale può non averla


def test_only_presale_and_managers_have_a_business_unit(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Cloud")
    session.commit()
    for role in ("admin", "viewer"):
        assert _new_user(api, h, role=role, business_unit_id=str(unit.id)).status_code == 422, role
    made = _new_user(api, h, business_unit_id=str(unit.id)).json()
    out = api.patch(f"/api/v1/users/{made['id']}", headers=h, json={"role": "viewer"})
    assert (
        out.status_code == 200 and out.json()["business_unit_id"] is None
    )  # cambiando ruolo la perde
    assert (
        api.patch(
            f"/api/v1/users/{made['id']}", headers=h, json={"business_unit_id": str(unit.id)}
        ).status_code
        == 422
    )


def test_business_unit_checks_for_people(api, session):
    h = _admin(session)
    off = make_business_unit(session, name="Spenta", is_active=False)
    live = make_business_unit(session, name="Viva")
    system = _system(session)
    session.commit()
    assert _new_user(api, h, business_unit_id=str(uuid.uuid4())).status_code == 422  # inesistente
    assert _new_user(api, h, business_unit_id=str(off.id)).status_code == 422  # disattivata
    assert (
        _new_user(api, h, business_unit_id=str(system.id)).status_code == 422
    )  # «Da assegnare» non è per le persone
    made = _new_user(api, h, business_unit_id=str(live.id)).json()
    api.patch(f"{URL}/{live.id}", headers=h, json={"is_active": False})
    assert (
        api.patch(
            f"/api/v1/users/{made['id']}", headers=h, json={"full_name": "Altro nome"}
        ).status_code
        == 200
    )  # tiene la sua
    assert (
        api.patch(f"/api/v1/users/{made['id']}", headers=h, json={"business_unit_id": None}).json()[
            "business_unit_id"
        ]
        is None
    )
    assert (
        api.patch(
            f"/api/v1/users/{made['id']}", headers=h, json={"business_unit_id": str(off.id)}
        ).status_code
        == 422
    )


def test_the_user_audit_entry_records_the_business_unit(api, session):
    h = _admin(session)
    unit = make_business_unit(session, name="Cloud")
    session.commit()
    made = _new_user(api, h, business_unit_id=str(unit.id)).json()
    api.patch(f"/api/v1/users/{made['id']}", headers=h, json={"business_unit_id": None})
    session.expire_all()
    entries = session.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "user", AuditLog.entity_id == uuid.UUID(made["id"]))
        .order_by(AuditLog.id)
    ).all()
    assert entries[0].changes["business_unit_id"] == str(unit.id)
    assert entries[1].changes["business_unit_id"] == [str(unit.id), None]
    assert User  # il registro dice anche da quale business unit si è passati
