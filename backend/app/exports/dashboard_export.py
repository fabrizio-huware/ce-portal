"""Export delle dashboard: CSV (tabella principale) ed Excel (tutte le tabelle, solo valori)."""

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter as L

from app.exports.common import STATUS_LABELS, csv_num, fmt_date
from app.exports.csv_export import to_csv
from app.exports.xlsx_export import (
    F_BOLD,
    F_HEAD,
    F_NORMAL,
    F_NOTE,
    F_TITLE,
    FILL_ALERT,
    FILL_HEAD,
    FMT_DATE,
    FMT_MONEY,
    FMT_MONTH,
    FMT_NUM,
    FMT_PCT,
    _book,
    _bytes,
    _table,
    finish,
    head,
    put,
    widths,
)
from app.schemas.dashboard import PortfolioOut, ResourcesOut, Totals

SCOPE_LABELS = {"approved": "Approvato", "pipeline": "Pipeline"}


# ====================================================================== portfolio
def portfolio_csv(data: PortfolioOut) -> bytes:
    header = ["Codice", "Cliente", "Progetto", "Business Unit", "Stato", "Ambito", "Versione", "Inizio",
              "Fine", "Ricavi", "Costi", "Margine", "Margine (%)", "Giornate"]  # fmt: skip
    rows = [
        [i.code, i.client_name, i.project_name, i.business_unit or "", STATUS_LABELS[i.status],
         SCOPE_LABELS[i.scope], i.version_number, fmt_date(i.start_date), fmt_date(i.end_date),
         csv_num(i.revenue), csv_num(i.cost), csv_num(i.margin),
         csv_num(None if i.margin_pct is None else i.margin_pct * 100), csv_num(i.days, 2)]
        for i in data.items
    ]  # fmt: skip
    return to_csv(header, rows)


def _totals_row(label: str, t: Totals) -> list:
    return [label, t.count, t.revenue, t.cost, t.margin, t.margin_pct, t.days]


