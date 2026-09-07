from __future__ import annotations

from models import BoardState, CompanyState
from app.pipeline import initialize_state


def test_board_state_still_contains_transient_execution_contract() -> None:
    state = initialize_state({"idea": "Compatibility test"})

    assert isinstance(state["company_state"], CompanyState)
    assert state["brief"]["idea"] == "Compatibility test"
    assert state["phase2_calculations"] == {}
    assert state["provenance_ledger"] == {}
    assert state["baseline_metrics"] == {}

    typed: BoardState = state
    assert typed["company_state"].identity.name == "Compatibility test"


def test_world_state_is_not_created_from_llm_or_report_fields() -> None:
    state = initialize_state({"idea": "Compatibility test"})
    state["cfo_formal"] = {"starting_cash": 999999}
    state["final_board_report"] = "The company has $999,999 in cash."

    assert state["company_state"].finance.cash_balance is None
    assert state["company_state"].finance.last_forecast == {}
