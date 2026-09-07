from __future__ import annotations

from utils.metrics import build_baseline_metrics


def test_baseline_evaluation_contract_has_all_required_dimensions() -> None:
    metrics = build_baseline_metrics(
        {
            "pipeline_errors": [],
            "final_board_report": "Recommendation",
            "phase2_calculations": {},
            "provenance_validation": {"valid": True},
            "provenance_ledger": {"summary": {"claims": 0, "sourced_claims": 0, "derived_claims": 0}},
            "deterministic_contradictions": [],
            "contradiction_adjudication": {"status": "NOT_RUN"},
            "pdf_path": "report.pdf",
            "notion_board_url": "",
            "consistency_status": "PASS",
        },
        100.0,
    )

    assert set(("decision_correctness", "calculation_correctness", "provenance_completeness", "contradiction_detection", "llm_cost")) <= metrics.keys()
    assert metrics["run"]["pipeline_latency_ms"] == 100.0
    assert metrics["outputs"]["pdf_present"] is True
    assert metrics["quality_gates"]["runtime_assessment"] == "passed"
