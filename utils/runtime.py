"""Truthful runtime outcome checks."""

from __future__ import annotations

from typing import Any

AGENTS = ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm")
FALLBACK_MARKERS = (
    "analysis unavailable due to a temporary ai service error",
    "reaction unavailable",
    "task assignment unavailable",
    "final ceo synthesis unavailable",
)


def assess_run(state: dict[str, Any], *, require_outputs: bool = False) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for agent in AGENTS:
        execution_error = str(state.get(f"{agent}_execution_error", "")).strip()
        if execution_error:
            errors.append({"stage": agent, "message": execution_error})

    scheduler_status = state.get("scheduler_status", {}) or {}
    for agent in AGENTS:
        if scheduler_status.get(agent) != "passed":
            errors.append({"stage": "scheduler", "message": f"Agent '{agent}' ended with status '{scheduler_status.get(agent, 'missing')}'."})

    for key, value in state.items():
        if isinstance(value, str) and any(marker in value.lower() for marker in FALLBACK_MARKERS):
            errors.append({"stage": "llm", "message": f"Fallback response detected in '{key}'."})

    if not str(state.get("final_board_report", "")).strip():
        errors.append({"stage": "synthesis", "message": "Final CEO board report is empty."})

    for item in state.get("pipeline_errors", []) or []:
        errors.append({"stage": str(item.get("stage", "pipeline")), "message": str(item.get("message", "Pipeline stage failed."))})
    for item in state.get("output_errors", []) or []:
        errors.append({"stage": str(item.get("stage", "output")), "message": str(item.get("message", "Output stage failed."))})

    if not state.get("notion_board_url"):
        warnings.append({"stage": "notion", "message": "No Notion board URL was produced."})
    if not state.get("pdf_path"):
        warnings.append({"stage": "pdf", "message": "No PDF path was produced."})

    if require_outputs:
        if not state.get("notion_board_url"):
            errors.append({"stage": "notion", "message": "Credentialed integration run requires a Notion board URL."})
        if not state.get("pdf_path"):
            errors.append({"stage": "pdf", "message": "Credentialed integration run requires a generated PDF."})

    status = "failed" if errors else ("degraded" if warnings else "success")
    return {"status": status, "success": status == "success", "errors": errors, "warnings": warnings}
