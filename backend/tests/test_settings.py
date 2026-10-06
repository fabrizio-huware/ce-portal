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
    ok = Settings(_env_file=None, app_env="prod", jwt_secret="s" * 32, mail_backend="console")
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


# ------------------------------------------------------------------ email
def test_mail_backend_defaults_follow_the_environment():
    assert Settings(_env_file=None, app_env="local").effective_mail_backend == "console"
    prod = Settings(
        _env_file=None,
        app_env="prod",
        jwt_secret="s" * 32,
        mailjet_api_key="k",
        mailjet_api_secret="s",
    )
    assert prod.effective_mail_backend == "mailjet"


def test_mailjet_credentials_are_required_when_emails_really_go_out():
    with pytest.raises(ValidationError, match="MAILJET_API_KEY"):
        Settings(_env_file=None, app_env="prod", jwt_secret="s" * 32)
    with pytest.raises(ValidationError, match="MAILJET_API_KEY"):
        Settings(
            _env_file=None, app_env="test", jwt_secret="s" * 32, mailjet_api_key="solo-la-chiave"
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="local", mail_backend="mailjet")


def test_console_backend_can_be_chosen_outside_local_for_staging_without_mail():
    ok = Settings(_env_file=None, app_env="test", jwt_secret="s" * 32, mail_backend="console")
    assert ok.effective_mail_backend == "console"


def test_mail_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("MAILJET_API_KEY", "k")
    monkeypatch.setenv("MAILJET_API_SECRET", "s")
    monkeypatch.setenv("MAIL_BACKEND", "mailjet")
    monkeypatch.setenv("MAILJET_SANDBOX", "true")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://portale.huware.com/")
    s = Settings(_env_file=None)
    assert s.mailjet_sandbox is True and s.public_base_url == "https://portale.huware.com"
    assert (s.mail_from, s.mail_timeout_seconds, s.mail_max_attempts) == (
        "teamdata@huware.com",
        5.0,
        5,
    )
