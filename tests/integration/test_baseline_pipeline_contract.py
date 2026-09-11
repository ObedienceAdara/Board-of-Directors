from __future__ import annotations

import app.pipeline as pipeline


class _FakeGraph:
    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        state["final_board_report"] = "Deterministic control recommendation"
        state["pipeline_errors"] = []
        state["output_errors"] = []
        state["consistency_status"] = "PASS"
        state["phase2_calculations"] = {}
        state["provenance_validation"] = {"valid": True}
        state["notion_board_url"] = "https://notion.so/baseline"
        state["pdf_path"] = "baseline.pdf"
        state["scheduler_status"] = {
            "researcher": "passed", "cfo": "passed", "cto": "passed", "cmo": "passed",
            "head_of_sales": "passed", "coo": "passed", "pm": "passed",
        }
        state["scheduler_failed_agents"] = []
        state["scheduler_blocked_agents"] = []
        return state


def test_run_board_meeting_exposes_phase0_baseline_metrics(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "board_graph", _FakeGraph())

    result = pipeline.run_board_meeting({"idea": "control", "target_market": "test"})

    assert result["success"] is True
    metrics = result["baseline_metrics"]
    assert metrics["schema_version"] == "1.0"
    assert metrics["run"]["success"] is True
    assert metrics["run"]["pipeline_latency_ms"] >= 0.0
    assert metrics["decision_correctness"]["status"] == "not_scored"
    assert metrics["llm_cost"]["status"] == "not_available"
