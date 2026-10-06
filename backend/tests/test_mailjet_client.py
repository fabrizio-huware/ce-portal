"""Il client Mailjet, provato con chiamate HTTP reali verso un finto Mailjet locale."""

import socket

import pytest

from app.core.config import Settings
from app.notifications.mailer import (
    BATCH_SIZE,
    ConsoleMailer,
    MailjetMailer,
    OutgoingEmail,
    build_mailer,
)

SECRET = "il-segreto-che-non-deve-uscire-mai"


def make(url: str, **over) -> MailjetMailer:
    values = dict(
        sender_email="teamdata@huware.com",
        sender_name="Portale CE",
        url=url,
        sandbox=False,
        timeout=2.0,
    )
    values.update(over)
    return MailjetMailer("chiave-pubblica", SECRET, **values)


def email(n: int = 1) -> OutgoingEmail:
    return OutgoingEmail(
        f"id-{n}",
        f"utente{n}@huware.com",
        f"Utente {n}",
        f"Oggetto {n}",
        f"Testo {n}",
        f"<p>Html {n}</p>",
    )


def free_port_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}/v3.1/send"  # nessuno è in ascolto


def error_message(code: str, status: int, text: str = "errore") -> dict:
    return {
        "Status": "error",
        "Errors": [{"ErrorCode": code, "StatusCode": status, "ErrorMessage": text}],
    }


# ------------------------------------------------------------------ formato della richiesta
def test_request_format_matches_the_send_api_v31(mailjet):
    outcome = make(mailjet.url).send([email(1)])[0]
    assert outcome.ok and outcome.provider_id == "1001"
    request = mailjet.requests[0]
    assert request["path"] == "/v3.1/send"
    assert request["headers"]["Content-Type"] == "application/json"
    assert mailjet.basic_auth(request) == f"chiave-pubblica:{SECRET}"
    assert request["json"] == {
        "Messages": [
            {
                "From": {"Email": "teamdata@huware.com", "Name": "Portale CE"},
                "To": [{"Email": "utente1@huware.com", "Name": "Utente 1"}],
                "Subject": "Oggetto 1",
                "TextPart": "Testo 1",
                "HTMLPart": "<p>Html 1</p>",
                "CustomID": "id-1",
            }
        ]
    }


def test_sandbox_mode_is_a_root_property(mailjet):
    outcome = make(mailjet.url, sandbox=True).send([email()])[0]
    body = mailjet.requests[0]["json"]
    assert body["SandboxMode"] is True and "SandboxMode" not in body["Messages"][0]
    assert (
        outcome.ok and outcome.provider_id == "sandbox"
    )  # in sandbox Mailjet non restituisce MessageID


def test_no_sandbox_flag_by_default(mailjet):
    make(mailjet.url).send([email()])
    assert "SandboxMode" not in mailjet.requests[0]["json"]


def test_each_email_is_a_separate_message_so_recipients_do_not_see_each_other(mailjet):
    outcomes = make(mailjet.url).send([email(1), email(2), email(3)])
    assert len(mailjet.requests) == 1  # un'unica chiamata
    messages = mailjet.requests[0]["json"]["Messages"]
    assert [m["To"][0]["Email"] for m in messages] == [f"utente{n}@huware.com" for n in (1, 2, 3)]
    assert all(len(m["To"]) == 1 for m in messages)
    assert [o.provider_id for o in outcomes] == ["1001", "1002", "1003"]  # ordine rispettato


def test_large_batches_are_split_in_chunks_of_50(mailjet):
    outcomes = make(mailjet.url).send([email(n) for n in range(BATCH_SIZE + 1)])
    assert [len(r["json"]["Messages"]) for r in mailjet.requests] == [50, 1]
    assert len(outcomes) == 51 and all(o.ok for o in outcomes)


def test_nothing_to_send_makes_no_call(mailjet):
    assert make(mailjet.url).send([]) == []
    assert mailjet.requests == []


# ------------------------------------------------------------------ errori per singolo messaggio
def test_one_bad_address_does_not_affect_the_others(mailjet):
    def ok(n):
        return {"Status": "success", "CustomID": f"id-{n}", "To": [{"Email": "x", "MessageID": n}]}

    bad = error_message("mj-0013", 400, '"nome" is an invalid email address.')
    mailjet.script = [(200, {"Messages": [ok(1), bad, ok(3)]})]
    a, b, c = make(mailjet.url).send([email(1), email(2), email(3)])
    assert a.ok and c.ok
    assert not b.ok and b.retry is False  # indirizzo non valido: inutile ritentare
    assert "invalid email address" in b.error


@pytest.mark.parametrize(
    "code,status", [("send-0008", 403), ("send-0007", 403), ("send-0006", 403), ("mj-0001", 401)]
)
def test_sender_and_credential_problems_are_retried_not_failed_for_good(mailjet, code, status):
    mailjet.script = [(200, {"Messages": [error_message(code, status, "sender not authorized")]})]
    outcome = make(mailjet.url).send([email()])[0]
    assert not outcome.ok and outcome.retry is True
    assert "Configurazione Mailjet" in outcome.error and code in outcome.error


