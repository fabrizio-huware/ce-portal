import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import InvalidTokenError, create_access_token, decode_access_token
from tests.helpers import TEST_SETTINGS


def test_token_roundtrip():
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(user_id, TEST_SETTINGS)
    assert expires_in == 8 * 3600
    assert decode_access_token(token, TEST_SETTINGS) == user_id


def _forge(**overrides):
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": "ce-portal",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    payload.update(overrides)
    secret = overrides.pop("_secret", TEST_SETTINGS.jwt_secret)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.parametrize(
    "token",
    [
        "non-un-token",
        "",
        _forge(exp=datetime.now(UTC) - timedelta(seconds=5)),  # scaduto
        _forge(iss="altro-servizio"),  # issuer errato
    ],
)
def test_invalid_tokens_are_rejected(token):
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, TEST_SETTINGS)


def test_token_signed_with_another_secret_is_rejected():
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iss": "ce-portal",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "un-altro-segreto-" + "y" * 30,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, TEST_SETTINGS)


def test_unsigned_and_expiryless_tokens_are_rejected():
    unsigned = jwt.encode({"sub": str(uuid.uuid4()), "iss": "ce-portal"}, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned, TEST_SETTINGS)
    no_exp = jwt.encode(
        {"sub": str(uuid.uuid4()), "iss": "ce-portal"}, TEST_SETTINGS.jwt_secret, algorithm="HS256"
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(no_exp, TEST_SETTINGS)


def test_subject_must_be_a_uuid():
    with pytest.raises(InvalidTokenError):
        decode_access_token(_forge(sub="123"), TEST_SETTINGS)
