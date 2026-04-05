"""
state.py — Shared state across all agents in the board.
Every agent reads from and writes to this single object.
"""

from typing import TypedDict


class BusinessBrief(TypedDict):
    idea:               str
    target_market:      str
    budget:             str
    founder_background: str
    timeline:           str
    constraints:        str


class BoardState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    brief:                dict

    # ── Phase 1 ────────────────────────────────────────────
    research_report:      str

    # ── Phase 2 ────────────────────────────────────────────
    financial_plan:       str
    tech_plan:            str
    marketing_plan:       str

    # ── Phase 3 ────────────────────────────────────────────
    operations_plan:      str
    sales_strategy:       str
    product_roadmap:      str

    # ── CEO ────────────────────────────────────────────────
    ceo_task_assignments: str
    final_board_report:   str

    # ── Revision tracking ──────────────────────────────────
    evaluations:          dict   # { agent_name: { passed, feedback, iterations } }
    revision_counts:      dict   # { agent_name: int }

    # ── Outputs ────────────────────────────────────────────
    notion_board_url:     str
    pdf_path:             str

    # ── Flow control ───────────────────────────────────────
    current_phase:        str
    needs_revision:       list
