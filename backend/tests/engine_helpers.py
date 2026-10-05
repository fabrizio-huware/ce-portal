"""Costruzione degli ingressi del motore a partire dai dati estratti dal foglio reale."""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from app.engine import CEInput, LineInput, PhaseInput, ProfileRate, rates_from_mapping

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ce_bonga.json").read_text())
CENT = Decimal("0.01")
RATIO = Decimal("0.000001")


def d(value) -> Decimal:
    return Decimal(str(value))


def cents(value) -> Decimal:
    """Valore del foglio (anche con rumore in virgola mobile) arrotondato al centesimo."""
    return d(value).quantize(CENT, rounding=ROUND_HALF_UP)


def ratio6(value) -> Decimal:
    return d(value).quantize(RATIO, rounding=ROUND_HALF_UP)


def month(y: int, m: int) -> date:
    return date(y, m, 1)


def rates() -> dict[str, ProfileRate]:
    return rates_from_mapping(FIXTURE["rates"], external={"Esterni"})


def base_phases(contingency: dict[str, str] | None = None) -> list[PhaseInput]:
    """Le fasi del CE reale (ore per attività e profilo). La fase PM è Project Management."""
    contingency = contingency or {}
    phases = []
    for phase in FIXTURE["phases"]:
        lines = [
            LineInput(
                activity=task["name"] or f"{phase['code']}-{task['id']}",
                profile=profile,
                hours=d(hours),
                is_project_management=phase["code"] == "PM",
            )
            for task in phase["tasks"]
            for profile, hours in task["hours"].items()
        ]
        phases.append(
            PhaseInput(
                name=phase["code"],
                lines=lines,
                contingency_pct=d(contingency.get(phase["code"], "0")),
            )
        )
    return phases


def base_ce(**overrides) -> CEInput:
    values = {
        "start_date": date(2026, 1, 20),
        "end_date": date(2026, 4, 20),
        "mode": "hours",
        "phases": base_phases(),
        "rates": rates(),
        "non_working_days": {month(2026, 1): 5},
    }
    values.update(overrides)
    return CEInput(**values)
