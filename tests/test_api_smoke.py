from __future__ import annotations

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_api_root_starts_cleanly():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["version"] == "3.0.0"


def test_board_meeting_route_is_registered(monkeypatch):
    monkeypatch.setattr(
        main,
        "run_board_meeting",
        lambda _brief: {
            "status": "success",
            "success": True,
            "final_report": "mock report",
            "notion_board_url": "",
            "pdf_path": "",
            "revision_summary": {},
            "consistency_status": "CONSISTENT",
            "deterministic_contradictions": [],
            "contradiction_adjudication": {},
            "formal_snapshot": {},
            "scheduler_status": {},
            "scheduler_events": [],
            "errors": [],
            "warnings": [],
        },
    )
    response = client.post(
        "/board-meeting/invoke",
        json={"input": {"brief": {"idea": "API smoke test"}}},
    )
    assert response.status_code == 200
    assert response.json()["output"]["status"] == "success"
