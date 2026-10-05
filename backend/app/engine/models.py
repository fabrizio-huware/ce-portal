"""Strutture dati del motore di calcolo: ingressi e risultati.

Il motore non conosce il database: riceve dati semplici e restituisce numeri.
Tutti gli importi, le ore e le percentuali sono `Decimal` (mai `float`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

PlanningMode = Literal["hours", "percent"]
ZERO = Decimal(0)


# ------------------------------------------------------------------ ingressi
@dataclass(frozen=True)
class ProfileRate:
    """Tariffe giornaliere di un profilo, già congelate nel CE."""

    daily_price: Decimal  # prezzo di vendita / giorno
    daily_cost: Decimal  # costo interno / giorno
    is_external: bool = False  # profilo "Esterni": confluisce in "Servizi Esterni"


@dataclass(frozen=True)
class LineInput:
    activity: str
    profile: str  # chiave nel dizionario delle tariffe
    hours: Decimal | None = None  # solo modalità "hours"
    # solo modalità "percent": mese (1° giorno) -> % di occupazione (0-100)
    allocations: Mapping[date, Decimal] = field(default_factory=dict)
    is_project_management: bool = False


@dataclass(frozen=True)
class PhaseInput:
    name: str
    lines: Sequence[LineInput]
    contingency_pct: Decimal = ZERO  # 0-100


@dataclass(frozen=True)
class CEInput:
    start_date: date
    end_date: date
    mode: PlanningMode
    phases: Sequence[PhaseInput]
    rates: Mapping[str, ProfileRate]
    # mese (1° giorno) -> giorni lavorativi persi per festività/chiusure (oltre a sabato e domenica)
    non_working_days: Mapping[date, int] = field(default_factory=dict)
    max_discount_pct: Decimal = ZERO  # 0-100, inserito da chi compila
    signed_price: Decimal | None = None


# ------------------------------------------------------------------ risultati
@dataclass(frozen=True)
class MonthInfo:
    month: date
    weekdays: int  # giorni lunedì-venerdì del mese intero
    non_working: int  # giorni non lavorativi inseriti sul CE
    work_days: int  # weekdays - non_working


@dataclass(frozen=True)
class LineResult:
    phase_index: int
    line_index: int
    activity: str
    profile: str
    is_external: bool
    is_project_management: bool
    hours: Decimal
    days: Decimal
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    fte: Decimal  # occupazione media (frazione: 1 = 100%)
    monthly_days: Mapping[date, Decimal]


@dataclass(frozen=True)
class PhaseResult:
    name: str
    contingency_pct: Decimal
    hours: Decimal
    days: Decimal
    days_with_contingency: Decimal
    revenue: Decimal  # ricavi base della fase
    cost: Decimal
    contingency_revenue: Decimal  # ricavo aggiuntivo da contingency (senza costi)
    revenue_with_contingency: Decimal


@dataclass(frozen=True)
class ProfileResult:
    profile: str
    is_external: bool
    hours: Decimal
    days: Decimal
    hours_share: Decimal | None  # quota delle ore totali (frazione)
    revenue: Decimal
    cost: Decimal
    margin: Decimal


@dataclass(frozen=True)
class Bucket:
    """Voce di riepilogo (Servizi Interni, Servizi Esterni, Contingency, Totale)."""

    days: Decimal
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_pct: Decimal | None  # None se i ricavi sono zero (non si divide per zero)
    cost_ratio: Decimal | None  # C/R = costi / ricavi


@dataclass(frozen=True)
class MonthStaffing:
    month: date
    work_days: int
    days: Decimal
    hours: Decimal
    fte: Decimal | None  # giorni / giorni lavorativi del mese
    revenue: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Kpis:
    price_project: Decimal
    max_discount_pct: Decimal
    price_min: Decimal  # prezzo progetto al netto del max sconto
    days_total: Decimal  # giornate base (senza contingency), esterni inclusi
    days_project_management: Decimal
    days_delivery: Decimal  # totale - project management
    days_total_with_contingency: Decimal
    weeks: Decimal
    weeks_with_contingency: Decimal
    fee_media_min: Decimal | None  # prezzo_min / giornate totali
    signed_price: Decimal | None
    fee_media_signed: Decimal | None
    margin_signed: Decimal | None
    margin_pct_signed: Decimal | None
    cost_ratio_signed: Decimal | None


@dataclass(frozen=True)
class CEResult:
    months: Sequence[MonthInfo]
    phases: Sequence[PhaseResult]
    lines: Sequence[LineResult]
    profiles: Sequence[ProfileResult]
    internal: Bucket
    external: Bucket
    contingency: Bucket
    total: Bucket
    monthly: Sequence[MonthStaffing]
    kpis: Kpis
    warnings: Sequence[str]


class CalculationError(ValueError):
    """Dati di ingresso non validi. `issues` elenca tutti i problemi trovati."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))
