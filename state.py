"""Shared state for the v3 formal-analysis board."""

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
    # Input
    brief: dict[str, Any]

    # Tier 0 panel
    researcher_panel: str
    cfo_panel: str
    cto_panel: str
    cmo_panel: str
    coo_panel: str
    head_of_sales_panel: str
    pm_panel: str
    ceo_task_assignments: str

    # Human-readable department reports
    research_report: str
    financial_plan: str
    tech_plan: str
    marketing_plan: str
    operations_plan: str
    sales_strategy: str
    product_roadmap: str

    # Machine-readable formal analyses and deterministic validation results
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

    # Revision tracking
    researcher_revisions: int
    researcher_passed: bool
    researcher_feedback: str
    cfo_revisions: int
    cfo_passed: bool
    cfo_feedback: str
    cto_revisions: int
    cto_passed: bool
    cto_feedback: str
    cmo_revisions: int
    cmo_passed: bool
    cmo_feedback: str
    coo_revisions: int
    coo_passed: bool
    coo_feedback: str
    head_of_sales_revisions: int
    head_of_sales_passed: bool
    head_of_sales_feedback: str
    pm_revisions: int
    pm_passed: bool
    pm_feedback: str

    # Dynamic scheduler observability
    scheduler_status: dict[str, str]
    scheduler_events: list[dict[str, Any]]
    revision_summary: dict[str, int]

    # Formal global consistency stage
    formal_snapshot: dict[str, Any]
    deterministic_contradictions: list[dict[str, Any]]
    contradiction_adjudication: dict[str, Any]
    consistency_status: str

    # Final output
    final_board_report: str
    notion_board_url: str
    pdf_path: str
