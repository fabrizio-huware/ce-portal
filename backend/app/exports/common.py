"""Utilità comuni degli export: sicurezza dei file, formati italiani, risposta HTTP."""

import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Response

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIME = "text/csv; charset=utf-8"
PDF_MIME = "application/pdf"
MIME = {"xlsx": XLSX_MIME, "csv": CSV_MIME, "pdf": PDF_MIME}

STATUS_LABELS = {
    "draft": "Bozza",
    "submitted": "In approvazione",
    "approved": "Approvato",
    "rejected": "Rifiutato",
}
MODE_LABELS = {"hours": "Ore", "percent": "Percentuali"}

# Un testo che inizia così può essere eseguito come formula da Excel (CSV injection).
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
MAX_EXPORT_ROWS = 5000
LOCAL_TZ = ZoneInfo(
    "Europe/Rome"
)  # nel database gli orari sono in UTC: nei file si mostra l'ora italiana


def neutralize(value: Any) -> Any:
    """Rende innocuo un testo che Excel potrebbe interpretare come formula."""
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


def safe_filename(*parts: Any, ext: str) -> str:
    """Nome di file sicuro e ASCII: niente percorsi, spazi o caratteri speciali."""
    base = "_".join(str(p) for p in parts if p not in (None, ""))
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-") or "export"
    return f"{base[:120]}.{ext}"


def file_response(content: bytes, fmt: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=MIME[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ------------------------------------------------------------------ formati italiani
def _q(value: Decimal | int | str, places: int) -> Decimal:
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def csv_num(value: Decimal | int | str | None, places: int = 2) -> str:
    """'1234.5' -> '1234,50' (virgola decimale, senza separatore delle migliaia)."""
    return "" if value is None else str(_q(value, places)).replace(".", ",")


def fmt_num(value: Decimal | int | str | None, places: int = 2) -> str:
    """'1234567.5' -> '1.234.567,50'"""
    if value is None:
        return "n/d"
    text = f"{_q(value, places):,.{places}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_money(value: Decimal | int | str | None) -> str:
    return "n/d" if value is None else f"{fmt_num(value, 2)} €"


def fmt_pct(fraction: Decimal | str | None) -> str:
    """Frazione -> percentuale: '0.571694' -> '57,17%'."""
    return "n/d" if fraction is None else f"{fmt_num(Decimal(fraction) * 100, 2)}%"


def _local(value: datetime) -> datetime:
    return value.astimezone(LOCAL_TZ) if value.tzinfo else value


def fmt_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return (_local(value) if isinstance(value, datetime) else value).strftime("%d/%m/%Y")


def fmt_datetime(value: datetime | None) -> str:
    return "" if value is None else _local(value).strftime("%d/%m/%Y %H:%M")


def yes_no(flag: bool) -> str:
    return "Sì" if flag else "No"
