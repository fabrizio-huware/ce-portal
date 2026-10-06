"""Comandi da terminale: invio della coda (per il job pianificato) ed email di prova."""

import pytest

import app.notifications.__main__ as cli
from app.models import EmailOutbox
from app.notifications import enqueue
from app.notifications.mailer import SendOutcome
from tests.helpers import TEST_SETTINGS


class SessionContext:
    """Fa usare ai comandi la sessione di test invece di aprirne una sul database locale."""

    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


@pytest.fixture
def wired(session, mailer, monkeypatch):
    monkeypatch.setattr(cli, "SessionLocal", SessionContext(session))
    monkeypatch.setattr(cli, "get_settings", lambda: TEST_SETTINGS)
    monkeypatch.setattr(cli, "build_mailer", lambda settings: mailer)
    return mailer


def queue(session, n=2):
    for i in range(n):
        enqueue(
            session,
            type_="test",
            recipient_email=f"u{i}@huware.com",
            payload={"recipient_name": "U"},
        )
    session.flush()


def test_dispatch_sends_the_queue_and_reports(wired, session, capsys):
    queue(session)
    assert cli.main(["dispatch"]) == 0
    assert "inviate 2" in capsys.readouterr().out and len(wired.sent) == 2


def test_dispatch_returns_an_error_code_when_something_fails_for_good(wired, session, capsys):
    queue(session, 1)
    wired.behavior = lambda emails: [SendOutcome(False, retry=False, error="x") for _ in emails]
    assert cli.main(["dispatch"]) == 1
    assert "fallite 1" in capsys.readouterr().out


def test_dispatch_respects_the_limit(wired, session):
    queue(session, 3)
    cli.main(["dispatch", "--limit", "2"])
    assert len(wired.sent) == 2
    assert session.query(EmailOutbox).filter_by(status="pending").count() == 1


def test_dispatch_with_an_empty_queue_is_fine(wired, capsys):
    assert cli.main(["dispatch"]) == 0
    assert "Elaborate 0" in capsys.readouterr().out


def test_send_test_reports_success_and_failure(wired, capsys):
    assert cli.main(["send-test", "io@huware.com"]) == 0
    assert "OK" in capsys.readouterr().out and wired.sent[0].to_email == "io@huware.com"
    wired.behavior = lambda emails: [
        SendOutcome(False, retry=True, error="credenziali") for _ in emails
    ]
    assert cli.main(["send-test", "io@huware.com"]) == 1
    assert "ERRORE" in capsys.readouterr().out


def test_send_test_does_not_use_the_queue(wired, session):
    cli.main(["send-test", "io@huware.com"])
    assert session.query(EmailOutbox).count() == 0


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])
