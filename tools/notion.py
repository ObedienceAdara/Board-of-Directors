"""Notion API integration using the current data-source page contract."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"


def _config() -> tuple[str, str, str, bool]:
    key = os.getenv("NOTION_API_KEY", "").strip()
    database_id = os.getenv("NOTION_DATABASE_ID", "").strip()
    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID", "").strip()
    enabled = os.getenv("NOTION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return key, database_id, data_source_id, enabled


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION}


def _request(method: str, path: str, api_key: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(method, f"{NOTION_API_BASE}{path}", headers=_headers(api_key), timeout=30, **kwargs)
    if not response.ok:
        raise RuntimeError(f"Notion API {method} {path} failed ({response.status_code}): {response.text[:800]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Notion API {method} {path} returned a non-object response")
    return data


def _resolve_data_source(api_key: str, database_id: str, configured_data_source_id: str = "") -> tuple[str, str]:
    if configured_data_source_id:
        source = _request("GET", f"/data_sources/{configured_data_source_id}", api_key)
        properties = source.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        title_property = next((name for name, spec in properties.items() if isinstance(spec, dict) and spec.get("type") == "title"), "Name")
        return configured_data_source_id, title_property
    database = _request("GET", f"/databases/{database_id}", api_key)
    sources = database.get("data_sources", [])
    if not isinstance(sources, list) or not sources:
        return database_id, "Name"
    first = sources[0] if isinstance(sources[0], dict) else {}
    data_source_id = str(first.get("id", "")).strip()
    if not data_source_id:
        raise RuntimeError("Notion database returned no usable data source ID")
    return _resolve_data_source(api_key, database_id, data_source_id)


def create_notion_board(title: str) -> str:
    api_key, database_id, configured_data_source_id, enabled = _config()
    if not enabled or not api_key or (not database_id and not configured_data_source_id):
        return ""
    data_source_id, title_property = _resolve_data_source(api_key, database_id, configured_data_source_id)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload: dict[str, Any] = {
        "parent": {"data_source_id": data_source_id},
        "properties": {title_property: {"title": [{"text": {"content": title[:2000]}}]}},
        "children": [
            {"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": title[:2000]}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Generated: {now}"}}]}},
        ],
    }
    return str(_request("POST", "/pages", api_key, json=payload).get("id", ""))


def create_notion_page(parent_id: str, title: str, content: str) -> str:
    api_key, _, _, enabled = _config()
    if not enabled or not api_key or not parent_id:
        return ""
    chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)] or [""]
    blocks: list[dict[str, Any]] = [{"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": title[:2000]}}]}}]
    blocks.extend({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}} for chunk in chunks)
    payload: dict[str, Any] = {"parent": {"page_id": parent_id}, "properties": {"title": {"title": [{"text": {"content": title[:2000]}}]}}, "children": blocks}
    return str(_request("POST", "/pages", api_key, json=payload).get("url", ""))