def portfolio_xlsx(data: PortfolioOut) -> bytes:
    wb = _book("Portfolio CE")
    ws = wb.active
    ws.title = "Riepilogo"
    put(ws, "A1", "Portfolio dei conti economici", font=F_TITLE)
    period = f"{fmt_date(data.date_from) or 'inizio'} - {fmt_date(data.date_to) or 'fine'}"
    put(ws, "A2", f"Periodo (CE con periodo sovrapposto): {period}", font=F_NOTE)
    head(ws, 4, ["Ambito", "CE", "Ricavi (€)", "Costi (€)", "Margine (€)", "Margine %", "Giornate"])
    formats = [None, "0", FMT_MONEY, FMT_MONEY, FMT_MONEY, FMT_PCT, FMT_NUM]
    for r, (label, totals) in enumerate(
        [("Approvati", data.approved), ("Pipeline", data.pipeline)], start=5
    ):
        for c, (value, fmt) in enumerate(
            zip(_totals_row(label, totals), formats, strict=True), start=1
        ):
            put(ws, f"{L(c)}{r}", value, fmt=fmt, font=F_BOLD if c == 1 else F_NORMAL,
                align=Alignment(horizontal="right") if c > 1 else None)  # fmt: skip
    notes = [
        "Approvati: ultima versione approvata di ogni CE. Pipeline: CE ancora senza una versione approvata (bozza, in approvazione, rifiutato).",
        f"Revisioni in corso di CE già approvati (non sommate): {data.revisions_in_progress}.",
        "I totali per cliente, business unit e stato sono i totali interi dei CE. La vista per mese usa gli importi mensili e non include la contingency.",
    ]
    for i, text in enumerate(notes, start=8):
        put(ws, f"A{i}", text, font=F_NOTE)
    widths(ws, {"A": 20, "B": 8, "C": 16, "D": 16, "E": 16, "F": 11, "G": 11})
    finish(ws)

    def groups(title: str, rows) -> None:
        header = [title, "CE appr.", "Ricavi appr. (€)", "Costi appr. (€)", "Margine appr. (€)", "Margine % appr.",
                  "Giornate appr.", "CE pipeline", "Ricavi pipeline (€)", "Giornate pipeline"]  # fmt: skip
        body = [[g.label, g.approved.count, g.approved.revenue, g.approved.cost, g.approved.margin,
                 g.approved.margin_pct, g.approved.days, g.pipeline.count, g.pipeline.revenue, g.pipeline.days]
                for g in rows]  # fmt: skip
        _table(wb, title, header, body, {3: FMT_MONEY, 4: FMT_MONEY, 5: FMT_MONEY, 6: FMT_PCT, 7: FMT_NUM, 9: FMT_MONEY, 10: FMT_NUM},
               size={"A": 30, **{c: 15 for c in "BCDEFGHIJ"}})  # fmt: skip

    groups("Per cliente", data.by_client)
    groups("Per business unit", data.by_business_unit)
    _table(wb, "Per stato", ["Stato", "Ambito", "CE", "Ricavi (€)"],
           [[s.label, SCOPE_LABELS[s.scope], s.count, s.revenue] for s in data.by_status], {4: FMT_MONEY},
           size={"A": 20, "B": 14, "C": 8, "D": 16})  # fmt: skip
    _table(wb, "Per mese", ["Mese", "Ricavi appr. (€)", "Costi appr. (€)", "Margine appr. (€)", "Giornate appr.",
                            "Ricavi pipeline (€)", "Costi pipeline (€)", "Giornate pipeline"],
           [[m.month, m.approved.revenue, m.approved.cost, m.approved.margin, m.approved.days,
             m.pipeline.revenue, m.pipeline.cost, m.pipeline.days] for m in data.by_month],
           {1: FMT_MONTH, 2: FMT_MONEY, 3: FMT_MONEY, 4: FMT_MONEY, 5: FMT_NUM, 6: FMT_MONEY, 7: FMT_MONEY, 8: FMT_NUM},
           size={"A": 12, **{c: 17 for c in "BCDEFGH"}})  # fmt: skip
    _table(wb, "Elenco CE", ["Codice", "Cliente", "Progetto", "Business Unit", "Stato", "Ambito", "Versione", "Inizio",
                             "Fine", "Ricavi (€)", "Costi (€)", "Margine (€)", "Margine %", "Giornate"],
           [[i.code, i.client_name, i.project_name, i.business_unit or "", STATUS_LABELS[i.status], SCOPE_LABELS[i.scope],
             i.version_number, i.start_date, i.end_date, i.revenue, i.cost, i.margin, i.margin_pct, i.days] for i in data.items],
           {8: FMT_DATE, 9: FMT_DATE, 10: FMT_MONEY, 11: FMT_MONEY, 12: FMT_MONEY, 13: FMT_PCT, 14: FMT_NUM},
           size={"A": 22, "B": 24, "C": 32, "D": 16, "E": 16, "F": 11, "G": 9, "H": 12, "I": 12, "J": 15, "K": 15, "L": 15, "M": 11, "N": 11})  # fmt: skip
    return _bytes(wb)


# ====================================================================== carico risorse
def resources_csv(data: ResourcesOut) -> bytes:
    """Formato lungo: una riga per ogni collaboratore o profilo e mese con giornate."""
    header = ["Tipo", "Nome", "Profilo", "Mese", "Giorni approvati", "Giorni pipeline", "Giorni totali", "Ore",
              "Capacità (giorni)", "FTE (%)", "Sovraccarico"]  # fmt: skip
    rows = []
    for group in (data.employees, data.profiles):
        for r in group:
            for month, cell in zip(data.months, r.cells, strict=True):
                if cell.days == 0:
                    continue
                rows.append([
                    "Collaboratore" if r.kind == "employee" else "Profilo", r.name, r.profile_name or "",
                    month.month.strftime("%m/%Y"), csv_num(cell.days_approved, 2), csv_num(cell.days_pipeline, 2),
                    csv_num(cell.days, 2), csv_num(cell.hours, 2), month.capacity_days,
                    csv_num(None if cell.fte is None else cell.fte * 100), "Sì" if cell.overloaded else "No",
                ])  # fmt: skip
    return to_csv(header, rows)


