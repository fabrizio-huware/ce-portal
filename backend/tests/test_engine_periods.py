import random
from datetime import date
from decimal import Decimal

import pytest

from app.engine.periods import distribute, month_start, months_between, weekdays_in_month


def test_weekdays_in_month():
    assert weekdays_in_month(date(2026, 1, 1)) == 22
    assert weekdays_in_month(date(2026, 2, 1)) == 20
    assert weekdays_in_month(date(2026, 12, 1)) == 23
    assert weekdays_in_month(date(2024, 2, 1)) == 21  # anno bisestile
    assert weekdays_in_month(date(2027, 8, 1)) == 22


def test_weekdays_match_the_sheet_calendar_for_2026():
    # riga WORK-DAYS del foglio (gen 17+5 = 22 feriali), poi mesi senza giorni inseriti a mano
    sheet = [22, 20, 22, 22, 21, 22, 23, 21, 22, 22, 21, 23]
    assert [weekdays_in_month(date(2026, m, 1)) for m in range(1, 13)] == sheet


def test_months_between_includes_first_and_last_month():
    assert months_between(date(2026, 1, 20), date(2026, 4, 20)) == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
    ]
    assert months_between(date(2026, 5, 3), date(2026, 5, 3)) == [date(2026, 5, 1)]
    assert months_between(date(2026, 11, 15), date(2027, 2, 1)) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]
    assert len(months_between(date(2026, 9, 1), date(2027, 8, 31))) == 12
    assert month_start(date(2026, 3, 17)) == date(2026, 3, 1)


def test_distribute_sums_exactly_and_is_deterministic():
    assert distribute(Decimal("16"), [22, 20, 22, 22]) == [
        Decimal("4.10"),
        Decimal("3.72"),
        Decimal("4.09"),
        Decimal("4.09"),
    ]
    assert distribute(Decimal("0.01"), [1, 1, 1]) == [Decimal("0.01"), Decimal("0"), Decimal("0")]
    assert distribute(Decimal("10"), [1, 0, 1]) == [
        Decimal("5.00"),
        Decimal("0.00"),
        Decimal("5.00"),
    ]
    assert distribute(Decimal("0"), [0, 0]) == [Decimal("0"), Decimal("0")]
    with pytest.raises(ValueError):
        distribute(Decimal("1"), [0, 0])


def test_distribute_never_loses_or_invents_hours():
    rng = random.Random(7)
    for _ in range(500):
        total = Decimal(rng.randint(0, 100_000)) / 100
        weights = [rng.randint(0, 23) for _ in range(rng.randint(1, 12))]
        if sum(weights) == 0:
            continue
        parts = distribute(total, weights)
        assert sum(parts) == total
        for part, weight in zip(parts, weights, strict=True):
            exact = total * weight / sum(weights)
            assert abs(part - exact) < Decimal("0.01")  # mai più di 1 centesimo dal valore esatto
            assert weight > 0 or part == 0  # un mese senza giorni lavorativi non riceve ore
