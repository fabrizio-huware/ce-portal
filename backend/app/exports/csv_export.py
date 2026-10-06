"""CSV per Excel italiano: UTF-8 con BOM, separatore ';', virgola decimale."""

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from app.exports.common import (
    MODE_LABELS,
    STATUS_LABELS,
    csv_num,
    fmt_date,
    fmt_datetime,
    neutralize,
    yes_no,
)
from app.schemas.ce import CEDetail, CEListItem, ViewerCE, ViewerListItem


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return yes_no(value)
    if isinstance(value, str):
        return neutralize(value)
    return str(value)


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([neutralize(h) for h in header])
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return buffer.getvalue().encode("utf-8-sig")  # il BOM fa riconoscere l'UTF-8 a Excel


# ------------------------------------------------------------------ singolo CE
def ce_lines_csv(detail: CEDetail) -> bytes:
    """Una riga per ogni riga del CE, con ricavi, costi e margini (solo per admin e presale)."""
    rates = {r.profile_id: r for r in detail.rates}
    rows = []
    for line_calc in detail.calculation.lines:
        phase = detail.phases[line_calc.phase_index]
        line = phase.lines[line_calc.line_index]
        rate = rates[line.profile_id]
        rows.append(
            [
                detail.ce.code,
                detail.version.number,
                phase.name,
                line.activity,
                line.profile_name,
                line.employee_name or "",
                yes_no(line.is_project_management),
                yes_no(rate.is_external),
                csv_num(line_calc.hours, 2),
                csv_num(line_calc.days, 4),
                csv_num(rate.daily_price),
                csv_num(rate.daily_cost),
                csv_num(line_calc.revenue),
                csv_num(line_calc.cost),
                csv_num(line_calc.margin),
                csv_num(phase.contingency_pct),
            ]
        )
    header = [
        "Codice", "Versione", "Fase", "Attività", "Profilo", "Collaboratore", "Project Management",
        "Esterno", "Ore", "Giorni", "Prezzo/giorno", "Costo/giorno", "Ricavo", "Costo", "Margine",
        "Contingency fase (%)",
    ]  # fmt: skip
    return to_csv(header, rows)


def reduced_csv(ce: ViewerCE) -> bytes:
    """Riepilogo del CE: stessi dati che vede il viewer, nessun costo né riga."""
    base = [ce.code, ce.client_name, ce.project_name]
    items = [
        ("Versione", str(ce.version_number)),
        ("Periodo", f"{fmt_date(ce.start_date)} - {fmt_date(ce.end_date)}"),
        ("Giornate management", csv_num(ce.days_project_management, 2)),
        ("Giornate delivery", csv_num(ce.days_delivery, 2)),
        ("Giornate totali", csv_num(ce.days_total, 2)),
        *[(f"Ricavi - {p.name}", csv_num(p.revenue)) for p in ce.phases],
        ("Ricavi totali", csv_num(ce.total_revenue)),
    ]
    return to_csv(
        ["Codice", "Cliente", "Progetto", "Voce", "Valore"], ([*base, k, v] for k, v in items)
    )


# ------------------------------------------------------------------ elenchi
def ce_list_csv(items: Sequence[CEListItem]) -> bytes:
    header = [
        "Codice", "Cliente", "Progetto", "Inizio", "Fine", "Modalità", "Versione", "Stato",
        "Autore", "Aggiornato il", "Prezzo", "Margine (%)", "Giornate",
    ]  # fmt: skip
    rows = []
    for i in items:
        margin = None if i.margin_pct is None else i.margin_pct * 100
        rows.append([
            i.code, i.client.name, i.project_name, fmt_date(i.start_date), fmt_date(i.end_date),
            MODE_LABELS[i.planning_mode], i.version_number, STATUS_LABELS[i.status],
            i.owner.full_name, fmt_datetime(i.updated_at), csv_num(i.price), csv_num(margin),
            csv_num(i.days_total, 2),
        ])  # fmt: skip
    return to_csv(header, rows)


def viewer_list_csv(items: Sequence[ViewerListItem]) -> bytes:
    header = [
        "Codice",
        "Cliente",
        "Progetto",
        "Inizio",
        "Fine",
        "Versione",
        "Approvato il",
        "Prezzo",
    ]
    rows = [
        [
            i.code, i.client_name, i.project_name, fmt_date(i.start_date), fmt_date(i.end_date),
            i.version_number, fmt_datetime(i.approved_at), csv_num(i.price),
        ]
        for i in items
    ]  # fmt: skip
    return to_csv(header, rows)
