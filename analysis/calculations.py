"""Deterministic Phase 2 domain calculators.

LLMs provide assumptions; these functions calculate consequences. No model or
external service is called from this module.
"""

from __future__ import annotations

from math import isfinite
from typing import Any

MONTHS = 12
EPSILON = 1e-9


def number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        result = float(value)
        return result if isfinite(result) else default
    if isinstance(value, str):
        try:
            result = float(value.replace(",", "").replace("$", "").replace("%", "").strip())
            return result if isfinite(result) else default
        except ValueError:
            return default
    return default


def nonnegative(value: Any, default: float = 0.0) -> float:
    result = number(value, default)
    return max(result if result is not None else default, 0.0)


def rate(value: Any, default: float = 0.0) -> float:
    result = number(value, default)
    if result is None:
        return default
    if result > 1:
        result /= 100.0
    return min(max(result, 0.0), 1.0)


def _monthly(values: Any) -> list[float]:
    if not isinstance(values, list) or not values:
        return [0.0] * MONTHS
    output = [nonnegative(value) for value in values[:MONTHS]]
    return output + [output[-1]] * (MONTHS - len(output))


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def calculate_financial_model(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compute monthly P&L, customer base, cash balance, burn and runway."""
    starting_cash = nonnegative(inputs.get("starting_cash"))
    price = nonnegative(inputs.get("price"))
    customers = nonnegative(inputs.get("starting_customers"))
    churn = rate(inputs.get("churn_rate"))
    cogs_unit = nonnegative(inputs.get("cogs_per_customer"))
    cogs_rate = rate(inputs.get("cogs_percent_revenue"))
    new_customers = _monthly(inputs.get("monthly_new_customers"))
    payroll = _monthly(inputs.get("payroll_monthly"))
    infrastructure = _monthly(inputs.get("infrastructure_monthly"))
    marketing = _monthly(inputs.get("marketing_monthly"))
    other = _monthly(inputs.get("other_monthly"))

    cash = starting_cash
    break_even_month: int | None = None
    months: list[dict[str, Any]] = []
    for month in range(1, MONTHS + 1):
        new = new_customers[month - 1]
        churned = min(customers, customers * churn)
        ending_customers = max(customers - churned + new, 0.0)
        average_customers = (customers + ending_customers) / 2.0
        revenue = average_customers * price
        cogs = revenue * cogs_rate + average_customers * cogs_unit
        gross_profit = revenue - cogs
        fixed_opex = payroll[month - 1] + infrastructure[month - 1] + marketing[month - 1] + other[month - 1]
        total_costs = cogs + fixed_opex
        net_burn = total_costs - revenue
        contribution = revenue - cogs - marketing[month - 1]
        cash -= net_burn
        if break_even_month is None and net_burn <= EPSILON:
            break_even_month = month
        months.append({
            "month": month,
            "customers": _round(ending_customers, 3),
            "new_customers": _round(new, 3),
            "churned_customers": _round(churned, 3),
            "revenue": _round(revenue),
            "cogs": _round(cogs),
            "gross_profit": _round(gross_profit),
            "gross_margin": _round(gross_profit / revenue, 4) if revenue > EPSILON else 0.0,
            "payroll": _round(payroll[month - 1]),
            "infrastructure": _round(infrastructure[month - 1]),
            "marketing": _round(marketing[month - 1]),
            "other_opex": _round(other[month - 1]),
            "operating_costs": _round(total_costs),
            "net_burn": _round(net_burn),
            "ending_cash": _round(cash),
            "contribution_margin": _round(contribution),
            "contribution_margin_ratio": _round(contribution / revenue, 4) if revenue > EPSILON else 0.0,
        })
        customers = ending_customers

    revenue_total = sum(float(row["revenue"]) for row in months)
    cogs_total = sum(float(row["cogs"]) for row in months)
    opex_total = sum(float(row["payroll"]) + float(row["infrastructure"]) + float(row["marketing"]) + float(row["other_opex"]) for row in months)
    contribution_total = revenue_total - cogs_total - sum(float(row["marketing"]) for row in months)
    positive_burns = [float(row["net_burn"]) for row in months if float(row["net_burn"]) > EPSILON]
    average_burn = sum(positive_burns) / len(positive_burns) if positive_burns else 0.0
    runway = starting_cash / average_burn if average_burn > EPSILON else None
    minimum_cash = min((float(row["ending_cash"]) for row in months), default=starting_cash)
    return {
        "model": "deterministic_financial_v1",
        "months": months,
        "monthly_revenue": months[-1]["revenue"] if months else 0.0,
        "monthly_costs": months[-1]["operating_costs"] if months else 0.0,
        "gross_profit": _round(revenue_total - cogs_total),
        "gross_margin": _round((revenue_total - cogs_total) / revenue_total, 4) if revenue_total > EPSILON else 0.0,
        "contribution_margin": _round(contribution_total),
        "contribution_margin_ratio": _round(contribution_total / revenue_total, 4) if revenue_total > EPSILON else 0.0,
        "net_burn": months[-1]["net_burn"] if months else 0.0,
        "ending_cash": _round(months[-1]["ending_cash"] if months else starting_cash),
        "runway_months": None if runway is None else _round(runway),
        "break_even_month": break_even_month,
        "12_month_revenue": _round(revenue_total),
        "12_month_cogs": _round(cogs_total),
        "12_month_opex": _round(opex_total),
        "12_month_operating_profit": _round(revenue_total - cogs_total - opex_total),
        "minimum_cash_balance": _round(minimum_cash),
    }


def calculate_financial_scenarios(base_inputs: dict[str, Any], scenarios: Any = None) -> dict[str, Any]:
    """Recompute the financial model for conservative/base/optimistic assumptions."""
    definitions = scenarios if isinstance(scenarios, dict) else {}
    defaults = {
        "conservative": {"customer_growth_factor": 0.75, "price_factor": 0.95},
        "base": {"customer_growth_factor": 1.0, "price_factor": 1.0},
        "optimistic": {"customer_growth_factor": 1.25, "price_factor": 1.05},
    }
    base_new = _monthly(base_inputs.get("monthly_new_customers"))
    output: dict[str, Any] = {}
    for name, default in defaults.items():
        definition = definitions.get(name, {}) if isinstance(definitions, dict) else {}
        definition = definition if isinstance(definition, dict) else {}
        growth = nonnegative(definition.get("customer_growth_factor"), default["customer_growth_factor"])
        price_factor = nonnegative(definition.get("price_factor"), default["price_factor"])
        scenario = dict(base_inputs)
        scenario["monthly_new_customers"] = [value * growth for value in base_new]
        scenario["price"] = nonnegative(base_inputs.get("price")) * price_factor
        if "cogs_percent_revenue" in definition:
            scenario["cogs_percent_revenue"] = definition["cogs_percent_revenue"]
        output[name] = {
            "assumptions": {
                "customer_growth_factor": growth,
                "price_factor": price_factor,
                "cogs_percent_revenue": rate(scenario.get("cogs_percent_revenue")),
            },
            "calculation": calculate_financial_model(scenario),
        }
    return {"model": "deterministic_financial_scenarios_v1", "scenarios": output}


def calculate_sales_funnel(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compute traffic -> qualified leads -> opportunities -> wins -> revenue."""
    traffic = _monthly(inputs.get("monthly_traffic"))
    qualification = rate(inputs.get("qualification_rate"))
    opportunity = rate(inputs.get("opportunity_rate"))
    close = rate(inputs.get("close_rate"))
    price = nonnegative(inputs.get("price"))
    churn = rate(inputs.get("monthly_churn_rate"))
    customers = nonnegative(inputs.get("starting_customers"))
    target = nonnegative(inputs.get("annual_revenue_target"))
    rows: list[dict[str, Any]] = []
    for month in range(1, MONTHS + 1):
        visitors = traffic[month - 1]
        qualified = visitors * qualification
        opportunities = qualified * opportunity
        won = opportunities * close
        churned = customers * churn
        ending_customers = max(customers - churned + won, 0.0)
        average_customers = (customers + ending_customers) / 2.0
        rows.append({
            "month": month,
            "traffic": _round(visitors, 3),
            "qualified_leads": _round(qualified, 3),
            "opportunities": _round(opportunities, 3),
            "new_customers": _round(won, 3),
            "churned_customers": _round(churned, 3),
            "ending_customers": _round(ending_customers, 3),
            "revenue": _round(average_customers * price),
        })
        customers = ending_customers
    annual_revenue = sum(float(row["revenue"]) for row in rows)
    required_customers = target / price if price > EPSILON else None
    funnel_yield = qualification * opportunity * close
    implied_traffic = required_customers / (12 * funnel_yield) if required_customers is not None and funnel_yield > EPSILON else None
    return {
        "model": "deterministic_sales_funnel_v1",
        "months": rows,
        "12_month_revenue": _round(annual_revenue),
        "annual_revenue_target": _round(target),
        "target_gap": _round(target - annual_revenue),
        "required_annual_customers": None if required_customers is None else _round(required_customers, 3),
        "implied_monthly_traffic_for_target": None if implied_traffic is None else _round(implied_traffic, 3),
        "funnel_yield": _round(funnel_yield, 6),
        "ending_customers": rows[-1]["ending_customers"] if rows else 0.0,
    }


def calculate_workforce_capacity(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compute hiring-date payroll, ramp-adjusted capacity and service capacity."""
    hires = inputs.get("headcount_plan", [])
    workload = nonnegative(inputs.get("workload_hours_per_customer"))
    productive = nonnegative(inputs.get("productive_hours_per_employee"), 120.0)
    default_ramp = max(0, int(nonnegative(inputs.get("default_ramp_months"), 1.0)))
    required = nonnegative(inputs.get("required_monthly_customers"))
    normalized: list[dict[str, Any]] = []
    runrate = 0.0
    if isinstance(hires, list):
        for item in hires[:50]:
            if not isinstance(item, dict):
                continue
            count = nonnegative(item.get("count"))
            salary = nonnegative(item.get("annual_salary"))
            start = max(1, int(nonnegative(item.get("start_month"), 1.0)))
            ramp = max(0, int(nonnegative(item.get("ramp_months"), float(default_ramp))))
            hours = nonnegative(item.get("monthly_capacity_hours"), productive)
            runrate += count * salary
            normalized.append({"count": count, "salary": salary, "start": start, "ramp": ramp, "hours": hours})

    months: list[dict[str, Any]] = []
    for month in range(1, MONTHS + 1):
        headcount = capacity_hours = payroll = 0.0
        for item in normalized:
            if month < item["start"]:
                continue
            active = month - item["start"]
            ramp_factor = min(1.0, (active + 1) / item["ramp"]) if item["ramp"] else 1.0
            headcount += item["count"]
            capacity_hours += item["count"] * item["hours"] * ramp_factor
            payroll += item["count"] * item["salary"] / MONTHS
        capacity_customers = capacity_hours / workload if workload > EPSILON else None
        months.append({
            "month": month,
            "headcount": _round(headcount, 3),
            "capacity_hours": _round(capacity_hours, 3),
            "capacity_customers": None if capacity_customers is None else _round(capacity_customers, 3),
            "payroll": _round(payroll),
            "capacity_gap": bool(capacity_customers is not None and capacity_customers + EPSILON < required),
        })
    return {
        "model": "deterministic_workforce_v1",
        "months": months,
        "12_month_payroll": _round(sum(float(row["payroll"]) for row in months)),
        "annual_payroll_run_rate": _round(runrate),
        "peak_headcount": max((row["headcount"] for row in months), default=0.0),
        "peak_capacity_hours": max((row["capacity_hours"] for row in months), default=0.0),
        "required_monthly_customers": _round(required, 3),
        "capacity_gap_months": [row["month"] for row in months if row["capacity_gap"]],
    }


def calculate_delivery_model(inputs: dict[str, Any]) -> dict[str, Any]:
    """Convert engineering phase effort, team capacity and dependencies into schedule weeks."""
    phases = inputs.get("development_phases", [])
    team = inputs.get("engineering_team", [])
    buffer = rate(inputs.get("schedule_buffer"), 0.1)
    capacity = 0.0
    if isinstance(team, list):
        for member in team:
            if not isinstance(member, dict):
                continue
            count = nonnegative(member.get("count"))
            weekly = nonnegative(member.get("weekly_capacity_weeks"), 1.0)
            if member.get("weekly_capacity_hours") is not None:
                weekly = nonnegative(member.get("weekly_capacity_hours")) / 40.0
            capacity += count * weekly
    capacity = max(capacity, 1.0)

    rows: list[dict[str, Any]] = []
    cursor = 0.0
    total_effort = 0.0
    if isinstance(phases, list):
        for index, phase in enumerate(phases[:30], start=1):
            if not isinstance(phase, dict):
                continue
            effort = nonnegative(phase.get("weeks"))
            deps = phase.get("dependencies", [])
            deps = deps if isinstance(deps, list) else []
            dep_names = {str(dep) for dep in deps}
            dep_end = max((row["end_week"] for row in rows if row["name"] in dep_names), default=0.0)
            start = max(cursor, dep_end)
            end = start + (effort / capacity) * (1.0 + buffer)
            rows.append({"index": index, "name": str(phase.get("name") or f"Phase {index}"), "effort_weeks": _round(effort, 3), "start_week": _round(start, 3), "end_week": _round(end, 3), "dependencies": [str(dep) for dep in deps]})
            cursor = end
            total_effort += effort
    return {
        "model": "deterministic_delivery_v1",
        "weekly_team_capacity": _round(capacity, 3),
        "schedule_buffer": _round(buffer, 4),
        "phases": rows,
        "total_effort_weeks": _round(total_effort, 3),
        "delivery_duration_weeks": _round(max((row["end_week"] for row in rows), default=0.0), 3),
    }


def calculate_product_priorities(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate impact / effort * strategic weight * dependency factor."""
    features = inputs.get("features", [])
    default_weight = nonnegative(inputs.get("strategic_weight"), 1.0)
    ranked: list[dict[str, Any]] = []
    if isinstance(features, list):
        for index, feature in enumerate(features[:100], start=1):
            if not isinstance(feature, dict):
                continue
            impact = nonnegative(feature.get("impact"))
            effort = max(nonnegative(feature.get("effort")), EPSILON)
            strategic = nonnegative(feature.get("strategic_weight"), default_weight)
            dependency = max(nonnegative(feature.get("dependency_factor"), 1.0), EPSILON)
            ranked.append({"index": index, "name": str(feature.get("name") or f"Feature {index}"), "impact": _round(impact, 4), "effort": _round(effort, 4), "strategic_weight": _round(strategic, 4), "dependency_factor": _round(dependency, 4), "priority_score": _round(impact / effort * strategic * dependency, 6), "in_scope": bool(feature.get("in_scope", True))})
    ranked.sort(key=lambda item: item["priority_score"], reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return {"model": "deterministic_product_priority_v1", "features": ranked, "mvp_features": [item for item in ranked if item["in_scope"]]}
