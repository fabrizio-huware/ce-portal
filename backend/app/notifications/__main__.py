"""Comandi da terminale (o da un job pianificato):

python -m app.notifications dispatch            # invia le email in coda scadute
python -m app.notifications send-test a@b.it     # email di prova (senza passare dalla coda)
"""

import argparse
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.notifications.mailer import OutgoingEmail, build_mailer
from app.notifications.outbox import dispatch
from app.notifications.templates import render


def cmd_dispatch(limit: int) -> int:
    settings = get_settings()
    with SessionLocal() as session:
        report = dispatch(session, build_mailer(settings), settings, limit=limit)
    print(
        f"Elaborate {report.processed}: inviate {report.sent}, rimandate {report.deferred}, "
        f"fallite {report.failed}. In attesa: {report.remaining}."
    )
    return 1 if report.failed else 0


def cmd_send_test(recipient: str) -> int:
    settings = get_settings()
    mailer = build_mailer(settings)
    rendered = render("test", {"recipient_name": recipient}, settings.public_base_url)
    outcome = mailer.send(
        [
            OutgoingEmail(
                "test", recipient, recipient, rendered.subject, rendered.text, rendered.html
            )
        ]
    )[0]
    mode = settings.effective_mail_backend + (
        " (sandbox: non consegnata)" if settings.mailjet_sandbox else ""
    )
    if outcome.ok:
        print(f"OK: email di prova accettata da {mode}. Destinatario: {recipient}")
        return 0
    print(f"ERRORE ({mode}): {outcome.error}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.notifications")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("dispatch", help="invia le email in coda")
    d.add_argument("--limit", type=int, default=50)
    t = sub.add_parser("send-test", help="invia un'email di prova")
    t.add_argument("recipient")
    args = parser.parse_args(argv)
    return cmd_dispatch(args.limit) if args.command == "dispatch" else cmd_send_test(args.recipient)


if __name__ == "__main__":
    sys.exit(main())
