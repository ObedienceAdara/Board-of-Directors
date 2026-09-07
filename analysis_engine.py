"""Formal business-analysis primitives and strict domain contracts."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

EPSILON = 0.02
MAX_CLAIMS = 80
MONTHS = 12


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "").replace("$", "").replace("%", "")
        multiplier = 1.0
        if cleaned.endswith("k"):
            multiplier, cleaned = 1_000.0, cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier, cleaned = 1_000_000.0, cleaned[:-1]
        elif cleaned.endswith("b"):
            multiplier, cleaned = 1_000_000_000.0, cleaned[:-1]
        try:
            parsed = float(cleaned) * multiplier
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def _required_number(analysis: dict[str, Any], key: str, errors: list[str], *, minimum: float | None = 0.0) -> float | None:
    value = _number(analysis.get(key))
    if value is None:
        errors.append(f"{key} must be provided as a finite number")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{key} must be >= {minimum}")
        return None
    return value


def _close(a: float, b: float, tolerance: float = EPSILON) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= tolerance * scale


def parse_formal_output(raw: str) -> tuple[str, dict[str, Any], list[str]]:
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


def _claim(claim_id: str, value: Any, *, unit: str = "", source: str = "derived", confidence: float = 0.7) -> dict[str, Any]:
    return {
        "id": claim_id,
        "value": value,
        "unit": unit,
        "source": source,
        "confidence": max(0.0, min(1.0, float(confidence))),
    }


def _validate_schedule(value: Any, key: str, errors: list[str]) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    if len(value) > MONTHS:
        errors.append(f"{key} cannot contain more than {MONTHS} values")
    for item in value[:MONTHS]:
        number = _number(item)
        if number is None:
            errors.append(f"{key} contains a non-numeric value")
        elif number < 0:
            errors.append(f"{key} contains a negative value")
    return value[:MONTHS]


def validate_research(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    market = analysis.get("market", {})
    if not isinstance(market, dict):
        errors.append("market must be an object")
        market = {}
    values = {}
    for key in ("tam", "sam", "som"):
        value = _number(market.get(key))
        values[key] = value
        if value is not None and value < 0:
            errors.append(f"market.{key} cannot be negative")
    tam, sam, som = values["tam"], values["sam"], values["som"]
    if tam is not None and sam is not None and sam > tam:
        errors.append("SAM cannot exceed TAM")
    if sam is not None and som is not None and som > sam:
        errors.append("SOM cannot exceed SAM")

    evidence = analysis.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []
    valid_evidence: list[dict[str, Any]] = []
    for item in evidence[:30]:
        if not isinstance(item, dict):
            errors.append("each evidence item must be an object")
            continue
        if not item.get("claim"):
            errors.append("evidence item missing claim")
        source_url = str(item.get("source_url", "")).strip()
        claim_id = item.get("claim_id")
        if not source_url and claim_id:
            errors.append("claim-addressable evidence must include source_url")
        valid_evidence.append(item)
    if values["tam"] is None and values["sam"] is None and values["som"] is None:
        warnings.append("No numeric market-size estimates were supplied")

    claims = [_claim(f"market.{key}", value, unit=str(market.get("currency", ""))) for key, value in values.items() if value is not None]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "evidence_count": len(valid_evidence)}


def validate_cfo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    currency = str(analysis.get("currency", "")).strip()
    if not currency:
        errors.append("currency must be provided")
    starting_cash = _required_number(analysis, "starting_cash", errors)
    startup_items = analysis.get("startup_costs")
    if not isinstance(startup_items, list):
        errors.append("startup_costs must be a list")
        startup_items = []
    startup_sum = 0.0
    for item in startup_items[:50]:
        if not isinstance(item, dict):
            errors.append("each startup cost must be an object")
            continue
        amount = _number(item.get("amount"))
        if amount is None or amount < 0:
            errors.append("each startup cost must have a non-negative numeric amount")
        else:
            startup_sum += amount

    cogs_unit = _number(analysis.get("cogs_per_customer"))
    cogs_rate = _number(analysis.get("cogs_percent_revenue"))
    if cogs_unit is None and cogs_rate is None:
        errors.append("at least one of cogs_per_customer or cogs_percent_revenue must be provided")
    if cogs_unit is not None and cogs_unit < 0:
        errors.append("cogs_per_customer cannot be negative")
    if cogs_rate is not None and not 0 <= cogs_rate <= 100:
        errors.append("cogs_percent_revenue must be between 0 and 100")

    schedules = {}
    for key in ("monthly_infrastructure_schedule", "monthly_marketing_schedule", "monthly_other_opex_schedule"):
        schedules[key] = _validate_schedule(analysis.get(key), key, errors)
    budget = analysis.get("monthly_budget_by_category", {})
    if not isinstance(budget, dict):
        errors.append("monthly_budget_by_category must be an object")
        budget = {}
    for key in ("payroll", "marketing", "infrastructure", "other"):
        value = _number(budget.get(key))
        if value is not None and value < 0:
            errors.append(f"monthly_budget_by_category.{key} cannot be negative")

    scenarios = analysis.get("financial_scenarios", {})
    if not isinstance(scenarios, dict):
        errors.append("financial_scenarios must be an object")
        scenarios = {}
    for name in ("conservative", "base", "optimistic"):
        definition = scenarios.get(name)
        if definition is None:
            continue
        if not isinstance(definition, dict):
            errors.append(f"financial_scenarios.{name} must be an object")
            continue
        for key in ("customer_growth_factor", "price_factor"):
            value = _number(definition.get(key))
            if value is not None and value < 0:
                errors.append(f"financial_scenarios.{name}.{key} cannot be negative")
        cogs_value = _number(definition.get("cogs_percent_revenue"))
        if cogs_value is not None and not 0 <= cogs_value <= 100:
            errors.append(f"financial_scenarios.{name}.cogs_percent_revenue must be between 0 and 100")

    claims = [_claim("finance.starting_cash", starting_cash, unit=currency), _claim("finance.startup_cost", startup_sum, unit=currency)]
    if cogs_unit is not None:
        claims.append(_claim("finance.cogs_per_customer", cogs_unit, unit=currency))
    if cogs_rate is not None:
        claims.append(_claim("finance.cogs_percent_revenue", cogs_rate / 100.0, unit="ratio"))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"startup_cost_sum": round(startup_sum, 2)}}


def _phase_dependency_errors(phases: list[Any], errors: list[str]) -> float:
    names: list[str] = []
    phase_map: dict[str, dict[str, Any]] = {}
    total = 0.0
    for item in phases[:30]:
        if not isinstance(item, dict):
            errors.append("each development phase must be an object")
            continue
        name = str(item.get("name") or "").strip()
        weeks = _number(item.get("weeks"))
        if not name:
            errors.append("each development phase must have a name")
            continue
        if name in phase_map:
            errors.append(f"duplicate development phase name: {name}")
        phase_map[name] = item
        names.append(name)
        if weeks is None or weeks <= 0:
            errors.append(f"phase '{name}' must have positive weeks")
        else:
            total += weeks
        deps = item.get("dependencies", [])
        if not isinstance(deps, list):
            errors.append(f"phase '{name}' dependencies must be a list")
    valid_names = set(names)
    for name, item in phase_map.items():
        deps = [str(dep).strip() for dep in item.get("dependencies", []) if str(dep).strip()]
        for dep in deps:
            if dep not in valid_names:
                errors.append(f"phase '{name}' references unknown dependency '{dep}'")
        if name in deps:
            errors.append(f"phase '{name}' cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            errors.append(f"development phase dependency cycle detected at '{name}'")
            return
        if name in visited:
            return
        visiting.add(name)
        for dep in phase_map[name].get("dependencies", []):
            dep_name = str(dep).strip()
            if dep_name in phase_map:
                visit(dep_name)
        visiting.remove(name)
        visited.add(name)

    for name in names:
        visit(name)
    return total


def validate_cto(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    phases = analysis.get("development_phases")
    if not isinstance(phases, list) or not phases:
        errors.append("development_phases must be a non-empty list")
        phases = []
    total_weeks = _phase_dependency_errors(phases, errors)

    team = analysis.get("engineering_team")
    if not isinstance(team, list) or not team:
        errors.append("engineering_team must be a non-empty list")
        team = []
    team_capacity = 0.0
    for item in team[:30]:
        if not isinstance(item, dict):
            errors.append("each engineering_team entry must be an object")
            continue
        count = _number(item.get("count"))
        weekly_weeks = _number(item.get("weekly_capacity_weeks"))
        weekly_hours = _number(item.get("weekly_capacity_hours"))
        if count is None or count < 0:
            errors.append("engineering_team count must be non-negative")
        if weekly_weeks is None and weekly_hours is None:
            errors.append("engineering_team entry needs weekly_capacity_weeks or weekly_capacity_hours")
        if weekly_weeks is not None and weekly_weeks < 0:
            errors.append("weekly_capacity_weeks cannot be negative")
        if weekly_hours is not None and weekly_hours < 0:
            errors.append("weekly_capacity_hours cannot be negative")
        if count is not None:
            if weekly_hours is not None:
                team_capacity += count * weekly_hours / 40.0
            elif weekly_weeks is not None:
                team_capacity += count * weekly_weeks
    if team_capacity <= EPSILON:
        errors.append("engineering_team total weekly capacity must be greater than zero")

    buffer = _number(analysis.get("schedule_buffer"))
    if buffer is not None and not 0 <= buffer <= 1:
        errors.append("schedule_buffer must be between 0 and 1")
    for key in ("engineering_build_cost", "monthly_infrastructure_cost"):
        value = _number(analysis.get(key))
        if value is not None and value < 0:
            errors.append(f"{key} cannot be negative")
    currency = str(analysis.get("currency", "")).strip()
    if not currency:
        errors.append("currency must be provided")
    claims = []
    mvp_weeks = _number(analysis.get("mvp_weeks"))
    if mvp_weeks is not None:
        if mvp_weeks <= 0:
            errors.append("mvp_weeks must be > 0 when supplied")
        claims.append(_claim("technical.mvp_weeks", mvp_weeks, unit="weeks"))
    build_cost = _number(analysis.get("engineering_build_cost"))
    infra = _number(analysis.get("monthly_infrastructure_cost"))
    if build_cost is not None:
        claims.append(_claim("technical.engineering_build_cost", build_cost, unit=currency))
    if infra is not None:
        claims.append(_claim("technical.monthly_infrastructure_cost", infra, unit=currency))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"phase_sum_weeks": round(total_weeks, 2), "weekly_team_capacity": round(team_capacity, 3)}}


def validate_cmo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    currency = str(analysis.get("currency", "")).strip()
    if not currency:
        errors.append("currency must be provided")
    budget = _required_number(analysis, "marketing_budget", errors)
    allocations = analysis.get("channel_allocations")
    if not isinstance(allocations, list) or not allocations:
        errors.append("channel_allocations must be a non-empty list")
        allocations = []
    allocation_sum = 0.0
    for item in allocations[:50]:
        if not isinstance(item, dict):
            errors.append("each channel allocation must be an object")
            continue
        amount = _number(item.get("amount"))
        if amount is None or amount < 0:
            errors.append("each channel allocation must have a non-negative numeric amount")
        else:
            allocation_sum += amount
        for key in ("expected_leads", "expected_customers"):
            value = _number(item.get(key))
            if value is not None and value < 0:
                errors.append(f"{key} cannot be negative")
    if budget is not None and not _close(allocation_sum, budget, tolerance=0.01):
        errors.append(f"marketing allocations sum to {allocation_sum:.2f}, but budget is {budget:.2f}")
    launch_weeks = _number(analysis.get("launch_weeks"))
    if launch_weeks is not None and launch_weeks < 0:
        errors.append("launch_weeks cannot be negative")
    claims = [_claim("marketing.budget", budget, unit=currency), _claim("marketing.channel_allocation_total", allocation_sum, unit=currency)]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"allocation_sum": round(allocation_sum, 2)}}


def validate_sales(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    currency = str(analysis.get("currency", "")).strip()
    if not currency:
        errors.append("currency must be provided")
    price = _required_number(analysis, "primary_price", errors, minimum=EPSILON)
    starting_customers = _required_number(analysis, "starting_customers", errors)
    annual_target = _required_number(analysis, "annual_revenue_target", errors)
    traffic = analysis.get("monthly_traffic")
    if not isinstance(traffic, list) or not traffic:
        errors.append("monthly_traffic must be a non-empty list")
        traffic = []
    else:
        _validate_schedule(traffic, "monthly_traffic", errors)
    for key in ("qualification_rate", "opportunity_rate", "close_rate", "lead_to_customer_rate", "monthly_churn_rate"):
        value = _number(analysis.get(key))
        if value is not None and not 0 <= value <= 100:
            errors.append(f"{key} must be between 0 and 1 or 0 and 100 percent")
    avg_customers = _number(analysis.get("average_monthly_new_customers"))
    if avg_customers is not None and avg_customers < 0:
        errors.append("average_monthly_new_customers cannot be negative")
    price_period = str(analysis.get("price_period", "month")).strip().lower()
    if price_period not in {"month", "year", "one_time", "transaction", "monthly", "annual", "yearly", "once", "per_transaction"}:
        errors.append("price_period must be month, year, one_time, or transaction")
    required_declared = _number(analysis.get("required_annual_sales"))
    if required_declared is None:
        required_declared = _number(analysis.get("required_annual_customers"))
    if annual_target is not None and price is not None:
        monthly_equivalent = price if price_period in {"month", "monthly"} else price / 12 if price_period in {"year", "annual", "yearly"} else price
        required = annual_target / (monthly_equivalent * 12) if monthly_equivalent > EPSILON and price_period in {"month", "monthly", "year", "annual", "yearly"} else annual_target / price
        if required_declared is not None and not _close(required_declared, required, tolerance=0.02):
            errors.append("required_annual_sales/customers is inconsistent with annual_revenue_target and price_period")
    claims = []
    if price is not None:
        claims.append(_claim("pricing.primary_price", price, unit=currency))
    if annual_target is not None:
        claims.append(_claim("sales.annual_revenue_target", annual_target, unit=currency))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {}}


def validate_coo(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    currency = str(analysis.get("currency", "")).strip()
    if not currency:
        errors.append("currency must be provided")
    hires = analysis.get("headcount_plan")
    if not isinstance(hires, list) or not hires:
        errors.append("headcount_plan must be a non-empty list")
        hires = []
    annual_payroll = 0.0
    for person in hires[:50]:
        if not isinstance(person, dict):
            errors.append("each headcount entry must be an object")
            continue
        count = _number(person.get("count"))
        salary = _number(person.get("annual_salary"))
        start = _number(person.get("start_month"))
        ramp = _number(person.get("ramp_months"))
        hours = _number(person.get("monthly_capacity_hours"))
        if count is None or count < 0:
            errors.append("headcount entries require non-negative count")
        if salary is None or salary < 0:
            errors.append("headcount entries require non-negative annual_salary")
        if start is None or not 1 <= start <= MONTHS:
            errors.append(f"start_month must be between 1 and {MONTHS}")
        if ramp is not None and ramp < 0:
            errors.append("ramp_months cannot be negative")
        if hours is not None and hours < 0:
            errors.append("monthly_capacity_hours cannot be negative")
        if count is not None and salary is not None:
            annual_payroll += count * salary
    workload = _required_number(analysis, "workload_hours_per_customer", errors)
    productive = _number(analysis.get("productive_hours_per_employee"))
    if productive is not None and productive < 0:
        errors.append("productive_hours_per_employee cannot be negative")
    declared = _number(analysis.get("annual_payroll"))
    if declared is not None and not _close(declared, annual_payroll, tolerance=0.02):
        errors.append(f"annual_payroll is inconsistent: declared {declared:.2f}, derived {annual_payroll:.2f}")
    claims = [_claim("operations.annual_payroll", annual_payroll, unit=currency), _claim("operations.monthly_payroll", annual_payroll / 12, unit=currency)]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"annual_payroll": round(annual_payroll, 2)}}


def validate_pm(analysis: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    features = analysis.get("mvp_features")
    if not isinstance(features, list) or not features:
        errors.append("mvp_features must be a non-empty list")
        features = []
    scores = []
    for feature in features[:50]:
        if not isinstance(feature, dict):
            errors.append("each MVP feature must be an object")
            continue
        impact = _number(feature.get("impact"))
        effort = _number(feature.get("effort"))
        strategic = _number(feature.get("strategic_weight"))
        dependency = _number(feature.get("dependency_factor"))
        if impact is None or impact < 0:
            errors.append("feature impact must be non-negative")
        if effort is None or effort <= 0:
            errors.append("feature effort must be positive")
        if strategic is not None and strategic < 0:
            errors.append("feature strategic_weight cannot be negative")
        if dependency is not None and dependency <= 0:
            errors.append("feature dependency_factor must be positive")
        if impact is not None and effort is not None and effort > 0:
            scores.append({"name": feature.get("name", ""), "score": impact / effort})
    claims = [_claim("product.mvp_feature_count", len(features), unit="features")]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims, "derived": {"priority_order": sorted(scores, key=lambda x: x["score"], reverse=True)}}

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
    result["claims"] = list(result.get("claims", []))[:MAX_CLAIMS]
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
        for claim_item in analysis.get("claims", []) if isinstance(analysis, dict) else []:
            if isinstance(claim_item, dict) and claim_item.get("id") is not None:
                item = dict(claim_item)
                item["agent"] = agent
                claims.append(item)
    return claims


def detect_contradictions(formal_by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim_item in _flatten_claims(formal_by_agent):
        grouped[str(claim_item["id"])].append(claim_item)
    contradictions: list[dict[str, Any]] = []
    for claim_id, items in grouped.items():
        numeric = [item for item in items if _number(item.get("value")) is not None]
        for index, left in enumerate(numeric):
            for right in numeric[index + 1:]:
                if left["agent"] == right["agent"]:
                    continue
                a = _number(left["value"])
                b = _number(right["value"])
                unit_left = str(left.get("unit", ""))
                unit_right = str(right.get("unit", ""))
                if unit_left and unit_right and unit_left != unit_right:
                    continue
                if not _close(a, b, tolerance=0.05):
                    contradictions.append({
                        "id": f"C{len(contradictions) + 1:03d}",
                        "claim_id": claim_id,
                        "type": "numeric_conflict",
                        "severity": "high" if abs(a - b) / max(abs(a), abs(b), 1.0) >= 0.25 else "medium",
                        "left": left,
                        "right": right,
                        "difference_ratio": abs(a - b) / max(abs(a), abs(b), 1.0),
                    })
    return {"contradictions": contradictions, "contradiction_count": len(contradictions), "claims_checked": len(_flatten_claims(formal_by_agent)), "claim_groups": len(grouped)}


def build_formal_snapshot(formal_by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validations = {agent: validate_formal_analysis(agent, analysis) for agent, analysis in formal_by_agent.items()}
    contradiction_report = detect_contradictions(formal_by_agent)
    errors = {agent: validation["errors"] for agent, validation in validations.items() if validation.get("errors")}
    return {"validations": validations, "contradictions": contradiction_report["contradictions"], "contradiction_count": contradiction_report["contradiction_count"], "claims_checked": contradiction_report["claims_checked"], "validation_error_agents": errors}


def compact_json(value: Any, limit: int = 12000) -> str:
    text = json.dumps(value, indent=2, ensure_ascii=False)
    return text[:limit]
