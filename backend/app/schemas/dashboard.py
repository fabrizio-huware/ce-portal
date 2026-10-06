"""Schemi delle dashboard (solo admin e presale): portfolio e carico risorse."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from app.schemas.common import OutputModel

Scope = Literal["approved", "pipeline"]


# ====================================================================== portfolio
class Totals(OutputModel):
    count: int
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_pct: Decimal | None  # None se i ricavi sono zero
    days: Decimal


class GroupRow(OutputModel):
    key: str
    label: str
    approved: Totals
    pipeline: Totals


class MonthFigures(OutputModel):
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    days: Decimal


class MonthRow(OutputModel):
    month: date
    approved: MonthFigures
    pipeline: MonthFigures


class StatusRow(OutputModel):
    status: str
    label: str
    scope: Scope
    count: int
    revenue: Decimal


class PortfolioItem(OutputModel):
    ce_id: uuid.UUID
    code: str
    client_name: str
    project_name: str
    business_unit: str | None
    status: str
    scope: Scope
    version_number: int
    start_date: date
    end_date: date
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_pct: Decimal | None
    days: Decimal


class PortfolioOut(OutputModel):
    date_from: date | None
    date_to: date | None
    include_pipeline: bool
    approved: Totals
    pipeline: Totals
    by_client: list[GroupRow]
    by_business_unit: list[GroupRow]
    by_status: list[StatusRow]
    by_month: list[MonthRow]
    items: list[PortfolioItem]
    revisions_in_progress: (
        int  # CE già approvati con una nuova versione in lavorazione (non sommati)
    )
    monthly_excludes_contingency: bool = True
    skipped: list[str] = []


# ====================================================================== carico risorse
class ResourceMonth(OutputModel):
    month: date
    capacity_days: int  # giorni lavorativi del calendario generale


class ResourceCell(OutputModel):
    days_approved: Decimal
    days_pipeline: Decimal
    days: Decimal  # approvati + pipeline (se inclusa)
    hours: Decimal
    fte: Decimal | None  # giorni / capacità del mese (1 = 100%)
    overloaded: bool  # solo per i collaboratori: FTE sopra il 100%


class ResourceRow(OutputModel):
    kind: Literal["employee", "profile"]
    id: uuid.UUID | None
    name: str
    profile_name: str | None  # profilo di default (collaboratori)
    cells: list[ResourceCell]  # nello stesso ordine di `months`
    total_days: Decimal
    unassigned_days: Decimal  # profili: giornate di righe senza collaboratore
    overloaded_months: int


class ResourcesOut(OutputModel):
    date_from: date
    date_to: date
    include_pipeline: bool
    overload_threshold_fte: Decimal
    months: list[ResourceMonth]
    employees: list[ResourceRow]
    profiles: list[ResourceRow]
    ces_count: int
    skipped: list[str] = []
