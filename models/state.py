"""Shared state models for the formal-analysis board."""

from __future__ import annotations

from typing import Any, TypedDict


class BusinessBrief(TypedDict, total=False):
    idea: str
    target_market: str
    budget: str
    founder_background: str
    timeline: str
    constraints: str


EVALUATED_AGENTS = [
    "researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"
]


class BoardState(TypedDict, total=False):
    brief: dict[str, Any]

    researcher_panel: str
    cfo_panel: str
    cto_panel: str
    cmo_panel: str
    coo_panel: str
    head_of_sales_panel: str
    pm_panel: str
    ceo_task_assignments: str

    research_report: str
    financial_plan: str
    tech_plan: str
    marketing_plan: str
    operations_plan: str
    sales_strategy: str
    product_roadmap: str

    researcher_formal: dict[str, Any]
    cfo_formal: dict[str, Any]
    cto_formal: dict[str, Any]
    cmo_formal: dict[str, Any]
    coo_formal: dict[str, Any]
    head_of_sales_formal: dict[str, Any]
    pm_formal: dict[str, Any]

    researcher_validation: dict[str, Any]
    cfo_validation: dict[str, Any]
    cto_validation: dict[str, Any]
    cmo_validation: dict[str, Any]
    coo_validation: dict[str, Any]
    head_of_sales_validation: dict[str, Any]
    pm_validation: dict[str, Any]

    researcher_revisions: int
    researcher_passed: bool
    researcher_feedback: str
    researcher_evaluation: dict[str, Any]
    researcher_execution_error: str
    researcher_forced_accept: bool
    cfo_revisions: int
    cfo_passed: bool
    cfo_feedback: str
    cfo_evaluation: dict[str, Any]
    cfo_execution_error: str
    cfo_forced_accept: bool
    cto_revisions: int
    cto_passed: bool
    cto_feedback: str
    cto_evaluation: dict[str, Any]
    cto_execution_error: str
    cto_forced_accept: bool
    cmo_revisions: int
    cmo_passed: bool
    cmo_feedback: str
    cmo_evaluation: dict[str, Any]
    cmo_execution_error: str
    cmo_forced_accept: bool
    coo_revisions: int
    coo_passed: bool
    coo_feedback: str
    coo_evaluation: dict[str, Any]
    coo_execution_error: str
    coo_forced_accept: bool
    head_of_sales_revisions: int
    head_of_sales_passed: bool
    head_of_sales_feedback: str
    head_of_sales_evaluation: dict[str, Any]
    head_of_sales_execution_error: str
    head_of_sales_forced_accept: bool
    pm_revisions: int
    pm_passed: bool
    pm_feedback: str
    pm_evaluation: dict[str, Any]
    pm_execution_error: str
    pm_forced_accept: bool

    scheduler_status: dict[str, str]
    scheduler_events: list[dict[str, Any]]
    revision_summary: dict[str, int]
    formal_snapshot: dict[str, Any]
    deterministic_contradictions: list[dict[str, Any]]
    contradiction_adjudication: dict[str, Any]
    consistency_status: str
    provenance_ledger: dict[str, Any]
    provenance_validation: dict[str, Any]
    provenance_summary: dict[str, Any]
    final_board_report: str
    notion_board_url: str
    pdf_path: str
    pipeline_errors: list[dict[str, str]]
    output_errors: list[dict[str, str]]
