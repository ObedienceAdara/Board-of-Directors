"""Deterministic Phase 2 domain calculators."""

from __future__ import annotations

from math import isfinite
from typing import Any

MONTHS = 12
EPSILON = 1e-9
VALID_PRICE_PERIODS = {"month", "year", "one_time", "transaction"}


def number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        result = float(value)
        return result if isfinite(result) else default
    if isinstance(value, str):
        text = value.replace(",", "").replace("$", "").replace("%", "").strip().lower()
        multiplier = 1.0
        if text.endswith("k"): multiplier, text = 1_000.0, text[:-1]
        elif text.endswith("m"): multiplier, text = 1_000_000.0, text[:-1]
        elif text.endswith("b"): multiplier, text = 1_000_000_000.0, text[:-1]
        try:
            result = float(text) * multiplier
            return result if isfinite(result) else default
        except ValueError:
            return default
    return default


def nonnegative(value: Any, default: float = 0.0) -> float:
    result = number(value, None)
    if result is None: return float(default)
    if result < 0: raise ValueError(f"Expected a non-negative number, got {result}")
    return result


def rate(value: Any, default: float = 0.0) -> float:
    result = number(value, None)
    if result is None: return float(default)
    if result < 0: raise ValueError(f"Expected a non-negative rate, got {result}")
    if result > 1: result /= 100.0
    if result > 1: raise ValueError(f"Rate must be between 0 and 1 or 0 and 100 percent, got {result}")
    return result


def _monthly(values: Any, *, default: float = 0.0) -> list[float]:
    if values is None: return [default] * MONTHS
    if not isinstance(values, list): raise ValueError("Monthly schedule must be a list, a scalar is not a valid schedule")
    if not values: return [default] * MONTHS
    if len(values) > MONTHS: raise ValueError(f"Monthly schedule cannot contain more than {MONTHS} values")
    output = [nonnegative(value) for value in values]
    return output + [output[-1]] * (MONTHS - len(output))


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _validate_price_period(value: Any) -> str:
    period = str(value or "month").strip().lower()
    period = {"monthly": "month", "annual": "year", "yearly": "year", "once": "one_time", "per_transaction": "transaction"}.get(period, period)
    if period not in VALID_PRICE_PERIODS: raise ValueError(f"Unsupported price_period '{period}'")
    return period


def _price_per_month(price: float, period: str) -> float:
    return price if period == "month" else price / 12.0 if period == "year" else price


def _recurring(period: str) -> bool:
    return period in {"month", "year"}


