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


def business_unit_division(session: Session, detail: CEDetail) -> list[DivisionRow]:
    """Le righe della tabella: una per business unit (in ordine alfabetico), poi le righe senza
    collaboratore e la contingency. Vuota se il CE non ha righe."""
    cal = detail.calculation
    if not cal.lines:
        return []
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
