from __future__ import annotations

from runtime import assess_run
from scheduler import DynamicReadinessScheduler

AGENTS = ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]


def good_state():
    return {
        "scheduler_status": {agent: "passed" for agent in AGENTS},
        "scheduler_failed_agents": [],
        "scheduler_blocked_agents": [],
        "final_board_report": "GO — complete mock report",
        "notion_board_url": "https://notion.so/mock",
        "pdf_path": "report.pdf",
        "output_errors": [],
    }


def test_missing_agent_status_fails_run():
    state = good_state(); state["scheduler_status"]["cfo"] = "failed"; state["scheduler_failed_agents"] = ["cfo"]
    result = assess_run(state)
    assert result["status"] == "failed"
    assert result["success"] is False
    assert any("cfo" in error["message"] for error in result["errors"])


def test_output_error_fails_run():
    state = good_state(); state["output_errors"] = [{"stage": "notion", "message": "HTTP 401"}]
    result = assess_run(state)
    assert result["status"] == "failed"
    assert any(error["stage"] == "notion" for error in result["errors"])


def test_optional_outputs_are_degraded_but_required_outputs_fail(monkeypatch):
    state = good_state(); state["notion_board_url"] = ""; state["pdf_path"] = ""; monkeypatch.setenv("NOTION_ENABLED", "false")
    degraded = assess_run(state)
    assert degraded["status"] == "degraded"
    assert degraded["success"] is False
    required = assess_run(state, require_outputs=True)
    assert required["status"] == "failed"
    assert {error["stage"] for error in required["errors"]} >= {"notion", "pdf"}


def test_blocked_agents_are_warnings_not_root_errors():
    state = good_state()
    state["scheduler_failed_agents"] = ["researcher"]
    state["scheduler_blocked_agents"] = [agent for agent in AGENTS if agent != "researcher"]
    state["scheduler_status"]["researcher"] = "failed"
    for agent in AGENTS:
        if agent != "researcher": state["scheduler_status"][agent] = "blocked"
    result = assess_run(state)
    assert result["status"] == "failed"
    assert any(error["stage"] == "scheduler" and "researcher" in error["message"] for error in result["errors"])
    assert all(error["stage"] != "scheduler" or "blocked" not in error["message"] for error in result["errors"])
    assert any(warning["stage"] == "scheduler" and "blocked" in warning["message"] for warning in result["warnings"])


def test_scheduler_never_reports_execution_failure_as_passed():
    def runner(agent, _state):
        if agent == "researcher":
            raise RuntimeError("simulated provider outage")
        return {f"{agent}_formal": {"ok": True}}
    def evaluator(_agent, _state):
        return {"passed": True, "feedback": ""}
    scheduler = DynamicReadinessScheduler(runner, evaluator, max_workers=7, max_revisions=1)
    state = scheduler.run({"brief": {"idea": "test"}})
    assert state["scheduler_status"]["researcher"] == "failed"
    assert state["scheduler_status"]["cfo"] == "blocked"
