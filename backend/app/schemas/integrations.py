"""Integrazioni: programmi esterni che agiscono con un account di servizio Google.

Due gruppi di schemi: la gestione da parte dell'amministratore e il contratto per i programmi
esterni (`/api/v1/integrazioni`), che non contiene mai costi, margini o tariffe.
"""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator

from app.schemas.ce import CEStatus, CodeStr, ContentIn
from app.schemas.common import InputModel, OutputModel, short_text

Permission = Literal["create", "edit", "read", "export"]

_SERVICE_ACCOUNT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*@[a-z0-9.-]+\.iam\.gserviceaccount\.com$")


def _normalize_service_account(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip().lower()
    if len(value) > 320 or not _SERVICE_ACCOUNT_RE.match(value):
        raise ValueError(
            "serve l'email di un account di servizio Google (finisce con .iam.gserviceaccount.com)"
        )
    return value


ServiceAccountEmail = Annotated[str, BeforeValidator(_normalize_service_account)]
Permissions = Annotated[list[Permission], Field(min_length=1, max_length=4)]


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


# ======= gestione (amministratore)
class IntegrationCreate(InputModel):
    name: short_text(100)
    service_account_email: ServiceAccountEmail
    permissions: Permissions

    _permissions = field_validator("permissions")(_unique_sorted)


class IntegrationUpdate(InputModel):
    name: short_text(100) | None = None
    permissions: Permissions | None = None
    is_active: bool | None = None

    @field_validator("permissions")
    @classmethod
    def _dedupe(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _unique_sorted(v)


class IntegrationOut(OutputModel):
    id: uuid.UUID
    name: str
    service_account_email: str
    permissions: list[str]
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    user_id: uuid.UUID  # l'utente di servizio, autore dei CE creati dall'integrazione


# ======= contratto per i programmi esterni
class LookupItem(OutputModel):
    id: uuid.UUID
    name: str


class IntegrationPhase(OutputModel):
    name: str
    revenue: Decimal


class IntegrationCEItem(OutputModel):
    """Una riga dell'elenco: nessun costo, margine o tariffa."""

    ce_id: uuid.UUID
    code: str
    client_name: str
    project_name: str
    start_date: date
    end_date: date
    version_number: int
    status: CEStatus
    mine: bool  # creato da questa integrazione e ancora suo (non assegnato a un presale)
    external_ref: str | None  # solo per i CE creati da questa integrazione


class IntegrationCE(OutputModel):
    """Riepilogo di un CE: giornate e ricavi, mai costi, margini o tariffe."""

    ce_id: uuid.UUID
    code: str
    client_name: str
    project_name: str
    start_date: date
    end_date: date
    version_number: int
    status: CEStatus
    notice: str | None  # «Versione non approvata…» se l'ultima versione non è approvata
    approved_at: datetime | None
    days_project_management: Decimal
    days_delivery: Decimal
    days_total: Decimal
    phases: list[IntegrationPhase]
    total_revenue: Decimal
    mine: bool
    external_ref: str | None
    requested_by: str | None


class IntegrationCEResult(OutputModel):
    created: bool  # False se l'identificativo esterno esisteva già: nessun duplicato
    ce: IntegrationCE
    revision: (
        int | None
    )  # da rimandare come expected_revision per modificare; None se non è più suo


class IntegrationContent(OutputModel):
    revision: int
    status: CEStatus
    content: ContentIn  # solo ciò che l'integrazione stessa ha inviato: nessun costo


class IntegrationCECreate(InputModel):
    code: CodeStr
    external_ref: short_text(100)
    requested_by: short_text(320) | None = None
    content: ContentIn
