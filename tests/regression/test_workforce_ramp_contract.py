from __future__ import annotations

from analysis.calculations import calculate_workforce_capacity


def test_workforce_ramp_regression_contract() -> None:
    result = calculate_workforce_capacity(
        {
            "workload_hours_per_customer": 10,
            "productive_hours_per_employee": 100,
            "required_monthly_customers": 20,
            "headcount_plan": [
                {"count": 2, "annual_salary": 1200, "start_month": 2, "ramp_months": 2, "monthly_capacity_hours": 100}
            ],
        }
    )

    assert result["annual_payroll_run_rate"] == 2400.0
    assert result["months"][0]["headcount"] == 0.0
    assert result["months"][1]["capacity_hours"] == 100.0
    assert result["months"][2]["capacity_hours"] == 200.0
    assert result["capacity_gap_months"][:2] == [1, 2]
    assert 3 not in result["capacity_gap_months"]
