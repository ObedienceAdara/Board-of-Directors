"""Board agent interfaces."""

from .board import (
    ceo_adjudicate_contradictions,
    ceo_assemble_report,
    ceo_assign_tasks,
    ceo_evaluate_agent,
    panel_reaction,
    run_department,
)

__all__ = [
    "ceo_adjudicate_contradictions", "ceo_assemble_report", "ceo_assign_tasks",
    "ceo_evaluate_agent", "panel_reaction", "run_department",
]
