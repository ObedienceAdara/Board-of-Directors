"""Deterministic cross-department consistency checks.

This module is intentionally non-LLM. It turns normalized departmental
analysis into explicit conflict candidates. An LLM may adjudicate the
candidates later, but it cannot invent whether arithmetic checks failed.
"""

from __future__ import annotations

import math
from typing import Any


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace(",", "").replace("$", "")
    multiplier = 1.0
    if text.endswith("k"):
        multiplier, text = 1_000.0, text[:-1]
    elif text.endswith("m"):
        multiplier, text = 1_000_000.0, text[:-1]
    elif text.endswith("b"):
        multiplier, text = 1_000_000_000.0, text[:-1]
    text = text.replace("usd", "").strip()
    try:
        parsed = float(text) * multiplier
        return parsed if math.isfinite(parsed) else None
    except ValueError:
        return None


def close(a: float, b: float, tolerance: float = 0.05) -> bool:
    return abs(a - b) <= tolerance * max(abs(a), abs(b), 1.0)


def claim(
    contradiction_id: str,
    category: str,
    severity: str,
    agents: list[str],
    statement: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": contradiction_id,
        "category": category,
        "severity": severity,
        "agents": agents,
        "statement": statement,
        "evidence": evidence,
        "resolution_status": "pending_adjudication",
    }


def detect_cross_domain_contradictions(
    formal_by_agent: dict[str, dict[str, Any]],
    brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Check business relationships that cannot be inferred from same-key matches."""
    contradictions: list[dict[str, Any]] = []
    brief = brief or {}
    cfo = formal_by_agent.get("cfo", {})
    cto = formal_by_agent.get("cto", {})
    cmo = formal_by_agent.get("cmo", {})
    coo = formal_by_agent.get("coo", {})
    sales = formal_by_agent.get("head_of_sales", {})
    research = formal_by_agent.get("researcher", {})

    cfo_currency = str(cfo.get("currency", "")).upper()
    cmo_currency = str(cmo.get("currency", "")).upper()
    cto_currency = str(cto.get("currency", "")).upper()
    coo_currency = str(coo.get("currency", "")).upper()
    sales_currency = str(sales.get("currency", "")).upper()

    # CFO operating budget must cover the operating components explicitly
    # claimed by CTO and COO. This is a feasibility relationship, not an
    # identical-value claim.
    cfo_monthly = number(cfo.get("monthly_operating_cost"))
    infra = number(cto.get("monthly_infrastructure_cost"))
    payroll = number(coo.get("monthly_operating_payroll", coo.get("annual_payroll")))
    if payroll is not None and "monthly_operating_payroll" not in coo:
        payroll /= 12.0
    currencies_match = not ({cfo_currency, cto_currency, coo_currency} - {"", cfo_currency}) or len({x for x in (cfo_currency, cto_currency, coo_currency) if x}) == 1
    if cfo_monthly is not None and infra is not None and payroll is not None and currencies_match:
        required = infra + payroll
        if required > cfo_monthly * 1.05:
            contradictions.append(claim(
                "CD-001", "budget_capacity", "high", ["cfo", "cto", "coo"],
                "CFO monthly operating budget is lower than the CTO infrastructure cost plus COO payroll.",
                {"cfo_monthly_operating_cost": cfo_monthly, "cto_monthly_infrastructure_cost": infra, "coo_monthly_payroll": payroll, "minimum_required": required},
            ))

    # CFO base-case annual revenue and Sales target must describe the same
    # planning horizon closely enough to be reconciled.
    base = cfo.get("revenue_scenarios", {}).get("base", {}) if isinstance(cfo.get("revenue_scenarios"), dict) else {}
    cfo_revenue = number(base.get("annual_revenue")) if isinstance(base, dict) else None
    sales_revenue = number(sales.get("annual_revenue_target"))
    if cfo_revenue is not None and sales_revenue is not None and cfo_revenue > 0 and sales_revenue > 0 and cfo_currency == sales_currency:
        if not close(cfo_revenue, sales_revenue, tolerance=0.25):
            contradictions.append(claim(
                "CD-002", "revenue_plan", "medium", ["cfo", "head_of_sales"],
                "CFO base-case annual revenue and Sales annual revenue target materially disagree.",
                {"cfo_base_annual_revenue": cfo_revenue, "sales_annual_revenue_target": sales_revenue},
            ))

    # CFO's explicit monthly marketing budget and CMO's requested marketing
    # budget should reconcile where the CFO provided a category budget.
    categories = cfo.get("monthly_budget_by_category", {})
    if isinstance(categories, dict):
        finance_marketing = number(categories.get("marketing"))
        cmo_budget = number(cmo.get("marketing_budget"))
        if finance_marketing is not None and cmo_budget is not None and cfo_currency == cmo_currency and not close(finance_marketing, cmo_budget, tolerance=0.15):
            contradictions.append(claim(
                "CD-003", "marketing_budget", "medium", ["cfo", "cmo"],
                "CFO monthly marketing budget and CMO marketing budget are inconsistent.",
                {"cfo_marketing_budget": finance_marketing, "cmo_marketing_budget": cmo_budget},
            ))

    # Research model: TAM >= SAM >= SOM is already validated locally, but
    # detect the more subtle case where the business claims a target larger
    # than the serviceable market.
    market = research.get("market", {}) if isinstance(research, dict) else {}
    som = number(market.get("som")) if isinstance(market, dict) else None
    if som is not None and sales_revenue is not None and som > 0 and sales_revenue > som * 1.05:
        contradictions.append(claim(
            "CD-004", "market_revenue", "high", ["researcher", "head_of_sales"],
            "Sales annual revenue target exceeds the Researcher's SOM estimate.",
            {"research_som": som, "sales_annual_revenue_target": sales_revenue},
        ))

    # Timeline consistency: CTO's MVP estimate cannot be materially later than
    # CMO's launch milestone labelled launch-ready.
    cto_weeks = number(cto.get("mvp_weeks"))
    launch_weeks = number(cmo.get("launch_weeks"))
    if cto_weeks is not None and launch_weeks is not None and cto_weeks > launch_weeks + 2:
        contradictions.append(claim(
            "CD-005", "timeline", "high", ["cto", "cmo"],
            "CTO's MVP completion estimate occurs after the CMO's planned launch window.",
            {"cto_mvp_weeks": cto_weeks, "cmo_launch_weeks": launch_weeks},
        ))

    # Brief budget vs explicit CFO startup cost.
    budget = number(brief.get("budget"))
    startup_items = cfo.get("startup_costs", [])
    startup_sum = sum((number(item.get("amount")) or 0) for item in startup_items if isinstance(item, dict))
    if budget is not None and startup_sum > budget * 1.05:
        contradictions.append(claim(
            "CD-006", "founder_budget", "high", ["cfo"],
            "The modeled startup costs exceed the budget supplied in the business brief.",
            {"brief_budget": budget, "startup_cost_total": startup_sum},
        ))

    return contradictions


def consistency_bundle(
    brief: dict[str, Any],
    formal_by_agent: dict[str, dict[str, Any]],
    local_validations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    local_errors = {
        agent: validation.get("errors", [])
        for agent, validation in local_validations.items()
        if validation.get("errors")
    }
    cross = detect_cross_domain_contradictions(formal_by_agent, brief)
    return {
        "claims_checked": sum(len(v.get("claims", [])) for v in local_validations.values()),
        "local_validation_errors": local_errors,
        "cross_domain_contradictions": cross,
        "contradiction_count": len(cross),
        "integrity_status": "FAIL" if local_errors or cross else "PASS",
    }