def calculate_financial_model(inputs: dict[str, Any]) -> dict[str, Any]:
    starting_cash = nonnegative(inputs.get("starting_cash"))
    startup_costs = nonnegative(inputs.get("startup_costs"))
    price = nonnegative(inputs.get("price"))
    price_period = _validate_price_period(inputs.get("price_period", "month"))
    customers = nonnegative(inputs.get("starting_customers"))
    churn = rate(inputs.get("churn_rate"))
    cogs_unit = nonnegative(inputs.get("cogs_per_customer"))
    cogs_rate = rate(inputs.get("cogs_percent_revenue"))
    new_customers = _monthly(inputs.get("monthly_new_customers"))
    payroll = _monthly(inputs.get("payroll_monthly"))
    infrastructure = _monthly(inputs.get("infrastructure_monthly"))
    marketing = _monthly(inputs.get("marketing_monthly"))
    other = _monthly(inputs.get("other_monthly"))
    cash = starting_cash - startup_costs
    opening_cash = cash
    break_even_month: int | None = None
    cash_depletion_month: int | None = None
    months: list[dict[str, Any]] = []

    for month in range(1, MONTHS + 1):
        new = new_customers[month - 1]
        churned = min(customers, customers * churn)
        ending_customers = max(customers - churned + new, 0.0)
        average_customers = (customers + ending_customers) / 2.0
        revenue = average_customers * _price_per_month(price, price_period) if _recurring(price_period) else new * price
        cogs = revenue * cogs_rate + average_customers * cogs_unit
        gross_profit = revenue - cogs
        fixed_opex = payroll[month - 1] + infrastructure[month - 1] + marketing[month - 1] + other[month - 1]
        total_costs = cogs + fixed_opex
        net_burn = total_costs - revenue
        cash_before = cash
        cash -= net_burn
        if break_even_month is None and net_burn <= EPSILON: break_even_month = month
        if cash_depletion_month is None and cash <= EPSILON: cash_depletion_month = month
        months.append({
            "month": month, "customers": _round(ending_customers, 3), "new_customers": _round(new, 3), "churned_customers": _round(churned, 3),
            "revenue": _round(revenue), "cogs": _round(cogs), "gross_profit": _round(gross_profit),
            "gross_margin": _round(gross_profit / revenue, 4) if revenue > EPSILON else 0.0,
            "payroll": _round(payroll[month - 1]), "infrastructure": _round(infrastructure[month - 1]), "marketing": _round(marketing[month - 1]), "other_opex": _round(other[month - 1]),
            "operating_costs": _round(total_costs), "net_burn": _round(net_burn), "cash_before": _round(cash_before), "ending_cash": _round(cash),
            "contribution_margin": _round(revenue - cogs - marketing[month - 1]), "contribution_margin_ratio": _round((revenue - cogs - marketing[month - 1]) / revenue, 4) if revenue > EPSILON else 0.0,
        })
        customers = ending_customers

    revenue_total = sum(row["revenue"] for row in months)
    cogs_total = sum(row["cogs"] for row in months)
    marketing_total = sum(row["marketing"] for row in months)
    opex_total = sum(row["payroll"] + row["infrastructure"] + row["marketing"] + row["other_opex"] for row in months)
    contribution_total = revenue_total - cogs_total - marketing_total
    minimum_cash = min([opening_cash] + [row["ending_cash"] for row in months])
    runway: float | None
    if opening_cash <= EPSILON:
        runway = 0.0 if any(row["net_burn"] > EPSILON for row in months) else None
    elif cash_depletion_month is not None:
        depleted = months[cash_depletion_month - 1]
        burn = float(depleted["net_burn"])
        runway = (cash_depletion_month - 1) + (max(float(depleted["cash_before"]), 0.0) / burn if burn > EPSILON else 0.0)
    else:
        runway = None
    return {
        "model": "deterministic_financial_v2", "opening_cash_after_startup": _round(opening_cash), "startup_costs": _round(startup_costs), "price_period": price_period,
        "months": months, "monthly_revenue": months[-1]["revenue"] if months else 0.0, "monthly_costs": months[-1]["operating_costs"] if months else 0.0,
        "gross_profit": _round(revenue_total - cogs_total), "gross_margin": _round((revenue_total - cogs_total) / revenue_total, 4) if revenue_total > EPSILON else 0.0,
        "contribution_margin": _round(contribution_total), "contribution_margin_ratio": _round(contribution_total / revenue_total, 4) if revenue_total > EPSILON else 0.0,
        "net_burn": months[-1]["net_burn"] if months else 0.0, "ending_cash": _round(months[-1]["ending_cash"] if months else opening_cash),
        "runway_months": None if runway is None else _round(runway), "cash_depletion_month": cash_depletion_month, "cash_positive_through_forecast": cash_depletion_month is None,
        "break_even_month": break_even_month, "12_month_revenue": _round(revenue_total), "12_month_cogs": _round(cogs_total), "12_month_opex": _round(opex_total),
        "12_month_operating_profit": _round(revenue_total - cogs_total - opex_total), "minimum_cash_balance": _round(minimum_cash),
    }


def calculate_financial_scenarios(base_inputs: dict[str, Any], scenarios: Any = None) -> dict[str, Any]:
    definitions = scenarios if isinstance(scenarios, dict) else {}
    defaults = {"conservative": {"customer_growth_factor": 0.75, "price_factor": 0.95, "cogs_percent_revenue": None}, "base": {"customer_growth_factor": 1.0, "price_factor": 1.0, "cogs_percent_revenue": None}, "optimistic": {"customer_growth_factor": 1.25, "price_factor": 1.05, "cogs_percent_revenue": None}}
    base_new = _monthly(base_inputs.get("monthly_new_customers"))
    output: dict[str, Any] = {}
    for name, default in defaults.items():
        definition = definitions.get(name, {}) if isinstance(definitions, dict) else {}
        if not isinstance(definition, dict): definition = {}
        growth = nonnegative(definition.get("customer_growth_factor"), default["customer_growth_factor"])
        price_factor = nonnegative(definition.get("price_factor"), default["price_factor"])
        scenario = dict(base_inputs)
        scenario["monthly_new_customers"] = [value * growth for value in base_new]
        scenario["price"] = nonnegative(base_inputs.get("price")) * price_factor
        if definition.get("cogs_percent_revenue") is not None: scenario["cogs_percent_revenue"] = definition["cogs_percent_revenue"]
        output[name] = {"assumptions": {"customer_growth_factor": growth, "price_factor": price_factor, "cogs_percent_revenue": rate(scenario.get("cogs_percent_revenue"))}, "calculation": calculate_financial_model(scenario)}
    return {"model": "deterministic_financial_scenarios_v2", "scenarios": output}


