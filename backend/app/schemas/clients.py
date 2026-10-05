import uuid
from datetime import datetime

from app.schemas.common import InputModel, OutputModel, short_text


class ClientOut(OutputModel):
    id: uuid.UUID
    name: str
    address: str | None
    external_ref: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientRef(OutputModel):
    """Vista minima per filtri e menu a tendina (accessibile anche al viewer)."""

    id: uuid.UUID
    name: str
    is_active: bool


class ClientCreate(InputModel):
    name: short_text(300)
    address: str | None = None
    external_ref: short_text(100) | None = None


class ClientUpdate(InputModel):
    name: short_text(300) | None = None
    address: str | None = None
    external_ref: short_text(100) | None = None
    is_active: bool | None = None
