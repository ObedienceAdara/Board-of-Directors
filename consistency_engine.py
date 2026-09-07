"""Deterministic cross-department consistency checks."""

from __future__ import annotations

import math
from typing import Any


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace(",", "").replace("$", "").replace("usd", "").strip()
    multiplier = 1.0
    if text.endswith("k"):
        multiplier, text = 1_000.0, text[:-1]
    elif text.endswith("m"):
        multiplier, text = 1_000_000.0, text[:-1]
    elif text.endswith("b"):
        multiplier, text = 1_000_000_000.0, text[:-1]
    try:
        parsed = float(text) * multiplier
        return parsed if math.isfinite(parsed) else None
    except ValueError:
        return None


def close(a: float, b: float, tolerance: float = 0.05) -> bool:
    return abs(a - b) <= tolerance * max(abs(a), abs(b), 1.0)


def claim(contradiction_id: str, category: str, severity: str, agents: list[str], statement: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": contradiction_id,
        "category": category,
        "severity": severity,
        "agents": agents,
        "statement": statement,
        "evidence": evidence,
        "resolution_status": "pending_adjudication",
    }


def _currency_match(*currencies: str) -> bool:
    normalized = {value.strip().upper() for value in currencies if value.strip()}
    return len(normalized) <= 1


def _monthly_budget(analysis: dict[str, Any], category: str) -> float | None:
    budget = analysis.get("monthly_budget_by_category", {})
    if not isinstance(budget, dict):
        return None
    return number(budget.get(category))


def _cmo_monthly_budget(cmo: dict[str, Any]) -> float | None:
    budget = number(cmo.get("marketing_budget"))
    if budget is None:
        return None
    period = str(cmo.get("budget_period", "year")).strip().lower()
    if period in {"month", "monthly"}:
        return budget
    if period in {"quarter", "quarterly"}:
        return budget / 3.0
    if period in {"year", "annual", "yearly"}:
        return budget / 12.0
    return budget


