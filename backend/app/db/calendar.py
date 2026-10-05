"""Festività nazionali italiane e Sant'Ambrogio (patrono di Milano)."""

from datetime import date, timedelta


def easter_sunday(year: int) -> date:
    """Data della Pasqua (algoritmo di Meeus/Jones/Butcher, calendario gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def holidays_for_year(year: int) -> list[tuple[date, str]]:
    """Festività dell'anno (sede di Milano), ordinate per data."""
    easter = easter_sunday(year)
    items = [
        (date(year, 1, 1), "Capodanno"),
        (date(year, 1, 6), "Epifania"),
        (easter, "Pasqua"),
        (easter + timedelta(days=1), "Lunedì dell'Angelo"),
        (date(year, 4, 25), "Festa della Liberazione"),
        (date(year, 5, 1), "Festa del Lavoro"),
        (date(year, 6, 2), "Festa della Repubblica"),
        (date(year, 8, 15), "Ferragosto"),
        (date(year, 11, 1), "Ognissanti"),
        (date(year, 12, 7), "Sant'Ambrogio"),
        (date(year, 12, 8), "Immacolata Concezione"),
        (date(year, 12, 25), "Natale"),
        (date(year, 12, 26), "Santo Stefano"),
    ]
    return sorted(items)
