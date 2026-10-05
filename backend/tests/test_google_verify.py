"""La libreria Google è simulata: qui si controlla come ne interpretiamo l'esito."""

import pytest

from app.core import google as g


def test_identity_is_mapped_and_email_lowercased(monkeypatch):
    seen = {}

    def fake_verify(token, request, client_id):
        seen.update(token=token, client_id=client_id)
        return {
            "email": " Mario.Rossi@Huware.com ",
            "sub": "123",
            "name": "Mario",
            "email_verified": True,
        }

    monkeypatch.setattr(g.id_token, "verify_oauth2_token", fake_verify)
    identity = g.verify_google_id_token("tok", "client-1")
    assert identity == g.GoogleIdentity("mario.rossi@huware.com", "123", "Mario", True)
    assert seen == {"token": "tok", "client_id": "client-1"}  # l'audience è sempre controllata


def test_missing_email_verified_means_not_verified(monkeypatch):
    monkeypatch.setattr(
        g.id_token, "verify_oauth2_token", lambda *a: {"email": "a@huware.com", "sub": "1"}
    )
    assert g.verify_google_id_token("t", "c").email_verified is False


def test_library_errors_become_our_error(monkeypatch):
    def boom(*args):
        raise ValueError("Token expired")

    monkeypatch.setattr(g.id_token, "verify_oauth2_token", boom)
    with pytest.raises(g.InvalidGoogleTokenError):
        g.verify_google_id_token("t", "c")