def detect_cross_domain_contradictions(formal_by_agent: dict[str, dict[str, Any]], brief: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    brief = brief or {}
    cfo = formal_by_agent.get("cfo", {})
    cto = formal_by_agent.get("cto", {})
    cmo = formal_by_agent.get("cmo", {})
    coo = formal_by_agent.get("coo", {})
    sales = formal_by_agent.get("head_of_sales", {})
    research = formal_by_agent.get("researcher", {})

    cfo_currency = str(cfo.get("currency", ""))
    cmo_currency = str(cmo.get("currency", ""))
    cto_currency = str(cto.get("currency", ""))
    coo_currency = str(coo.get("currency", ""))
    sales_currency = str(sales.get("currency", ""))

    cfo_payroll = _monthly_budget(cfo, "payroll")
    coo_monthly_payroll = None
    headcount = coo.get("headcount_plan", [])
    if isinstance(headcount, list):
        annual = 0.0
        valid = True
        for item in headcount:
            if not isinstance(item, dict):
                valid = False
                break
            count = number(item.get("count"))
            salary = number(item.get("annual_salary"))
            if count is None or salary is None or count < 0 or salary < 0:
                valid = False
                break
            annual += count * salary
        if valid:
            coo_monthly_payroll = annual / 12.0

    cfo_infra = _monthly_budget(cfo, "infrastructure")
    cto_infra = number(cto.get("monthly_infrastructure_cost"))
    if cfo_infra is not None and cto_infra is not None and _currency_match(cfo_currency, cto_currency) and cfo_infra + max(1.0, abs(cfo_infra) * 0.05) < cto_infra:
        contradictions.append(claim("CD-001", "budget_capacity", "high", ["cfo", "cto"], "CFO infrastructure budget is below the CTO's explicit monthly infrastructure requirement.", {"cfo_monthly_infrastructure_budget": cfo_infra, "cto_monthly_infrastructure_cost": cto_infra}))
    if cfo_payroll is not None and coo_monthly_payroll is not None and _currency_match(cfo_currency, coo_currency) and cfo_payroll + max(1.0, abs(cfo_payroll) * 0.05) < coo_monthly_payroll:
        contradictions.append(claim("CD-002", "payroll_capacity", "high", ["cfo", "coo"], "CFO payroll budget is below the payroll implied by the COO headcount plan.", {"cfo_monthly_payroll_budget": cfo_payroll, "coo_derived_monthly_payroll": coo_monthly_payroll}))

    sales_target = number(sales.get("annual_revenue_target"))
    cfo_scenario = cfo.get("financial_scenarios", {})
    base_scenario = cfo_scenario.get("base", {}) if isinstance(cfo_scenario, dict) else {}
    if isinstance(base_scenario, dict):
        expected_price_factor = number(base_scenario.get("price_factor"))
        if expected_price_factor is not None and expected_price_factor <= 0:
            contradictions.append(claim("CD-003", "revenue_plan", "high", ["cfo"], "CFO base financial scenario has a non-positive price factor.", {"price_factor": expected_price_factor}))

    cmo_monthly = _cmo_monthly_budget(cmo)
    cfo_marketing = _monthly_budget(cfo, "marketing")
    if cfo_marketing is not None and cmo_monthly is not None and _currency_match(cfo_currency, cmo_currency) and not close(cfo_marketing, cmo_monthly, tolerance=0.15):
        contradictions.append(claim("CD-004", "marketing_budget", "medium", ["cfo", "cmo"], "CFO monthly marketing budget and CMO normalized monthly marketing budget are inconsistent.", {"cfo_monthly_marketing_budget": cfo_marketing, "cmo_monthly_marketing_budget": cmo_monthly, "cmo_budget_period": cmo.get("budget_period", "year")}))

    market = research.get("market", {}) if isinstance(research, dict) else {}
    som = number(market.get("som")) if isinstance(market, dict) else None
    if som is not None and sales_target is not None and som > 0 and sales_target > som * 1.05 and _currency_match(str(market.get("currency", "")), sales_currency):
        contradictions.append(claim("CD-005", "market_revenue", "high", ["researcher", "head_of_sales"], "Sales annual revenue target exceeds the Researcher's SOM estimate.", {"research_som": som, "sales_annual_revenue_target": sales_target}))

    cto_mvp = number(cto.get("mvp_weeks"))
    cmo_launch = number(cmo.get("launch_weeks"))
    if cto_mvp is not None and cmo_launch is not None and cto_mvp > cmo_launch + 2:
        contradictions.append(claim("CD-006", "timeline", "high", ["cto", "cmo"], "CTO's stated MVP estimate occurs materially after the CMO's planned launch window.", {"cto_mvp_weeks": cto_mvp, "cmo_launch_weeks": cmo_launch}))

    budget = number(brief.get("budget"))
    startup_items = cfo.get("startup_costs", [])
    startup_sum = sum(number(item.get("amount")) or 0 for item in startup_items if isinstance(item, dict)) if isinstance(startup_items, list) else 0.0
    if budget is not None and startup_sum > budget * 1.05:
        contradictions.append(claim("CD-007", "founder_budget", "high", ["cfo"], "The modeled startup costs exceed the budget supplied in the business brief.", {"brief_budget": budget, "startup_cost_total": startup_sum}))

    return contradictions


def consistency_bundle(brief: dict[str, Any], formal_by_agent: dict[str, dict[str, Any]], local_validations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    local_errors = {agent: validation.get("errors", []) for agent, validation in local_validations.items() if validation.get("errors")}
    cross = detect_cross_domain_contradictions(formal_by_agent, brief)
    return {
        "claims_checked": sum(len(v.get("claims", [])) for v in local_validations.values()),
        "local_validation_errors": local_errors,
        "cross_domain_contradictions": cross,
        "contradiction_count": len(cross),
        "integrity_status": "FAIL" if local_errors or cross else "PASS",
    }
