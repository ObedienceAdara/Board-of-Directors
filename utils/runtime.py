"""Truthful runtime outcome checks with root-cause diagnostics."""

from __future__ import annotations

from typing import Any

AGENTS = ("researcher", "cfo", "cto", "cmo", "head_of_sales", "coo", "pm")
FALLBACK_MARKERS = ("analysis unavailable due to a temporary ai service error", "reaction unavailable", "task assignment unavailable", "final ceo synthesis unavailable")


def _append_unique(errors: list[dict[str, str]], stage: str, message: str) -> None:
    item = {"stage": stage, "message": message}
    if item not in errors:
        errors.append(item)


def assess_run(state: dict[str, Any], *, require_outputs: bool = False) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    scheduler_status = state.get("scheduler_status", {}) or {}
    failed = list(state.get("scheduler_failed_agents", []) or [])
    blocked = list(state.get("scheduler_blocked_agents", []) or [])
    for agent in AGENTS:
        execution_error = str(state.get(f"{agent}_execution_error", "")).strip()
        if execution_error:
            _append_unique(errors, agent, execution_error)
    for agent in failed:
        _append_unique(errors, "scheduler", f"Agent '{agent}' failed after its allowed execution/revision attempts.")
    for agent in blocked:
        _append_unique(warnings, "scheduler", f"Agent '{agent}' was blocked by an upstream failure; see failed agent(s) above.")
    if isinstance(scheduler_status, dict) and not scheduler_status:
        _append_unique(errors, "scheduler", "Scheduler did not produce a status map.")

    for key, value in state.items():
        if isinstance(value, str) and any(marker in value.lower() for marker in FALLBACK_MARKERS):
            _append_unique(errors, "llm", f"Fallback response detected in '{key}'.")
        if key.endswith("_panel_error") and str(value).strip():
            _append_unique(warnings, "panel", f"{key}: {str(value)[:500]}")

    if not str(state.get("final_board_report", "")).strip():
        _append_unique(errors, "synthesis", "Final CEO board report is empty.")

    for item in state.get("pipeline_errors", []) or []:
        if isinstance(item, dict):
            _append_unique(errors, str(item.get("stage", "pipeline")), str(item.get("message", "Pipeline stage failed.")))
    for item in state.get("output_errors", []) or []:
        if isinstance(item, dict):
            _append_unique(errors, str(item.get("stage", "output")), str(item.get("message", "Output stage failed.")))

    if not state.get("notion_board_url"):
        warnings.append({"stage": "notion", "message": "No Notion board URL was produced."})
    if not state.get("pdf_path"):
        warnings.append({"stage": "pdf", "message": "No PDF path was produced."})
    if state.get("panel_errors"):
        _append_unique(warnings, "panel", f"{len(state['panel_errors'])} panel reaction(s) failed; formal analysis remains the authoritative quality gate.")

    if require_outputs:
        if not state.get("notion_board_url"):
            _append_unique(errors, "notion", "Credentialed integration run requires a Notion board URL.")
        if not state.get("pdf_path"):
            _append_unique(errors, "pdf", "Credentialed integration run requires a generated PDF.")

    status = "failed" if errors else ("degraded" if warnings else "success")
    return {"status": status, "success": status == "success", "errors": errors, "warnings": warnings}
