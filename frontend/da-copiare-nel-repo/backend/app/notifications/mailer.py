"""Invio delle email: Mailjet (produzione e test) oppure log (sviluppo locale).

`send` non solleva eccezioni per errori attesi: restituisce un esito per ogni email, con
l'indicazione se vale la pena ritentare. Il segreto di Mailjet non compare mai in log o errori.
"""

import base64
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import requests

from app.core.config import Settings

logger = logging.getLogger("ce_portal.mail")

# Errori di configurazione (credenziali, mittente non verificato): non dipendono dall'email,
# quindi si ritenta dopo che l'amministratore ha sistemato la configurazione.
CONFIG_ERROR_CODES = {"send-0006", "send-0007", "send-0008", "mj-0001"}
BATCH_SIZE = 50  # limite di Send API v3.1
BATCH_ATTACHMENT_BYTES = 8_000_000  # una richiesta Mailjet non può superare ~15 MB (base64 incluso)


@dataclass(frozen=True)
class Attachment:
    name: str
    mime: str
    content: bytes


@dataclass(frozen=True)
class OutgoingEmail:
    id: str  # identificativo nella coda (CustomID su Mailjet)
    to_email: str
    to_name: str
    subject: str
    text: str
    html: str
    attachment: Attachment | None = None


@dataclass(frozen=True)
class SendOutcome:
    ok: bool
    provider_id: str | None = None
    retry: bool = False  # True: errore temporaneo o di configurazione, si può ritentare
    error: str | None = None


class Mailer(Protocol):
    def send(self, emails: Sequence[OutgoingEmail]) -> list[SendOutcome]: ...


class ConsoleMailer:
    """Sviluppo locale: scrive l'email nel log invece di spedirla."""

    def send(self, emails: Sequence[OutgoingEmail]) -> list[SendOutcome]:
        for email in emails:
            attached = f" allegato={email.attachment.name!r}" if email.attachment else ""
            logger.info(
                "EMAIL (solo log) a=%s oggetto=%r%s\n%s",
                email.to_email,
                email.subject,
                attached,
                email.text,
            )
        return [SendOutcome(ok=True, provider_id="console") for _ in emails]


class MailjetMailer:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        sender_email: str,
        sender_name: str,
        url: str,
        sandbox: bool,
        timeout: float,
    ) -> None:
        self._auth = (api_key, api_secret)
        self._sender = {"Email": sender_email, "Name": sender_name}
        self._url = url
        self._sandbox = sandbox
        self._timeout = timeout

    # ------------------------------------------------------------------ invio
    def send(self, emails: Sequence[OutgoingEmail]) -> list[SendOutcome]:
        outcomes: list[SendOutcome] = []
        for batch in self._batches(emails):
            outcomes += self._send_batch(batch)
        return outcomes

    @staticmethod
    def _batches(emails: Sequence[OutgoingEmail]) -> list[list[OutgoingEmail]]:
        """Gruppi da al massimo 50 email e circa 8 MB di allegati, nell'ordine di arrivo."""
        batches: list[list[OutgoingEmail]] = []
        size = 0
        for email in emails:
            weight = len(email.attachment.content) if email.attachment else 0
            if (
                not batches
                or len(batches[-1]) >= BATCH_SIZE
                or size + weight > BATCH_ATTACHMENT_BYTES
            ):
                batches.append([])
                size = 0
            batches[-1].append(email)
            size += weight
        return batches

    def _payload(self, emails: Sequence[OutgoingEmail]) -> dict[str, Any]:
        payload: dict[str, Any] = {"Messages": [self._message(e) for e in emails]}
        if self._sandbox:
            payload["SandboxMode"] = True  # proprietà della radice: convalida senza consegnare
        return payload

    def _message(self, e: OutgoingEmail) -> dict[str, Any]:
        message: dict[str, Any] = {
            "From": self._sender,
            "To": [{"Email": e.to_email, "Name": e.to_name}],
            "Subject": e.subject,
            "TextPart": e.text,
            "HTMLPart": e.html,
            "CustomID": e.id,
        }
        if e.attachment:
            message["Attachments"] = [
                {
                    "ContentType": e.attachment.mime.split(";")[0],
                    "Filename": e.attachment.name,
                    "Base64Content": base64.b64encode(e.attachment.content).decode("ascii"),
                }
            ]
        return message

    def _send_batch(self, emails: Sequence[OutgoingEmail]) -> list[SendOutcome]:
        def everyone(outcome: SendOutcome) -> list[SendOutcome]:
            return [outcome] * len(emails)

        try:
            response = requests.post(
                self._url, json=self._payload(emails), auth=self._auth, timeout=self._timeout
            )
        except requests.Timeout:
            return everyone(
                SendOutcome(False, retry=True, error="Mailjet non ha risposto in tempo")
            )
        except requests.RequestException as exc:
            return everyone(
                SendOutcome(
                    False, retry=True, error=f"Mailjet non raggiungibile ({type(exc).__name__})"
                )
            )

        status = response.status_code
        body = self._json(response)
        if status in (401, 403):
            return everyone(
                SendOutcome(
                    False,
                    retry=True,
                    error="Mailjet ha rifiutato le credenziali (verifica chiave e segreto)",
                )
            )
        if status == 429 or status >= 500:
            return everyone(
                SendOutcome(
                    False, retry=True, error=f"Mailjet temporaneamente non disponibile ({status})"
                )
            )

        messages = body.get("Messages") if isinstance(body, dict) else None
        if not isinstance(messages, list) or len(messages) != len(emails):
            if 200 <= status < 300:  # risposta anomala: potrebbe essere partita, ma non lo sappiamo
                return everyone(
                    SendOutcome(False, retry=True, error="Risposta di Mailjet non riconosciuta")
                )
            detail = self._error_text(body) or f"richiesta rifiutata ({status})"
            return everyone(SendOutcome(False, retry=False, error=f"Mailjet: {detail}"))
        return [self._outcome(m) for m in messages]

    # ------------------------------------------------------------------ risposte
    @staticmethod
    def _json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _error_text(body: Any) -> str | None:
        if isinstance(body, dict):
            message = body.get("ErrorMessage") or body.get("Message")
            return str(message)[:300] if message else None
        return None

    @classmethod
    def _outcome(cls, message: dict[str, Any]) -> SendOutcome:
        if message.get("Status") == "success":
            recipients = message.get("To") or [{}]
            provider_id = recipients[0].get("MessageID") or recipients[0].get("MessageUUID")
            return SendOutcome(True, provider_id=str(provider_id) if provider_id else "sandbox")
        errors = message.get("Errors") or []
        first = errors[0] if errors else {}
        code = str(first.get("ErrorCode", ""))
        text = f"{code}: {first.get('ErrorMessage', 'errore sconosciuto')}"[:300]
        config = code in CONFIG_ERROR_CODES or first.get("StatusCode") in (401, 403)
        if config:
            return SendOutcome(False, retry=True, error=f"Configurazione Mailjet ({text})")
        return SendOutcome(False, retry=False, error=f"Mailjet ha rifiutato l'email ({text})")


def build_mailer(settings: Settings) -> Mailer:
    if settings.effective_mail_backend == "console":
        return ConsoleMailer()
    return MailjetMailer(
        settings.mailjet_api_key or "",
        settings.mailjet_api_secret or "",
        sender_email=settings.mail_from,
        sender_name=settings.mail_from_name,
        url=settings.mailjet_url,
        sandbox=settings.mailjet_sandbox,
        timeout=settings.mail_timeout_seconds,
    )
