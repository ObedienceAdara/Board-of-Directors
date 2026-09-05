from __future__ import annotations

from analysis.phase2 import run_phase2_calculations


def test_phase2_connects_sales_operations_and_finance() -> None:
    state = {
        "head_of_sales_formal": {
            "primary_price": 100,
            "starting_customers": 0,
            "annual_revenue_target": 12000,
            "monthly_traffic": [100] * 12,
            "qualification_rate": 0.5,
            "opportunity_rate": 0.5,
            "close_rate": 0.2,
            "monthly_churn_rate": 0,
        },
        "cfo_formal": {
            "starting_cash": 5000,
            "cogs_per_customer": 10,
            "cogs_percent_revenue": 0,
            "monthly_budget_by_category": {"payroll": 0, "marketing": 0, "infrastructure": 0, "other": 0},
        },
        "coo_formal": {
            "headcount_plan": [
                {"role": "Engineer", "count": 1, "annual_salary": 1200, "start_month": 2, "ramp_months": 1, "monthly_capacity_hours": 100}
            ],
            "productive_hours_per_employee": 120,
            "workload_hours_per_customer": 10,
            "default_ramp_months": 1,
        },
        "cto_formal": {
            "development_phases": [{"name": "Build", "weeks": 4, "dependencies": []}],
            "engineering_team": [{"role": "Engineer", "count": 1, "weekly_capacity_weeks": 1}],
            "schedule_buffer": 0,
        },
        "pm_formal": {
            "mvp_features": [{"name": "Core", "impact": 10, "effort": 2, "strategic_weight": 1, "dependency_factor": 1, "in_scope": True}]
        },
        "cmo_formal": {"marketing_budget": 0},
    }
    result = run_phase2_calculations(state)
    assert result["finance"]["months"][0]["payroll"] == 0.0
    assert result["finance"]["months"][1]["payroll"] == 100.0
    assert result["sales"]["months"][0]["qualified_leads"] == 50.0
    assert result["sales"]["months"][0]["new_customers"] == 5.0
    assert result["operations"]["months"][0]["headcount"] == 0.0
    assert result["technical"]["delivery_duration_weeks"] == 4.0
    assert result["product"]["features"][0]["priority_score"] == 5.0
