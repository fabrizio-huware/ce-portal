from datetime import date
from decimal import Decimal

import pytest

from app.services.csv_utils import (
    CsvFileError,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_int,
    read_csv,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.800,00", "1800.00"),
        ("1800,5", "1800.50"),
        ("1800.50", "1800.50"),
        ("1800", "1800.00"),
        ("1.800", "1800.00"),  # punto come separatore delle migliaia, all'italiana
        ("€ 1.800,00", "1800.00"),
        ("1,800.50", "1800.50"),  # formato inglese
        ("1.234.567,89", "1234567.89"),
        ("0.5", "0.50"),
        ("1.5", "1.50"),
        ("66", "66.00"),
        ("0", "0.00"),
    ],
)
def test_parse_decimal_accepts_italian_and_english_formats(raw, expected):
    assert parse_decimal(raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw", ["", "abc", "12,5,3", "1800.555", "1,234,567", "NaN", "Infinity", "1e3x"]
)
def test_parse_decimal_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        parse_decimal(raw)


def test_parse_bool_parse_int_parse_date():
    assert [parse_bool(x) for x in ("Sì", "si", "SI", "1", "true", "x")] == [True] * 6
    assert [parse_bool(x) for x in ("no", "No", "0", "falso")] == [False] * 4
    assert parse_bool("", default=True) is True and parse_bool("", default=False) is False
    with pytest.raises(ValueError):
        parse_bool("forse")
    assert parse_int(" 2026 ") == 2026
    with pytest.raises(ValueError):
        parse_int("2026.5")
    assert parse_date("24/12/2026") == date(2026, 12, 24)
    assert parse_date("2026-12-24") == date(2026, 12, 24)
    assert parse_date("24-12-2026") == date(2026, 12, 24)
    with pytest.raises(ValueError):
        parse_date("31/02/2026")


COLUMNS = {"nome": ("first_name",), "valore": ("prezzo giorno",)}


def test_read_csv_detects_delimiters_bom_and_ignores_extra_columns():
    for text in (
        "Nome;Valore;Extra\nAda;1;zzz\n",
        "Nome,Valore,Extra\nAda,1,zzz\n",
        "Nome\tValore\tExtra\nAda\t1\tzzz\n",
        "\ufeffNome;Valore\nAda;1\n",
    ):
        rows = read_csv(text.encode("utf-8"), COLUMNS, {"nome", "valore"})
        assert [r.values for r in rows] == [{"nome": "Ada", "valore": "1"}]


def test_read_csv_headers_are_case_accent_and_space_insensitive():
    rows = read_csv(b"FIRST_NAME;Prezzo  Giorno\nAda;5\n", COLUMNS, {"nome", "valore"})
    assert rows[0].values == {"nome": "Ada", "valore": "5"}


def test_read_csv_handles_windows_encoding_and_skips_blank_lines():
    content = "Nome;Valore\nSocietà;1\n;\n\nAltra;2\n".encode("cp1252")
    rows = read_csv(content, COLUMNS, {"nome"})
    assert [r.values["nome"] for r in rows] == ["Società", "Altra"]
    assert [r.line for r in rows] == [2, 5]


def test_read_csv_file_level_errors():
    with pytest.raises(CsvFileError, match="mancanti"):
        read_csv(b"Nome\nAda\n", COLUMNS, {"nome", "valore"})
    with pytest.raises(CsvFileError, match="vuoto"):
        read_csv(b"  \n", COLUMNS, {"nome"})
    with pytest.raises(CsvFileError, match="righe di dati"):
        read_csv(b"Nome;Valore\n", COLUMNS, {"nome"})
    with pytest.raises(CsvFileError, match="troppo grande"):
        read_csv(b"x" * 1_000_001, COLUMNS, {"nome"})