def _forecast_sales(traffic: list[float], qualification: float, opportunity: float, close: float, price: float, period: str, churn: float, starting_customers: float) -> list[dict[str, Any]]:
    customers = starting_customers
    rows: list[dict[str, Any]] = []
    unit_month = _price_per_month(price, period)
    for month, visitors in enumerate(traffic, 1):
        qualified = visitors * qualification; opportunities = qualified * opportunity; won = opportunities * close
        churned = min(customers, customers * churn); ending = max(customers - churned + won, 0.0); average = (customers + ending) / 2.0
        revenue = average * unit_month if _recurring(period) else won * price
        rows.append({"month": month, "traffic": _round(visitors, 3), "qualified_leads": _round(qualified, 3), "opportunities": _round(opportunities, 3), "new_customers": _round(won, 3), "churned_customers": _round(churned, 3), "ending_customers": _round(ending, 3), "revenue": _round(revenue)})
        customers = ending
    return rows


def calculate_sales_funnel(inputs: dict[str, Any]) -> dict[str, Any]:
    traffic = _monthly(inputs.get("monthly_traffic")); qualification = rate(inputs.get("qualification_rate")); opportunity = rate(inputs.get("opportunity_rate")); close = rate(inputs.get("close_rate"))
    price = nonnegative(inputs.get("price")); period = _validate_price_period(inputs.get("price_period", "month")); churn = rate(inputs.get("monthly_churn_rate")); starting = nonnegative(inputs.get("starting_customers")); target = nonnegative(inputs.get("annual_revenue_target"))
    rows = _forecast_sales(traffic, qualification, opportunity, close, price, period, churn, starting)
    annual_revenue = sum(row["revenue"] for row in rows)
    unit_annual_revenue = price * 12 if period == "month" else price if period == "year" else price
    required_units = target / unit_annual_revenue if price > EPSILON else None
    result: dict[str, Any] = {
        "model": "deterministic_sales_funnel_v2", "price_period": period, "monthly_unit_revenue": _round(_price_per_month(price, period)), "months": rows,
        "12_month_revenue": _round(annual_revenue), "annual_revenue_target": _round(target), "target_gap": _round(target - annual_revenue),
        "required_annual_sales": None if _recurring(period) else (None if required_units is None else _round(required_units, 3)),
        "required_average_active_customers": required_units if _recurring(period) else None,
        "annual_revenue_per_active_customer": _round(unit_annual_revenue),
        "funnel_yield": _round(qualification * opportunity * close, 6), "ending_customers": rows[-1]["ending_customers"] if rows else 0.0,
    }
    if _recurring(period) and target > 0:
        # Solve the monthly traffic level needed for the modeled 12-month target,
        # including churn and the starting customer base.
        def revenue_for(traffic_level: float) -> float:
            test_rows = _forecast_sales([traffic_level] * MONTHS, qualification, opportunity, close, price, period, churn, starting)
            return sum(row["revenue"] for row in test_rows)
        low, high = 0.0, 1.0
        while high < 1_000_000 and revenue_for(high) < target: high *= 2
        if revenue_for(high) >= target:
            for _ in range(60):
                mid = (low + high) / 2
                if revenue_for(mid) >= target: high = mid
                else: low = mid
            result["implied_monthly_traffic_for_target"] = _round(high, 3)
        else:
            result["implied_monthly_traffic_for_target"] = None
    else:
        yield_rate = qualification * opportunity * close
        result["implied_monthly_traffic_for_target"] = None if required_units is None or yield_rate <= EPSILON else _round(required_units / 12 / yield_rate, 3)
    return result


