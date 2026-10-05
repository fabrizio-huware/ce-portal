"""Mesi del progetto, giorni lavorativi e ripartizione esatta delle ore sui mesi."""

import calendar
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_FLOOR, Decimal

MAX_MONTHS = 12


def month_start(d: date) -> date:
    return d.replace(day=1)


def months_between(start: date, end: date) -> list[date]:
    """Primo giorno di ogni mese, dal mese di inizio al mese di fine (inclusi)."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def weekdays_in_month(month: date) -> int:
    """Giorni da lunedì a venerdì dell'intero mese (come NETWORKDAYS.INTL del foglio)."""
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    return sum(
        1 for day in range(1, days_in_month + 1) if date(month.year, month.month, day).weekday() < 5
    )


def distribute(total: Decimal, weights: Sequence[int], places: int = 2) -> list[Decimal]:
    """Ripartisce `total` in proporzione ai pesi, a `places` decimali, con somma esatta.

    Metodo del resto più grande: ogni quota è arrotondata per difetto e i centesimi
    rimasti vanno alle quote con la parte decimale maggiore (a parità, al mese più vicino).
    `total` deve avere al massimo `places` decimali.
    """
    unit = Decimal(1).scaleb(-places)
    weight_sum = sum(weights)
    if weight_sum == 0:
        if total == 0:
            return [Decimal(0)] * len(weights)
        raise ValueError("impossibile ripartire su pesi tutti a zero")
    exact = [total * w / weight_sum for w in weights]
    floors = [(e / unit).to_integral_value(rounding=ROUND_FLOOR) * unit for e in exact]
    leftover = int(((total - sum(floors)) / unit).to_integral_value())
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:leftover]:
        floors[i] += unit
    return floors
