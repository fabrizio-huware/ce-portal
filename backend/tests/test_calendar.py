from datetime import date

from app.db.calendar import easter_sunday, holidays_for_year


def test_easter_known_dates():
    assert easter_sunday(2024) == date(2024, 3, 31)
    assert easter_sunday(2025) == date(2025, 4, 20)
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)


def test_holidays_include_local_and_movable_days():
    days = dict(holidays_for_year(2026))
    assert days[date(2026, 4, 6)] == "Lunedì dell'Angelo"
    assert days[date(2026, 12, 7)] == "Sant'Ambrogio"
    assert len(days) == 13