def resources_xlsx(data: ResourcesOut) -> bytes:
    wb = _book("Carico risorse")
    n = len(data.months)

    def matrix(title: str, rows, *, fte: bool, first: bool = False) -> None:
        sheet = wb.active if first else wb.create_sheet()
        sheet.title = title
        head(
            sheet,
            1,
            [
                "Collaboratore" if fte else "Profilo",
                "Profilo di default" if fte else "Non assegnato (giorni)",
            ],
        )
        for i, m in enumerate(data.months):
            put(sheet, f"{L(3 + i)}1", m.month, font=F_HEAD, fmt=FMT_MONTH, fill=FILL_HEAD,
                align=Alignment(horizontal="center"))  # fmt: skip
        put(sheet, f"{L(3 + n)}1", "Giorni totali", font=F_HEAD, fill=FILL_HEAD)
        put(
            sheet,
            f"{L(4 + n)}1",
            "Mesi sovraccarichi",
            font=F_HEAD,
            fill=FILL_HEAD,
        )
        for r, row in enumerate(rows, start=2):
            put(sheet, f"A{r}", row.name)
            put(
                sheet,
                f"B{r}",
                row.profile_name or "" if fte else row.unassigned_days,
                fmt=None if fte else FMT_NUM,
            )
            for i, cell in enumerate(row.cells):
                value = (cell.fte if fte else cell.days) or None
                put(sheet, f"{L(3 + i)}{r}", value, fmt=FMT_PCT if fte else FMT_NUM,
                    fill=FILL_ALERT if cell.overloaded else None)  # fmt: skip
            put(sheet, f"{L(3 + n)}{r}", row.total_days, fmt=FMT_NUM, font=F_BOLD)
            put(sheet, f"{L(4 + n)}{r}", row.overloaded_months or None, fmt="0")
        cap_row = len(rows) + 3
        put(sheet, f"A{cap_row}", "Capacità del mese (giorni lavorativi)", font=F_BOLD)
        for i, m in enumerate(data.months):
            put(sheet, f"{L(3 + i)}{cap_row}", m.capacity_days, fmt="0")
        note = (
            "FTE = giorni del collaboratore / giorni lavorativi del mese (calendario generale). "
            "Sfondo rosso: oltre il 100%."
            if fte
            else "Giorni per profilo, di tutti i CE inclusi."
        )
        put(sheet, f"A{cap_row + 2}", note, font=F_NOTE)
        widths(sheet, {"A": 30, "B": 22})
        for i in range(n + 2):
            sheet.column_dimensions[L(3 + i)].width = 12
        finish(sheet, freeze="C2")

    matrix("Collaboratori", data.employees, fte=True, first=True)
    matrix("Profili", data.profiles, fte=False)
    long_rows = []
    for group in (data.employees, data.profiles):
        for r in group:
            for month, cell in zip(data.months, r.cells, strict=True):
                if cell.days:
                    long_rows.append([
                        "Collaboratore" if r.kind == "employee" else "Profilo", r.name, r.profile_name or "", month.month,
                        cell.days_approved, cell.days_pipeline, cell.days, cell.hours, month.capacity_days, cell.fte,
                        "Sì" if cell.overloaded else "No",
                    ])  # fmt: skip
    _table(wb, "Dati", ["Tipo", "Nome", "Profilo", "Mese", "Giorni approvati", "Giorni pipeline", "Giorni totali", "Ore",
                        "Capacità (giorni)", "FTE", "Sovraccarico"], long_rows,
           {4: FMT_MONTH, 5: FMT_NUM, 6: FMT_NUM, 7: FMT_NUM, 8: FMT_NUM, 10: FMT_PCT},
           size={"A": 14, "B": 30, "C": 22, "D": 11, "E": 15, "F": 15, "G": 14, "H": 10, "I": 16, "J": 10, "K": 13})  # fmt: skip
    return _bytes(wb)
