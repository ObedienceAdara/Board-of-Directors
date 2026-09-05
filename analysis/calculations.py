"""Deterministic domain calculators for Phase 2.

LLMs provide assumptions. These engines calculate consequences.
No external service or model call is used here.
"""

from __future__ import annotations

from math import ceil, isfinite
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
    if result > 1.0:
        result /= 100.0
    return min(max(result, 0.0), 1.0)


def rounded(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _monthly_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return [0.0] * MONTHS
    values = [nonnegative(item) for item in value[:MONTHS]]
    if not values:
        return [0.0] * MONTHS
    return values + [values[-1]] * (MONTHS - len(values))


def _sum_numeric(items: Any, key: str) -> float:
    if not isinstance(items, list):
        return 0.0
    return sum(nonnegative(item.get(key)) for item in items if isinstance(item, dict))


def calculate_financial_model(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate 12 months of revenue, costs, profit, cash and runway."""
    starting_cash = nonnegative(inputs.get("starting_cash"))
    price = nonnegative(inputs.get("price"))
    customers = nonnegative(inputs.get("starting_customers"))
    churn_rate = rate(inputs.get("churn_rate"))
    cogs_per_customer = nonnegative(inputs.get("cogs_per_customer"))
    cogs_percent_revenue = rate(inputs.get("cogs_percent_revenue"))
    new_customers = _monthly_list(inputs.get("monthly_new_customers"))
    payroll = _monthly_list(inputs.get("payroll_monthly"))
    infrastructure = _monthly_list(inputs.get("infrastructure_monthly"))
    marketing = _monthly_list(inputs.get("marketing_monthly"))
    other = _monthly_list(inputs.get("other_monthly"))

    months: list[dict[str, Any]] = []
    cash = starting_cash
    break_even_month: int | None = None

    for month in range(1, MONTHS + 1):
        new = new_customers[month - 1]
        churned = min(customers, customers * churn_rate)
        ending_customers = max(customers - churned + new, 0.0)
        average_customers = max((customers + ending_customers) / 2.0, 0.0)
        revenue = average_customers * price
        cogs = revenue * cogs_percent_revenue + average_customers * cogs_per_customer
        gross_profit = revenue - cogs
        fixed_opex = payroll[month - 1] + infrastructure[month - 1] + marketing[month - 1] + other[month - 1]
        total_costs = cogs + fixed_opex
        net_burn = total_costs - revenue
        contribution_margin = revenue - cogs - marketing[month - 1]
        contribution_ratio = contribution_margin / revenue if revenue > EPSILON else 0.0
        cash -= net_burn
        if break_even_month is None and net_burn <= EPSILON:
            break_even_month = month
        months.append({
            "month": month,
            "customers": rounded(ending_customers, 3),
            "new_customers": rounded(new, 3),
            "churned_customers": rounded(churned, 3),
            "revenue": rounded(revenue),
            "cogs": rounded(cogs),
            "gross_profit": rounded(gross_profit),
            "gross_margin": rounded(gross_profit / revenue, 4) if revenue > EPSILON else 0.0,
            "payroll": rounded(payroll[month - 1]),
            "infrastructure": rounded(infrastructure[month - 1]),
            "marketing": rounded(marketing[month - 1]),
            "other_opex": rounded(other[month - 1]),
            "operating_costs": rounded(total_costs),
            "net_burn": rounded(net_burn),
            "ending_cash": rounded(cash),
            "contribution_margin": rounded(contribution_margin),
            "contribution_margin_ratio": rounded(contribution_ratio, 4),
        })
        customers = ending_customers

    total_revenue = sum(float(item["revenue"]) for item in months)
    total_cogs = sum(float(item["cogs"]) for item in months)
    total_opex = sum(float(item["payroll"]) + float(item["infrastructure"]) + float(item["marketing"]) + float(item["other_opex"]) for item in months)
    total_marketing = sum(float(item["marketing"]) for item in months)
    gross_profit = total_revenue - total_cogs
    contribution_margin = gross_profit - total_marketing
    burn_values = [float(item["net_burn"]) for item in months if float(item["net_burn"]) > EPSILON]
    average_positive_burn = sum(burn_values) / len(burn_values) if burn_values else 0.0
    runway = starting_cash / average_positive_burn if average_positive_burn > EPSILON else None
    ending_cash = float(months[-1]["ending_cash"]) if months else starting_cash
    minimum_cash = min((float(item["ending_cash"]) for item in months), default=starting_cash)
    return {
        "model": "deterministic_financial_v1",
        "months": months,
        "monthly_revenue": months[-1]["revenue"] if months else 0.0,
        "monthly_costs": months[-1]["operating_costs"] if months else 0.0,
        "gross_profit": rounded(gross_profit),
        "gross_margin": rounded(gross_profit / total_revenue, 4) if total_revenue > EPSILON else 0.0,
        "contribution_margin": rounded(contribution_margin),
        "contribution_margin_ratio": rounded(contribution_margin / total_revenue, 4) if total_revenue > EPSILON else 0.0,
        "net_burn": months[-1]["net_burn"] if months else 0.0,
        "ending_cash": rounded(ending_cash),
        "runway_months": None if runway is None else rounded(runway),
        "break_even_month": break_even_month,
        "12_month_revenue": rounded(total_revenue),
        "12_month_cogs": rounded(total_cogs),
        "12_month_opex": rounded(total_opex),
        "12_month_operating_profit": rounded(gross_profit - total_opex),
        "minimum_cash_balance": rounded(minimum_cash),
        "peak_cash_need": rounded(max(0.0, starting_cash - minimum_cash)),
    }


def calculate_sales_funnel(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate traffic -> leads -> opportunities -> customers -> revenue."""
    traffic = _monthly_list(inputs.get("monthly_traffic"))
    qualification_rate = rate(inputs.get("qualification_rate"))
    opportunity_rate = rate(inputs.get("opportunity_rate"))
    close_rate = rate(inputs.get("close_rate"))
    price = nonnegative(inputs.get("price"))
    churn_rate = rate(inputs.get("monthly_churn_rate"))
    customers = nonnegative(inputs.get("starting_customers"))
    target = nonnegative(inputs.get("annual_revenue_target"))
    rows: list[dict[str, Any]] = []

    for month in range(1, MONTHS + 1):
        visitors = traffic[month - 1]
        qualified = visitors * qualification_rate
        opportunities = qualified * opportunity_rate
        won = opportunities * close_rate
        churned = customers * churn_rate
        ending_customers = max(customers - churned + won, 0.0)
        average_customers = max((customers + ending_customers) / 2.0, 0.0)
        revenue = average_customers * price
        rows.append({
            "month": month,
            "traffic": rounded(visitors, 3),
            "qualified_leads": rounded(qualified, 3),
            "opportunities": rounded(opportunities, 3),
            "new_customers": rounded(won, 3),
            "churned_customers": rounded(churned, 3),
            "ending_customers": rounded(ending_customers, 3),
            "revenue": rounded(revenue),
        })
        customers = ending_customers

    annual_revenue = sum(float(row["revenue"]) for row in rows)
    required_customers = target / price if price > EPSILON else None
    funnel_yield = qualification_rate * opportunity_rate * close_rate
    implied_traffic = None
    if required_customers is not None and funnel_yield > EPSILON:
        implied_traffic = required_customers / 12.0 / funnel_yield
    return {
        "model": "deterministic_sales_funnel_v1",
        "months": rows,
        "12_month_revenue": rounded(annual_revenue),
        "annual_revenue_target": rounded(target),
        "target_gap": rounded(target - annual_revenue),
        "required_annual_customers": None if required_customers is None else rounded(required_customers, 3),
        "implied_monthly_traffic_for_target": None if implied_traffic is None else rounded(implied_traffic, 3),
        "funnel_yield": rounded(funnel_yield, 6),
        "ending_customers": rows[-1]["ending_customers"] if rows else customers,
    }


def calculate_workforce_capacity(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate hiring timing, ramped capacity, payroll and capacity gaps."""
    hires = inputs.get("headcount_plan", [])
    workload_hours = nonnegative(inputs.get("workload_hours_per_customer"))
    productive_hours = nonnegative(inputs.get("productive_hours_per_employee"), 120.0)
    default_ramp = max(0, int(nonnegative(inputs.get("default_ramp_months"), 1.0)))
    required_customers = nonnegative(inputs.get("required_monthly_customers"))
    normalized: list[dict[str, Any]] = []
    annual_payroll = 0.0
    if isinstance(hires, list):
        for item in hires[:50]:
            if not isinstance(item, dict):
                continue
            count = nonnegative(item.get("count"))
            salary = nonnegative(item.get("annual_salary"))
            start_month = max(1, int(nonnegative(item.get("start_month"), 1.0)))
            ramp_months = max(0, int(nonnegative(item.get("ramp_months"), float(default_ramp))))
            capacity_hours = nonnegative(item.get("monthly_capacity_hours"), productive_hours)
            annual_payroll += count * salary
            normalized.append({
                "role": str(item.get("role") or "Unspecified"),
                "count": count,
                "annual_salary": salary,
                "start_month": start_month,
                "ramp_months": ramp_months,
                "monthly_capacity_hours": capacity_hours,
            })

    months: list[dict[str, Any]] = []
    for month in range(1, MONTHS + 1):
        headcount = 0.0
        capacity_hours_total = 0.0
        payroll = 0.0
        for item in normalized:
            if month < item["start_month"]:
                continue
            active = month - item["start_month"]
            ramp = min(1.0, (active + 1) / item["ramp_months"]) if item["ramp_months"] else 1.0
            headcount += item["count"]
            capacity_hours_total += item["count"] * item["monthly_capacity_hours"] * ramp
            payroll += item["count"] * item["annual_salary"] / MONTHS
        capacity_customers = capacity_hours_total / workload_hours if workload_hours > EPSILON else None
        months.append({
            "month": month,
            "headcount": rounded(headcount, 3),
            "capacity_hours": rounded(capacity_hours_total, 3),
            "capacity_customers": None if capacity_customers is None else rounded(capacity_customers, 3),
            "payroll": rounded(payroll),
            "capacity_gap": bool(capacity_customers is not None and capacity_customers + EPSILON < required_customers),
        })

    return {
        "model": "deterministic_workforce_v1",
        "months": months,
        "annual_payroll": rounded(annual_payroll),
        "peak_headcount": max((row["headcount"] for row in months), default=0.0),
        "peak_capacity_hours": max((row["capacity_hours"] for row in months), default=0.0),
        "capacity_gap_months": [row["month"] for row in months if row["capacity_gap"]],
        "required_monthly_customers": rounded(required_customers, 3),
    }


def calculate_delivery_model(inputs: dict[str, Any]) -> dict[str, Any]:
    """Schedule engineering work against team capacity and phase dependencies."""
    phases = inputs.get("development_phases", [])
    team = inputs.get("engineering_team", [])
    schedule_buffer = rate(inputs.get("schedule_buffer"), 0.1)
    weekly_capacity = 0.0
    if isinstance(team, list):
        for member in team:
            if isinstance(member, dict):
                count = nonnegative(member.get("count"))
                capacity = nonnegative(member.get("weekly_capacity_weeks"), 1.0)
                if "weekly_capacity_hours" in member:
                    capacity = nonnegative(member.get("weekly_capacity_hours")) / 40.0
                weekly_capacity += count * capacity
    weekly_capacity = max(weekly_capacity, 1.0)
    rows: list[dict[str, Any]] = []
    cursor = 0.0
    total_effort = 0.0
    for index, phase in enumerate(phases[:30], start=1) if isinstance(phases, list) else []:
        if not isinstance(phase, dict):
            continue
        effort = nonnegative(phase.get("weeks"))
        dependencies = phase.get("dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = []
        dependency_names = {str(dep) for dep in dependencies}
        dependency_end = max((row["end_week"] for row in rows if row["name"] in dependency_names), default=0.0)
        start = max(cursor, dependency_end)
        duration = effort / weekly_capacity
        end = start + duration * (1.0 + schedule_buffer)
        rows.append({
            "index": index,
            "name": str(phase.get("name") or f"Phase {index}"),
            "effort_weeks": rounded(effort, 3),
            "start_week": rounded(start, 3),
            "end_week": rounded(end, 3),
            "dependencies": [str(dep) for dep in dependencies],
        })
        cursor = end
        total_effort += effort

    return {
        "model": "deterministic_delivery_v1",
        "weekly_team_capacity": rounded(weekly_capacity, 3),
        "schedule_buffer": rounded(schedule_buffer, 4),
        "phases": rows,
        "total_effort_weeks": rounded(total_effort, 3),
        "delivery_duration_weeks": rounded(max((row["end_week"] for row in rows), default=0.0), 3),
    }


def calculate_product_priorities(inputs: dict[str, Any]) -> dict[str, Any]:
    """Calculate impact/effort/strategy/dependency priority scores."""
    features = inputs.get("features", [])
    default_weight = nonnegative(inputs.get("strategic_weight"), 1.0)
    ranked: list[dict[str, Any]] = []
    for index, feature in enumerate(features[:100], start=1) if isinstance(features, list) else []:
        if not isinstance(feature, dict):
            continue
        impact = nonnegative(feature.get("impact"))
        effort = max(nonnegative(feature.get("effort")), EPSILON)
        strategic_weight = nonnegative(feature.get("strategic_weight"), default_weight)
        dependency_factor = max(nonnegative(feature.get("dependency_factor"), 1.0), EPSILON)
        score = impact / effort * strategic_weight * dependency_factor
        ranked.append({
            "index": index,
            "name": str(feature.get("name") or f"Feature {index}"),
            "impact": rounded(impact, 4),
            "effort": rounded(effort, 4),
            "strategic_weight": rounded(strategic_weight, 4),
            "dependency_factor": rounded(dependency_factor, 4),
            "priority_score": rounded(score, 6),
            "in_scope": bool(feature.get("in_scope", True)),
        })
    ranked.sort(key=lambda item: item["priority_score"], reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return {
        "model": "deterministic_product_priority_v1",
        "features": ranked,
        "mvp_features": [item for item in ranked if item["in_scope"]],
    }


def calculate_all_domains(state: dict[str, Any]) -> dict[str, Any]:
    """Run all Phase 2 calculators from LLM-proposed department assumptions."""
    cfo = state.get("cfo_formal", {}) or {}
    sales = state.get("head_of_sales_formal", {}) or {}
    coo = state.get("coo_formal", {}) or {}
    cto = state.get("cto_formal", {}) or {}
    pm = state.get("pm_formal", {}) or {}
    cmo = state.get("cmo_formal", {}) or {}

    budget = cfo.get("monthly_budget_by_category", {}) if isinstance(cfo, dict) else {}
    budget = budget if isinstance(budget, dict) else {}
    coo_payroll = _sum_numeric(coo.get("headcount_plan", []) if isinstance(coo, dict) else [], "annual_salary")
    payroll_monthly = nonnegative(budget.get("payroll"), coo_payroll / MONTHS)
    marketing_monthly = nonnegative(budget.get("marketing"), nonnegative(cmo.get("marketing_budget")) / MONTHS)
    infrastructure_monthly = nonnegative(budget.get("infrastructure"), nonnegative(cto.get("monthly_infrastructure_cost")))
    other_monthly = nonnegative(budget.get("other"))

    monthly_targets = sales.get("monthly_revenue_targets", []) if isinstance(sales, dict) else []
    new_customers = [item.get("new_customers", 0) for item in monthly_targets] if isinstance(monthly_targets, list) else []
    traffic = sales.get("monthly_traffic", sales.get("traffic_by_month", [])) if isinstance(sales, dict) else []

    finance = calculate_financial_model({
        "starting_cash": cfo.get("starting_cash", cfo.get("funding_required", 0)) if isinstance(cfo, dict) else 0,
        "price": sales.get("primary_price", 0) if isinstance(sales, dict) else 0,
        "starting_customers": sales.get("starting_customers", 0) if isinstance(sales, dict) else 0,
        "monthly_new_customers": new_customers,
        "churn_rate": sales.get("monthly_churn_rate", 0) if isinstance(sales, dict) else 0,
        "cogs_per_customer": cfo.get("cogs_per_customer", 0) if isinstance(cfo, dict) else 0,
        "cogs_percent_revenue": cfo.get("cogs_percent_revenue", 0) if isinstance(cfo, dict) else 0,
        "payroll_monthly": [payroll_monthly] * MONTHS,
        "infrastructure_monthly": [infrastructure_monthly] * MONTHS,
        "marketing_monthly": [marketing_monthly] * MONTHS,
        "other_monthly": [other_monthly] * MONTHS,
    })

    sales_model = calculate_sales_funnel({
        "monthly_traffic": traffic,
        "qualification_rate": sales.get("qualification_rate", 0) if isinstance(sales, dict) else 0,
        "opportunity_rate": sales.get("opportunity_rate", 0) if isinstance(sales, dict) else 0,
        "close_rate": sales.get("close_rate", sales.get("lead_to_customer_rate", 0)) if isinstance(sales, dict) else 0,
        "price": sales.get("primary_price", 0) if isinstance(sales, dict) else 0,
        "monthly_churn_rate": sales.get("monthly_churn_rate", 0) if isinstance(sales, dict) else 0,
        "starting_customers": sales.get("starting_customers", 0) if isinstance(sales, dict) else 0,
        "annual_revenue_target": sales.get("annual_revenue_target", 0) if isinstance(sales, dict) else 0,
    })

    workforce = calculate_workforce_capacity({
        "headcount_plan": coo.get("headcount_plan", []) if isinstance(coo, dict) else [],
        "workload_hours_per_customer": coo.get("workload_hours_per_customer", 0) if isinstance(coo, dict) else 0,
        "productive_hours_per_employee": coo.get("productive_hours_per_employee", 120) if isinstance(coo, dict) else 120,
        "default_ramp_months": coo.get("default_ramp_months", 1) if isinstance(coo, dict) else 1,
        "required_monthly_customers": max((row["new_customers"] for row in sales_model["months"]), default=0.0),
    })

    delivery = calculate_delivery_model({
        "development_phases": cto.get("development_phases", []) if isinstance(cto, dict) else [],
        "engineering_team": cto.get("engineering_team", []) if isinstance(cto, dict) else [],
        "schedule_buffer": cto.get("schedule_buffer", 0.1) if isinstance(cto, dict) else 0.1,
    })

    product = calculate_product_priorities({
        "features": pm.get("mvp_features", []) if isinstance(pm, dict) else [],
        "strategic_weight": pm.get("strategic_weight", 1.0) if isinstance(pm, dict) else 1.0,
    })

    return {
        "finance": finance,
        "sales": sales_model,
        "operations": workforce,
        "technical": delivery,
        "product": product,
    }
