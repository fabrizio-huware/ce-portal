"""Gestione delle integrazioni: solo amministratori; l'utente di servizio resta fuori dalle schermate delle persone."""

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Integration, User
from tests.helpers import TEST_SETTINGS
from tests.s2s_helpers import EMAIL, register

URL = "/api/v1/integrations"


def test_only_admins_manage_integrations(api, env):
    created = register(api, env)
    for user in (env.presale, env.viewer):
        assert api.get(URL, headers=env.h(user)).status_code == 403
        assert (
            api.patch(f"{URL}/{created['id']}", json={"name": "X"}, headers=env.h(user)).status_code
            == 403
        )
        body = {
            "name": "Altro",
            "service_account_email": "a@p.iam.gserviceaccount.com",
            "permissions": ["read"],
        }
        assert api.post(URL, json=body, headers=env.h(user)).status_code == 403
    assert api.get(URL).status_code == 401


def test_register_creates_the_service_user_and_hides_it_from_people_screens(api, env, session):
    created = register(api, env, permissions=("read", "create", "read"))
    assert created["permissions"] == ["create", "read"]  # senza doppioni, in ordine
    assert created["is_active"] is True and created["last_used_at"] is None
    assert created["service_account_email"] == EMAIL

    user = session.get(User, created["user_id"])
    assert (user.role, user.is_service, user.is_active, user.email) == (
        "presale",
        True,
        True,
        EMAIL,
    )
    assert user.full_name == "Portale esterno (servizio)"

    listed = api.get("/api/v1/users", headers=env.h(env.admin)).json()["items"]
    assert str(user.id) not in {u["id"] for u in listed}
    assert api.get(f"/api/v1/users/{user.id}", headers=env.h(env.admin)).status_code == 404
    patch = api.patch(f"/api/v1/users/{user.id}", json={"role": "admin"}, headers=env.h(env.admin))
    assert patch.status_code == 404  # non si può trasformare in amministratore da lì


def test_registration_is_validated(api, env):
    h = env.h(env.admin)
    ok = {
        "name": "Uno",
        "service_account_email": "uno@p.iam.gserviceaccount.com",
        "permissions": ["read"],
    }
    for bad in (
        {**ok, "service_account_email": "anna@huware.com"},  # non è un account di servizio
        {**ok, "service_account_email": "non-una-email"},
        {**ok, "permissions": []},
        {**ok, "permissions": ["read", "delete"]},
        {**ok, "name": "   "},
        {**ok, "inventato": 1},
    ):
        assert api.post(URL, json=bad, headers=h).status_code == 422, bad
    assert api.post(URL, json=ok, headers=h).status_code == 201
    assert (
        api.post(URL, json={**ok, "name": "Due"}, headers=h).status_code == 409
    )  # stesso indirizzo
    upper = {**ok, "name": "Due", "service_account_email": "UNO@P.IAM.GSERVICEACCOUNT.COM"}
    assert api.post(URL, json=upper, headers=h).status_code == 409  # maiuscole indifferenti
    other = {**ok, "service_account_email": "due@p.iam.gserviceaccount.com", "name": "UNO"}
    assert api.post(URL, json=other, headers=h).status_code == 409  # stesso nome


def test_an_address_that_is_not_a_service_account_is_refused_even_if_it_belongs_to_a_person(
    api, env
):
    body = {"name": "X", "service_account_email": env.presale.email, "permissions": ["read"]}
    assert (
        api.post(URL, json=body, headers=env.h(env.admin)).status_code == 422
    )  # non è un account di servizio


def test_update_keeps_the_service_user_in_sync(api, env, session):
    created = register(api, env)
    h = env.h(env.admin)
    user = session.get(User, created["user_id"])
    r = api.patch(
        f"{URL}/{created['id']}",
        json={"name": "Nuovo nome", "permissions": ["read", "read"]},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["permissions"] == ["read"]
    session.refresh(user)
    assert user.full_name == "Nuovo nome (servizio)"
    r = api.patch(f"{URL}/{created['id']}", json={"is_active": False}, headers=h)
    assert r.json()["is_active"] is False
    session.refresh(user)
    assert user.is_active is False
    assert (
        api.patch(f"{URL}/{created['id']}", json={"is_active": True}, headers=h).status_code == 200
    )
    session.refresh(user)
    assert user.is_active is True
    assert api.patch(f"{URL}/{created['id']}", json={"name": None}, headers=h).status_code == 422
    assert (
        api.patch(
            f"{URL}/{created['id']}",
            json={"service_account_email": "x@p.iam.gserviceaccount.com"},
            headers=h,
        ).status_code
        == 422
    )
    assert (
        api.patch(
            f"{URL}/00000000-0000-0000-0000-000000000000", json={"name": "X"}, headers=h
        ).status_code
        == 404
    )


def test_renaming_to_an_existing_name_is_refused(api, env):
    register(api, env, name="Alfa")
    beta = register(api, env, name="Beta", email="beta@p.iam.gserviceaccount.com")
    r = api.patch(f"{URL}/{beta['id']}", json={"name": "alfa"}, headers=env.h(env.admin))
    assert r.status_code == 409


def test_changes_are_recorded_in_the_audit_log(api, env, session):
    from app.models import AuditLog

    created = register(api, env)
    api.patch(f"{URL}/{created['id']}", json={"is_active": False}, headers=env.h(env.admin))
    actions = session.scalars(
        select(AuditLog.action).where(AuditLog.entity_type == "integration").order_by(AuditLog.id)
    ).all()
    assert actions == ["create", "update"]


def test_a_service_user_can_never_log_in_nor_use_a_portal_token(api, env, session):
    created = register(api, env)
    user = session.get(User, created["user_id"])
    token, _ = create_access_token(user.id, TEST_SETTINGS)  # anche se un token esistesse...
    assert (
        api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )
    assert api.get("/api/v1/ce", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    login = api.post("/api/v1/auth/dev-login", json={"email": EMAIL})
    assert login.status_code in (403, 404)  # il login simulato (solo locale) lo rifiuta


@pytest.mark.parametrize("path", ["", "/00000000-0000-0000-0000-000000000000"])
def test_integrations_are_never_deleted(api, env, path):
    created = register(api, env)
    assert (
        api.delete(f"{URL}{path or '/' + created['id']}", headers=env.h(env.admin)).status_code
        == 405
    )
    assert api.get(URL, headers=env.h(env.admin)).json()[0]["id"] == created["id"]
    assert Integration  # nessuna rotta di eliminazione: si disattiva


def test_a_service_user_cannot_log_in_through_google_even_with_an_allowed_domain(
    api, env, session, google
):
    """Anche se un utente di servizio avesse un indirizzo di un dominio ammesso, il login lo rifiuta."""
    from app.core.google import GoogleIdentity
    from tests.factories import make_user

    make_user(session, role="presale", email="servizio@huware.com", is_service=True)
    session.commit()
    google.identity = GoogleIdentity(
        email="servizio@huware.com", sub="g-1", name="S", email_verified=True
    )
    response = api.post("/api/v1/auth/google", json={"id_token": "x"})
    assert response.status_code == 403
    person = make_user(session, role="presale", email="persona@huware.com")
    session.commit()
    google.identity = GoogleIdentity(email=person.email, sub="g-2", name="P", email_verified=True)
    assert (
        api.post("/api/v1/auth/google", json={"id_token": "x"}).status_code == 200
    )  # una persona entra
