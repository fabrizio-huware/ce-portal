"""I test non devono dipendere dall'ambiente di chi li lancia né toccare servizi reali."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

BACKEND = Path(__file__).resolve().parents[1]

# Quello che potrebbe essere rimasto esportato nel terminale dopo una prova con Mailjet vero
POLLUTED = {
    "MAIL_BACKEND": "mailjet",
    "MAILJET_API_KEY": "chiave-vera",
    "MAILJET_API_SECRET": "segreto-vero",
    "MAILJET_SANDBOX": "false",
    "PUBLIC_BASE_URL": "https://altro.example.com",
    "APP_ENV": "prod",
    "BOOTSTRAP_ADMIN_EMAIL": "qualcuno@huware.com",
}
SELECTED = [
    "tests/test_settings.py",
    "tests/test_mailjet_client.py::test_backend_selection_follows_the_environment",
    "tests/test_notification_events.py::test_the_local_console_backend_marks_emails_as_sent",
]


def test_the_suite_passes_even_when_the_shell_has_real_mailjet_variables_exported():
    env = {**os.environ, **POLLUTED}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *SELECTED],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=240,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-1000:]


def test_environment_variables_of_the_settings_are_removed_at_startup():
    for name in (
        "MAIL_BACKEND",
        "MAILJET_API_KEY",
        "MAILJET_API_SECRET",
        "APP_ENV",
        "JWT_SECRET",
        "DATABASE_URL",
    ):
        assert name not in os.environ


def test_test_settings_never_use_a_real_mail_provider():
    from tests.helpers import TEST_SETTINGS

    assert TEST_SETTINGS.effective_mail_backend == "console" and not TEST_SETTINGS.mailjet_api_key


@pytest.mark.parametrize(
    "url", ["https://api.mailjet.com/v3.1/send", "https://example.com", "http://192.168.1.10/x"]
)
def test_external_network_calls_are_blocked_in_tests(url):
    with pytest.raises(
        BaseException
    ) as exc:  # pytest.fail solleva un'eccezione che non si può ignorare
        requests.post(url, json={}, timeout=1)
    assert "bloccata" in str(exc.value)


def test_local_addresses_are_still_allowed(mailjet):
    assert requests.post(mailjet.url, json={"Messages": []}, timeout=2).status_code == 200
