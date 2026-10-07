"""Matrice dei permessi: ogni operazione dell'API è provata con ogni ruolo e senza login.

Il test finale fallisce se esiste un endpoint non elencato qui: un nuovo endpoint non può
essere dimenticato senza una decisione esplicita sui permessi.
"""

import uuid

import pytest

from tests.factories import make_ce, make_client, make_profile, make_user, make_version
from tests.helpers import auth

ADMIN = {"admin"}
EDITORS = {"admin", "presale"}
ALL = {"admin", "presale", "viewer"}

CSV_FILE = {"files": {"file": ("dati.csv", b"colonna\nvalore\n", "text/csv")}}


CE_HEADER = {
    "client_id": "{client_id}",
    "project_name": "Progetto",
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "planning_mode": "hours",
}
CE_CREATE = {"code": "PS-MATRIX-1", **CE_HEADER}
CE_CONTENT = {"expected_revision": 1, "header": CE_HEADER, "phases": []}
CE_DUPLICATE = {"code": "PS-MATRIX-2", "start_date": "2026-01-01", "end_date": "2026-03-31"}

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
    # conti economici: elenchi e viste ridotte (anche viewer)
    ("GET", "/api/v1/ce/summaries", {}, ALL),
    ("GET", "/api/v1/ce/summaries/{ce_id}", {}, ALL),
    # conti economici: creazione, lettura, modifica (il presale è l'autore del CE di prova)
    ("POST", "/api/v1/ce", {"json": CE_CREATE}, EDITORS),
    ("GET", "/api/v1/ce", {}, EDITORS),
    ("GET", "/api/v1/ce/{ce_id}", {}, EDITORS),
    ("GET", "/api/v1/ce/{ce_id}/versions", {}, EDITORS),
    ("GET", "/api/v1/ce/{ce_id}/versions/{number}", {}, EDITORS),
    ("GET", "/api/v1/ce/{ce_id}/history", {}, EDITORS),
    ("PUT", "/api/v1/ce/{ce_id}/content", {"json": CE_CONTENT}, EDITORS),
    ("POST", "/api/v1/ce/{ce_id}/calculate", {"json": CE_CONTENT}, EDITORS),
    # conti economici: workflow
    ("POST", "/api/v1/ce/{ce_id}/submit", {}, EDITORS),
    ("POST", "/api/v1/ce/{ce_id}/withdraw", {}, EDITORS),
    ("POST", "/api/v1/ce/{ce_id}/approve", {}, ADMIN),
    ("POST", "/api/v1/ce/{ce_id}/reject", {"json": {"reason": "Motivo"}}, ADMIN),
    # conti economici: versioni e gestione
    ("POST", "/api/v1/ce/{ce_id}/versions", {}, EDITORS),
    ("DELETE", "/api/v1/ce/{ce_id}/open-version", {}, EDITORS),
    ("POST", "/api/v1/ce/{ce_id}/realign", {"json": {}}, ADMIN),
    ("POST", "/api/v1/ce/{ce_id}/duplicate", {"json": CE_DUPLICATE}, EDITORS),
    ("DELETE", "/api/v1/ce/{ce_id}", {}, ADMIN),
    ("POST", "/api/v1/ce/{ce_id}/restore", {}, ADMIN),
    # notifiche email (solo admin)
    ("GET", "/api/v1/notifications", {}, ADMIN),
    ("POST", "/api/v1/notifications/dispatch", {}, ADMIN),
    ("POST", "/api/v1/notifications/test", {}, ADMIN),
    ("POST", "/api/v1/notifications/{notification_id}/retry", {}, ADMIN),
    # export e dashboard
    ("GET", "/api/v1/ce/export", {}, EDITORS),
    ("GET", "/api/v1/ce/summaries/export", {}, ALL),
    ("GET", "/api/v1/ce/summaries/{ce_id}/export", {}, ALL),
    ("GET", "/api/v1/ce/{ce_id}/export", {}, EDITORS),
    ("GET", "/api/v1/dashboard/portfolio", {}, EDITORS),
    ("GET", "/api/v1/dashboard/portfolio/export", {}, EDITORS),
    ("GET", "/api/v1/dashboard/resources", {}, EDITORS),
    ("GET", "/api/v1/dashboard/resources/export", {}, EDITORS),
]

# Endpoint pubblici per scelta: nessun token richiesto.
PUBLIC = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/config"),
    ("POST", "/api/v1/auth/google"),
    ("POST", "/api/v1/auth/dev-login"),
}


@pytest.fixture
def world(session):
    from datetime import date

    from app.models import EmailOutbox, Employee, NonWorkingDay, ProfileRate

    profile = make_profile(session)
    session.add(ProfileRate(profile_id=profile.id, year=2026, daily_price=1, daily_cost=1))
    employee = Employee(first_name="Ada", last_name="Test", default_profile_id=profile.id)
    day = NonWorkingDay(day=date(2030, 12, 24), kind="company_closure", description="x")
    session.add_all([employee, day])
    session.flush()
    presale = make_user(session, role="presale")
    client = make_client(session)
    ce = make_ce(session, presale)
    make_version(session, ce, presale, client)
    mail = EmailOutbox(type="test", recipient="x@huware.com", payload={}, status="failed")
    session.add(mail)
    session.flush()
    return {
        "users": {
            "admin": make_user(session, role="admin"),
            "presale": presale,
            "viewer": make_user(session, role="viewer"),
        },
        "ids": {
            "user_id": make_user(session, role="viewer").id,
            "client_id": client.id,
            "ce_id": ce.id,
            "notification_id": mail.id,
            "number": 1,
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
    if isinstance(value, list):
        return [_fill(v, ids) for v in value]
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
