"""Schemi dell'API dei conti economici (CE)."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field

from app.schemas.clients import ClientRef
from app.schemas.common import InputModel, Money, OutputModel, short_text

CEStatus = Literal["draft", "submitted", "approved", "rejected"]
PlanningMode = Literal["hours", "percent"]
Pct = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Hours = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,99}$")


def _normalize_code(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip().upper()
    if not _CODE_RE.match(value):
        raise ValueError(
            "il codice ha 3-100 caratteri: lettere, numeri, punto, trattino, underscore"
        )
    return value


CodeStr = Annotated[str, BeforeValidator(_normalize_code)]


# ======= ingressi
class HeaderIn(InputModel):
    client_id: uuid.UUID
    project_name: short_text(300)
    start_date: date
    end_date: date
    planning_mode: PlanningMode
    sf_opportunity: short_text(100) | None = None
    business_unit: short_text(100) | None = None
    notes: str | None = Field(default=None, max_length=5000)
    max_discount_pct: Pct = Decimal(0)
    signed_price: Money | None = None


class CECreate(HeaderIn):
    code: CodeStr
    standard_phases: bool = True  # parte con le fasi standard del foglio (solo i nomi)


class AllocationIn(InputModel):
    month: date  # primo giorno del mese
    pct: Pct


class LineIn(InputModel):
    activity: short_text(300)
    profile_id: uuid.UUID
    employee_id: uuid.UUID | None = None
    is_project_management: bool = False
    hours: Hours | None = None  # solo modalità "hours"
    allocations: list[AllocationIn] = Field(default_factory=list, max_length=12)  # solo "percent"


class PhaseIn(InputModel):
    name: short_text(200)
    contingency_pct: Pct = Decimal(0)
    lines: list[LineIn] = Field(default_factory=list, max_length=300)


class MonthIn(InputModel):
    month: date  # primo giorno del mese
    non_working_days: int = Field(ge=0, le=23)


class MilestoneIn(InputModel):
    month: date
    label: short_text(200)


class ContentIn(InputModel):
    """Intero contenuto di una versione: si salva e si calcola in un'unica richiesta."""

    expected_revision: int | None = Field(default=None, ge=1)  # obbligatorio per salvare
    header: HeaderIn
    non_working_days: list[MonthIn] = Field(default_factory=list, max_length=12)
    phases: list[PhaseIn] = Field(default_factory=list, max_length=60)
    milestones: list[MilestoneIn] = Field(default_factory=list, max_length=100)


class RejectIn(InputModel):
    reason: short_text(1000)


class RealignIn(InputModel):
    rates: bool = True
    calendar: bool = True


class DuplicateIn(InputModel):
    code: CodeStr
    start_date: date
    end_date: date
    project_name: short_text(300) | None = None
    client_id: uuid.UUID | None = None


# ======= uscite comuni
class UserRef(OutputModel):
    id: uuid.UUID
    full_name: str


class Actions(OutputModel):
    """Cosa può fare l'utente corrente su questa versione (attiva i pulsanti dell'interfaccia)."""

    edit: bool
    submit: bool
    withdraw: bool
    approve: bool
    reject: bool
    new_version: bool
    discard_version: bool
    realign: bool
    delete: bool


class VersionMeta(OutputModel):
    number: int
    status: CEStatus
    revision: int
    rate_year: int
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by: UserRef | None
    rejected_at: datetime | None
    rejected_by: UserRef | None
    rejection_reason: str | None


class CEMeta(OutputModel):
    id: uuid.UUID
    code: str
    owner: UserRef
    created_at: datetime
    versions_count: int


class HeaderOut(OutputModel):
    client: ClientRef
    project_name: str
    start_date: date
    end_date: date
    planning_mode: PlanningMode
    sf_opportunity: str | None
    business_unit: str | None
    notes: str | None
    max_discount_pct: Decimal
    signed_price: Decimal | None


class AllocationOut(OutputModel):
    month: date
    pct: Decimal


class LineOut(OutputModel):
    id: uuid.UUID
    activity: str
    profile_id: uuid.UUID
    profile_name: str
    employee_id: uuid.UUID | None
    employee_name: str | None
    is_project_management: bool
    hours: Decimal | None
    allocations: list[AllocationOut]


class PhaseOut(OutputModel):
    id: uuid.UUID
    name: str
    contingency_pct: Decimal
    lines: list[LineOut]


