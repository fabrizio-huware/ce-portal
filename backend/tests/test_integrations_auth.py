"""Accesso dei programmi esterni: token, elenco delle integrazioni, permessi e limite di una richiesta al secondo."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.service_auth import ServiceIdentity
from app.models import Integration, User
from tests.s2s_helpers import ALL, BASE, EMAIL, Caller, register

CLIENTS = "/anagrafiche/clienti"


@pytest.fixture
def call(api, env, session, service) -> Caller:
    register(api, env)
    return Caller(api, session, service)


def test_it_is_off_until_an_audience_is_configured(api, env):
    register(
        api, env
    )  # nessun verificatore simulato e nessuna audience: come in un ambiente non configurato
    response = api.get(f"{BASE}{CLIENTS}", headers={"Authorization": "Bearer x"})
    assert response.status_code == 503 and "non configurato" in response.json()["detail"]


def test_requests_without_or_with_bad_tokens_are_refused(call, service):
    assert call.api.get(f"{BASE}{CLIENTS}").status_code == 401  # nessun token
    service.fail = True
    assert call.get(CLIENTS).status_code == 401  # firma, scadenza o audience sbagliate
    service.fail = False
    service.unavailable = True
    assert (
        call.get(CLIENTS).status_code == 503
    )  # certificati di Google non raggiungibili: non è colpa di chi chiama
    service.unavailable = False
    assert call.get(CLIENTS).status_code == 200


def test_a_valid_token_of_an_unregistered_or_unverified_account_is_refused(call, service):
    service.identity = ServiceIdentity(
        email="altro@p.iam.gserviceaccount.com", sub="x", email_verified=True
    )
    headers = {"Authorization": "Bearer t"}
    assert call.api.get(f"{BASE}{CLIENTS}", headers=headers).status_code == 401  # non registrato
    service.identity = ServiceIdentity(email="anna@huware.com", sub="x", email_verified=True)
    assert (
        call.api.get(f"{BASE}{CLIENTS}", headers=headers).status_code == 401
    )  # una persona non è un'integrazione
    service.identity = ServiceIdentity(email=EMAIL, sub="x", email_verified=False)
    assert (
        call.api.get(f"{BASE}{CLIENTS}", headers=headers).status_code == 401
    )  # email non verificata
    service.identity = ServiceIdentity(email="", sub="x", email_verified=True)
    assert call.api.get(f"{BASE}{CLIENTS}", headers=headers).status_code == 401


def test_the_error_does_not_say_whether_the_account_exists(call, service):
    service.identity = ServiceIdentity(
        email="altro@p.iam.gserviceaccount.com", sub="x", email_verified=True
    )
    unknown = call.api.get(f"{BASE}{CLIENTS}", headers={"Authorization": "Bearer t"})
    service.identity = ServiceIdentity(email=EMAIL, sub="s", email_verified=False)
    unverified = call.api.get(f"{BASE}{CLIENTS}", headers={"Authorization": "Bearer t"})
    assert (
        unknown.json() == unverified.json()
    )  # stesso messaggio: non si può «provare» quali indirizzi esistono


def test_deactivating_stops_the_integration_at_the_next_request(call, api, env):
    assert call.get(CLIENTS).status_code == 200
    integration_id = api.get("/api/v1/integrations", headers=env.h(env.admin)).json()[0]["id"]
    api.patch(
        f"/api/v1/integrations/{integration_id}",
        json={"is_active": False},
        headers=env.h(env.admin),
    )
    assert call.get(CLIENTS).status_code == 401
    api.patch(
        f"/api/v1/integrations/{integration_id}", json={"is_active": True}, headers=env.h(env.admin)
    )
    assert call.get(CLIENTS).status_code == 200


def test_a_deactivated_service_user_stops_it_too(call, session):
    session.execute(update(User).where(User.is_service).values(is_active=False))
    session.commit()
    assert call.get(CLIENTS).status_code == 401


def test_the_first_call_binds_the_account_identifier_and_a_different_one_is_refused(call, session):
    assert call.get(CLIENTS).status_code == 200
    assert session.scalar(select(Integration.service_account_sub)) == "sa-1"
    other = Caller(
        call.api, call.session, call.service, sub="sa-2"
    )  # stesso indirizzo, account ricreato
    assert other.get(CLIENTS).status_code == 401
    assert call.get(CLIENTS).status_code == 200  # quello vero continua a funzionare


def test_permissions_are_enforced_per_endpoint(api, env, session, service):
    register(api, env, permissions=("read",))
    reader = Caller(api, session, service)
    assert reader.get(CLIENTS).status_code == 200
    assert (
        reader.post("/ce", json={}).status_code == 403
    )  # manca «create»: il permesso si controlla prima del contenuto
    uuid = "00000000-0000-0000-0000-000000000000"
    assert reader.put(f"/ce/{uuid}/content", json={}).status_code == 403
    assert reader.get(f"/ce/{uuid}/pdf").status_code == 403  # manca «export»


@pytest.mark.parametrize(
    "granted", [("create",), ("edit",), ("export",), ("create", "edit", "export")]
)
def test_without_read_nothing_can_be_read(api, env, session, service, granted):
    register(api, env, permissions=granted)
    caller = Caller(api, session, service)
    for path in (CLIENTS, "/anagrafiche/profili", "/anagrafiche/collaboratori", "/ce"):
        assert caller.get(path).status_code == 403, path


def test_one_request_per_second_per_integration(call, session):
    assert call.get(CLIENTS).status_code == 200
    second = call.get(CLIENTS, rate_reset=False)  # subito dopo: troppo presto
    assert second.status_code == 429 and second.headers["Retry-After"] == "1"
    assert "una al secondo" in second.json()["detail"]
    marker = session.scalar(select(Integration.last_used_at))
    assert call.get(CLIENTS, rate_reset=False).status_code == 429
    session.expire_all()
    assert (
        session.scalar(select(Integration.last_used_at)) == marker
    )  # il rifiuto non sposta la finestra


def test_after_a_second_the_next_request_goes_through(call, session):
    assert call.get(CLIENTS).status_code == 200
    session.execute(
        update(Integration).values(last_used_at=datetime.now(UTC) - timedelta(seconds=1.5))
    )
    session.commit()
    assert call.get(CLIENTS, rate_reset=False).status_code == 200


def test_the_limit_is_per_integration(api, env, session, service):
    register(api, env)
    register(api, env, name="Altro", email="altro@p.iam.gserviceaccount.com")
    first = Caller(api, session, service)
    second = Caller(api, session, service, email="altro@p.iam.gserviceaccount.com", sub="sa-9")
    assert first.get(CLIENTS).status_code == 200
    session.execute(
        update(Integration)
        .where(Integration.service_account_email != EMAIL)
        .values(last_used_at=None)
    )
    session.commit()
    assert (
        second.get(CLIENTS, rate_reset=False).status_code == 200
    )  # l'altra non è toccata dal limite della prima
    assert first.get(CLIENTS, rate_reset=False).status_code == 429


def test_last_use_is_recorded_for_the_admin_screen(call, api, env):
    assert (
        api.get("/api/v1/integrations", headers=env.h(env.admin)).json()[0]["last_used_at"] is None
    )
    assert call.get(CLIENTS).status_code == 200
    assert (
        api.get("/api/v1/integrations", headers=env.h(env.admin)).json()[0]["last_used_at"]
        is not None
    )
    assert set(ALL) == {"create", "edit", "read", "export"}


def test_each_deactivation_flag_stops_it_on_its_own(call, session):
    """L'integrazione e il suo utente di servizio sono due interruttori: ciascuno basta da solo."""
    assert call.get(CLIENTS).status_code == 200
    session.execute(
        update(Integration).values(is_active=False)
    )  # solo l'integrazione, l'utente resta attivo
    session.commit()
    assert call.get(CLIENTS).status_code == 401
    session.execute(update(Integration).values(is_active=True))
    session.commit()
    assert call.get(CLIENTS).status_code == 200
