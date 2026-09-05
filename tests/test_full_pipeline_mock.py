from __future__ import annotations

import main


BRIEF = {
    "idea": "Mocked board test product",
    "target_market": "Small businesses",
    "budget": "$10000",
    "founder_background": "Technical founder",
    "timeline": "MVP in 12 weeks",
    "constraints": "Bootstrapped",
}


def test_run_board_meeting_mocked_full_pipeline(monkeypatch):
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
            state[f"{agent}_validation"] = {"errors": [], "warnings": []}
            state[f"{agent}_passed"] = True
            state[f"{agent}_revisions"] = 1
        state["scheduler_status"] = {agent: "passed" for agent in agents}
        state["revision_summary"] = {agent: 1 for agent in agents}
        state["scheduler_events"] = []
        return state

    def fake_consistency(_state):
        return {
            "formal_snapshot": {"cross_domain_contradictions": []},
            "deterministic_contradictions": [],
        }

    def fake_adjudication(_state):
        return {
            "contradiction_adjudication": {"overall_status": "CONSISTENT", "issues": []},
            "consistency_status": "CONSISTENT",
        }

    def fake_synthesis(_state):
        return {"final_board_report": "GO — mocked board recommendation."}

    def fake_output(state):
        state["notion_board_url"] = "https://notion.so/mock"
        state["pdf_path"] = "mock-report.pdf"
        return state

    monkeypatch.setattr(main, "run_panel", fake_panel)
    monkeypatch.setattr(main, "ceo_assign_tasks", fake_assign)
    monkeypatch.setattr(main, "run_formal_board", fake_formal)
    monkeypatch.setattr(main, "adjudicate_contradictions", fake_consistency)
    monkeypatch.setattr(main, "ceo_adjudicate_contradictions", fake_adjudication)
    monkeypatch.setattr(main, "ceo_assemble_report", fake_synthesis)
    monkeypatch.setattr(main, "node_output", fake_output)

    result = main.run_board_meeting(BRIEF)

    assert result["status"] == "success"
    assert result["success"] is True
    assert result["final_report"].startswith("GO")
    assert result["scheduler_status"] == {agent: "passed" for agent in agents}
    assert result["errors"] == []
