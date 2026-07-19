"""
state.py — Shared state across all agents in the board.
Every agent reads from and writes to this single object.

v3 — flattened per-agent tracking fields
─────────────────────────────────────────
The old schema had one shared `evaluations` dict and one shared
`revision_counts` dict that every agent's eval step read-modified-wrote.
That's safe under strictly sequential execution (one write at a time),
but it breaks the moment two agents run in parallel: both branches read
the same snapshot of the shared dict, each builds its own updated copy,
and whichever one LangGraph applies second silently overwrites the
other's update — with no error, just quietly wrong revision counts.

Flattening into one key per agent per field means each parallel branch
only ever writes keys no other branch touches, so there's no write to
reconcile in the first place. Every agent gets its own three fields
instead of sharing two dicts:
"""

from typing import TypedDict


class BusinessBrief(TypedDict):
    idea:               str
    target_market:      str
    budget:             str
    founder_background: str
    timeline:           str
    constraints:        str


# Every agent that goes through CEO evaluation, in the order they first
# appear across the pipeline. Used by main.py to build routing/gating
# logic and the final revision log without repeating this list everywhere.
EVALUATED_AGENTS = [
    "researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"
]


class BoardState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    brief:                dict

    # ── Tier 0: initial panel reactions ─────────────────────
    # Quick gut-reactions from every department to the raw brief, before
    # the CEO assigns any formal tasks. Flattened per agent for the same
    # reason as everything below — each panelist only ever writes its
    # own key, so the 7-way parallel fan-out has nothing to collide on.
    researcher_panel:            str
    cfo_panel:                    str
    cto_panel:                     str
    cmo_panel:                      str
    coo_panel:                       str
    head_of_sales_panel:              str
    pm_panel:                          str

    # ── Department outputs ─────────────────────────────────
    research_report:      str
    financial_plan:        str
    tech_plan:              str
    marketing_plan:          str
    operations_plan:          str
    sales_strategy:            str
    product_roadmap:            str

    # ── CEO ────────────────────────────────────────────────
    ceo_task_assignments: str
    final_board_report:   str

    # ── Per-agent revision tracking (flattened) ─────────────
    # Each agent's own three fields — only that agent's node/eval pair
    # ever writes to them, so concurrent branches never collide.
    researcher_revisions:        int
    researcher_passed:           bool
    researcher_feedback:         str

    cfo_revisions:                int
    cfo_passed:                   bool
    cfo_feedback:                 str

    cto_revisions:                 int
    cto_passed:                    bool
    cto_feedback:                  str

    cmo_revisions:                  int
    cmo_passed:                     bool
    cmo_feedback:                   str

    coo_revisions:                   int
    coo_passed:                      bool
    coo_feedback:                    str

    head_of_sales_revisions:          int
    head_of_sales_passed:             bool
    head_of_sales_feedback:           str

    pm_revisions:                      int
    pm_passed:                         bool
    pm_feedback:                       str

    # ── Outputs ────────────────────────────────────────────
    notion_board_url:     str
    pdf_path:              str
