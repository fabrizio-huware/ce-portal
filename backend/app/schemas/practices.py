import uuid
from datetime import datetime

from app.schemas.common import InputModel, OutputModel, short_text


class PracticeOut(OutputModel):
    id: uuid.UUID
    name: str
    is_active: bool
    employees_count: int  # collaboratori attivi di questa practice
    business_unit_id: uuid.UUID
    business_unit_name: str
    created_at: datetime
    updated_at: datetime


class PracticeRef(OutputModel):
    """Vista minima per filtri e menu a tendina."""

    id: uuid.UUID
    name: str
    is_active: bool
    business_unit_id: uuid.UUID


class PracticeCreate(InputModel):
    name: short_text(100)
    # Facoltativa: senza indicazione la practice va nella business unit «Da assegnare».
    business_unit_id: uuid.UUID | None = None


class PracticeUpdate(InputModel):
    name: short_text(100) | None = None
    is_active: bool | None = None
    business_unit_id: uuid.UUID | None = None
