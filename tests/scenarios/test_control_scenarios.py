from __future__ import annotations

from analysis.calculations import calculate_financial_model, calculate_sales_funnel, calculate_workforce_capacity
from tests.scenarios.control_cases import FINANCE_CONTROL, SALES_CONTROL, WORKFORCE_CONTROL


def test_finance_control_case_is_exact_and_stable() -> None:
    result = calculate_financial_model(FINANCE_CONTROL)

    assert result["12_month_revenue"] == 7800.0
    assert result["gross_profit"] == 7800.0
    assert result["ending_cash"] == 8800.0
    assert result["cash_depletion_month"] is None
    assert result["break_even_month"] == 1


def test_sales_control_case_reconciles_funnel() -> None:
    result = calculate_sales_funnel(SALES_CONTROL)

    assert result["funnel_yield"] == 0.125
    assert result["months"][0]["traffic"] == 100.0
    assert result["months"][0]["qualified_leads"] == 50.0
    assert result["months"][0]["opportunities"] == 25.0
    assert result["months"][0]["new_customers"] == 12.5
    assert result["12_month_revenue"] == 15000.0


def test_workforce_control_case_preserves_ramp_math() -> None:
    result = calculate_workforce_capacity(WORKFORCE_CONTROL)

    assert result["annual_payroll_run_rate"] == 2400.0
    assert result["months"][0]["headcount"] == 0.0
    assert result["months"][1]["capacity_hours"] == 100.0
    assert result["months"][2]["capacity_hours"] == 200.0
    assert 1 in result["capacity_gap_months"]
    assert 2 in result["capacity_gap_months"]
    assert 3 not in result["capacity_gap_months"]
