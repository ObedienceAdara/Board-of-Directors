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

AGENTS = ("researcher", "cfo", "cto", "cmo", "head_of_sales", "coo", "pm")


def _formal(state: dict[str, Any], agent: str) -> dict[str, Any]:
    value = state.get(f"{agent}_formal", {})
    return value if isinstance(value, dict) else {}


def _require_valid_formal_inputs(state: dict[str, Any]) -> None:
    failures: dict[str, list[str]] = {}
    for agent in AGENTS:
        validation = state.get(f"{agent}_validation", {})
        if not isinstance(validation, dict):
            failures[agent] = ["Missing deterministic validation result"]
            continue
        errors = validation.get("errors", [])
        if errors:
            failures[agent] = [str(error) for error in errors]
        if validation.get("valid") is not True:
            failures.setdefault(agent, []).append("Formal analysis did not pass its deterministic contract")
    if failures:
        detail = "; ".join(f"{agent}: {', '.join(errors)}" for agent, errors in failures.items())
        raise ValueError("Phase 2 calculation blocked by invalid formal inputs: " + detail)


def _monthly_or_constant(value: Any, fallback: float) -> list[float]:
    if value is None:
        return [fallback] * MONTHS
    if isinstance(value, list):
        return value
    return [nonnegative(value)] * MONTHS


def run_phase2_calculations(state: dict[str, Any]) -> dict[str, Any]:
    """Run the deterministic domain layer only after formal contracts pass."""
    _require_valid_formal_inputs(state)
    cfo = _formal(state, "cfo")
    sales = _formal(state, "head_of_sales")
    coo = _formal(state, "coo")
    cto = _formal(state, "cto")
    pm = _formal(state, "pm")
    cmo = _formal(state, "cmo")

    traffic = sales.get("monthly_traffic")
    sales_model = calculate_sales_funnel({
        "monthly_traffic": traffic,
        "qualification_rate": sales["qualification_rate"],
        "opportunity_rate": sales["opportunity_rate"],
        "close_rate": sales["close_rate"],
        "price": sales["primary_price"],
        "price_period": sales.get("price_period", "month"),
        "monthly_churn_rate": sales.get("monthly_churn_rate", 0),
        "starting_customers": sales["starting_customers"],
        "annual_revenue_target": sales["annual_revenue_target"],
    })

    # Service-capacity requirements are based on active customer load, not only
    # acquisition flow. This prevents a business with low new-customer volume
    # and a large retained base from appearing artificially over-capable.
    peak_active_customers = max((float(row["ending_customers"]) for row in sales_model["months"]), default=0.0)
    workforce = calculate_workforce_capacity({
        "headcount_plan": coo["headcount_plan"],
        "workload_hours_per_customer": coo["workload_hours_per_customer"],
        "productive_hours_per_employee": coo.get("productive_hours_per_employee", 120),
        "default_ramp_months": coo.get("default_ramp_months", 1),
        "required_monthly_customers": peak_active_customers,
    })
    workforce["annual_payroll"] = workforce.get("annual_payroll_run_rate", 0.0)

    workforce_payroll = [float(row["payroll"]) for row in workforce["months"]]
    cfo_budget = cfo.get("monthly_budget_by_category", {})
    cfo_budget = cfo_budget if isinstance(cfo_budget, dict) else {}
    budget_payroll = nonnegative(cfo_budget.get("payroll")) if cfo_budget.get("payroll") is not None else 0.0
    # Use the explicit COO plan whenever present. CFO payroll is a fallback,
    # never an additive second payroll stream.
    if not any(workforce_payroll):
        workforce_payroll = [budget_payroll] * MONTHS

    infra_schedule = _monthly_or_constant(cfo.get("monthly_infrastructure_schedule"), nonnegative(cto.get("monthly_infrastructure_cost")))
    marketing_schedule = _monthly_or_constant(cfo.get("monthly_marketing_schedule"), 0.0)
    other_schedule = _monthly_or_constant(cfo.get("monthly_other_opex_schedule"), 0.0)
    if all(value == 0 for value in marketing_schedule):
        cmo_budget = nonnegative(cmo.get("marketing_budget"))
        cmo_period = str(cmo.get("budget_period", "year")).strip().lower()
        if cmo_period in {"month", "monthly"}:
            monthly_marketing = cmo_budget
        elif cmo_period in {"quarter", "quarterly"}:
            monthly_marketing = cmo_budget / 3.0
        elif cmo_period in {"year", "annual", "yearly"}:
            monthly_marketing = cmo_budget / MONTHS
        else:
            monthly_marketing = cmo_budget / MONTHS
        marketing_schedule = [monthly_marketing] * MONTHS

    finance_inputs = {
        "starting_cash": cfo["starting_cash"],
        "startup_costs": sum(nonnegative(item.get("amount")) for item in cfo.get("startup_costs", []) if isinstance(item, dict)),
        "price": sales["primary_price"],
        "price_period": sales.get("price_period", "month"),
        "starting_customers": sales["starting_customers"],
        "monthly_new_customers": [row["new_customers"] for row in sales_model["months"]],
        "churn_rate": sales.get("monthly_churn_rate", 0),
        "cogs_per_customer": cfo.get("cogs_per_customer", 0),
        "cogs_percent_revenue": cfo.get("cogs_percent_revenue", 0),
        "payroll_monthly": workforce_payroll,
        "infrastructure_monthly": infra_schedule,
        "marketing_monthly": marketing_schedule,
        "other_monthly": other_schedule,
    }
    finance = calculate_financial_model(finance_inputs)
    financial_scenarios = calculate_financial_scenarios(finance_inputs, cfo.get("financial_scenarios"))

    delivery = calculate_delivery_model({
        "development_phases": cto["development_phases"],
        "engineering_team": cto["engineering_team"],
        "schedule_buffer": cto.get("schedule_buffer", 0.1),
    })

    product = calculate_product_priorities({
        "features": pm["mvp_features"],
        "strategic_weight": pm.get("strategic_weight", 1.0),
    })

    expected = {
        "finance": ["starting_cash", "startup_costs", "cogs assumptions"],
        "sales": ["monthly_traffic", "qualification_rate", "opportunity_rate", "close_rate", "primary_price", "price_period"],
        "operations": ["headcount_plan", "workload_hours_per_customer"],
        "technical": ["development_phases", "engineering_team"],
        "product": ["mvp_features", "impact", "effort"],
    }
    missing = {
        domain: [name for name in names if not _field_present(state, name)]
        for domain, names in expected.items()
    }
    return {
        "model_version": "phase2-v2",
        "finance": finance,
        "finance_scenarios": financial_scenarios,
        "sales": sales_model,
        "operations": workforce,
        "technical": delivery,
        "product": product,
        "input_quality": {"missing_expected_inputs": missing},
    }


