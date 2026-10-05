import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_DEV_SECRET, Settings


def test_default_secret_allowed_only_locally():
    assert Settings(_env_file=None, app_env="local").jwt_secret == DEFAULT_DEV_SECRET
    for env in ("test", "prod"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, app_env=env)


def test_short_secret_rejected_outside_local():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="prod", jwt_secret="troppo-corto")
    ok = Settings(_env_file=None, app_env="prod", jwt_secret="s" * 32)
    assert ok.app_env == "prod"


def test_lists_are_read_from_comma_separated_environment_variables(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "Huware.com, @esempio.it")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["http://a.test", "http://b.test"]
    assert s.allowed_email_domains == ["huware.com", "esempio.it"]


def test_bootstrap_email_is_normalized(monkeypatch):
    assert Settings(
        _env_file=None, bootstrap_admin_email="  Admin@Huware.com "
    ).bootstrap_admin_email == ("admin@huware.com")
    assert Settings(_env_file=None, bootstrap_admin_email="  ").bootstrap_admin_email is None
