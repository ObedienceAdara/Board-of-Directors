"""Notion API integration."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
NOTION_ENABLED = os.getenv("NOTION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def create_notion_board(title: str) -> str:
    if not NOTION_ENABLED or not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return ""
    payload: dict[str, Any] = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {"Name": {"title": [{"text": {"content": title[:2000]}}]}},
        "children": [
            {"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": title[:2000]}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}}]}},
        ],
    }
    response = requests.post(f"{NOTION_API_BASE}/pages", headers=_headers(), json=payload, timeout=30)
    if response.status_code == 200:
        data = response.json()
        return str(data.get("id", ""))
    raise RuntimeError(f"Notion board creation failed ({response.status_code}): {response.text[:500]}")


def create_notion_page(parent_id: str, title: str, content: str) -> str:
    if not NOTION_ENABLED or not parent_id:
        return ""
    chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)] or [""]
    blocks = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": title[:2000]}}]}}
    ]
    blocks.extend(
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}}
        for chunk in chunks
    )
    payload: dict[str, Any] = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title[:2000]}}]}},
        "children": blocks,
    }
    response = requests.post(f"{NOTION_API_BASE}/pages", headers=_headers(), json=payload, timeout=30)
    if response.status_code == 200:
        return str(response.json().get("url", ""))
    raise RuntimeError(f"Notion page creation failed for '{title}' ({response.status_code}): {response.text[:500]}")
