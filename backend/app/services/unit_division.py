"""Divisione di un CE tra le business unit, per il PDF completo.

Ogni riga del CE è attribuita alla business unit del collaboratore indicato (quella della sua
practice **attuale**). Le righe senza collaboratore e la contingency (ricavo senza costi) stanno a
parte, così la somma delle righe è sempre il totale del CE.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BusinessUnit, Employee, Practice
from app.schemas.ce import CEDetail

NO_EMPLOYEE = "Senza collaboratore"
CONTINGENCY = "Contingency"
ZERO = Decimal("0")


@dataclass(frozen=True)
class DivisionRow:
    label: str
    kind: Literal["unit", "unassigned", "contingency"]
    days: Decimal
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_pct: Decimal | None  # frazione (0,57 = 57%); None se non ci sono ricavi
    share: Decimal | None  # quota dei ricavi totali del CE; None se il CE non ha ricavi


def _row(label, kind, days, revenue, cost, total_revenue) -> DivisionRow:
    margin = revenue - cost
    return DivisionRow(
        label=label,
        kind=kind,
        days=days,
        revenue=revenue,
        cost=cost,
        margin=margin,
        margin_pct=margin / revenue if revenue else None,
        share=revenue / total_revenue if total_revenue else None,
    )


def _units_of_lines(
    session: Session, detail: CEDetail
) -> tuple[dict[tuple[int, int], uuid.UUID | None], dict[uuid.UUID, str]]:
    """Il collaboratore di ogni riga (fase, riga) e la business unit di ogni collaboratore."""
    employee_of: dict[tuple[int, int], uuid.UUID | None] = {
        (pi, li): line.employee_id
        for pi, phase in enumerate(detail.phases)
        for li, line in enumerate(phase.lines)
    }
    ids = {e for e in employee_of.values() if e}
    unit_of: dict[uuid.UUID, str] = {}
    if ids:
        unit_of = dict(
            session.execute(
                select(Employee.id, BusinessUnit.name)
                .join(Practice, Practice.id == Employee.practice_id)
                .join(BusinessUnit, BusinessUnit.id == Practice.business_unit_id)
                .where(Employee.id.in_(ids))
            ).all()
        )
    return employee_of, unit_of


def business_unit_division(session: Session, detail: CEDetail) -> list[DivisionRow]:
    """Le righe della tabella: una per business unit (in ordine alfabetico), poi le righe senza
    collaboratore e la contingency. Vuota se il CE non ha righe."""
    cal = detail.calculation
    if not cal.lines:
        return []
    employee_of, unit_of = _units_of_lines(session, detail)
    sums: dict[str, list[Decimal]] = {}
    unassigned = [ZERO, ZERO, ZERO]
    for line in cal.lines:
        employee = employee_of.get((line.phase_index, line.line_index))
        unit = unit_of.get(employee) if employee else None
        target = sums.setdefault(unit, [ZERO, ZERO, ZERO]) if unit else unassigned
        target[0] += line.days
        target[1] += line.revenue
        target[2] += line.cost
    total = cal.total.revenue
    rows = [
        _row(label, "unit", d, r, c, total)
        for label, (d, r, c) in sorted(sums.items(), key=lambda kv: kv[0].lower())
    ]
    if any(unassigned):
        rows.append(_row(NO_EMPLOYEE, "unassigned", *unassigned, total))
    contingency = cal.contingency
    if contingency.revenue or contingency.cost or contingency.days:
        rows.append(
            _row(
                CONTINGENCY,
                "contingency",
                contingency.days,
                contingency.revenue,
                contingency.cost,
                total,
            )
        )
    return rows


@dataclass(frozen=True)
class RevenueRow:
    """Una riga del riepilogo: **solo ricavi**: il tipo non ha giornate, costi o margini."""

    label: str
    revenue: Decimal
    share: Decimal | None  # quota dei ricavi totali; None se il CE non ha ricavi


CENT = Decimal("0.01")


def spread(amount: Decimal, weights: dict[str, Decimal]) -> dict[str, Decimal]:
    """Ripartisce `amount` in proporzione ai pesi, a centesimi: la somma è sempre `amount`
    (l'eventuale resto dell'arrotondamento va alla voce più grande)."""
    base = sum(weights.values(), ZERO)
    shares = {k: (amount * v / base).quantize(CENT) for k, v in weights.items()}
    rest = amount - sum(shares.values(), ZERO)
    if rest:
        shares[max(weights, key=lambda k: weights[k])] += rest
    return shares


def business_unit_revenue(session: Session, detail: CEDetail) -> list[RevenueRow]:
    """I ricavi in euro di ogni business unit, per il PDF **riepilogativo** (senza costi).

    Come nella divisione completa, ogni riga va alla business unit del suo collaboratore e le
    righe senza collaboratore stanno a parte. La **contingency non compare a parte**: nel
    riepilogo i ricavi per fase la comprendono già e mostrarne l'importo la rivelerebbe. Si
    ripartisce, fase per fase, tra le business unit in proporzione ai ricavi delle loro righe (a
    centesimi, con l'eventuale resto sulla più grande), così le righe sommano sempre ai ricavi
    totali. Vuota se il CE non ha righe.
    """
    cal = detail.calculation
    if not cal.lines:
        return []
    employee_of, unit_of = _units_of_lines(session, detail)
    per_phase: dict[int, dict[str, Decimal]] = {}
    for line in cal.lines:
        employee = employee_of.get((line.phase_index, line.line_index))
        label = unit_of.get(employee) if employee else None
        bucket = per_phase.setdefault(line.phase_index, {})
        bucket[label or NO_EMPLOYEE] = bucket.get(label or NO_EMPLOYEE, ZERO) + line.revenue
    totals: dict[str, Decimal] = {}
    for index, phase in enumerate(cal.phases):
        bucket = dict(per_phase.get(index, {}))
        extra = phase.contingency_revenue
        base = sum(bucket.values(), ZERO)
        if extra and base:
            for k, v in spread(extra, bucket).items():
                bucket[k] += v
        elif extra:
            bucket[NO_EMPLOYEE] = bucket.get(NO_EMPLOYEE, ZERO) + extra
        for k, v in bucket.items():
            totals[k] = totals.get(k, ZERO) + v
    total = sum(totals.values(), ZERO)
    names = sorted((k for k in totals if k != NO_EMPLOYEE), key=str.lower)
    if NO_EMPLOYEE in totals:
        names.append(NO_EMPLOYEE)
    return [RevenueRow(k, totals[k], totals[k] / total if total else None) for k in names]
