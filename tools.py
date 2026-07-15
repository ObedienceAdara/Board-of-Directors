"""
tools.py — Search, Notion, and PDF utilities.

Fixes applied:
  - Uses langchain_tavily.TavilySearch (not deprecated TavilySearchResults)
  - Safe result parsing handles str, list[dict], and list[str] returns
"""

import os
import json
import requests
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════

from langchain_tavily import TavilySearch


def get_search_tool(max_results: int = 5) -> TavilySearch:
    return TavilySearch(max_results=max_results)


def parse_search_results(results) -> str:
    """
    Safely parse Tavily results regardless of return type.
    Handles: str, list[dict], list[str], dict
    """
    if isinstance(results, str):
        return results

    if isinstance(results, dict):
        # Sometimes returns a single result dict
        return f"URL: {results.get('url', '')}\nContent: {results.get('content', results.get('snippet', str(results)))}"

    if isinstance(results, list):
        parts = []
        for r in results:
            if isinstance(r, dict):
                parts.append(
                    f"URL: {r.get('url', '')}\n"
                    f"Content: {r.get('content', r.get('snippet', str(r)))}"
                )
            else:
                parts.append(str(r))
        return "\n\n".join(parts)

    return str(results)


# ══════════════════════════════════════════════════════════════
# NOTION
# ══════════════════════════════════════════════════════════════

NOTION_API_KEY     = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
NOTION_API_BASE    = "https://api.notion.com/v1"
NOTION_HEADERS     = {
    "Authorization":  f"Bearer {NOTION_API_KEY}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28"
}


