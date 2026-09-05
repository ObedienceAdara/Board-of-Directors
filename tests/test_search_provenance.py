"""Tests for structured search retrieval provenance."""

from __future__ import annotations

from tools import search


class _FakeSearchTool:
    def __init__(self, payload):
        self.payload = payload

    def invoke(self, _query):
        return self.payload


def test_search_with_provenance_records_tool_metadata(monkeypatch):
    payload = {"results": [{
        "url": "https://example.com/report",
        "title": "Example Report",
        "content": "Market size is $420M.",
        "score": 0.91,
        "published_at": "2026-08-01",
    }]}
    monkeypatch.setattr(search, "get_search_tool", lambda max_results=5: _FakeSearchTool(payload))

    result = search.search_with_provenance("market size 2026")

    assert result["error"] is None
    assert result["results"] == [{
        "url": "https://example.com/report",
        "title": "Example Report",
        "publisher": None,
        "query": "market size 2026",
        "rank": 1,
        "retrieved_at": result["retrieved_at"],
        "provider": "tavily",
        "score": 0.91,
        "published_at": "2026-08-01",
    }]
    assert "420M" in result["content"]


def test_multi_search_flattens_observed_trace(monkeypatch):
    responses = [
        {"results": [{"url": "https://example.com/a", "title": "A", "content": "A"}]},
        {"results": [{"url": "https://example.com/b", "title": "B", "content": "B"}]},
    ]
    tools = [_FakeSearchTool(payload) for payload in responses]
    monkeypatch.setattr(search, "get_search_tool", lambda max_results=5: tools.pop(0))

    result = search.multi_search_with_provenance(["query a", "query b"])

    assert [item["url"] for item in result["trace"]] == ["https://example.com/a", "https://example.com/b"]
    assert result["searches"][0]["query"] == "query a"
    assert result["searches"][1]["query"] == "query b"
