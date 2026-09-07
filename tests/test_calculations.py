from __future__ import annotations

import pytest

from analysis.calculations import calculate_delivery_model, calculate_financial_model, calculate_product_priorities, calculate_sales_funnel, calculate_workforce_capacity


def test_financial_engine_calculates_pnl_cash_and_break_even() -> None:
    result = calculate_financial_model({
        "starting_cash": 1000, "price": 100, "price_period": "month", "starting_customers": 0, "monthly_new_customers": [5] * 12,
        "churn_rate": 0, "cogs_per_customer": 10, "cogs_percent_revenue": 0, "payroll_monthly": [100] * 12,
        "infrastructure_monthly": [20] * 12, "marketing_monthly": [30] * 12, "other_monthly": [0] * 12,
    })
    assert len(result["months"]) == 12
    assert result["months"][0]["revenue"] == 250.0
    assert result["months"][0]["cogs"] == 25.0
    assert result["months"][0]["net_burn"] == -75.0
    assert result["break_even_month"] == 1
    assert result["ending_cash"] > 1000


def test_financial_model_accounts_for_startup_cost_before_month_one() -> None:
    result = calculate_financial_model({
        "starting_cash": 5000, "startup_costs": 1500, "price": 0, "price_period": "month", "starting_customers": 0,
        "monthly_new_customers": [0] * 12, "payroll_monthly": [0] * 12, "infrastructure_monthly": [0] * 12,
        "marketing_monthly": [0] * 12, "other_monthly": [0] * 12,
    })
    assert result["opening_cash_after_startup"] == 3500.0
    assert result["ending_cash"] == 3500.0


def test_financial_runway_is_cash_depletion_based() -> None:
    result = calculate_financial_model({
        "starting_cash": 250, "price": 0, "price_period": "month", "starting_customers": 0,
        "monthly_new_customers": [0] * 12, "payroll_monthly": [100] * 12, "infrastructure_monthly": [0] * 12,
        "marketing_monthly": [0] * 12, "other_monthly": [0] * 12,
    })
    assert result["runway_months"] == 2.5
    assert result["cash_depletion_month"] == 3


def test_negative_financial_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_financial_model({"starting_cash": -1, "price": 10, "monthly_new_customers": [1], "payroll_monthly": [0], "infrastructure_monthly": [0], "marketing_monthly": [0], "other_monthly": [0]})


def test_annual_recurring_price_is_normalized_to_monthly_revenue() -> None:
    result = calculate_sales_funnel({
        "monthly_traffic": [10] * 12, "qualification_rate": 1, "opportunity_rate": 1, "close_rate": 1,
        "price": 1200, "price_period": "year", "starting_customers": 0, "monthly_churn_rate": 0, "annual_revenue_target": 12000,
    })
    assert result["months"][0]["new_customers"] == 10.0
    assert result["months"][0]["revenue"] == 500.0
    assert result["required_annual_sales"] == 10.0


def test_sales_funnel_connects_traffic_to_customers_and_revenue() -> None:
    result = calculate_sales_funnel({
        "monthly_traffic": [100] * 12, "qualification_rate": 0.5, "opportunity_rate": 0.5, "close_rate": 0.2,
        "price": 100, "price_period": "month", "starting_customers": 0, "monthly_churn_rate": 0, "annual_revenue_target": 12000,
    })
    assert result["funnel_yield"] == 0.05
    assert result["months"][0]["qualified_leads"] == 50.0
    assert result["months"][0]["opportunities"] == 25.0
    assert result["months"][0]["new_customers"] == 5.0
    assert result["required_annual_sales"] == 120.0


def test_workforce_model_applies_start_dates_and_ramp() -> None:
    result = calculate_workforce_capacity({
        "headcount_plan": [{"role": "Engineer", "count": 2, "annual_salary": 1200, "start_month": 2, "ramp_months": 2, "monthly_capacity_hours": 100}],
        "workload_hours_per_customer": 10, "required_monthly_customers": 15,
    })
    assert result["annual_payroll_run_rate"] == 2400.0
    assert result["months"][0]["headcount"] == 0.0
    assert result["months"][1]["capacity_hours"] == 100.0
    assert result["months"][2]["capacity_hours"] == 200.0
    assert 1 in result["capacity_gap_months"]
    assert 2 in result["capacity_gap_months"]
    assert 3 not in result["capacity_gap_months"]


def test_delivery_model_parallelizes_independent_phases() -> None:
    result = calculate_delivery_model({
        "engineering_team": [{"role": "Engineer", "count": 2, "weekly_capacity_weeks": 1}],
        "development_phases": [
            {"name": "A", "weeks": 4, "dependencies": []}, {"name": "B", "weeks": 4, "dependencies": []}, {"name": "C", "weeks": 4, "dependencies": ["A", "B"]},
        ], "schedule_buffer": 0,
    })
    assert result["delivery_duration_weeks"] == 6.0
    assert result["phases"][0]["start_week"] == 0.0
    assert result["phases"][1]["start_week"] == 0.0
    assert result["phases"][2]["start_week"] == 4.0


def test_delivery_model_rejects_unknown_dependency_and_cycle() -> None:
    with pytest.raises(ValueError, match="unknown dependency"):
        calculate_delivery_model({"engineering_team": [{"count": 1, "weekly_capacity_weeks": 1}], "development_phases": [{"name": "A", "weeks": 1, "dependencies": ["Missing"]}]})
    with pytest.raises(ValueError, match="cycle"):
        calculate_delivery_model({"engineering_team": [{"count": 1, "weekly_capacity_weeks": 1}], "development_phases": [{"name": "A", "weeks": 1, "dependencies": ["B"]}, {"name": "B", "weeks": 1, "dependencies": ["A"]}]})


def test_product_priority_uses_deterministic_formula_and_ranks() -> None:
    result = calculate_product_priorities({"features": [{"name": "A", "impact": 10, "effort": 2, "strategic_weight": 1, "dependency_factor": 1}, {"name": "B", "impact": 6, "effort": 1, "strategic_weight": 2, "dependency_factor": 0.5}]})
    assert result["features"][0]["name"] == "B"
    assert result["features"][0]["priority_score"] == 6.0
    assert result["features"][1]["priority_score"] == 5.0