def calculate_workforce_capacity(inputs: dict[str, Any]) -> dict[str, Any]:
    hires = inputs.get("headcount_plan", []); workload = nonnegative(inputs.get("workload_hours_per_customer")); productive = nonnegative(inputs.get("productive_hours_per_employee"), 120.0); default_ramp = max(0, int(nonnegative(inputs.get("default_ramp_months"), 1.0))); required = nonnegative(inputs.get("required_monthly_customers"))
    if not isinstance(hires, list): raise ValueError("headcount_plan must be a list")
    normalized: list[dict[str, Any]] = []; runrate = 0.0
    for item in hires[:50]:
        if not isinstance(item, dict): raise ValueError("each headcount entry must be an object")
        count = nonnegative(item.get("count")); salary = nonnegative(item.get("annual_salary")); start = int(number(item.get("start_month"), 1.0) or 1); ramp = int(number(item.get("ramp_months"), float(default_ramp)) or 0); hours = nonnegative(item.get("monthly_capacity_hours"), productive)
        if start < 1 or start > MONTHS: raise ValueError(f"start_month must be between 1 and {MONTHS}")
        if ramp < 0: raise ValueError("ramp_months cannot be negative")
        runrate += count * salary; normalized.append({"count": count, "salary": salary, "start": start, "ramp": ramp, "hours": hours})
    months: list[dict[str, Any]] = []
    for month in range(1, MONTHS + 1):
        headcount = capacity_hours = payroll = 0.0
        for item in normalized:
            if month < item["start"]: continue
            active = month - item["start"]; ramp_factor = min(1.0, (active + 1) / item["ramp"]) if item["ramp"] else 1.0
            headcount += item["count"]; capacity_hours += item["count"] * item["hours"] * ramp_factor; payroll += item["count"] * item["salary"] / MONTHS
        cap_customers = capacity_hours / workload if workload > EPSILON else None
        months.append({"month": month, "headcount": _round(headcount, 3), "capacity_hours": _round(capacity_hours, 3), "capacity_customers": None if cap_customers is None else _round(cap_customers, 3), "payroll": _round(payroll), "capacity_gap": bool(cap_customers is not None and cap_customers + EPSILON < required)})
    return {"model": "deterministic_workforce_v2", "months": months, "12_month_payroll": _round(sum(row["payroll"] for row in months)), "annual_payroll_run_rate": _round(runrate), "peak_headcount": max((row["headcount"] for row in months), default=0.0), "peak_capacity_hours": max((row["capacity_hours"] for row in months), default=0.0), "peak_capacity_customers": _round(max((row["capacity_customers"] or 0.0 for row in months), default=0.0), 3), "required_monthly_customers": _round(required, 3), "capacity_gap_months": [row["month"] for row in months if row["capacity_gap"]]}