def _field_present(state: dict[str, Any], name: str) -> bool:
    cfo = _formal(state, "cfo")
    sales = _formal(state, "head_of_sales")
    coo = _formal(state, "coo")
    cto = _formal(state, "cto")
    pm = _formal(state, "pm")
    mapping = {
        "starting_cash": cfo.get("starting_cash") is not None,
        "startup_costs": isinstance(cfo.get("startup_costs"), list),
        "cogs assumptions": cfo.get("cogs_per_customer") is not None or cfo.get("cogs_percent_revenue") is not None,
        "monthly_traffic": bool(sales.get("monthly_traffic")),
        "qualification_rate": sales.get("qualification_rate") is not None,
        "opportunity_rate": sales.get("opportunity_rate") is not None,
        "close_rate": sales.get("close_rate") is not None,
        "primary_price": sales.get("primary_price") is not None,
        "price_period": sales.get("price_period") is not None,
        "headcount_plan": bool(coo.get("headcount_plan")),
        "workload_hours_per_customer": coo.get("workload_hours_per_customer") is not None,
        "development_phases": bool(cto.get("development_phases")),
        "engineering_team": bool(cto.get("engineering_team")),
        "mvp_features": bool(pm.get("mvp_features")),
        "impact": all(isinstance(feature, dict) and feature.get("impact") is not None for feature in pm.get("mvp_features", [])) if isinstance(pm.get("mvp_features", []), list) else False,
        "effort": all(isinstance(feature, dict) and feature.get("effort") is not None for feature in pm.get("mvp_features", [])) if isinstance(pm.get("mvp_features", []), list) else False,
    }
    return mapping.get(name, True)
