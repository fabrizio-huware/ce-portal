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
    is_external: bool
    sort_order: int
    band: str | None
    billability_target: Decimal | None
    rates: list[RateOut]


class ProfileCreate(InputModel):
    name: short_text(100)
    is_external: bool = False
    sort_order: int = 0
    band: short_text(10) | None = None
    billability_target: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)


class ProfileUpdate(InputModel):
    name: short_text(100) | None = None
    is_active: bool | None = None
    is_external: bool | None = None
    sort_order: int | None = None
    band: short_text(10) | None = None
    billability_target: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)


class RateUpsert(InputModel):
    daily_price: Money
    daily_cost: Money


class CopyRatesIn(InputModel):
    """Copia le tariffe di un anno su uno o più altri anni, con un adeguamento facoltativo."""

    from_year: int = Field(ge=2000, le=2100)
    to_years: list[int] = Field(min_length=1, max_length=10)
    price_adjust_pct: Decimal = Field(
        default=Decimal(0),
        ge=Decimal(-90),
        le=Decimal(100),
        max_digits=6,
        decimal_places=2,
        description="Adeguamento del prezzo al giorno in % (0 = identico)",
    )
    cost_adjust_pct: Decimal = Field(
        default=Decimal(0),
        ge=Decimal(-90),
        le=Decimal(100),
        max_digits=6,
        decimal_places=2,
        description="Adeguamento del costo al giorno in % (0 = identico)",
    )


class CopyRatesItem(OutputModel):
    profile_id: uuid.UUID
    profile_name: str
    year: int
    action: str  # created | updated | unchanged
    old_price: Decimal | None = None
    old_cost: Decimal | None = None
    new_price: Decimal
    new_cost: Decimal


class CopyRatesResult(OutputModel):
    dry_run: bool
    applied: bool
    from_year: int
    to_years: list[int]
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    items: list[CopyRatesItem] = []
