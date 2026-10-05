"""Matrice dei permessi: ogni operazione dell'API è provata con ogni ruolo e senza login.

Il test finale fallisce se esiste un endpoint non elencato qui: un nuovo endpoint non può
essere dimenticato senza una decisione esplicita sui permessi.
"""

import uuid

import pytest

from tests.factories import make_client, make_profile, make_user
from tests.helpers import auth

ADMIN = {"admin"}
EDITORS = {"admin", "presale"}
ALL = {"admin", "presale", "viewer"}

CSV_FILE = {"files": {"file": ("dati.csv", b"colonna\nvalore\n", "text/csv")}}

# (metodo, percorso, argomenti della richiesta, ruoli ammessi)
MATRIX = [
    ("GET", "/api/v1/auth/me", {}, ALL),
    # utenti
    ("GET", "/api/v1/users", {}, ADMIN),
    (
        "POST",
        "/api/v1/users",
        {"json": {"email": "n@huware.com", "full_name": "N", "role": "viewer"}},
        ADMIN,
    ),
    ("GET", "/api/v1/users/{user_id}", {}, ADMIN),
    ("PATCH", "/api/v1/users/{user_id}", {"json": {"full_name": "Nuovo"}}, ADMIN),
    # clienti
    ("GET", "/api/v1/clients/lookup", {}, ALL),
    ("GET", "/api/v1/clients", {}, EDITORS),
    ("POST", "/api/v1/clients", {"json": {"name": "Nuovo cliente"}}, EDITORS),
    ("GET", "/api/v1/clients/{client_id}", {}, EDITORS),
    ("PATCH", "/api/v1/clients/{client_id}", {"json": {"address": "Via Roma 1"}}, EDITORS),
    # collaboratori
    ("GET", "/api/v1/employees", {}, EDITORS),
    (
        "POST",
        "/api/v1/employees",
        {"json": {"first_name": "A", "last_name": "B", "default_profile_id": "{profile_id}"}},
        ADMIN,
    ),
    ("POST", "/api/v1/employees/import", CSV_FILE, ADMIN),
    ("GET", "/api/v1/employees/{employee_id}", {}, EDITORS),
    ("PATCH", "/api/v1/employees/{employee_id}", {"json": {"is_active": False}}, ADMIN),
    # profili e tariffe
    ("GET", "/api/v1/profiles", {}, EDITORS),
    ("POST", "/api/v1/profiles", {"json": {"name": "Nuovo profilo"}}, ADMIN),
    ("POST", "/api/v1/profiles/import-rates", CSV_FILE, ADMIN),
    ("GET", "/api/v1/profiles/{profile_id}", {}, EDITORS),
    ("PATCH", "/api/v1/profiles/{profile_id}", {"json": {"sort_order": 5}}, ADMIN),
    (
        "PUT",
        "/api/v1/profiles/{profile_id}/rates/{year}",
        {"json": {"daily_price": "100", "daily_cost": "50"}},
        ADMIN,
    ),
    ("DELETE", "/api/v1/profiles/{profile_id}/rates/{year}", {}, ADMIN),
    # calendario
    ("GET", "/api/v1/calendar", {}, EDITORS),
    (
        "POST",
        "/api/v1/calendar",
        {"json": {"day": "2030-01-02", "kind": "company_closure", "description": "x"}},
        ADMIN,
    ),
    ("POST", "/api/v1/calendar/import", CSV_FILE, ADMIN),
    ("POST", "/api/v1/calendar/generate-holidays", {"json": {"year": 2031}}, ADMIN),
    ("PATCH", "/api/v1/calendar/{day_id}", {"json": {"description": "nuova"}}, ADMIN),
    ("DELETE", "/api/v1/calendar/{day_id}", {}, ADMIN),
]

# Endpoint pubblici per scelta: nessun token richiesto.
PUBLIC = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/google"),
    ("POST", "/api/v1/auth/dev-login"),
}


@pytest.fixture
def world(session):
    from datetime import date

    from app.models import Employee, NonWorkingDay, ProfileRate

    profile = make_profile(session)
    session.add(ProfileRate(profile_id=profile.id, year=2026, daily_price=1, daily_cost=1))
    employee = Employee(first_name="Ada", last_name="Test", default_profile_id=profile.id)
    day = NonWorkingDay(day=date(2030, 12, 24), kind="company_closure", description="x")
    session.add_all([employee, day])
    session.flush()
    return {
        "users": {r: make_user(session, role=r) for r in ("admin", "presale", "viewer")},
        "ids": {
            "user_id": make_user(session, role="viewer").id,
            "client_id": make_client(session).id,
            "profile_id": profile.id,
            "employee_id": employee.id,
            "day_id": day.id,
            "year": 2026,
        },
    }


def _fill(value, ids):
    if isinstance(value, str):
        return value.format(**{k: v for k, v in ids.items()}) if "{" in value else value
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.parametrize("role", ["admin", "presale", "viewer", None])
@pytest.mark.parametrize(
    "method,path,kwargs,allowed", MATRIX, ids=[f"{m} {p}" for m, p, _, _ in MATRIX]
)
def test_permission_matrix(api, world, method, path, kwargs, allowed, role):
    headers = {} if role is None else auth(world["users"][role])
    url = path.format(**world["ids"])
    kw = {k: (_fill(v, world["ids"]) if k == "json" else v) for k, v in kwargs.items()}

    resp = api.request(method, url, headers=headers, **kw)

    if role is None:
        assert resp.status_code == 401, resp.text
    elif role in allowed:
        assert resp.status_code not in (401, 403), resp.text
        assert resp.status_code < 500, resp.text
    else:
        assert resp.status_code == 403, resp.text


def test_every_endpoint_is_covered_by_the_matrix(app):
    """Un endpoint nuovo senza una riga nella matrice (o in PUBLIC) fa fallire questo test."""
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    covered = {(m, p) for m, p, _, _ in MATRIX} | PUBLIC
    assert actual - covered == set(), "endpoint senza regola di permesso nella matrice"
    assert covered - actual == set(), "righe della matrice per endpoint che non esistono più"


def test_public_endpoints_need_no_token(api):
    assert api.get("/api/v1/health").status_code == 200
    assert uuid.UUID(int=0)  # i login sono provati in test_auth_api
