"""Formal business-analysis primitives.

The LLMs remain responsible for domain interpretation, but all important
numeric claims are normalized into JSON and passed through deterministic
validation. Cross-department contradictions are detected from those claims
before an LLM adjudicates them.

No external service is required by this module.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

EPSILON = 0.02
MAX_CLAIMS = 80


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            parsed = float(cleaned)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def _positive(value: Any) -> bool:
    n = _number(value)
    return n is not None and n >= 0


def _close(a: float, b: float, tolerance: float = EPSILON) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= tolerance * scale


def parse_formal_output(raw: str) -> tuple[str, dict[str, Any], list[str]]:
    """Parse the required {report, analysis} envelope without trusting it."""
    errors: list[str] = []
    try:
        obj = json.loads(raw)
    except Exception as exc:
        return raw, {}, [f"Invalid JSON envelope: {exc}"]

    if not isinstance(obj, dict):
        return str(raw), {}, ["Formal output must be a JSON object."]

    report = obj.get("report", "")
    analysis = obj.get("analysis", {})
    if not isinstance(report, str):
        errors.append("report must be a string")
        report = str(report)
    if not isinstance(analysis, dict):
        errors.append("analysis must be an object")
        analysis = {}
    return report, analysis, errors


def _claim(
    claim_id: str,
    value: Any,
    *,
    unit: str = "",
    source: str = "derived",
    confidence: float = 0.7,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "value": value,
        "unit": unit,
        "source": source,
        "confidence": max(0.0, min(1.0, float(confidence))),
    }


def _numeric_claim(analysis: dict[str, Any], key: str, label: str, unit: str = "") -> dict[str, Any] | None:
    value = analysis.get(key)
    number = _number(value)
    if number is None:
        return None
    return _claim(label, number, unit=unit)


def validate_research(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    evidence = analysis.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []
    valid_evidence = []
    for item in evidence[:30]:
        if not isinstance(item, dict):
            errors.append("each evidence item must be an object")
            continue
        if not item.get("claim"):
            errors.append("evidence item missing claim")
        if not item.get("source_url"):
            warnings.append("evidence item has no source_url")
        valid_evidence.append(item)
    market = analysis.get("market", {})
    for key in ("tam", "sam", "som"):
        n = _number(market.get(key)) if isinstance(market, dict) else None
        if n is not None and n < 0:
            errors.append(f"market.{key} cannot be negative")
    if isinstance(market, dict):
        tam, sam, som = (_number(market.get(k)) for k in ("tam", "sam", "som"))
        if tam is not None and sam is not None and sam > tam:
            errors.append("SAM cannot exceed TAM")
        if sam is not None and som is not None and som > sam:
            errors.append("SOM cannot exceed SAM")
    claims = []
    if isinstance(market, dict):
        for key in ("tam", "sam", "som"):
            if _number(market.get(key)) is not None:
                claims.append(_claim(f"market.{key}", _number(market[key]), unit=market.get("currency", "")))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "evidence_count": len(valid_evidence)}


def validate_cfo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    startup_items = analysis.get("startup_costs", [])
    if not isinstance(startup_items, list):
        errors.append("startup_costs must be a list")
        startup_items = []
    startup_sum = 0.0
    for item in startup_items[:50]:
        amount = _number(item.get("amount")) if isinstance(item, dict) else None
        if amount is None:
            errors.append("every startup cost must have a numeric amount")
        elif amount < 0:
            errors.append("startup cost cannot be negative")
        else:
            startup_sum += amount
    monthly = _number(analysis.get("monthly_operating_cost"))
    if monthly is None or monthly < 0:
        errors.append("monthly_operating_cost must be a non-negative number")
        monthly = None

    ue = analysis.get("unit_economics", {})
    if not isinstance(ue, dict):
        errors.append("unit_economics must be an object")
        ue = {}
    cac, ltv, ratio = (_number(ue.get(k)) for k in ("cac", "ltv", "ltv_cac_ratio"))
    if cac is not None and cac <= 0:
        errors.append("CAC must be > 0")
    if ltv is not None and ltv < 0:
        errors.append("LTV cannot be negative")
    if cac and ltv is not None:
        derived_ratio = ltv / cac
        if ratio is not None and not _close(ratio, derived_ratio):
            errors.append(f"LTV:CAC ratio is inconsistent: reported {ratio:.3f}, derived {derived_ratio:.3f}")
        ratio = derived_ratio
    scenarios = analysis.get("revenue_scenarios", {})
    if not isinstance(scenarios, dict):
        errors.append("revenue_scenarios must be an object")
        scenarios = {}
    for scenario_name in ("conservative", "base", "optimistic"):
        if scenario_name in scenarios:
            scenario = scenarios[scenario_name]
            if not isinstance(scenario, dict):
                errors.append(f"revenue_scenarios.{scenario_name} must be an object")
                continue
            revenue = _number(scenario.get("annual_revenue"))
            if revenue is not None and revenue < 0:
                errors.append(f"{scenario_name} annual revenue cannot be negative")

    break_even = _number(analysis.get("break_even_month"))
    if break_even is not None and break_even < 0:
        errors.append("break_even_month cannot be negative")
    claims = [_claim("finance.startup_cost", startup_sum, unit=analysis.get("currency", ""))]
    if monthly is not None:
        claims.append(_claim("finance.monthly_operating_cost", monthly, unit=analysis.get("currency", "")))
    if cac is not None:
        claims.append(_claim("unit_economics.cac", cac, unit=analysis.get("currency", "")))
    if ltv is not None:
        claims.append(_claim("unit_economics.ltv", ltv, unit=analysis.get("currency", "")))
    if ratio is not None:
        claims.append(_claim("unit_economics.ltv_cac_ratio", ratio, unit="x"))
    if break_even is not None:
        claims.append(_claim("finance.break_even_month", break_even, unit="months"))
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "claims": claims,
        "derived": {"startup_cost_sum": round(startup_sum, 2), "ltv_cac_ratio": ratio},
    }


def validate_cto(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    phases = analysis.get("development_phases", [])
    if not isinstance(phases, list):
        errors.append("development_phases must be a list")
        phases = []
    total_weeks = 0.0
    for phase in phases[:30]:
        weeks = _number(phase.get("weeks")) if isinstance(phase, dict) else None
        if weeks is None or weeks <= 0:
            errors.append("each development phase needs positive weeks")
        else:
            total_weeks += weeks
    mvp_weeks = _number(analysis.get("mvp_weeks"))
    if mvp_weeks is not None and mvp_weeks <= 0:
        errors.append("mvp_weeks must be > 0")
    if mvp_weeks is not None and total_weeks and mvp_weeks + EPSILON < total_weeks:
        warnings.append("mvp_weeks is shorter than the sum of all listed development phases")
    build_cost = _number(analysis.get("engineering_build_cost"))
    infra_monthly = _number(analysis.get("monthly_infrastructure_cost"))
    for label, value in (("engineering_build_cost", build_cost), ("monthly_infrastructure_cost", infra_monthly)):
        if value is not None and value < 0:
            errors.append(f"{label} cannot be negative")
    claims = [_claim("technical.mvp_weeks", mvp_weeks, unit="weeks")] if mvp_weeks is not None else []
    if build_cost is not None:
        claims.append(_claim("technical.engineering_build_cost", build_cost, unit=analysis.get("currency", "")))
    if infra_monthly is not None:
        claims.append(_claim("technical.monthly_infrastructure_cost", infra_monthly, unit=analysis.get("currency", "")))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"phase_sum_weeks": round(total_weeks, 2)}}


def validate_cmo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    budget = _number(analysis.get("marketing_budget"))
    allocations = analysis.get("channel_allocations", [])
    if budget is not None and budget < 0:
        errors.append("marketing_budget cannot be negative")
    if not isinstance(allocations, list):
        errors.append("channel_allocations must be a list")
        allocations = []
    allocation_sum = sum((_number(x.get("amount")) or 0.0) for x in allocations if isinstance(x, dict))
    if budget is not None and not _close(allocation_sum, budget):
        errors.append(f"marketing allocations sum to {allocation_sum:.2f}, but budget is {budget:.2f}")
    claims = []
    if budget is not None:
        claims.append(_claim("marketing.budget", budget, unit=analysis.get("currency", "")))
    if allocations:
        claims.append(_claim("marketing.channel_allocation_total", allocation_sum, unit=analysis.get("currency", "")))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"allocation_sum": round(allocation_sum, 2)}}


def validate_sales(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    price = _number(analysis.get("primary_price"))
    annual_target = _number(analysis.get("annual_revenue_target"))
    conversion = _number(analysis.get("lead_to_customer_rate"))
    avg_customers = _number(analysis.get("average_monthly_new_customers"))
    if price is not None and price <= 0:
        errors.append("primary_price must be > 0")
    if annual_target is not None and annual_target < 0:
        errors.append("annual_revenue_target cannot be negative")
    if conversion is not None and not 0 <= conversion <= 1:
        errors.append("lead_to_customer_rate must be between 0 and 1")
    if avg_customers is not None and avg_customers < 0:
        errors.append("average_monthly_new_customers cannot be negative")
    derived_required_customers = None
    if annual_target is not None and price and price > 0:
        derived_required_customers = annual_target / price
        declared = _number(analysis.get("required_annual_customers"))
        if declared is not None and not _close(declared, derived_required_customers):
            errors.append("required_annual_customers is inconsistent with annual revenue target / price")
    claims = []
    if price is not None:
        claims.append(_claim("pricing.primary_price", price, unit=analysis.get("currency", "")))
    if annual_target is not None:
        claims.append(_claim("sales.annual_revenue_target", annual_target, unit=analysis.get("currency", "")))
    if derived_required_customers is not None:
        claims.append(_claim("sales.required_annual_customers", derived_required_customers, unit="customers"))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"required_annual_customers": derived_required_customers}}


def validate_coo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    hires = analysis.get("headcount_plan", [])
    if not isinstance(hires, list):
        errors.append("headcount_plan must be a list")
        hires = []
    annual_payroll = 0.0
    for person in hires[:50]:
        count = _number(person.get("count")) if isinstance(person, dict) else None
        salary = _number(person.get("annual_salary")) if isinstance(person, dict) else None
        if count is None or count < 0:
            errors.append("headcount entries require non-negative count")
        if salary is None or salary < 0:
            errors.append("headcount entries require non-negative annual_salary")
        if count is not None and salary is not None:
            annual_payroll += count * salary
    declared = _number(analysis.get("annual_payroll"))
    if declared is not None and not _close(declared, annual_payroll):
        errors.append(f"annual_payroll is inconsistent: declared {declared:.2f}, derived {annual_payroll:.2f}")
    monthly_payroll = annual_payroll / 12 if annual_payroll else 0.0
    claims = [_claim("operations.annual_payroll", annual_payroll, unit=analysis.get("currency", ""))]
    claims.append(_claim("operations.monthly_payroll", monthly_payroll, unit=analysis.get("currency", "")))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"annual_payroll": round(annual_payroll, 2)}}


def validate_pm(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    features = analysis.get("mvp_features", [])
    if not isinstance(features, list):
        errors.append("mvp_features must be a list")
        features = []
    scores = []
    for feature in features[:50]:
        if not isinstance(feature, dict):
            errors.append("each MVP feature must be an object")
            continue
        impact = _number(feature.get("impact"))
        effort = _number(feature.get("effort"))
        if impact is None or effort is None or effort <= 0:
            errors.append("each feature needs numeric impact and positive effort")
            continue
        if impact < 0:
            errors.append("feature impact cannot be negative")
        scores.append({"name": feature.get("name", ""), "score": impact / effort})
    scores.sort(key=lambda x: x["score"], reverse=True)
    claims = [_claim("product.mvp_feature_count", len(features), unit="features")]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"priority_order": scores}}

VALIDATORS = {
    "researcher": validate_research,
    "cfo": validate_cfo,
    "cto": validate_cto,
    "cmo": validate_cmo,
    "head_of_sales": validate_sales,
    "coo": validate_coo,
    "pm": validate_pm,
}


def validate_formal_analysis(agent_name: str, analysis: dict[str, Any]) -> dict[str, Any]:
    validator = VALIDATORS.get(agent_name)
    if validator is None:
        return {"valid": True, "errors": [], "warnings": [], "claims": []}
    result = validator(analysis)
    claims = result.get("claims", [])
    result["claims"] = claims[:MAX_CLAIMS]
    return result


def formalize_agent_output(agent_name: str, raw: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    report, analysis, parse_errors = parse_formal_output(raw)
    validation = validate_formal_analysis(agent_name, analysis)
    if parse_errors:
        validation["errors"] = parse_errors + validation.get("errors", [])
        validation["valid"] = False
    validation["agent"] = agent_name
    return report, analysis, validation


def _flatten_claims(formal_by_agent: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for agent, analysis in formal_by_agent.items():
        for claim in analysis.get("claims", []):
            if isinstance(claim, dict) and claim.get("id") is not None:
                item = dict(claim)
                item["agent"] = agent
                claims.append(item)
    return claims


def detect_contradictions(formal_by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Deterministically detect incompatible claims before LLM adjudication."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in _flatten_claims(formal_by_agent):
        grouped[str(claim["id"])].append(claim)

    contradictions: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for claim_id, items in grouped.items():
        numeric = [x for x in items if _number(x.get("value")) is not None]
        for i, left in enumerate(numeric):
            for right in numeric[i + 1:]:
                if left["agent"] == right["agent"]:
                    continue
                a = _number(left["value"])
                b = _number(right["value"])
                unit_left = str(left.get("unit", ""))
                unit_right = str(right.get("unit", ""))
                if unit_left and unit_right and unit_left != unit_right:
                    continue
                if not _close(a, b, tolerance=0.05):
                    pair = tuple(sorted((left["agent"], right["agent"])) + [claim_id])
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    contradictions.append({
                        "id": f"C{len(contradictions) + 1:03d}",
                        "claim_id": claim_id,
                        "type": "numeric_conflict",
                        "severity": "high" if max(abs(a), abs(b), 1.0) > 0 and abs(a-b) / max(abs(a), abs(b), 1.0) >= 0.25 else "medium",
                        "left": left,
                        "right": right,
                        "difference_ratio": abs(a-b) / max(abs(a), abs(b), 1.0),
                    })
    return {
        "contradictions": contradictions,
        "contradiction_count": len(contradictions),
        "claims_checked": len(_flatten_claims(formal_by_agent)),
        "claim_groups": len(grouped),
    }


def build_formal_snapshot(formal_by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validations = {}
    for agent, analysis in formal_by_agent.items():
        validations[agent] = validate_formal_analysis(agent, analysis)
    contradiction_report = detect_contradictions(formal_by_agent)
    errors = {agent: v["errors"] for agent, v in validations.items() if v.get("errors")}
    return {
        "validations": validations,
        "contradictions": contradiction_report["contradictions"],
        "contradiction_count": contradiction_report["contradiction_count"],
        "claims_checked": contradiction_report["claims_checked"],
        "validation_error_agents": errors,
    }


def compact_json(value: Any, limit: int = 12000) -> str:
    text = json.dumps(value, indent=2, ensure_ascii=False)
    return text[:limit]