def calculate_delivery_model(inputs: dict[str, Any]) -> dict[str, Any]:
    phases = inputs.get("development_phases", []); team = inputs.get("engineering_team", []); buffer = rate(inputs.get("schedule_buffer"), 0.1)
    if not isinstance(phases, list): raise ValueError("development_phases must be a list")
    if not isinstance(team, list): raise ValueError("engineering_team must be a list")
    capacity = 0.0
    for member in team:
        if not isinstance(member, dict): raise ValueError("each engineering team entry must be an object")
        count = nonnegative(member.get("count")); weekly = nonnegative(member.get("weekly_capacity_weeks"), 1.0)
        if member.get("weekly_capacity_hours") is not None: weekly = nonnegative(member.get("weekly_capacity_hours")) / 40.0
        capacity += count * weekly
    if capacity <= EPSILON: raise ValueError("Engineering team capacity must be greater than zero")
    normalized: dict[str, dict[str, Any]] = {}; order: list[str] = []
    for index, phase in enumerate(phases[:30], 1):
        if not isinstance(phase, dict): raise ValueError(f"development phase {index} must be an object")
        name = str(phase.get("name") or f"Phase {index}").strip(); effort = nonnegative(phase.get("weeks")); deps = phase.get("dependencies", [])
        if name in normalized: raise ValueError(f"Duplicate development phase name: '{name}'")
        if effort <= EPSILON: raise ValueError(f"Phase '{name}' must have positive effort weeks")
        if not isinstance(deps, list): raise ValueError(f"Phase '{name}' dependencies must be a list")
        normalized[name] = {"index": index, "name": name, "effort": effort, "deps": [str(dep).strip() for dep in deps if str(dep).strip()]}; order.append(name)
    names = set(normalized)
    for name, phase in normalized.items():
        unknown = sorted(set(phase["deps"]) - names)
        if unknown: raise ValueError(f"Phase '{name}' references unknown dependencies: {unknown}")
        if name in phase["deps"]: raise ValueError(f"Phase '{name}' cannot depend on itself")
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(name: str) -> None:
        if name in visiting: raise ValueError(f"Development phase dependency cycle detected at '{name}'")
        if name in visited: return
        visiting.add(name)
        for dep in normalized[name]["deps"]: visit(dep)
        visiting.remove(name); visited.add(name)
    for name in order: visit(name)
    remaining = {name: data["effort"] * (1.0 + buffer) for name, data in normalized.items()}; completed: dict[str, float] = {}; active: set[str] = set(); starts: dict[str, float] = {}; ends: dict[str, float] = {}; current = 0.0
    while len(completed) < len(normalized):
        for name in order:
            if name not in completed and name not in active and all(dep in completed for dep in normalized[name]["deps"]): starts[name] = current; active.add(name)
        if not active: raise RuntimeError("Unable to schedule development phases")
        share = capacity / len(active); delta = min(remaining[name] / share for name in active); current += delta
        finished = [name for name in active if remaining[name] <= share * delta + EPSILON]
        for name in finished: remaining[name] = 0.0; ends[name] = current; active.remove(name); completed[name] = current
        for name in active: remaining[name] = max(0.0, remaining[name] - share * delta)
    rows = [{"index": normalized[name]["index"], "name": name, "effort_weeks": _round(normalized[name]["effort"], 3), "start_week": _round(starts[name], 3), "end_week": _round(ends[name], 3), "dependencies": normalized[name]["deps"]} for name in order]
    rows.sort(key=lambda row: (row["start_week"], row["index"]))
    return {"model": "deterministic_delivery_v2", "weekly_team_capacity": _round(capacity, 3), "schedule_buffer": _round(buffer, 4), "phases": rows, "total_effort_weeks": _round(sum(row["effort_weeks"] for row in rows), 3), "delivery_duration_weeks": _round(max((row["end_week"] for row in rows), default=0.0), 3), "dependency_validation": "passed", "parallelized": len({row["start_week"] for row in rows}) < len(rows)}


def calculate_product_priorities(inputs: dict[str, Any]) -> dict[str, Any]:
    features = inputs.get("features", []); default_weight = nonnegative(inputs.get("strategic_weight"), 1.0)
    if not isinstance(features, list): raise ValueError("features must be a list")
    ranked: list[dict[str, Any]] = []
    for index, feature in enumerate(features[:100], 1):
        if not isinstance(feature, dict): raise ValueError("each feature must be an object")
        impact = nonnegative(feature.get("impact")); effort = nonnegative(feature.get("effort")); strategic = nonnegative(feature.get("strategic_weight"), default_weight); dependency = nonnegative(feature.get("dependency_factor"), 1.0)
        if effort <= EPSILON: raise ValueError(f"Feature '{feature.get('name', index)}' must have positive effort")
        if dependency <= EPSILON: raise ValueError(f"Feature '{feature.get('name', index)}' must have a positive dependency_factor")
        ranked.append({"index": index, "name": str(feature.get("name") or f"Feature {index}"), "impact": _round(impact, 4), "effort": _round(effort, 4), "strategic_weight": _round(strategic, 4), "dependency_factor": _round(dependency, 4), "priority_score": _round(impact / effort * strategic * dependency, 6), "in_scope": bool(feature.get("in_scope", True))})
    ranked.sort(key=lambda item: (-item["priority_score"], item["name"].lower()))
    for rank, item in enumerate(ranked, 1): item["rank"] = rank
    return {"model": "deterministic_product_priority_v2", "features": ranked, "mvp_features": [item for item in ranked if item["in_scope"]]}
