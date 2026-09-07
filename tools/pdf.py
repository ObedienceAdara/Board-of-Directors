"""Compact board-report PDF renderer.

The renderer receives a bounded page model from reports.executive and keeps
one deliberate page per strategic question. It never dumps raw department
transcripts into the PDF.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

PAGE_WIDTH, PAGE_HEIGHT = A4
MAX_CONTENT_PAGES = 12


def _inline(text: str) -> str:
    text = html.escape(str(text or ""), quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)


def _paragraphs(text: str, body_style: ParagraphStyle, bullet_style: ParagraphStyle) -> list[Any]:
    flowables: list[Any] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            flowables.append(Spacer(1, 0.08 * cm))
            continue
        if line.startswith(("•", "-", "*")):
            flowables.append(Paragraph(f"• {_inline(line[1:].strip())}", bullet_style))
        else:
            flowables.append(Paragraph(_inline(line), body_style))
    return flowables or [Paragraph("No information available.", body_style)]


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9DDE5"))
    canvas.line(2 * cm, 1.35 * cm, PAGE_WIDTH - 2 * cm, 1.35 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(2 * cm, 0.85 * cm, "Plex Hedge · Board of Directors AI")
    canvas.drawRightString(PAGE_WIDTH - 2 * cm, 0.85 * cm, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf(board_data: dict[str, Any], output_path: str = "board_report.pdf") -> str:
    """Generate a bounded decision-grade board report with one cover page."""
    pages = list(board_data.get("pages", []))
    if not pages:
        raise ValueError("PDF report requires at least one page model")
    if len(pages) > MAX_CONTENT_PAGES:
        raise ValueError(f"Executive PDF is capped at {MAX_CONTENT_PAGES} content pages")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PageTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor("#172033"), spaceAfter=5)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#667085"), spaceAfter=10)
    section_style = ParagraphStyle("BlockTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor("#344054"), spaceBefore=6, spaceAfter=4)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13.3, textColor=colors.HexColor("#243042"), spaceAfter=4)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=10, firstLineIndent=-5, spaceAfter=2.5)
    cover_title = ParagraphStyle("CoverTitle", parent=title_style, fontSize=25, leading=30, alignment=TA_CENTER, spaceAfter=12)
    cover_subtitle = ParagraphStyle("CoverSubtitle", parent=subtitle_style, fontSize=11.5, leading=16, alignment=TA_CENTER)

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.7 * cm, bottomMargin=1.7 * cm, title=f"Board Report — {board_data.get('idea', 'Business Idea')}", author="Plex Hedge Board of Directors AI")
    story: list[Any] = []
    idea = str(board_data.get("idea", "Business Idea"))[:180]
    story.extend([
        Spacer(1, 5.0 * cm), Paragraph("BOARD OF DIRECTORS", cover_subtitle), Paragraph("STRATEGIC DECISION REPORT", cover_title),
        HRFlowable(width="72%", thickness=1.5, color=colors.HexColor("#344054"), hAlign="CENTER"), Spacer(1, 0.8 * cm), Paragraph(_inline(idea), cover_subtitle),
        Spacer(1, 1.0 * cm), Paragraph(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", cover_subtitle), Spacer(1, 6.4 * cm),
        Paragraph("Decision-grade synthesis of the board's research, economics, engineering, market, sales, operations and product analysis.", cover_subtitle), PageBreak(),
    ])
    for page_index, page in enumerate(pages):
        story.append(Paragraph(_inline(page.get("title", "Board Analysis")), title_style))
        if page.get("subtitle"):
            story.append(Paragraph(_inline(page["subtitle"]), subtitle_style))
        story.extend([HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#D9DDE5")), Spacer(1, 0.25 * cm)])
        for block_title, content in page.get("blocks", []):
            story.append(Paragraph(_inline(block_title), section_style))
            story.extend(_paragraphs(content, body_style, bullet_style))
            story.append(Spacer(1, 0.12 * cm))
        if page_index < len(pages) - 1:
            story.append(PageBreak())
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return str(path)
