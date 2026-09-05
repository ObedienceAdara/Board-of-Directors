"""Phase 2 integration layer connecting LLM assumptions to deterministic engines."""

from __future__ import annotations

from typing import Any

from .calculations import (
    MONTHS,
    calculate_delivery_model,
    calculate_financial_model,
    calculate_financial_scenarios,
    calculate_product_priorities,
    calculate_sales_funnel,
    calculate_workforce_capacity,
    nonnegative,
)


def run_phase2_calculations(state: dict[str, Any]) -> dict[str, Any]:
    """Run the complete deterministic domain layer from department assumptions."""
    cfo = state.get("cfo_formal", {}) or {}
    sales = state.get("head_of_sales_formal", {}) or {}
    coo = state.get("coo_formal", {}) or {}
    cto = state.get("cto_formal", {}) or {}
    pm = state.get("pm_formal", {}) or {}
    cmo = state.get("cmo_formal", {}) or {}
    sales = sales if isinstance(sales, dict) else {}
    cfo = cfo if isinstance(cfo, dict) else {}
    coo = coo if isinstance(coo, dict) else {}
    cto = cto if isinstance(cto, dict) else {}
    pm = pm if isinstance(pm, dict) else {}
    cmo = cmo if isinstance(cmo, dict) else {}

    traffic = sales.get("monthly_traffic", sales.get("traffic_by_month", []))
    sales_model = calculate_sales_funnel({
        "monthly_traffic": traffic,
        "qualification_rate": sales.get("qualification_rate", sales.get("lead_to_qualified_rate", 0)),
        "opportunity_rate": sales.get("opportunity_rate", sales.get("qualified_to_opportunity_rate", 0)),
        "close_rate": sales.get("close_rate", sales.get("lead_to_customer_rate", 0)),
        "price": sales.get("primary_price", 0),
        "monthly_churn_rate": sales.get("monthly_churn_rate", sales.get("churn_rate", 0)),
        "starting_customers": sales.get("starting_customers", 0),
        "annual_revenue_target": sales.get("annual_revenue_target", 0),
    })

    workforce = calculate_workforce_capacity({
        "headcount_plan": coo.get("headcount_plan", []),
        "workload_hours_per_customer": coo.get("workload_hours_per_customer", 0),
        "productive_hours_per_employee": coo.get("productive_hours_per_employee", 120),
        "default_ramp_months": coo.get("default_ramp_months", 1),
        "required_monthly_customers": max((row["new_customers"] for row in sales_model["months"]), default=0.0),
    })

    payroll_monthly = [float(row["payroll"]) for row in workforce["months"]]
    if not any(payroll_monthly):
        budget = cfo.get("monthly_budget_by_category", {})
        budget = budget if isinstance(budget, dict) else {}
        fallback = nonnegative(budget.get("payroll"))
        payroll_monthly = [fallback] * MONTHS

    finance_inputs = {
        "starting_cash": cfo.get("starting_cash", 0),
        "price": sales.get("primary_price", 0),
        "starting_customers": sales.get("starting_customers", 0),
        # The deterministic funnel, not the LLM's target table, controls customer acquisition.
        "monthly_new_customers": [row["new_customers"] for row in sales_model["months"]],
        "churn_rate": sales.get("monthly_churn_rate", sales.get("churn_rate", 0)),
        "cogs_per_customer": cfo.get("cogs_per_customer", 0),
        "cogs_percent_revenue": cfo.get("cogs_percent_revenue", 0),
        "payroll_monthly": payroll_monthly,
        "infrastructure_monthly": cfo.get("monthly_infrastructure_schedule", [cto.get("monthly_infrastructure_cost", 0)] * MONTHS),
        "marketing_monthly": cfo.get("monthly_marketing_schedule", [nonnegative(cmo.get("marketing_budget")) / MONTHS] * MONTHS),
        "other_monthly": cfo.get("monthly_other_opex_schedule", [0] * MONTHS),
    }
    finance = calculate_financial_model(finance_inputs)
    financial_scenarios = calculate_financial_scenarios(finance_inputs, cfo.get("financial_scenarios"))

    delivery = calculate_delivery_model({
        "development_phases": cto.get("development_phases", []),
        "engineering_team": cto.get("engineering_team", []),
        "schedule_buffer": cto.get("schedule_buffer", 0.1),
    })

    product = calculate_product_priorities({
        "features": pm.get("mvp_features", []),
        "strategic_weight": pm.get("strategic_weight", 1.0),
    })

    expected = {
        "finance": ["starting_cash", "primary_price", "cogs assumptions"],
        "sales": ["monthly_traffic", "qualification_rate", "opportunity_rate", "close_rate", "primary_price"],
        "operations": ["headcount_plan", "workload_hours_per_customer"],
        "technical": ["development_phases", "engineering_team"],
        "product": ["mvp_features", "impact", "effort"],
    }
    missing = {
        domain: [name for name in names if not _field_present(state, name)]
        for domain, names in expected.items()
    }
    return {
        "model_version": "phase2-v1",
        "finance": finance,
        "finance_scenarios": financial_scenarios,
        "sales": sales_model,
        "operations": workforce,
        "technical": delivery,
        "product": product,
        "input_quality": {"missing_expected_inputs": missing},
    }


def _field_present(state: dict[str, Any], name: str) -> bool:
    cfo = state.get("cfo_formal", {})
    sales = state.get("head_of_sales_formal", {})
    coo = state.get("coo_formal", {})
    cto = state.get("cto_formal", {})
    pm = state.get("pm_formal", {})
    cfo = cfo if isinstance(cfo, dict) else {}
    sales = sales if isinstance(sales, dict) else {}
    coo = coo if isinstance(coo, dict) else {}
    cto = cto if isinstance(cto, dict) else {}
    pm = pm if isinstance(pm, dict) else {}
    mapping = {
        "starting_cash": cfo.get("starting_cash") is not None,
        "primary_price": sales.get("primary_price") is not None,
        "cogs assumptions": cfo.get("cogs_per_customer") is not None or cfo.get("cogs_percent_revenue") is not None,
        "monthly_traffic": bool(sales.get("monthly_traffic", sales.get("traffic_by_month", []))),
        "qualification_rate": sales.get("qualification_rate") is not None,
        "opportunity_rate": sales.get("opportunity_rate") is not None,
        "close_rate": sales.get("close_rate") is not None or sales.get("lead_to_customer_rate") is not None,
        "headcount_plan": bool(coo.get("headcount_plan")),
        "workload_hours_per_customer": coo.get("workload_hours_per_customer") is not None,
        "development_phases": bool(cto.get("development_phases")),
        "engineering_team": bool(cto.get("engineering_team")),
        "mvp_features": bool(pm.get("mvp_features")),
        "impact": any(isinstance(feature, dict) and feature.get("impact") is not None for feature in pm.get("mvp_features", [])) if isinstance(pm.get("mvp_features", []), list) else False,
        "effort": any(isinstance(feature, dict) and feature.get("effort") is not None for feature in pm.get("mvp_features", [])) if isinstance(pm.get("mvp_features", []), list) else False,
    }
    return mapping.get(name, True)
