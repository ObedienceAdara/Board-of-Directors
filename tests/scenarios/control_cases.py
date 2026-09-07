"""Small deterministic scenarios used as Phase 0 control experiments."""

from __future__ import annotations

from typing import Any


FINANCE_CONTROL: dict[str, Any] = {
    "starting_cash": 1000,
    "startup_costs": 0,
    "price": 100,
    "price_period": "month",
    "starting_customers": 0,
    "churn_rate": 0,
    "cogs_per_customer": 0,
    "cogs_percent_revenue": 0,
    "monthly_new_customers": [1] * 12,
    "payroll_monthly": [0] * 12,
    "infrastructure_monthly": [0] * 12,
    "marketing_monthly": [0] * 12,
    "other_monthly": [0] * 12,
}


SALES_CONTROL: dict[str, Any] = {
    "monthly_traffic": [100] * 12,
    "qualification_rate": 0.5,
    "opportunity_rate": 0.5,
    "close_rate": 0.5,
    "price": 100,
    "price_period": "one_time",
    "monthly_churn_rate": 0,
    "starting_customers": 0,
    "annual_revenue_target": 0,
}


WORKFORCE_CONTROL: dict[str, Any] = {
    "workload_hours_per_customer": 10,
    "productive_hours_per_employee": 100,
    "required_monthly_customers": 20,
    "headcount_plan": [
        {"count": 2, "annual_salary": 1200, "start_month": 2, "ramp_months": 2, "monthly_capacity_hours": 100}
    ],
}
