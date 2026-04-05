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
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
)
from reportlab.lib.enums     import TA_CENTER


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
    summary = board_data.get("executive_summary", "").replace("\n", "<br/>")
    story.append(Paragraph(summary, body_style))
    story.append(PageBreak())

    # Department Sections
    for section in board_data.get("sections", []):
        story.append(Paragraph(section["title"], section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 0.3*cm))
        content = (section["content"]
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\n", "<br/>"))
        story.append(Paragraph(content, body_style))
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
