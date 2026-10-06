"""PDF con reportlab: completo (uso interno, A4 orizzontale) e riepilogo (A4 verticale)."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exports.common import (
    MODE_LABELS,
    STATUS_LABELS,
    fmt_date,
    fmt_datetime,
    fmt_money,
    fmt_num,
    fmt_pct,
)
from app.schemas.ce import CEDetail, ViewerCE

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
NAVY = colors.HexColor("#101828")
ACCENT = colors.HexColor("#1d4ed8")
GRID = colors.HexColor("#d0d5dd")
SOFT = colors.HexColor("#eef2f6")
MUTED = colors.HexColor("#667085")

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=NAVY)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=7.5, leading=9, textColor=MUTED)
H1 = ParagraphStyle("h1", parent=BASE, fontName="Helvetica-Bold", fontSize=16, leading=19)
H2 = ParagraphStyle(
    "h2",
    parent=BASE,
    fontName="Helvetica-Bold",
    fontSize=10.5,
    leading=13,
    spaceBefore=10,
    spaceAfter=4,
)
CELL = ParagraphStyle("cell", parent=BASE, fontSize=8, leading=9.5)
CELL_R = ParagraphStyle("cell_r", parent=CELL, alignment=2)
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
HEAD_R = ParagraphStyle("head_r", parent=HEAD, alignment=2)
PHASE_TITLE = ParagraphStyle(
    "ph", parent=BASE, fontName="Helvetica-Bold", fontSize=9.5, spaceBefore=6, spaceAfter=2
)


def pdf_text(value: object) -> str:
    """Testo sicuro per il PDF: niente markup interpretato e niente caratteri che i font standard non hanno."""
    text = str(value).encode("cp1252", errors="replace").decode("cp1252")
    return escape(" ".join(text.split()))


def P(value: object, style: ParagraphStyle = CELL) -> Paragraph:
    return Paragraph(pdf_text(value), style)


class _NumberedCanvas(canvas.Canvas):
    """Piè di pagina con 'Pagina x di y' e testo di riservatezza."""

    def __init__(self, *args, footer: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._footer = footer
        self._saved: list[dict] = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        width, _ = self._pagesize
        self.setFont("Helvetica", 7)
        self.setFillColor(MUTED)
        self.setStrokeColor(GRID)
        self.line(15 * mm, 12 * mm, width - 15 * mm, 12 * mm)
        self.drawString(15 * mm, 8 * mm, pdf_text(self._footer))
        self.drawRightString(width - 15 * mm, 8 * mm, f"Pagina {self._pageNumber} di {total}")


def _doc(buffer: BytesIO, title: str, page_size, footer: str) -> tuple[SimpleDocTemplate, callable]:
    doc = SimpleDocTemplate(
        buffer, pagesize=page_size, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=18 * mm,
        title=pdf_text(title), author="Portale Conti Economici", creator="Portale Conti Economici",
        subject="Conto economico di progetto",
    )  # fmt: skip
    return doc, lambda *a, **kw: _NumberedCanvas(*a, footer=footer, **kw)


def _logo(logo_path: Path | None, height: float = 11 * mm):
    path = logo_path if logo_path is not None else LOGO_PATH
    if not path or not Path(path).exists():
        return None
    width, h = ImageReader(str(path)).getSize()
    return Image(str(path), width=height * width / h, height=height)


def _title_block(title: str, subtitle: str, width: float, logo_path: Path | None) -> Table:
    left = _logo(logo_path) or Paragraph(
        "<b>Portale Conti Economici</b>", ParagraphStyle("t", parent=BASE, fontSize=10)
    )
    right = [Paragraph(pdf_text(title), H1), Paragraph(pdf_text(subtitle), SMALL)]
    table = Table([[left, right]], colWidths=[width * 0.28, width * 0.72])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, ACCENT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (0, 0), 0),
    ]))  # fmt: skip
    return table


def _info_grid(pairs: list[tuple[str, str]], width: float, columns: int = 2) -> Table:
    rows, per = [], (len(pairs) + columns - 1) // columns
    for i in range(per):
        row = []
        for c in range(columns):
            idx = i + c * per
            label, value = pairs[idx] if idx < len(pairs) else ("", "")
            row += [Paragraph(f"<b>{pdf_text(label)}</b>" if label else "", CELL), P(value)]
        rows.append(row)
    label_w = 28 * mm
    value_w = (width - columns * label_w) / columns
    table = Table(rows, colWidths=[label_w, value_w] * columns)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))  # fmt: skip
    return table


def _grid(rows: list[list], widths: list[float], *, right_from: int = 1, total_rows: tuple[int, ...] = (),
          sub_rows: tuple[int, ...] = ()) -> Table:  # fmt: skip
    table = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]  # fmt: skip
    for r in sub_rows:
        style += [("BACKGROUND", (0, r), (-1, r), SOFT)]
    for r in total_rows:
        style += [("BACKGROUND", (0, r), (-1, r), SOFT), ("LINEABOVE", (0, r), (-1, r), 0.8, NAVY)]
    table.setStyle(TableStyle(style))
    return table


def _h(labels: list[str], right_from: int = 1) -> list[Paragraph]:
    return [
        Paragraph(pdf_text(label), HEAD_R if i >= right_from else HEAD)
        for i, label in enumerate(labels)
    ]


def _bold(value: object, right: bool = True) -> Paragraph:
    base = CELL_R if right else CELL
    return Paragraph(f"<b>{pdf_text(value)}</b>", base)


def _r(value: object) -> Paragraph:
    return P(value, CELL_R)


# ====================================================================== completo
def ce_full_pdf(detail: CEDetail, generated_at: datetime, logo_path: Path | None = None) -> bytes:
    buffer = BytesIO()
    h, v, cal = detail.header, detail.version, detail.calculation
    footer = f"Riservato - uso interno · CE {detail.ce.code} v{v.number} · generato il {fmt_datetime(generated_at)}"
    doc, canvasmaker = _doc(buffer, f"CE {detail.ce.code} v{v.number}", landscape(A4), footer)
    width = doc.width
    story: list = [
        _title_block(
            f"Conto economico {detail.ce.code}",
            f"{h.client.name} · {h.project_name}",
            width,
            logo_path,
        ),
        Spacer(1, 6),
    ]
    approved = (
        f"{fmt_datetime(v.approved_at)} · {v.approved_by.full_name}"
        if v.approved_at and v.approved_by
        else "-"
    )
    story.append(_info_grid([
        ("Cliente", h.client.name), ("Progetto", h.project_name),
        ("Periodo", f"{fmt_date(h.start_date)} - {fmt_date(h.end_date)}"), ("Modalità", MODE_LABELS[h.planning_mode]),
        ("Versione", f"{v.number} ({STATUS_LABELS[v.status]})"), ("Approvato", approved),
        ("Business Unit", h.business_unit or "-"), ("Opportunità SF", h.sf_opportunity or "-"),
        ("Autore", detail.ce.owner.full_name), ("Anno tariffe", str(v.rate_year)),
    ], width, columns=2))  # fmt: skip

    k, t = cal.kpis, cal.total
    story += [Paragraph("Indicatori", H2)]
    labels = [
        "Prezzo progetto",
        "Costi",
        "Margine",
        "Margine %",
        "C/R",
        "Giornate",
        "GG management",
        "GG delivery",
        "Prezzo minimo",
        "Fee media min",
    ]
    values = [fmt_money(k.price_project), fmt_money(t.cost), fmt_money(t.margin), fmt_pct(t.margin_pct), fmt_pct(t.cost_ratio),
              fmt_num(k.days_total), fmt_num(k.days_project_management), fmt_num(k.days_delivery), fmt_money(k.price_min),
              fmt_money(k.fee_media_min)]  # fmt: skip
    kpi = Table(
        [[P(x, SMALL) for x in labels], [_bold(x, False) for x in values]],
        colWidths=[width / 10] * 10,
    )
    kpi.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))  # fmt: skip
    story.append(kpi)
    if k.signed_price is not None:
        story.append(Spacer(1, 3))
        story.append(P(
            f"Prezzo firmato {fmt_money(k.signed_price)} · margine {fmt_money(k.margin_signed)} ({fmt_pct(k.margin_pct_signed)}) · "
            f"fee media {fmt_money(k.fee_media_signed)}", SMALL))  # fmt: skip
    if k.max_discount_pct:
        story.append(P(f"Max sconto {fmt_num(k.max_discount_pct)}%", SMALL))

    story += [Paragraph("Ricavi e costi", H2)]
    rows = [_h(["Voce", "Ricavi (€)", "Costi (€)", "Margine (€)", "Margine %", "C/R", "Giornate"])]
    for label, b in (
        ("Servizi interni", cal.internal),
        ("Servizi esterni", cal.external),
        ("Contingency", cal.contingency),
    ):
        rows.append([P(label), _r(fmt_num(b.revenue)), _r(fmt_num(b.cost)), _r(fmt_num(b.margin)),
                     _r(fmt_pct(b.margin_pct)), _r(fmt_pct(b.cost_ratio)), _r(fmt_num(b.days))])  # fmt: skip
    rows.append([_bold("Totale", False), _bold(fmt_num(t.revenue)), _bold(fmt_num(t.cost)), _bold(fmt_num(t.margin)),
                 _bold(fmt_pct(t.margin_pct)), _bold(fmt_pct(t.cost_ratio)), _bold(fmt_num(t.days))])  # fmt: skip
    story.append(_grid(rows, [width * 0.28] + [width * 0.12] * 6, total_rows=(4,)))

    story += [Paragraph("Dettaglio per fase", H2)]
    rate_by_id = {r.profile_id: r for r in detail.rates}
    calc_by_pos = {(c.phase_index, c.line_index): c for c in cal.lines}
    cw = [width * f for f in (0.26, 0.13, 0.15, 0.07, 0.07, 0.11, 0.11, 0.10)]
    for p, (phase, pc) in enumerate(zip(detail.phases, cal.phases, strict=True)):
        title = f"{phase.name}" + (
            f" · contingency {fmt_num(phase.contingency_pct)}%" if phase.contingency_pct else ""
        )
        rows = [
            _h(
                [
                    "Attività",
                    "Profilo",
                    "Collaboratore",
                    "Ore",
                    "Giorni",
                    "Ricavo (€)",
                    "Costo (€)",
                    "Margine (€)",
                ],
                right_from=3,
            )
        ]
        for l_, line in enumerate(phase.lines):
            c = calc_by_pos[(p, l_)]
            tag = " (PM)" if line.is_project_management else ""
            ext = " [esterno]" if rate_by_id[line.profile_id].is_external else ""
            rows.append([P(line.activity + tag), P(line.profile_name + ext), P(line.employee_name or "-"), _r(fmt_num(c.hours)),
                         _r(fmt_num(c.days)), _r(fmt_num(c.revenue)), _r(fmt_num(c.cost)), _r(fmt_num(c.margin))])  # fmt: skip
        rows.append([_bold(f"Totale {phase.name}", False), "", "", _bold(fmt_num(pc.hours)), _bold(fmt_num(pc.days)),
                     _bold(fmt_num(pc.revenue)), _bold(fmt_num(pc.cost)), _bold(fmt_num(pc.revenue - pc.cost))])  # fmt: skip
        sub = (len(rows) - 1,)
        if phase.contingency_pct:
            rows.append(
                [
                    P(f"Ricavo da contingency {fmt_num(phase.contingency_pct)}% (senza costi)"),
                    "",
                    "",
                    "",
                    "",
                    _r(fmt_num(pc.contingency_revenue)),
                    "",
                    "",
                ]
            )
        phase_title = Paragraph(pdf_text(title), PHASE_TITLE)
        table = _grid(rows, cw, total_rows=sub)
        if (
            len(phase.lines) < 8
        ):  # le fasi corte restano unite; quelle lunghe si spezzano ripetendo l'intestazione
            story.append(KeepTogether([phase_title, table]))
        else:
            story += [phase_title, table]
    if not detail.phases:
        story.append(P("Nessuna fase."))

    story += [Paragraph("Riepilogo per profilo", H2)]
    rows = [_h(["Profilo", "Ore", "Giorni", "Quota ore", "Ricavi (€)", "Costi (€)", "Margine (€)"])]
    for pr in cal.profiles:
        rows.append([P(pr.profile_name + (" [esterno]" if pr.is_external else "")), _r(fmt_num(pr.hours)), _r(fmt_num(pr.days)),
                     _r(fmt_pct(pr.hours_share)), _r(fmt_num(pr.revenue)), _r(fmt_num(pr.cost)), _r(fmt_num(pr.margin))])  # fmt: skip
    story.append(_grid(rows, [width * 0.28] + [width * 0.12] * 6))

    story += [Paragraph("Staffing mensile", H2)]
    rows = [_h(["Mese", "Giorni lavorativi", "Giorni", "Ore", "FTE", "Ricavi (€)", "Costi (€)"])]
    for m in cal.monthly:
        rows.append([P(m.month.strftime("%m/%Y")), _r(m.work_days), _r(fmt_num(m.days)), _r(fmt_num(m.hours)),
                     _r(fmt_pct(m.fte)), _r(fmt_num(m.revenue)), _r(fmt_num(m.cost))])  # fmt: skip
    story.append(_grid(rows, [width * 0.16] + [width * 0.14] * 6))
    story += [
        Spacer(1, 4),
        P(
            "Ricavi e costi mensili escludono la contingency. 1 giorno = 8 ore. FTE = giorni / giorni lavorativi del mese.",
            SMALL,
        ),
    ]
    if cal.warnings:
        story.append(P("Avvisi: " + "; ".join(cal.warnings), SMALL))

    doc.build(story, canvasmaker=canvasmaker)
    return buffer.getvalue()


# ====================================================================== riepilogo (anche per il viewer)
def ce_summary_pdf(
    ce: ViewerCE, status: str | None, generated_at: datetime, logo_path: Path | None = None
) -> bytes:
    buffer = BytesIO()
    footer = f"CE {ce.code} v{ce.version_number} · generato il {fmt_datetime(generated_at)}"
    doc, canvasmaker = _doc(buffer, f"Riepilogo CE {ce.code} v{ce.version_number}", A4, footer)
    width = doc.width
    story: list = [
        _title_block(f"Riepilogo {ce.code}", f"{ce.client_name} · {ce.project_name}", width, logo_path), Spacer(1, 6),
        _info_grid([("Cliente", ce.client_name), ("Progetto", ce.project_name),
                    ("Periodo", f"{fmt_date(ce.start_date)} - {fmt_date(ce.end_date)}"), ("Versione", str(ce.version_number)),
                    ("Stato", STATUS_LABELS.get(status or "approved", "Approvato")),
                    ("Approvato il", fmt_datetime(ce.approved_at) or "-")], width, columns=1),
    ]  # fmt: skip
    if status and status != "approved":
        story += [Spacer(1, 4), P("Versione non approvata: i valori possono cambiare.", SMALL)]
    story += [Paragraph("Giornate", H2)]
    rows = [_h(["Attività", "Giornate"]),
            [P("Project management"), _r(fmt_num(ce.days_project_management))],
            [P("Delivery"), _r(fmt_num(ce.days_delivery))],
            [_bold("Totale giornate", False), _bold(fmt_num(ce.days_total))]]  # fmt: skip
    story.append(_grid(rows, [width * 0.7, width * 0.3], total_rows=(3,)))
    story += [Paragraph("Ricavi per fase", H2)]
    rows = [_h(["Fase", "Ricavi (€)"])] + [[P(p.name), _r(fmt_num(p.revenue))] for p in ce.phases]
    rows.append([_bold("Totale generale", False), _bold(fmt_num(ce.total_revenue))])
    story.append(_grid(rows, [width * 0.7, width * 0.3], total_rows=(len(rows) - 1,)))
    story += [
        Spacer(1, 8),
        P(
            "Documento riepilogativo: indica giornate e ricavi, senza il dettaglio delle attività e dei costi.",
            SMALL,
        ),
    ]
    doc.build(story, canvasmaker=canvasmaker)
    return buffer.getvalue()