class RateOut(OutputModel):
    profile_id: uuid.UUID
    profile_name: str
    is_external: bool
    daily_price: Decimal
    daily_cost: Decimal


class MilestoneOut(OutputModel):
    month: date
    label: str


# ======= risultati del calcolo
class MonthCalc(OutputModel):
    month: date
    weekdays: int
    non_working: int
    work_days: int


class LineCalc(OutputModel):
    phase_index: int
    line_index: int
    activity: str
    profile_id: uuid.UUID
    profile_name: str
    is_external: bool
    is_project_management: bool
    hours: Decimal
    days: Decimal
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    fte: Decimal
    monthly_days: dict[date, Decimal]


class PhaseCalc(OutputModel):
    name: str
    contingency_pct: Decimal
    hours: Decimal
    days: Decimal
    days_with_contingency: Decimal
    revenue: Decimal
    cost: Decimal
    contingency_revenue: Decimal
    revenue_with_contingency: Decimal


class ProfileCalc(OutputModel):
    profile_id: uuid.UUID
    profile_name: str
    is_external: bool
    hours: Decimal
    days: Decimal
    hours_share: Decimal | None
    revenue: Decimal
    cost: Decimal
    margin: Decimal


class BucketCalc(OutputModel):
    days: Decimal
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_pct: Decimal | None
    cost_ratio: Decimal | None


class MonthStaffingCalc(OutputModel):
    month: date
    work_days: int
    days: Decimal
    hours: Decimal
    fte: Decimal | None
    revenue: Decimal
    cost: Decimal


class KpisCalc(OutputModel):
    price_project: Decimal
    max_discount_pct: Decimal
    price_min: Decimal
    days_total: Decimal
    days_project_management: Decimal
    days_delivery: Decimal
    days_total_with_contingency: Decimal
    weeks: Decimal
    weeks_with_contingency: Decimal
    fee_media_min: Decimal | None
    signed_price: Decimal | None
    fee_media_signed: Decimal | None
    margin_signed: Decimal | None
    margin_pct_signed: Decimal | None
    cost_ratio_signed: Decimal | None


class CalculationOut(OutputModel):
    months: list[MonthCalc]
    phases: list[PhaseCalc]
    lines: list[LineCalc]
    profiles: list[ProfileCalc]
    internal: BucketCalc
    external: BucketCalc
    contingency: BucketCalc
    total: BucketCalc
    monthly: list[MonthStaffingCalc]
    kpis: KpisCalc
    warnings: list[str]


# ======= dettaglio, elenchi
class CEDetail(OutputModel):
    ce: CEMeta
    version: VersionMeta
    header: HeaderOut
    phases: list[PhaseOut]
    rates: list[RateOut]
    milestones: list[MilestoneOut]
    calculation: CalculationOut
    actions: Actions


class CEListItem(OutputModel):
    ce_id: uuid.UUID
    code: str
    client: ClientRef
    project_name: str
    start_date: date
    end_date: date
    planning_mode: PlanningMode
    version_number: int
    status: CEStatus
    owner: UserRef
    updated_at: datetime
    deleted: bool
    price: Decimal | None
    margin_pct: Decimal | None
    days_total: Decimal | None


class VersionListItem(OutputModel):
    number: int
    status: CEStatus
    revision: int
    created_by: UserRef
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    price: Decimal | None


class HistoryItem(OutputModel):
    id: int
    occurred_at: datetime
    user: UserRef | None
    action: str
    changes: dict[str, Any] | None


class DiscardResult(OutputModel):
    discarded_version: int


# ======= vista ridotta (viewer)
class ViewerListItem(OutputModel):
    """Solo ciò che il viewer può vedere: nessun costo, margine, ora o riga."""

    ce_id: uuid.UUID
    code: str
    client_name: str
    project_name: str
    start_date: date
    end_date: date
    version_number: int
    approved_at: datetime | None
    price: Decimal | None


class ViewerPhase(OutputModel):
    name: str
    revenue: Decimal


class ViewerCE(OutputModel):
    ce_id: uuid.UUID
    code: str
    client_name: str
    project_name: str
    start_date: date
    end_date: date
    version_number: int
    approved_at: datetime | None
    days_project_management: Decimal
    days_delivery: Decimal
    days_total: Decimal
    phases: list[ViewerPhase]
    total_revenue: Decimal
