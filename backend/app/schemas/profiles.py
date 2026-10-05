import uuid
from decimal import Decimal

from pydantic import Field

from app.schemas.common import InputModel, Money, OutputModel, short_text


class RateOut(OutputModel):
    year: int
    daily_price: Decimal
    daily_cost: Decimal


class ProfileOut(OutputModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int
    band: str | None
    billability_target: Decimal | None
    rates: list[RateOut]


class ProfileCreate(InputModel):
    name: short_text(100)
    sort_order: int = 0
    band: short_text(10) | None = None
    billability_target: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)


class ProfileUpdate(InputModel):
    name: short_text(100) | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    band: short_text(10) | None = None
    billability_target: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)


class RateUpsert(InputModel):
    daily_price: Money
    daily_cost: Money
