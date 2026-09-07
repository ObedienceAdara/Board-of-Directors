from __future__ import annotations

from utils.metrics import build_baseline_metrics


def test_baseline_metrics_marks_unknown_dimensions_explicitly() -> None:
    result = build_baseline_metrics(
        {
            "pipeline_errors": [],
            "final_board_report": "Recommendation",
            "phase2_calculations": {},
            "provenance_validation": {},
            "deterministic_contradictions": [],
            "contradiction_adjudication": {},
            "pdf_path": "",
            "notion_board_url": "",
            "consistency_status": "NOT_RUN",
        },
        12.5,
    )

    assert result["schema_version"] == "1.0"
    assert result["run"]["success"] is True
    assert result["run"]["pipeline_latency_ms"] == 12.5
    assert result["decision_correctness"]["status"] == "not_scored"
    assert result["llm_cost"]["status"] == "not_available"
    assert result["calculation_correctness"]["status"] == "not_scored"


def test_baseline_metrics_reports_failed_run_without_fake_quality_score() -> None:
    result = build_baseline_metrics(
        {
            "pipeline_errors": [{"stage": "formal_scheduler", "message": "failed"}],
            "final_board_report": "",
            "phase2_calculations": {},
            "provenance_validation": {},
            "deterministic_contradictions": [],
            "contradiction_adjudication": {},
            "pdf_path": "",
            "notion_board_url": "",
            "consistency_status": "NOT_RUN",
        },
        25.0,
    )

    assert result["run"]["success"] is False
    assert result["run"]["failure_rate"] == 1.0
    assert result["run"]["status"] == "failed"
