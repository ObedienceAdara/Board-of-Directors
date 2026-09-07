"""Baseline observability metrics for the stable deliberative pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass
class PipelineTimer:
    """Small standard-library timer used to measure one pipeline execution."""

    started_at: float = field(default_factory=perf_counter)

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self.started_at) * 1000.0, 3)


def _is_nonempty_mapping(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def calculation_correctness(state: dict[str, Any]) -> dict[str, Any]:
    """Score structural invariants of deterministic Phase 2 outputs.

    This is deliberately not presented as business-decision correctness. It verifies
    that deterministic model outputs remain internally coherent and complete.
    """

    calculations = state.get("phase2_calculations")
    if not isinstance(calculations, dict) or not calculations:
        return {"status": "not_scored", "score": None, "checks": [], "reason": "No Phase 2 calculation results were produced."}

    checks: list[dict[str, Any]] = []

    finance = calculations.get("finance", {})
    if isinstance(finance, dict):
        months = finance.get("months")
        checks.append({"name": "finance_has_12_months", "passed": isinstance(months, list) and len(months) == 12})
        if isinstance(months, list) and months:
            revenue = sum(_safe_float(row.get("revenue")) or 0.0 for row in months if isinstance(row, dict))
            reported = _safe_float(finance.get("12_month_revenue"))
            checks.append({"name": "finance_revenue_total_reconciles", "passed": reported is not None and abs(revenue - reported) <= 0.02})

    sales = calculations.get("sales", {})
    if isinstance(sales, dict):
        months = sales.get("months")
        checks.append({"name": "sales_has_12_months", "passed": isinstance(months, list) and len(months) == 12})
        expected_yield = None
        inputs = state.get("head_of_sales_formal", {})
        if isinstance(inputs, dict):
            # The detailed funnel is already calculated by the deterministic engine;
            # this check only verifies that a finite yield is surfaced.
            expected_yield = _safe_float(sales.get("funnel_yield"))
        checks.append({"name": "sales_funnel_yield_is_finite", "passed": expected_yield is not None and expected_yield >= 0.0})

    operations = calculations.get("operations", {})
    if isinstance(operations, dict):
        months = operations.get("months")
        checks.append({"name": "operations_has_12_months", "passed": isinstance(months, list) and len(months) == 12})
        payroll = _safe_float(operations.get("annual_payroll_run_rate"))
        checks.append({"name": "operations_payroll_run_rate_nonnegative", "passed": payroll is not None and payroll >= 0.0})

    technical = calculations.get("technical", {})
    if isinstance(technical, dict):
        duration = _safe_float(technical.get("delivery_duration_weeks"))
        checks.append({"name": "technical_delivery_duration_valid", "passed": duration is not None and duration >= 0.0})

    product = calculations.get("product", {})
    if isinstance(product, dict):
        features = product.get("features")
        scores = [_safe_float(item.get("priority_score")) for item in features if isinstance(item, dict)] if isinstance(features, list) else []
        scores = [score for score in scores if score is not None]
        checks.append({"name": "product_priority_scores_present", "passed": isinstance(features, list) and len(scores) == len(features)})

    scored = [item["passed"] for item in checks]
    score = round(sum(1 for passed in scored if passed) / len(scored), 4) if scored else None
    return {"status": "scored" if checks else "not_scored", "score": score, "checks": checks}


def provenance_completeness(state: dict[str, Any]) -> dict[str, Any]:
    validation = state.get("provenance_validation")
    ledger = state.get("provenance_ledger")
    if not isinstance(validation, dict) or not isinstance(ledger, dict):
        return {"status": "not_scored", "score": None, "reason": "Provenance output was not produced."}

    summary = ledger.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    claims = int(summary.get("claims", 0) or 0)
    sourced = int(summary.get("sourced_claims", 0) or 0)
    derived = int(summary.get("derived_claims", 0) or 0)
    return {
        "status": "scored",
        "score": round(sourced / claims, 4) if claims else None,
        "claims": claims,
        "sourced_claims": sourced,
        "derived_claims": derived,
        "validation_valid": bool(validation.get("valid", False)),
    }


def contradiction_detection(state: dict[str, Any]) -> dict[str, Any]:
    contradictions = state.get("deterministic_contradictions", [])
    adjudication = state.get("contradiction_adjudication", {})
    issues = adjudication.get("issues", []) if isinstance(adjudication, dict) else []
    return {
        "status": "scored",
        "detected": len(contradictions) if isinstance(contradictions, list) else 0,
        "adjudicated": len(issues) if isinstance(issues, list) else 0,
        "adjudication_status": str(adjudication.get("status", "NOT_RUN")) if isinstance(adjudication, dict) else "NOT_RUN",
    }


def build_baseline_metrics(state: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    """Build a truthful baseline metrics envelope for one board run."""

    errors = state.get("pipeline_errors", [])
    runtime_failed = bool(errors)
    report_present = bool(str(state.get("final_board_report", "")).strip())

    decision_correctness = {
        "status": "not_scored",
        "score": None,
        "reason": "No labeled ground-truth decision outcome is available in the current deliberative runtime.",
    }
    llm_cost = {
        "status": "not_available",
        "usd": None,
        "reason": "The current provider adapter does not expose normalized token/cost telemetry to the pipeline state.",
    }

    return {
        "schema_version": "1.0",
        "run": {
            "status": "failed" if runtime_failed else "completed",
            "success": not runtime_failed and report_present,
            "pipeline_latency_ms": round(elapsed_ms, 3),
            "failure_rate": 1.0 if runtime_failed else 0.0,
        },
        "decision_correctness": decision_correctness,
        "calculation_correctness": calculation_correctness(state),
        "provenance_completeness": provenance_completeness(state),
        "contradiction_detection": contradiction_detection(state),
        "llm_cost": llm_cost,
        "outputs": {
            "final_report_present": report_present,
            "pdf_present": bool(state.get("pdf_path")),
            "notion_present": bool(state.get("notion_board_url")),
        },
        "quality_gates": {
            "runtime_assessment": "failed" if runtime_failed else "passed",
            "provenance_validation": bool((state.get("provenance_validation") or {}).get("valid", False)) if isinstance(state.get("provenance_validation"), dict) else False,
            "consistency_status": state.get("consistency_status", "NOT_RUN"),
        },
    }
