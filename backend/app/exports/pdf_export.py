"""PDF con reportlab: completo (uso interno, A4 orizzontale) e riepilogo (A4 verticale).

Stile «moderno» del marchio Huware (CL-036): fascia nera con il logo bianco e un filo sfumato ciano-turchese,
riquadri per gli indicatori, ciambella costi/margine e barre disegnate come grafica vettoriale (nessuna immagine,
file piccoli e nitidi a ogni ingrandimento), tabelle con intestazioni turchesi. Font DM Sans (licenza OFL) incorporato:
se i file dei font mancassero si ripiega su Helvetica e il PDF si produce comunque.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
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
from app.services.unit_division import DivisionRow

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO_PATH = ASSETS / "logo.png"  # logo nero, per sfondi chiari
LOGO_WHITE_PATH = ASSETS / "logo-white.png"  # logo bianco, per la fascia scura
FONT_DIR = ASSETS / "fonts"

# ---- colori del marchio
INK = colors.HexColor("#0a0a0a")
CYAN = colors.HexColor("#00f5fe")
TEAL = colors.HexColor("#00acc7")
TEAL_700 = colors.HexColor("#00798d")
SURFACE = colors.HexColor("#f4f6f7")
LINE = colors.HexColor("#dfe5e8")
MUTED = colors.HexColor("#5b6770")
TINT = colors.HexColor("#e6fcfd")
TRACK = colors.HexColor("#e3e9ec")
COST_GREY = colors.HexColor("#c9d3d8")
BAND_MUTED = colors.HexColor("#9fb0b8")
ALERT = colors.HexColor("#c0392b")
BAR_COLORS = [TEAL, CYAN, TEAL_700, colors.HexColor("#7ad9e6"), BAND_MUTED]

# ---- geometria
BAND_FIRST = 25 * mm  # fascia della prima pagina
BAND_LATER = 10 * mm  # fascia sottile delle pagine successive
GAP_UNDER_BAND = 6 * mm
FOOTER_H = 11 * mm
FRAME_BOTTOM = 15 * mm
MARGIN_X = 15 * mm


# ====================================================================== font
@dataclass(frozen=True)
class Fonts:
    regular: str
    medium: str
    bold: str
    light: str
    embedded: bool


def load_fonts(font_dir: Path = FONT_DIR) -> Fonts:
    """Registra DM Sans; se i file non ci sono o sono illeggibili ripiega su Helvetica."""
    files = {
        "DMSans-Light": "DMSans-Light.ttf",
        "DMSans": "DMSans-Regular.ttf",
        "DMSans-Medium": "DMSans-Medium.ttf",
        "DMSans-Bold": "DMSans-Bold.ttf",
    }
    try:
        for name, filename in files.items():
            path = Path(font_dir) / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily(
            "DMSans", normal="DMSans", bold="DMSans-Bold", italic="DMSans", boldItalic="DMSans-Bold"
        )
        return Fonts("DMSans", "DMSans-Medium", "DMSans-Bold", "DMSans-Light", True)
    except Exception:  # file mancante o rovinato: il PDF si produce comunque, con i font standard
        return Fonts("Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica", False)


F = load_fonts()

BASE = ParagraphStyle("base", fontName=F.regular, fontSize=8.5, leading=10.8, textColor=INK)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=7.5, leading=9.5, textColor=MUTED)
LABEL = ParagraphStyle(
    "label", parent=BASE, fontName=F.medium, fontSize=8, leading=9.8, textColor=MUTED
)
CELL = ParagraphStyle("cell", parent=BASE, fontSize=8, leading=9.8)
CELL_R = ParagraphStyle("cell_r", parent=CELL, alignment=2)
HEAD = ParagraphStyle("head", parent=CELL, fontName=F.medium, textColor=colors.white)
HEAD_R = ParagraphStyle("head_r", parent=HEAD, alignment=2)
PHASE_TITLE = ParagraphStyle(
    "ph",
    parent=BASE,
    fontName=F.medium,
    fontSize=9.5,
    leading=12,
    textColor=TEAL_700,
    spaceBefore=7,
    spaceAfter=3,
)


def pdf_text(value: object) -> str:
    """Testo sicuro per il PDF: niente markup interpretato e niente caratteri che i font non hanno."""
    text = str(value).encode("cp1252", errors="replace").decode("cp1252")
    return escape(" ".join(text.split()))


def canvas_text(value: object) -> str:
    """Testo da disegnare direttamente sulla pagina (nessun markup da neutralizzare)."""
    return " ".join(str(value).encode("cp1252", errors="replace").decode("cp1252").split())


def fit_text(text: str, font: str, size: float, max_width: float) -> str:
    """Accorcia il testo con «...» se non sta nella larghezza indicata."""
    if stringWidth(text, font, size) <= max_width:
        return text
    while text and stringWidth(text + "...", font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + "..."


def P(value: object, style: ParagraphStyle = CELL) -> Paragraph:
    return Paragraph(pdf_text(value), style)


# ====================================================================== fascia, piè di pagina, pagine
@dataclass(frozen=True)
class Band:
    title: str  # titolo nella fascia della prima pagina
    subtitle: str
    chip: str  # stato (Bozza, Approvato…)
    running: str  # testo nella fascia sottile delle pagine successive


def _band_logo(logo_path: Path | None, height: float):
    """(percorso, larghezza, su_piastra) del logo adatto alla fascia scura, oppure None."""
    path = Path(logo_path) if logo_path is not None else LOGO_PATH
    if not path.exists():
        return None
    white = path.with_name("logo-white.png")
    if (
        path.name == "logo.png" and white.exists()
    ):  # coppia standard: nella fascia scura va quello bianco
        path, plate = white, False
    else:  # logo personalizzato senza versione bianca: lo si appoggia su una piastra chiara
        plate = True
    width, h = ImageReader(str(path)).getSize()
    return str(path), height * width / h, plate


def _draw_band(
    c, page_w: float, page_h: float, band: Band, logo_path: Path | None, first: bool
) -> None:
    height = BAND_FIRST if first else BAND_LATER
    y0 = page_h - height
    c.saveState()
    c.setFillColor(INK)
    c.rect(0, y0, page_w, height, stroke=0, fill=1)
    c.saveState()  # filo sfumato ciano → turchese sul bordo inferiore
    clip = c.beginPath()
    clip.rect(0, y0, page_w, 1.1 * mm)
    c.clipPath(clip, stroke=0, fill=0)
    c.linearGradient(0, y0, page_w, y0, (CYAN, TEAL), extend=False)
    c.restoreState()

    logo_h = 9 * mm if first else 4.6 * mm
    logo = _band_logo(logo_path, logo_h)
    x = MARGIN_X
    cy = y0 + height / 2
    if logo:
        path, logo_w, plate = logo
        if plate:
            c.setFillColor(colors.white)
            c.roundRect(
                x - 2 * mm,
                cy - logo_h / 2 - 1 * mm,
                logo_w + 4 * mm,
                logo_h + 2 * mm,
                1.5 * mm,
                stroke=0,
                fill=1,
            )
        c.drawImage(path, x, cy - logo_h / 2, width=logo_w, height=logo_h, mask="auto")
        x += logo_w + (9 * mm if first else 6 * mm)
    else:
        name_size = 10 if first else 7.5
        c.setFillColor(colors.white)
        c.setFont(F.bold, name_size)
        c.drawString(x, cy - name_size / 3, "Portale Conti Economici")
        x += stringWidth("Portale Conti Economici", F.bold, name_size) + (
            9 * mm if first else 6 * mm
        )

    right = page_w - MARGIN_X
    if first:
        chip = canvas_text(band.chip)
        c.setFont(F.medium, 8)
        chip_w = stringWidth(chip, F.medium, 8) + 7 * mm
        c.setFillColor(CYAN)
        c.roundRect(right - chip_w, cy - 2.6 * mm, chip_w, 5.2 * mm, 2.6 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.drawCentredString(right - chip_w / 2, cy - 1 * mm, chip)
        room = right - chip_w - 6 * mm - x
        c.setFillColor(colors.white)
        c.setFont(F.light, 17)
        c.drawString(x, cy + 0.8 * mm, fit_text(canvas_text(band.title), F.light, 17, room))
        c.setFillColor(BAND_MUTED)
        c.setFont(F.regular, 8.5)
        c.drawString(x, cy - 5.6 * mm, fit_text(canvas_text(band.subtitle), F.regular, 8.5, room))
    else:
        c.setFillColor(BAND_MUTED)
        c.setFont(F.regular, 7.5)
        text = fit_text(canvas_text(band.running), F.regular, 7.5, right - x)
        c.drawRightString(right, cy - 1 * mm, text)
    c.restoreState()


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
        self.setFillColor(SURFACE)
        self.rect(0, 0, width, FOOTER_H, stroke=0, fill=1)
        self.setFont(F.regular, 7)
        self.setFillColor(MUTED)
        self.drawString(MARGIN_X, 4.2 * mm, pdf_text(self._footer))
        self.drawRightString(width - MARGIN_X, 4.2 * mm, f"Pagina {self._pageNumber} di {total}")


def _doc(buffer: BytesIO, title: str, page_size, footer: str, band: Band, logo_path: Path | None):
    page_w, page_h = page_size
    doc = BaseDocTemplate(
        buffer, pagesize=page_size, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=BAND_FIRST + GAP_UNDER_BAND, bottomMargin=FRAME_BOTTOM,
        title=pdf_text(title), author="Portale Conti Economici", creator="Portale Conti Economici",
        subject="Conto economico di progetto",
    )  # fmt: skip

    def frame(top: float) -> Frame:
        return Frame(
            MARGIN_X, FRAME_BOTTOM, page_w - 2 * MARGIN_X, page_h - top - FRAME_BOTTOM,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )  # fmt: skip

    doc.addPageTemplates([
        PageTemplate(id="first", frames=[frame(BAND_FIRST + GAP_UNDER_BAND)], pagesize=page_size,
                     onPage=lambda c, d: _draw_band(c, page_w, page_h, band, logo_path, True)),
        PageTemplate(id="later", frames=[frame(BAND_LATER + GAP_UNDER_BAND)], pagesize=page_size,
                     onPage=lambda c, d: _draw_band(c, page_w, page_h, band, logo_path, False)),
    ])  # fmt: skip
    return doc, lambda *a, **kw: _NumberedCanvas(*a, footer=footer, **kw)


# ====================================================================== elementi grafici
class KpiCards(Flowable):
    """Riquadri degli indicatori: fondo chiaro con filo turchese in alto; quello in evidenza è ciano."""

    def __init__(
        self,
        items: list[dict],
        width: float,
        weights: list[float] | None = None,
        height: float = 17 * mm,
        gap: float = 3 * mm,
    ):
        super().__init__()
        self.items, self.width, self.height, self.gap = items, width, height, gap
        self.weights = weights or [1] * len(items)

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        unit = (self.width - self.gap * (len(self.items) - 1)) / sum(self.weights)
        x = 0.0
        for item, weight in zip(self.items, self.weights, strict=True):
            w = unit * weight
            hero = bool(item.get("hero"))
            c.saveState()
            clip = c.beginPath()
            clip.roundRect(x, 0, w, self.height, 2.2 * mm)
            c.clipPath(clip, stroke=0, fill=0)
            c.setFillColor(CYAN if hero else SURFACE)
            c.rect(x, 0, w, self.height, stroke=0, fill=1)
            c.setFillColor(INK if hero else TEAL)
            c.rect(x, self.height - 1.1 * mm, w, 1.1 * mm, stroke=0, fill=1)
            c.restoreState()
            pad = 3 * mm
            c.setFillColor(INK if hero else MUTED)
            c.setFont(F.regular, 6)
            c.drawString(x + pad, self.height - 5.6 * mm, canvas_text(item["label"]).upper())
            value, size = canvas_text(item["value"]), 13.0
            while size > 7.5 and stringWidth(value, F.medium, size) > w - 2 * pad:
                size -= (
                    0.5  # un importo molto grande si rimpicciolisce invece di uscire dal riquadro
                )
            c.setFillColor(INK)
            c.setFont(F.medium, size)
            c.drawString(x + pad, self.height - 11.6 * mm, value)
            if item.get("extra"):
                c.setFillColor(INK if hero else TEAL_700)
                c.setFont(F.regular, 6.8)
                c.drawString(x + pad, 2.4 * mm, canvas_text(item["extra"]))
            x += w + self.gap


def _section(story: list, text: str, width: float) -> None:
    """Titolo di sezione che non resta mai solo in fondo a una pagina: se sotto non c'è posto per
    l'intestazione e almeno una riga della tabella, si va a pagina nuova."""
    story += [CondPageBreak(32 * mm), SectionTitle(text, width)]