def create_notion_board(title: str) -> str:
    """Create a parent Notion page. Returns page_id or empty string."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        print("⚠️  Notion credentials missing — skipping Notion output.")
        return ""

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]}
        },
        "children": [
            {
                "object": "block",
                "type":   "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                }
            },
            {
                "object": "block",
                "type":   "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                    }]
                }
            }
        ]
    }

    resp = requests.post(f"{NOTION_API_BASE}/pages", headers=NOTION_HEADERS, json=payload)
    if resp.status_code == 200:
        page_id  = resp.json()["id"]
        page_url = resp.json()["url"]
        print(f"   ✅ Notion board: {page_url}")
        return page_id
    else:
        print(f"   ❌ Notion board failed: {resp.text}")
        return ""


def create_notion_page(parent_id: str, title: str, content: str) -> str:
    """Create a child page under the board. Returns page URL."""
    if not parent_id:
        return ""

    # Notion blocks max 2000 chars each
    chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
    text_blocks = [{
        "object": "block",
        "type":   "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": chunk}}]
        }
    } for chunk in chunks]

    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}
        },
        "children": [
            {
                "object": "block",
                "type":   "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                }
            },
            *text_blocks
        ]
    }

    resp = requests.post(f"{NOTION_API_BASE}/pages", headers=NOTION_HEADERS, json=payload)
    if resp.status_code == 200:
        url = resp.json()["url"]
        print(f"   📄 Notion page: {title}")
        return url
    else:
        print(f"   ❌ Notion page failed '{title}': {resp.text}")
        return ""


# ══════════════════════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════════════════════

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import cm
from reportlab.lib           import colors
from reportlab.platypus      import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, Table, TableStyle
)
from reportlab.lib.enums     import TA_CENTER


def markdown_to_flowables(text: str, body_style, heading_style) -> list:
    """
    Convert markdown text to a list of ReportLab flowables.
    Handles: **bold**, # headings, * and - bullet lists, numbered lists, plain paragraphs.
    """
    import re
    flowables = []

    def render_inline(line: str) -> str:
        """Convert inline markdown (**bold**, *italic*) to ReportLab XML tags."""
        # Escape XML special chars first (except we handle & already)
        line = line.replace("&", "&amp;")
        # Bold: **text** or __text__
        line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
        line = re.sub(r'__(.+?)__',     r'<b>\1</b>', line)
        # Italic: *text* or _text_ (single, not double)
        line = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', line)
        line = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)',       r'<i>\1</i>', line)
        return line

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip empty lines
        if not line.strip():
            flowables.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Headings: ### ## #
        heading_match = re.match(r'^(#{1,3})\s+(.*)', line)
        if heading_match:
            flowables.append(Paragraph(render_inline(heading_match.group(2)), heading_style))
            i += 1
            continue

        # Numbered section headings like "1. Executive Summary" or "**1. Title**"
        numbered_heading = re.match(r'^\*{0,2}(\d+)\.\s+([A-Z][^*\n]{3,})\*{0,2}$', line)
        if numbered_heading:
            label = f"{numbered_heading.group(1)}. {numbered_heading.group(2)}"
            flowables.append(Spacer(1, 0.15 * cm))
            flowables.append(Paragraph(f"<b>{label}</b>", body_style))
            i += 1
            continue

        # Bullet points: * or - or •
        bullet_match = re.match(r'^[\*\-•]\s+(.*)', line)
        if bullet_match:
            bullet_style = ParagraphStyle(
                "Bullet", parent=body_style,
                leftIndent=16, bulletIndent=6,
                spaceAfter=4
            )
            flowables.append(Paragraph(f"• {render_inline(bullet_match.group(1))}", bullet_style))
            i += 1
            continue

        # Numbered list items: "1. item"
        num_match = re.match(r'^(\d+)\.\s+(.*)', line)
        if num_match:
            bullet_style = ParagraphStyle(
                "Numbered", parent=body_style,
                leftIndent=16, spaceAfter=4
            )
            flowables.append(Paragraph(
                f"{num_match.group(1)}. {render_inline(num_match.group(2))}",
                bullet_style
            ))
            i += 1
            continue

        # Markdown table — collect all consecutive | lines
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].rstrip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1

            # Parse rows, skip separator rows (---|---)
            rows = []
            for tl in table_lines:
                # Separator row
                if re.match(r'^\|[\s\-\|:]+\|$', tl):
                    continue
                cells = [c.strip() for c in tl.strip("|").split("|")]
                rows.append(cells)

            if rows:
                # Normalize all rows to same column count
                col_count = max(len(r) for r in rows)
                for r in rows:
                    while len(r) < col_count:
                        r.append("")

                # Build cell content with inline markdown rendered
                table_data = [
                    [Paragraph(render_inline(cell), body_style) for cell in row]
                    for row in rows
                ]

                col_width = (A4[0] - 4 * cm) / col_count
                tbl = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
                tbl.setStyle(TableStyle([
                    # Header row
                    ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
                    ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
                    ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
                    ("FONTSIZE",     (0, 0), (-1, 0),  9),
                    # Body rows
                    ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE",     (0, 1), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f5f5"), colors.white]),
                    # Grid
                    ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING",   (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
                    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]))
                flowables.append(Spacer(1, 0.2 * cm))
                flowables.append(tbl)
                flowables.append(Spacer(1, 0.3 * cm))
            continue

        # Plain paragraph
        flowables.append(Paragraph(render_inline(line), body_style))
        i += 1

    return flowables


def generate_pdf(board_data: dict, output_path: str = "board_report.pdf") -> str:
    """
    Generate structured PDF board report.
    board_data keys:
      idea, date, executive_summary,
      sections: list[{title, content}],
      revision_log: list[{agent, revisions}]
    """
    doc    = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BoardTitle", parent=styles["Title"],
        fontSize=24, textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=12, alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        "BoardSubtitle", parent=styles["Normal"],
        fontSize=12, textColor=colors.HexColor("#555555"),
        spaceAfter=6, alignment=TA_CENTER
    )
    section_style = ParagraphStyle(
        "SectionTitle", parent=styles["Heading1"],
        fontSize=16, textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=20, spaceAfter=10
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=16,
        textColor=colors.HexColor("#333333"), spaceAfter=8
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER
    )

    story = []

    # Cover
    story.append(Spacer(1, 4*cm))
    story.append(Paragraph("BOARD OF DIRECTORS", subtitle_style))
    story.append(Paragraph("STRATEGIC ANALYSIS REPORT", title_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(board_data.get("idea", "Business Idea"), subtitle_style))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"Generated: {board_data.get('date', datetime.now().strftime('%Y-%m-%d'))}", footer_style))
    story.append(Paragraph("Powered by Plex Hedge AI Board System", footer_style))
    story.append(PageBreak())

    # Executive Summary
    story.append(Paragraph("Executive Summary", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.3*cm))
    story.extend(markdown_to_flowables(
        board_data.get("executive_summary", ""), body_style, section_style
    ))
    story.append(PageBreak())

    # Department Sections
    for section in board_data.get("sections", []):
        story.append(Paragraph(section["title"], section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 0.3*cm))
        story.extend(markdown_to_flowables(
            section["content"], body_style, section_style
        ))
        story.append(PageBreak())

    # Revision Log
    if board_data.get("revision_log"):
        story.append(Paragraph("Appendix — Revision Log", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 0.3*cm))
        for entry in board_data["revision_log"]:
            story.append(Paragraph(
                f"<b>{entry['agent']}</b>: {entry['revisions']} revision(s)",
                body_style
            ))

    doc.build(story)
    print(f"   ✅ PDF saved: {output_path}")
    return output_path
