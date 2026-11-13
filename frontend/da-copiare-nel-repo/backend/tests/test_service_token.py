"""Verifica reale degli ID token Google: firma, scadenza, issuer, audience.

Nessuna rete: i certificati «di Google» sono una chiave generata qui e servita da un finto client HTTP,
ma la libreria che controlla il token è quella vera. Così si prova che un token sbagliato non passa.
"""

import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from google.auth import crypt, jwt

from app.core.config import Settings
from app.core.service_auth import (
    InvalidServiceTokenError,
    ServiceVerifierUnavailableError,
    expand_audiences,
    get_service_verifier,
    verify_service_token,
)

AUD = "https://portale-ce.example.run.app"
KID = "chiave-1"
ISSUER = "https://accounts.google.com"


def make_key():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem.decode()


PRIVATE, PUBLIC = make_key()
OTHER_PRIVATE, _ = make_key()


class FakeResponse:
    def __init__(self, status: int, data: bytes) -> None:
        self.status, self.data, self.headers = status, data, {}


class FakeCerts:
    """Al posto dell'indirizzo dei certificati di Google."""

    def __init__(self, certs: dict[str, str], status: int = 200) -> None:
        self.certs, self.status = certs, status

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        return FakeResponse(self.status, json.dumps(self.certs).encode())


CERTS = FakeCerts({KID: PUBLIC})


def token(*, key=PRIVATE, kid=KID, **over) -> str:
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": AUD,
        "sub": "1234567890",
        "email": "Portale@Progetto.iam.gserviceaccount.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
        **over,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(crypt.RSASigner.from_string(key, kid), payload, {"kid": kid}).decode()


def verify(raw: str, audiences=(AUD,), certs=CERTS):
    return verify_service_token(raw, list(audiences), request=certs)


def test_a_genuine_token_is_accepted_and_the_email_is_lowercased():
    identity = verify(token())
    assert (identity.email, identity.sub, identity.email_verified) == (
        "portale@progetto.iam.gserviceaccount.com",
        "1234567890",
        True,
    )


def test_the_account_flag_for_an_unverified_email_is_passed_on():
    assert (
        verify(token(email_verified=False)).email_verified is False
    )  # è il chiamante a rifiutarlo


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            lambda: token(aud="https://un-altro-servizio.run.app"), id="audience-sbagliata"
        ),
        pytest.param(lambda: token(aud=None), id="senza-audience"),
        pytest.param(lambda: token(exp=int(time.time()) - 3600), id="scaduto"),
        pytest.param(
            lambda: token(iat=int(time.time()) + 3600, exp=int(time.time()) + 7200), id="dal-futuro"
        ),
        pytest.param(lambda: token(iss="https://accounts.evil.example"), id="issuer-sbagliato"),
        pytest.param(lambda: token(iss=None), id="senza-issuer"),
        pytest.param(lambda: token(key=OTHER_PRIVATE), id="firmato-con-un-altra-chiave"),
        pytest.param(lambda: token(kid="chiave-sconosciuta"), id="chiave-sconosciuta"),
        pytest.param(lambda: token(sub=None), id="senza-identificativo"),
        pytest.param(lambda: "non-e-un-token", id="spazzatura"),
        pytest.param(lambda: "", id="vuoto"),
    ],
)
def test_wrong_tokens_never_pass(bad):
    with pytest.raises(InvalidServiceTokenError):
        verify(bad())


def test_a_tampered_payload_is_refused():
    head, payload, signature = token().split(".")
    forged = jwt.encode(
        crypt.RSASigner.from_string(OTHER_PRIVATE, KID), {"aud": AUD}, {"kid": KID}
    ).decode()
    _, forged_payload, _ = forged.split(".")
    with pytest.raises(InvalidServiceTokenError):
        verify(f"{head}.{forged_payload}.{signature}")  # payload cambiato, firma originale


def test_a_token_for_the_wrong_portal_is_refused_even_if_perfectly_signed():
    with pytest.raises(InvalidServiceTokenError):
        verify(token(aud="https://portale-di-test.example.run.app"))


def test_without_a_configured_audience_nothing_is_ever_accepted():
    for audiences in ([], [""], ["  "]):
        with pytest.raises(InvalidServiceTokenError):
            verify(
                token(), audiences=audiences
            )  # la libreria, senza audience, non la controllerebbe


def test_the_trailing_slash_does_not_matter_and_several_addresses_can_be_configured():
    assert verify(
        token(aud=AUD + "/")
    ).sub  # il chiamante ha scritto l'indirizzo con la barra finale
    assert verify(token(), audiences=[AUD + "/"]).sub  # configurato con la barra finale
    assert verify(
        token(aud="https://secondo.example"),
        audiences=["https://primo.example", AUD, "https://secondo.example"],
    ).sub
    assert expand_audiences([" https://a.example/ ", ""]) == [
        "https://a.example",
        "https://a.example/",
    ]


def test_a_few_seconds_of_clock_difference_are_tolerated_but_not_minutes():
    now = int(time.time())
    assert verify(
        token(iat=now + 5, exp=now + 3600)
    ).sub  # orologio del chiamante avanti di 5 secondi
    assert verify(token(exp=now - 5)).sub  # scaduto da 5 secondi
    with pytest.raises(InvalidServiceTokenError):
        verify(token(exp=now - 120))
    with pytest.raises(InvalidServiceTokenError):
        verify(token(iat=now + 120, exp=now + 3600))


def test_unreachable_google_certificates_are_not_the_callers_fault():
    with pytest.raises(ServiceVerifierUnavailableError):
        verify(token(), certs=FakeCerts({}, status=500))


def test_the_dependency_needs_audiences_to_exist():
    settings = Settings(s2s_audiences="")
    with pytest.raises(HTTPException) as caught:
        get_service_verifier(settings)
    assert caught.value.status_code == 503
    verifier = get_service_verifier(Settings(s2s_audiences=AUD))
    assert callable(verifier)
