"""Filled application form as a PDF (reportlab, built-in fonts, so values are Roman script)."""
import io
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import fields as F
from .translit import has_devanagari, to_roman

INK = colors.HexColor("#1d2b53")
ACCENT = colors.HexColor("#e07a1f")
PAPER = colors.HexColor("#f6f1e7")


def _safe(s: str) -> str:
    return to_roman(s) if has_devanagari(s) else s


def build_pdf(form: dict, values: dict, today: date = None) -> bytes:
    today = today or date.today()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=f"{form['title']['en']} - filled by voice", author="Vaani")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, textColor=INK, spaceAfter=2)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#5b6478"), spaceAfter=10)
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=11, textColor=INK, leading=14)
    label = ParagraphStyle("label", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#5b6478"), leading=12)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#5b6478"), leading=12)

    rows = []
    for i, f in enumerate(form["fields"], 1):
        v = values.get(f["id"])
        shown = F.fmt(f, v, "en")[0] if v is not None else "-"
        rows.append([Paragraph(f"{i}", label), Paragraph(f["label"]["en"], label), Paragraph(_safe(str(shown)), cell)])

    table = Table(rows, colWidths=[10 * mm, 52 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d2c0")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
    ]))

    story = [
        Paragraph(form["title"]["en"], h1),
        Paragraph(f"Form filled by voice with Vaani (Gnani Prisma + Timbre) on {today.strftime('%d %B %Y')}", sub),
        table,
        Spacer(1, 14 * mm),
        Paragraph("I declare that the information given above is true to the best of my knowledge.", small),
        Spacer(1, 16 * mm),
        Table([[Paragraph("Date: ____________________", small), Paragraph("Signature: ____________________", small)]],
              colWidths=[80 * mm, 82 * mm]),
        Spacer(1, 10 * mm),
        Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}. "
                  "Your answers are not stored on the server after this session.", small),
    ]
    doc.build(story)
    return buf.getvalue()
