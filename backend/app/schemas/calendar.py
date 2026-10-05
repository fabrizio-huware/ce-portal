import uuid
from datetime import date

from pydantic import Field

from app.schemas.common import InputModel, NonWorkingKind, OutputModel, short_text


class NonWorkingDayOut(OutputModel):
    id: uuid.UUID
    day: date
    kind: NonWorkingKind
    description: str


class NonWorkingDayCreate(InputModel):
    day: date
    kind: NonWorkingKind
    description: short_text(200)


class NonWorkingDayUpdate(InputModel):
    kind: NonWorkingKind | None = None
    description: short_text(200) | None = None


class GenerateHolidaysRequest(InputModel):
    year: int = Field(ge=2000, le=2100)


class GenerateHolidaysResponse(OutputModel):
    year: int
    created: int
