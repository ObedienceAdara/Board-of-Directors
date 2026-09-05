from __future__ import annotations

from pathlib import Path

import main
from app import pipeline


BRIEF = {
    "idea": "Mocked board test product",
    "target_market": "Small businesses",
    "budget": "$10000",
    "founder_background": "Technical founder",
    "timeline": "MVP in 12 weeks",
    "constraints": "Bootstrapped",
}


def test_run_board_meeting_mocked_full_pipeline(monkeypatch, tmp_path):
    agents = ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]
    reports = {
        "researcher": "research_report",
        "cfo": "financial_plan",
        "cto": "tech_plan",
        "cmo": "marketing_plan",
        "coo": "operations_plan",
        "head_of_sales": "sales_strategy",
        "pm": "product_roadmap",
    }

    def fake_panel(_state):
        return {f"{agent}_panel": f"{agent} panel reaction" for agent in agents}

    def fake_assign(_state):
        return {"ceo_task_assignments": "{}"}

    def fake_formal(state):
        for agent, key in reports.items():
            state[key] = f"{agent} report"
            state[f"{agent}_formal"] = {"report": f"{agent} report"}
            state[f"{agent}_validation"] = {"errors": [], "warnings": [], "claims": []}
            state[f"{agent}_passed"] = True
            state[f"{agent}_revisions"] = 1
        state["scheduler_status"] = {agent: "passed" for agent in agents}
        state["revision_summary"] = {agent: 1 for agent in agents}
        state["scheduler_events"] = []
        return state

    def fake_consistency(_state):
        return {"formal_snapshot": {"cross_domain_contradictions": []}, "deterministic_contradictions": []}

    def fake_adjudication(_state):
        return {
            "contradiction_adjudication": {"overall_status": "CONSISTENT", "issues": []},
            "consistency_status": "CONSISTENT",
        }

    def fake_synthesis(_state):
        return {"final_board_report": "GO — mocked board recommendation."}

    def fake_output(state):
        state["notion_board_url"] = "https://notion.so/mockboardid"
        Path("mock-board-report.pdf").write_bytes(b"%PDF-1.4 mocked report")
        state["pdf_path"] = "mock-board-report.pdf"
        return state

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "run_panel", fake_panel)
    monkeypatch.setattr(pipeline, "ceo_assign_tasks", fake_assign)
    monkeypatch.setattr(pipeline, "run_formal_board", fake_formal)
    monkeypatch.setattr(pipeline, "_deterministic_consistency", fake_consistency)
    monkeypatch.setattr(pipeline, "ceo_adjudicate_contradictions", fake_adjudication)
    monkeypatch.setattr(pipeline, "ceo_assemble_report", fake_synthesis)
    monkeypatch.setattr(pipeline, "node_output", fake_output)
    monkeypatch.setattr(main, "run_board_meeting", pipeline.run_board_meeting)
    pipeline.board_graph = pipeline.build_board_graph()

    result = main.run_board_meeting(BRIEF)

    assert result["status"] == "success"
    assert result["success"] is True
    assert result["final_report"].startswith("GO")
    assert result["scheduler_status"] == {agent: "passed" for agent in agents}
    assert result["notion_board_url"] == "https://notion.so/mockboardid"
    assert Path(result["pdf_path"]).exists()
    assert result["errors"] == []
