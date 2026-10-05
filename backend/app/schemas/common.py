import re
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

T = TypeVar("T")

Role = Literal["admin", "presale", "viewer"]
NonWorkingKind = Literal["holiday", "company_closure"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class InputModel(BaseModel):
    """Base per i dati in ingresso: campi sconosciuti (es. refusi) vengono rifiutati."""

    model_config = ConfigDict(extra="forbid")


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def short_text(max_length: int):
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip().lower()
    if not _EMAIL_RE.match(value) or len(value) > 320:
        raise ValueError("indirizzo email non valido")
    return value


Email = Annotated[str, BeforeValidator(_normalize_email)]

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
