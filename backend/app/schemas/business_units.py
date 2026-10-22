import uuid
from datetime import datetime

from app.schemas.common import InputModel, OutputModel, short_text


class BusinessUnitOut(OutputModel):
    id: uuid.UUID
    name: str
    is_active: bool
    practices_count: int  # practice attive di questa business unit
    employees_count: int  # collaboratori attivi delle sue practice
    users_count: int  # presale e responsabili attivi assegnati
    created_at: datetime
    updated_at: datetime


class BusinessUnitRef(OutputModel):
    """Vista minima per filtri e menu a tendina."""

    id: uuid.UUID
    name: str
    is_active: bool


class BusinessUnitCreate(InputModel):
    name: short_text(100)


class BusinessUnitUpdate(InputModel):
    name: short_text(100) | None = None
    is_active: bool | None = None
