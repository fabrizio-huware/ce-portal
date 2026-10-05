"""Lettura robusta di CSV in stile Excel italiano (separatore ';', numeri '1.800,00')."""

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MAX_BYTES = 1_000_000
MAX_ROWS = 5000

TRUE_VALUES = {"si", "s", "1", "true", "vero", "yes", "y", "x"}
FALSE_VALUES = {"no", "n", "0", "false", "falso"}


class CsvFileError(Exception):
    """Problema che riguarda l'intero file (non una singola riga)."""


@dataclass(frozen=True)
class CsvRow:
    line: int
    values: dict[str, str]


def _norm_header(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\s\-]+", "_", text)


def read_csv(
    content: bytes, columns: dict[str, tuple[str, ...]], required: set[str]
) -> list[CsvRow]:
    """Legge il file e restituisce le righe con i nomi di colonna canonici.

    `columns` associa ogni nome canonico ai suoi alias accettati nell'intestazione.
    """
    if len(content) > MAX_BYTES:
        raise CsvFileError("File troppo grande (massimo 1 MB)")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")  # export di Excel su Windows
    if not text.strip():
        raise CsvFileError("Il file è vuoto")

    first_line = text.splitlines()[0]
    delimiter = ";" if ";" in first_line else "\t" if "\t" in first_line else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    alias_to_canonical = {
        _norm_header(alias): canonical
        for canonical, aliases in columns.items()
        for alias in (canonical, *aliases)
    }
    header = next(reader)
    index: dict[str, int] = {}
    for position, name in enumerate(header):
        canonical = alias_to_canonical.get(_norm_header(name))
        if canonical and canonical not in index:
            index[canonical] = position
    missing = sorted(required - set(index))
    if missing:
        raise CsvFileError(f"Colonne obbligatorie mancanti: {', '.join(missing)}")

    rows: list[CsvRow] = []
    for fields in reader:
        if not any(f.strip() for f in fields):
            continue  # riga vuota
        values = {
            name: (fields[pos].strip() if pos < len(fields) else "") for name, pos in index.items()
        }
        rows.append(CsvRow(line=reader.line_num, values=values))
        if len(rows) > MAX_ROWS:
            raise CsvFileError(f"Troppe righe (massimo {MAX_ROWS})")
    if not rows:
        raise CsvFileError("Il file non contiene righe di dati")
    return rows


def parse_decimal(raw: str) -> Decimal:
    """Accetta '1.800,00', '1800,5', '1800.50', '€ 1.800'. Massimo 2 decimali."""
    s = raw.strip().replace("€", "").replace(" ", "").replace("\u00a0", "")
    if not s:
        raise ValueError("valore mancante")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.800,50
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,800.50
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?[1-9]\d{0,2}(\.\d{3})+", s):  # 1.800 = migliaia all'italiana
        s = s.replace(".", "")
    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"numero non valido: '{raw}'") from exc
    if not value.is_finite():
        raise ValueError(f"numero non valido: '{raw}'")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError(f"massimo 2 decimali: '{raw}'")
    return value.quantize(Decimal("0.01"))


def parse_int(raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"numero intero non valido: '{raw}'") from exc


def parse_bool(raw: str, default: bool = True) -> bool:
    value = _norm_header(raw)
    if not value:
        return default
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(f"valore non valido: '{raw}' (usa sì/no)")


def parse_date(raw: str) -> date:
    text = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data non valida: '{raw}' (usa gg/mm/aaaa)")
