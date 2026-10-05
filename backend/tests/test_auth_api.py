import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.google import GoogleIdentity
from app.main import create_app
from app.models import AuditLog, User
from tests.factories import make_user
from tests.helpers import TEST_SETTINGS, auth

LOGIN = "/api/v1/auth/google"


def _identity(email, sub="g-1", verified=True):
    return GoogleIdentity(email=email, sub=sub, name="Nome", email_verified=verified)


def test_login_success_links_google_account_and_returns_working_token(api, google, session):
    user = make_user(session, role="presale", email="mario@huware.com")
    google.identity = _identity("mario@huware.com", sub="google-sub-1")

    resp = api.post(LOGIN, json={"id_token": "qualsiasi"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 8 * 3600
    assert body["user"]["email"] == "mario@huware.com"
    assert body["user"]["role"] == "presale"
    session.refresh(user)
    assert user.google_sub == "google-sub-1"
    assert user.last_login_at is not None
    assert "link_google" in session.scalars(select(AuditLog.action)).all()

    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == str(user.id)


def test_second_login_with_same_google_account_works(api, google, session):
    make_user(session, email="mario@huware.com")
    google.identity = _identity("mario@huware.com", sub="s1")
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 200
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 200


def test_different_google_account_for_same_email_is_rejected(api, google, session):
    make_user(session, email="mario@huware.com", google_sub="originale")
    google.identity = _identity("mario@huware.com", sub="intruso")
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 403


def test_unknown_user_is_rejected(api, google):
    google.identity = _identity("sconosciuto@huware.com")
    resp = api.post(LOGIN, json={"id_token": "t"})
    assert resp.status_code == 403
    assert "non abilitato" in resp.json()["detail"]


def test_inactive_user_is_rejected(api, google, session):
    make_user(session, email="ex@huware.com", is_active=False)
    google.identity = _identity("ex@huware.com")
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 403


def test_domain_not_allowed_is_rejected_even_if_user_exists(api, google, session):
    make_user(session, email="esterno@gmail.com")
    google.identity = _identity("esterno@gmail.com")
    resp = api.post(LOGIN, json={"id_token": "t"})
    assert resp.status_code == 403
    assert "Dominio" in resp.json()["detail"]


def test_unverified_google_email_is_rejected(api, google, session):
    make_user(session, email="mario@huware.com")
    google.identity = _identity("mario@huware.com", verified=False)
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 403


def test_invalid_google_token_is_401(api, google):
    google.fail = True
    assert api.post(LOGIN, json={"id_token": "t"}).status_code == 401


def test_login_without_configured_client_id_is_503(session):
    settings = TEST_SETTINGS.model_copy(update={"google_oauth_client_id": None})
    application = create_app(settings)
    from app.db.session import get_session

    application.dependency_overrides[get_session] = lambda: session
    application.dependency_overrides[get_settings] = lambda: settings
    resp = TestClient(application).post(LOGIN, json={"id_token": "t"})
    assert resp.status_code == 503


def test_login_request_rejects_unknown_fields(api, google):
    assert api.post(LOGIN, json={"id_token": "t", "extra": 1}).status_code == 422
    assert api.post(LOGIN, json={}).status_code == 422


# ---- uso del token ----
def test_missing_or_malformed_authorization_is_401(api):
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_expired_token_is_401(api, session):
    user = make_user(session)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "iss": "ce-portal",
            "iat": now - timedelta(hours=9),
            "exp": now - timedelta(hours=1),
        },
        TEST_SETTINGS.jwt_secret,
        algorithm="HS256",
    )
    assert (
        api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_token_of_unknown_user_is_401(api):
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iss": "ce-portal",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        TEST_SETTINGS.jwt_secret,
        algorithm="HS256",
    )
    assert (
        api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_deactivating_a_user_invalidates_their_token_immediately(api, session):
    user = make_user(session)
    headers = auth(user)
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 200
    user.is_active = False
    session.flush()
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_role_change_takes_effect_immediately(api, session):
    user = make_user(session, role="viewer")
    headers = auth(user)
    assert api.get("/api/v1/users", headers=headers).status_code == 403
    user.role = "admin"
    session.flush()
    assert api.get("/api/v1/users", headers=headers).status_code == 200
    user.role = "viewer"
    session.flush()
    assert api.get("/api/v1/users", headers=headers).status_code == 403


# ---- login simulato solo in locale ----
def test_dev_login_works_locally(api, session):
    make_user(session, email="dev@huware.com", role="admin")
    resp = api.post("/api/v1/auth/dev-login", json={"email": "DEV@huware.com"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert api.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_dev_login_rejects_unknown_and_inactive_users(api, session):
    make_user(session, email="off@huware.com", is_active=False)
    assert api.post("/api/v1/auth/dev-login", json={"email": "off@huware.com"}).status_code == 403
    assert (
        api.post("/api/v1/auth/dev-login", json={"email": "nessuno@huware.com"}).status_code == 403
    )


def test_dev_login_does_not_exist_outside_local():
    settings = TEST_SETTINGS.model_copy(update={"app_env": "test"})
    application = create_app(settings)
    paths = application.openapi()["paths"]
    assert "/api/v1/auth/dev-login" not in paths
    assert (
        TestClient(application)
        .post("/api/v1/auth/dev-login", json={"email": "a@huware.com"})
        .status_code
        == 404
    )


def test_user_model_is_untouched_by_failed_logins(api, google, session):
    user = make_user(session, email="mario@huware.com")
    google.identity = _identity("mario@huware.com", verified=False)
    api.post(LOGIN, json={"id_token": "t"})
    session.refresh(user)
    assert user.google_sub is None and user.last_login_at is None
    assert session.scalar(select(User.id).where(User.id == user.id)) is not None