class SectionTitle(Flowable):
    """Titolo di sezione con un quadratino turchese; resta unito alla tabella che segue."""

    def __init__(self, text: str, width: float):
        super().__init__()
        self.text, self.width, self.height = text, width, 6 * mm
        self.spaceBefore, self.spaceAfter, self.keepWithNext = 9, 3, True

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(TEAL)
        c.roundRect(0, 1.5 * mm, 2.2 * mm, 2.2 * mm, 0.5 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont(F.medium, 10)
        c.drawString(4 * mm, 1.4 * mm, canvas_text(self.text))


class ChartRow(Flowable):
    """Grafici vettoriali affiancati: ciambella costi/margine (facoltativa) e barre orizzontali."""

    ROW = 5.4 * mm

    def __init__(
        self,
        width: float,
        *,
        bars_title: str,
        bars: list[tuple[str, float, str]],
        donut: dict | None = None,
    ):
        super().__init__()
        self.width, self.bars_title, self.bars, self.donut = (
            width,
            bars_title,
            list(bars)[:6],
            donut,
        )
        self.height = max(30 * mm if donut else 0, 10 * mm + self.ROW * max(len(self.bars), 1))

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        x_bars = 0.0
        if self.donut:
            self._draw_donut(self.canv, self.donut)
            x_bars = self.width * 0.5
        self._draw_bars(self.canv, x_bars, self.width - x_bars)

    def _title(self, c, x: float, text: str) -> None:
        c.setFillColor(MUTED)
        c.setFont(F.regular, 6.2)
        c.drawString(x, self.height - 3 * mm, canvas_text(text).upper())

    def _draw_donut(self, c, d: dict) -> None:
        radius, ring = 10 * mm, 4 * mm
        cx, cy = radius + ring / 2 + 1 * mm, (self.height - 6 * mm) / 2
        self._title(c, 0, d["title"])
        c.setLineWidth(ring)
        c.setStrokeColor(COST_GREY)
        c.circle(cx, cy, radius, stroke=1, fill=0)
        share = d["share"]  # quota del margine tra 0 e 1, oppure None se non calcolabile
        if share:
            c.setStrokeColor(d["color"])
            if share >= 0.9999:
                c.circle(cx, cy, radius, stroke=1, fill=0)
            else:
                c.arc(cx - radius, cy - radius, cx + radius, cy + radius, 90, -360 * share)
        c.setFillColor(INK)
        c.setFont(F.medium, 12)
        c.drawCentredString(cx, cy - 0.5 * mm, canvas_text(d["center"]))
        c.setFillColor(MUTED)
        c.setFont(F.regular, 6.2)
        c.drawCentredString(cx, cy - 4.4 * mm, "margine")
        lx = cx + radius + ring / 2 + 6 * mm
        for i, (color, text) in enumerate(d["legend"]):
            y = cy + 3 * mm - i * 5.2 * mm
            c.setFillColor(color)
            c.roundRect(lx, y - 0.7 * mm, 2.6 * mm, 2.6 * mm, 0.6 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont(F.regular, 8)
            c.drawString(lx + 4.2 * mm, y, canvas_text(text))

    def _draw_bars(self, c, x0: float, w: float) -> None:
        self._title(c, x0, self.bars_title)
        if not self.bars:
            c.setFillColor(MUTED)
            c.setFont(F.regular, 8)
            c.drawString(x0, self.height - 9 * mm, "Nessun dato")
            return
        label_w, value_w = 30 * mm, 21 * mm
        track_x, track_w = x0 + label_w + 2 * mm, max(w - label_w - value_w - 4 * mm, 10 * mm)
        top = max(value for _, value, _ in self.bars) or 1.0
        for i, (label, value, text) in enumerate(self.bars):
            y = self.height - 9 * mm - i * self.ROW
            c.setFillColor(INK)
            c.setFont(F.regular, 7.6)
            c.drawString(x0, y, fit_text(canvas_text(label), F.regular, 7.6, label_w))
            c.setFillColor(TRACK)
            c.roundRect(track_x, y - 0.4 * mm, track_w, 2.8 * mm, 1.4 * mm, stroke=0, fill=1)
            if value > 0:
                c.setFillColor(BAR_COLORS[i % len(BAR_COLORS)])
                c.roundRect(
                    track_x,
                    y - 0.4 * mm,
                    max(track_w * value / top, 2.8 * mm),
                    2.8 * mm,
                    1.4 * mm,
                    stroke=0,
                    fill=1,
                )
            c.setFillColor(INK)
            c.setFont(F.regular, 7.6)
            c.drawRightString(x0 + w, y, canvas_text(text))


def _donut_for(margin_pct: Decimal | None, cost_ratio: Decimal | None) -> dict:
    """Dati della ciambella: il margine in turchese sul resto (i costi). Margine non calcolabile o negativo: lo si dice."""
    base = {"title": "Come si divide il prezzo", "color": TEAL}
    if margin_pct is None:
        return {
            **base,
            "share": None,
            "center": "n/d",
            "legend": [(TEAL, "Margine n/d"), (COST_GREY, "Costi n/d")],
        }
    share = float(margin_pct)
    if share < 0:
        return {**base, "share": 1.0, "color": ALERT, "center": f"{round(share * 100)}%",
                "legend": [(ALERT, f"Margine negativo {fmt_pct(margin_pct)}"), (COST_GREY, f"Costi {fmt_pct(cost_ratio)}")]}  # fmt: skip
    return {**base, "share": min(share, 1.0), "center": f"{round(share * 100)}%",
            "legend": [(TEAL, f"Margine {fmt_pct(margin_pct)}"), (COST_GREY, f"Costi {fmt_pct(cost_ratio)}")]}  # fmt: skip


# ====================================================================== tabelle
def _info_grid(pairs: list[tuple[str, str]], width: float, columns: int = 2) -> Table:
    rows, per = [], (len(pairs) + columns - 1) // columns
    for i in range(per):
        row = []
        for c in range(columns):
            idx = i + c * per
            label, value = pairs[idx] if idx < len(pairs) else ("", "")
            row += [Paragraph(pdf_text(label), LABEL) if label else "", P(value)]
        rows.append(row)
    label_w = (27 if columns >= 3 else 28) * mm
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
        ("BACKGROUND", (0, 0), (-1, 0), TEAL_700), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("TOPPADDING", (0, 0), (-1, -1), 2.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]  # fmt: skip
    for r in sub_rows:
        style += [("BACKGROUND", (0, r), (-1, r), TINT)]
    for r in total_rows:
        style += [("BACKGROUND", (0, r), (-1, r), TINT), ("LINEABOVE", (0, r), (-1, r), 1, TEAL)]
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


def _profile_bars(profiles) -> list[tuple[str, float, str]]:
    return [
        (
            pr.profile_name + (" [esterno]" if pr.is_external else ""),
            float(pr.days),
            f"{fmt_num(pr.days)} gg",
        )
        for pr in profiles
        if pr.days
    ]


# ====================================================================== completo
def ce_full_pdf(
    detail: CEDetail,
    generated_at: datetime,
    logo_path: Path | None = None,
    division: list[DivisionRow] | None = None,
) -> bytes:
    buffer = BytesIO()
    h, v, cal = detail.header, detail.version, detail.calculation
    code = detail.ce.code
    footer = f"Riservato - uso interno · CE {code} v{v.number} · generato il {fmt_datetime(generated_at)}"
    band = Band(
        title=f"Conto economico {code}",
        subtitle=f"{h.client.name} · {h.project_name}",
        chip=STATUS_LABELS[v.status],
        running=f"Conto economico {code} · {h.client.name} · v{v.number}",
    )
    doc, canvasmaker = _doc(
        buffer, f"CE {code} v{v.number}", landscape(A4), footer, band, logo_path
    )
    width = doc.width
    story: list = [NextPageTemplate("later")]
    approved = (
        f"{fmt_datetime(v.approved_at)} · {v.approved_by.full_name}"
        if v.approved_at and v.approved_by
        else "-"
    )
    story += [_info_grid([
        ("Cliente", h.client.name), ("Progetto", h.project_name),
        ("Periodo", f"{fmt_date(h.start_date)} - {fmt_date(h.end_date)}"), ("Modalità", MODE_LABELS[h.planning_mode]),
        ("Versione", f"{v.number} ({STATUS_LABELS[v.status]})"), ("Approvato", approved),
        ("Business Unit", h.business_unit or "-"), ("Opportunità SF", h.sf_opportunity or "-"),
        ("Autore", detail.ce.owner.full_name), ("Anno tariffe", str(v.rate_year)),
    ], width, columns=3), Spacer(1, 8)]  # fmt: skip

    k, t = cal.kpis, cal.total
    story.append(KpiCards([
        {"label": "Prezzo progetto", "value": fmt_money(k.price_project), "hero": True},
        {"label": "Costi", "value": fmt_money(t.cost)},
        {"label": "Margine", "value": fmt_money(t.margin), "extra": fmt_pct(t.margin_pct)},
        {"label": "Giornate", "value": fmt_num(k.days_total)},
        {"label": "Fee media min", "value": fmt_money(k.fee_media_min)},
    ], width, weights=[1.25, 1, 1.15, 0.8, 1]))  # fmt: skip
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"C/R <b>{pdf_text(fmt_pct(t.cost_ratio))}</b> · GG management <b>{pdf_text(fmt_num(k.days_project_management))}</b> · "
        f"GG delivery <b>{pdf_text(fmt_num(k.days_delivery))}</b> · Prezzo minimo <b>{pdf_text(fmt_money(k.price_min))}</b>", SMALL))  # fmt: skip
    if k.signed_price is not None:
        story.append(Spacer(1, 2))
        story.append(P(
            f"Prezzo firmato {fmt_money(k.signed_price)} · margine {fmt_money(k.margin_signed)} ({fmt_pct(k.margin_pct_signed)}) · "
            f"fee media {fmt_money(k.fee_media_signed)}", SMALL))  # fmt: skip
    if k.max_discount_pct:
        story.append(P(f"Max sconto {fmt_num(k.max_discount_pct)}%", SMALL))
    story += [
        Spacer(1, 7),
        ChartRow(
            width,
            bars_title="Giornate per profilo",
            bars=_profile_bars(cal.profiles),
            donut=_donut_for(t.margin_pct, t.cost_ratio),
        ),
    ]

    _section(story, "Ricavi e costi", width)
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

    if division:  # divisione tra le business unit (solo nel PDF completo: ha costi e margini)
        _section(story, "Divisione per business unit", width)
        rows = [
            _h(
                [
                    "Business unit",
                    "Giornate",
                    "Ricavi (€)",
                    "Costi (€)",
                    "Margine (€)",
                    "Margine %",
                    "% dei ricavi",
                ]
            )
        ]
        for r in division:
            rows.append([P(r.label), _r(fmt_num(r.days)), _r(fmt_num(r.revenue)), _r(fmt_num(r.cost)),
                         _r(fmt_num(r.margin)), _r(fmt_pct(r.margin_pct)), _r(fmt_pct(r.share))])  # fmt: skip
        rows.append([_bold("Totale", False), _bold(fmt_num(t.days)), _bold(fmt_num(t.revenue)), _bold(fmt_num(t.cost)),
                     _bold(fmt_num(t.margin)), _bold(fmt_pct(t.margin_pct)), _bold(fmt_pct(1 if t.revenue else None))])  # fmt: skip
        story.append(_grid(rows, [width * 0.28] + [width * 0.12] * 6, total_rows=(len(rows) - 1,)))
        story.append(Spacer(1, 3))
        story.append(P(
            "Ogni riga è attribuita alla business unit del collaboratore indicato (quella della sua practice attuale); "
            "le righe senza collaboratore e la contingency (ricavo senza costi) sono a parte.", SMALL))  # fmt: skip

    _section(story, "Dettaglio per fase", width)
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
            rows.append([P(f"Ricavo da contingency {fmt_num(phase.contingency_pct)}% (senza costi)"), "", "", "", "",
                         _r(fmt_num(pc.contingency_revenue)), "", ""])  # fmt: skip
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

    _section(story, "Riepilogo per profilo", width)
    rows = [_h(["Profilo", "Ore", "Giorni", "Quota ore", "Ricavi (€)", "Costi (€)", "Margine (€)"])]
    for pr in cal.profiles:
        rows.append([P(pr.profile_name + (" [esterno]" if pr.is_external else "")), _r(fmt_num(pr.hours)), _r(fmt_num(pr.days)),
                     _r(fmt_pct(pr.hours_share)), _r(fmt_num(pr.revenue)), _r(fmt_num(pr.cost)), _r(fmt_num(pr.margin))])  # fmt: skip
    story.append(_grid(rows, [width * 0.28] + [width * 0.12] * 6))

    _section(story, "Staffing mensile", width)
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
    """Solo giornate e ricavi per fase: nessun costo, margine, tariffa o dettaglio delle attività."""
    buffer = BytesIO()
    footer = f"CE {ce.code} v{ce.version_number} · generato il {fmt_datetime(generated_at)}"
    band = Band(
        title=f"Riepilogo {ce.code}",
        subtitle=f"{ce.client_name} · {ce.project_name}",
        chip=STATUS_LABELS.get(status or "approved", "Approvato"),
        running=f"Riepilogo {ce.code} · {ce.client_name} · v{ce.version_number}",
    )
    doc, canvasmaker = _doc(
        buffer, f"Riepilogo CE {ce.code} v{ce.version_number}", A4, footer, band, logo_path
    )
    width = doc.width
    story: list = [
        NextPageTemplate("later"),
        _info_grid([("Cliente", ce.client_name), ("Progetto", ce.project_name),
                    ("Periodo", f"{fmt_date(ce.start_date)} - {fmt_date(ce.end_date)}"), ("Versione", str(ce.version_number)),
                    ("Stato", STATUS_LABELS.get(status or "approved", "Approvato")),
                    ("Approvato il", fmt_datetime(ce.approved_at) or "-")], width, columns=2),
        Spacer(1, 8),
    ]  # fmt: skip
    if status and status != "approved":
        story += [P("Versione non approvata: i valori possono cambiare.", SMALL), Spacer(1, 6)]
    story.append(KpiCards([
        {"label": "Giornate totali", "value": fmt_num(ce.days_total)},
        {"label": "Ricavi totali", "value": fmt_money(ce.total_revenue), "hero": True},
    ], width, weights=[1, 1.3]))  # fmt: skip
    story += [
        Spacer(1, 8),
        ChartRow(
            width,
            bars_title="Ricavi per fase",
            bars=[(p.name, float(p.revenue), fmt_num(p.revenue)) for p in ce.phases],
        ),
    ]
    _section(story, "Giornate", width)
    rows = [_h(["Attività", "Giornate"]),
            [P("Project management"), _r(fmt_num(ce.days_project_management))],
            [P("Delivery"), _r(fmt_num(ce.days_delivery))],
            [_bold("Totale giornate", False), _bold(fmt_num(ce.days_total))]]  # fmt: skip
    story.append(_grid(rows, [width * 0.7, width * 0.3], total_rows=(3,)))
    _section(story, "Ricavi per fase", width)
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