def test_an_error_inside_a_403_status_is_a_configuration_error_even_with_an_unknown_code(mailjet):
    mailjet.script = [(200, {"Messages": [error_message("send-9999", 403)]})]
    assert make(mailjet.url).send([email()])[0].retry is True


def test_all_messages_failing_comes_back_as_400_with_per_message_errors(mailjet):
    mailjet.script = [
        (
            400,
            {
                "Messages": [
                    error_message("send-0003", 400, "At least HTMLPart, TextPart must be provided")
                ]
            },
        )
    ]
    outcome = make(mailjet.url).send([email()])[0]
    assert not outcome.ok and outcome.retry is False and "send-0003" in outcome.error


# ------------------------------------------------------------------ errori dell'intera richiesta
@pytest.mark.parametrize("status", [401, 403])
def test_rejected_credentials_are_retried_with_a_clear_message(mailjet, status):
    mailjet.script = [(status, {"ErrorMessage": "API key authentication/authorization failure"})]
    outcome = make(mailjet.url).send([email(1), email(2)])
    assert [o.retry for o in outcome] == [True, True]
    assert "credenziali" in outcome[0].error


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_rate_limit_and_server_errors_are_retried(mailjet, status):
    mailjet.script = [(status, {"ErrorMessage": "boom"})]
    outcome = make(mailjet.url).send([email()])[0]
    assert not outcome.ok and outcome.retry is True and str(status) in outcome.error


def test_a_rejected_request_without_details_is_permanent(mailjet):
    mailjet.script = [(400, {"ErrorMessage": "Malformed JSON", "StatusCode": 400})]
    outcome = make(mailjet.url).send([email(1), email(2)])
    assert [o.retry for o in outcome] == [False, False] and "Malformed JSON" in outcome[0].error


def test_other_client_errors_are_permanent(mailjet):
    mailjet.script = [(404, "non è JSON")]
    outcome = make(mailjet.url).send([email()])[0]
    assert not outcome.ok and outcome.retry is False


def test_an_unrecognised_success_response_is_retried_not_trusted(mailjet):
    mailjet.script = [(200, "<html>proxy</html>"), (200, {"Messages": []})]
    for _ in range(2):
        outcome = make(mailjet.url).send([email()])[0]
        assert not outcome.ok and outcome.retry is True and "non riconosciuta" in outcome.error


def test_timeout_is_a_temporary_error(mailjet):
    mailjet.script = [(200, {"Messages": []}, 1.5)]
    outcome = make(mailjet.url, timeout=0.2).send([email()])[0]
    assert not outcome.ok and outcome.retry is True and "in tempo" in outcome.error


def test_connection_refused_is_a_temporary_error():
    outcome = make(free_port_url(), timeout=1.0).send([email()])[0]
    assert not outcome.ok and outcome.retry is True and "non raggiungibile" in outcome.error


def test_the_secret_never_appears_in_any_error(mailjet):
    scripts = [
        [(401, {"ErrorMessage": SECRET})],  # perfino se il server lo ripetesse
        [(500, "x")],
        [(200, {"Messages": [error_message("send-0008", 403, "n/a")]})],
        [(200, {"Messages": [error_message("mj-0013", 400, "bad")]})],
    ]
    for script in scripts:
        mailjet.script = list(script)
        for outcome in make(mailjet.url).send([email()]):
            assert SECRET not in (outcome.error or "")
    assert SECRET not in (make(free_port_url(), timeout=0.5).send([email()])[0].error or "")
    mailjet.script = [(200, {"Messages": []}, 1.0)]  # anche il timeout
    timed_out = make(mailjet.url, timeout=0.2).send([email()])[0]
    assert "in tempo" in timed_out.error and SECRET not in timed_out.error


# ------------------------------------------------------------------ scelta del client
def test_backend_selection_follows_the_environment():
    assert isinstance(build_mailer(Settings(_env_file=None, app_env="local")), ConsoleMailer)
    prod = Settings(
        _env_file=None,
        app_env="prod",
        jwt_secret="s" * 40,
        mailjet_api_key="k",
        mailjet_api_secret="s",
    )
    assert isinstance(build_mailer(prod), MailjetMailer)
    forced = Settings(
        _env_file=None,
        app_env="local",
        mail_backend="mailjet",
        mailjet_api_key="k",
        mailjet_api_secret="s",
    )
    assert isinstance(build_mailer(forced), MailjetMailer)


def test_the_configured_sender_timeout_url_and_sandbox_reach_the_client(mailjet):
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="s" * 40,
        mailjet_api_key="k",
        mailjet_api_secret="s",
        mailjet_url=mailjet.url,
        mailjet_sandbox=True,
        mail_from="altro@huware.com",
        mail_from_name="Altro",
    )
    build_mailer(settings).send([email()])
    body = mailjet.requests[0]["json"]
    assert body["SandboxMode"] is True
    assert body["Messages"][0]["From"] == {"Email": "altro@huware.com", "Name": "Altro"}


def test_console_mailer_reports_success_without_sending(caplog):
    with caplog.at_level("INFO", logger="ce_portal.mail"):
        outcomes = ConsoleMailer().send([email(1), email(2)])
    assert [o.ok for o in outcomes] == [True, True] and outcomes[0].provider_id == "console"
    assert "utente1@huware.com" in caplog.text and "Oggetto 1" in caplog.text
