from __future__ import annotations

from analysis.phase2 import run_phase2_calculations
from analysis_engine import validate_formal_analysis


def _state() -> dict:
    state = {
        "head_of_sales_formal": {
            "currency": "USD", "primary_price": 100, "price_period": "month", "starting_customers": 0, "annual_revenue_target": 12000,
            "monthly_traffic": [100] * 12, "qualification_rate": 0.5, "opportunity_rate": 0.5, "close_rate": 0.2, "monthly_churn_rate": 0,
        },
        "cfo_formal": {
            "currency": "USD", "starting_cash": 5000, "startup_costs": [{"name": "Setup", "amount": 500}], "cogs_per_customer": 10,
            "cogs_percent_revenue": 0, "monthly_budget_by_category": {"payroll": 0, "marketing": 0, "infrastructure": 0, "other": 0},
            "monthly_infrastructure_schedule": [0] * 12, "monthly_marketing_schedule": [0] * 12, "monthly_other_opex_schedule": [0] * 12,
            "financial_scenarios": {},
        },
        "coo_formal": {
            "currency": "USD", "headcount_plan": [{"role": "Engineer", "count": 1, "annual_salary": 1200, "start_month": 2, "ramp_months": 1, "monthly_capacity_hours": 100}],
            "productive_hours_per_employee": 120, "workload_hours_per_customer": 10, "default_ramp_months": 1,
        },
        "cto_formal": {
            "currency": "USD", "development_phases": [{"name": "Build", "weeks": 4, "dependencies": []}],
            "engineering_team": [{"role": "Engineer", "count": 1, "weekly_capacity_weeks": 1}], "schedule_buffer": 0,
            "engineering_build_cost": 0, "monthly_infrastructure_cost": 0,
        },
        "pm_formal": {"mvp_features": [{"name": "Core", "impact": 10, "effort": 2, "strategic_weight": 1, "dependency_factor": 1, "in_scope": True}], "strategic_weight": 1},
        "cmo_formal": {"currency": "USD", "marketing_budget": 0, "budget_period": "year", "channel_allocations": [{"channel": "Organic", "amount": 0, "expected_leads": 0, "expected_customers": 0}], "launch_weeks": 4},
        "researcher_formal": {"market": {"tam": 1000, "sam": 500, "som": 100, "currency": "USD"}, "evidence": []},
    }
    for agent, formal in (("head_of_sales", state["head_of_sales_formal"]), ("cfo", state["cfo_formal"]), ("coo", state["coo_formal"]), ("cto", state["cto_formal"]), ("pm", state["pm_formal"]), ("cmo", state["cmo_formal"]), ("researcher", state["researcher_formal"])):
        state[f"{agent}_validation"] = validate_formal_analysis(agent, formal)
    return state


def test_phase2_connects_sales_operations_and_finance() -> None:
    result = run_phase2_calculations(_state())
    assert result["finance"]["opening_cash_after_startup"] == 4500.0
    assert result["finance"]["months"][0]["payroll"] == 0.0
    assert result["finance"]["months"][1]["payroll"] == 100.0
    assert result["sales"]["months"][0]["qualified_leads"] == 50.0
    assert result["sales"]["months"][0]["new_customers"] == 5.0
    assert result["operations"]["required_monthly_customers"] > 0
    assert result["operations"]["months"][0]["headcount"] == 0.0
    assert result["technical"]["delivery_duration_weeks"] == 4.0
    assert result["product"]["features"][0]["priority_score"] == 5.0


def test_phase2_blocks_missing_formal_validation() -> None:
    state = _state()
    state["cfo_validation"] = {"valid": False, "errors": ["starting_cash must be provided"]}
    try:
        run_phase2_calculations(state)
    except ValueError as exc:
        assert "blocked by invalid formal inputs" in str(exc)
    else:
        raise AssertionError("Phase 2 should reject invalid formal inputs")
