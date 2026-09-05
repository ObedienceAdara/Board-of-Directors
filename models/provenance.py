"""Evidence and decision provenance models for the board.

The ledger records lineage without inventing provenance. A source can only be
marked as retrieved when the evidence payload explicitly carries a retrieval
 timestamp. Otherwise the ledger keeps retrieval time as ``None`` and records
the ledger capture time separately.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

PROVENANCE_SCHEMA_VERSION = "1.0"
MAX_LEDGER_CLAIMS = 160
MAX_LEDGER_EVIDENCE = 160
MAX_LEDGER_SOURCES = 120
MAX_LEDGER_TRANSFORMATIONS = 120
MAX_LEDGER_DECISIONS = 40


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            number = float(cleaned)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _clamp_confidence(value: Any, default: float = 0.7) -> float:
    number = _finite_number(value)
    return round(max(0.0, min(1.0, default if number is None else number)), 3)


def _text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _analysis_confidence(analysis: dict[str, Any]) -> float:
    return _clamp_confidence(analysis.get("confidence"), 0.7)


def _claim_type(claim_id: str) -> str:
    return {
        "market": "market_size",
        "finance": "financial_metric",
        "unit_economics": "unit_economics",
        "technical": "technical_metric",
        "marketing": "marketing_metric",
        "sales": "sales_metric",
        "pricing": "pricing",
        "operations": "operating_metric",
        "product": "product_metric",
    }.get(claim_id.split(".", 1)[0], "business_metric")


def _source_identity(url: str, title: str) -> str:
    return _stable_id("SRC", f"{url.strip()}|{title.strip()}")


def _make_source(evidence: dict[str, Any], captured_at: str) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    url = _text(evidence.get("source_url"), 1200)
    if not url:
        return None, None
    title = _text(evidence.get("source_title") or evidence.get("title") or evidence.get("source_name"), 400)
    publisher = _text(evidence.get("publisher") or evidence.get("source_publisher") or evidence.get("source_name"), 300)
    retrieved_at = _text(evidence.get("retrieved_at"), 80) or None
    provider = _text(evidence.get("provider"), 80) or None
    query = _text(evidence.get("query"), 700) or None
    rank = evidence.get("rank") if isinstance(evidence.get("rank"), int) else None
    source_id = _source_identity(url, title)
    return (
        {
            "source_id": source_id,
            "url": url,
            "title": title or url,
            "publisher": publisher or None,
            "retrieved_at": retrieved_at,
            "retrieval_metadata": {
                "provider": provider,
                "query": query,
                "rank": rank,
                "retrieval_method": "live_web_search" if provider else "external_source",
                "retrieval_timestamp_recorded": retrieved_at is not None,
                "captured_at": captured_at,
            },
        },
        {
            "evidence_id": "",
            "source_id": source_id,
            "evidence_type": "source_excerpt",
            "claim_id": _text(evidence.get("claim_id"), 180) or None,
            "claim_text": _text(evidence.get("claim"), 700),
            "value": evidence.get("value"),
            "unit": _text(evidence.get("unit"), 80),
            "excerpt": _text(evidence.get("evidence_excerpt") or evidence.get("retrieved_context") or evidence.get("context"), 1800),
            "captured_at": captured_at,
        },
    )


def _research_evidence(analysis: dict[str, Any], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    for index, item in enumerate(analysis.get("evidence", [])[:60] if isinstance(analysis.get("evidence"), list) else [], start=1):
        if not isinstance(item, dict):
            continue
        source, evidence = _make_source(item, captured_at)
        if source is None or evidence is None:
            continue
        evidence["evidence_id"] = f"EVID-{index:04d}"
        evidence_records.append(evidence)
        if not any(existing["source_id"] == source["source_id"] for existing in sources):
            sources.append(source)
    return sources[:MAX_LEDGER_SOURCES], evidence_records[:MAX_LEDGER_EVIDENCE]


def _claim_matches_evidence(claim_id: str, value: Any, unit: str, evidence: dict[str, Any]) -> bool:
    explicit_id = _text(evidence.get("claim_id"), 180)
    if explicit_id:
        return explicit_id == claim_id
    text = " ".join(_text(evidence.get(key), 700).lower() for key in ("claim", "evidence_excerpt", "retrieved_context"))
    metric_tokens = [token for token in claim_id.rsplit(".", 1)[-1].replace("_", " ").split() if len(token) > 2]
    has_metric = bool(metric_tokens) and sum(token in text for token in metric_tokens) >= max(1, len(metric_tokens) - 1)
    number = _finite_number(value)
    evidence_number = _finite_number(evidence.get("value"))
    same_value = number is not None and evidence_number is not None and abs(number - evidence_number) <= max(abs(number), 1.0) * 0.001
    ev_unit = _text(evidence.get("unit"), 80).lower()
    same_unit = not unit or not ev_unit or unit.lower() == ev_unit
    return same_value and same_unit and has_metric


def _formula_for_claim(claim_id: str) -> tuple[str, list[str]] | None:
    return {
        "sales.required_annual_customers": ("sales.annual_revenue_target / pricing.primary_price", ["sales.annual_revenue_target", "pricing.primary_price"]),
        "unit_economics.ltv_cac_ratio": ("unit_economics.ltv / unit_economics.cac", ["unit_economics.ltv", "unit_economics.cac"]),
        "operations.monthly_payroll": ("operations.annual_payroll / 12", ["operations.annual_payroll"]),
        "finance.startup_cost": ("sum(finance.startup_cost.item.<n>)", []),
        "operations.annual_payroll": ("sum(operations.payroll.item.<n>)", []),
        "marketing.channel_allocation_total": ("sum(marketing.channel.<n>.amount)", []),
        "technical.development_phase_sum_weeks": ("sum(technical.development_phase.<n>.weeks)", []),
    }.get(claim_id)


def _component_claims(agent: str, analysis: dict[str, Any], currency: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    confidence = _analysis_confidence(analysis)
    if agent == "cfo" and isinstance(analysis.get("startup_costs"), list):
        for index, item in enumerate(analysis["startup_costs"][:50], 1):
            if isinstance(item, dict) and _finite_number(item.get("amount")) is not None:
                result.append({"claim_id": f"finance.startup_cost.item.{index}", "value": float(item["amount"]), "unit": currency, "claim_type": "cost_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("name"), 200)})
    if agent == "coo" and isinstance(analysis.get("headcount_plan"), list):
        for index, item in enumerate(analysis["headcount_plan"][:50], 1):
            if not isinstance(item, dict):
                continue
            count, salary = _finite_number(item.get("count")), _finite_number(item.get("annual_salary"))
            if count is not None and salary is not None:
                result.append({"claim_id": f"operations.payroll.item.{index}", "value": count * salary, "unit": currency, "claim_type": "payroll_component", "method": "derived", "formula": f"{count:g} * {salary:g}", "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("role"), 200)})
    if agent == "cmo" and isinstance(analysis.get("channel_allocations"), list):
        for index, item in enumerate(analysis["channel_allocations"][:50], 1):
            if isinstance(item, dict) and _finite_number(item.get("amount")) is not None:
                result.append({"claim_id": f"marketing.channel.{index}.amount", "value": float(item["amount"]), "unit": currency, "claim_type": "marketing_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("channel"), 200)})
    if agent == "cto" and isinstance(analysis.get("development_phases"), list):
        for index, item in enumerate(analysis["development_phases"][:30], 1):
            if isinstance(item, dict) and _finite_number(item.get("weeks")) is not None:
                result.append({"claim_id": f"technical.development_phase.{index}.weeks", "value": float(item["weeks"]), "unit": "weeks", "claim_type": "timeline_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("name"), 200)})
    return result


def _dependencies(claim_id: str, analysis: dict[str, Any]) -> list[str]:
    formula = _formula_for_claim(claim_id)
    if formula is None:
        return []
    _, direct = formula
    if direct:
        return direct
    if claim_id == "finance.startup_cost":
        return [f"finance.startup_cost.item.{i}" for i, x in enumerate(analysis.get("startup_costs", [])[:50], 1) if isinstance(x, dict) and _finite_number(x.get("amount")) is not None]
    if claim_id == "operations.annual_payroll":
        return [f"operations.payroll.item.{i}" for i, x in enumerate(analysis.get("headcount_plan", [])[:50], 1) if isinstance(x, dict) and _finite_number(x.get("count")) is not None and _finite_number(x.get("annual_salary")) is not None]
    if claim_id == "marketing.channel_allocation_total":
        return [f"marketing.channel.{i}.amount" for i, x in enumerate(analysis.get("channel_allocations", [])[:50], 1) if isinstance(x, dict) and _finite_number(x.get("amount")) is not None]
    if claim_id == "technical.development_phase_sum_weeks":
        return [f"technical.development_phase.{i}.weeks" for i, x in enumerate(analysis.get("development_phases", [])[:30], 1) if isinstance(x, dict) and _finite_number(x.get("weeks")) is not None]
    return []


def build_provenance_ledger(state: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    captured_at = generated_at or utc_now()
    research = state.get("researcher_formal", {}) or {}
    sources, evidence_records = _research_evidence(research if isinstance(research, dict) else {}, captured_at)
    evidence_index = {item["evidence_id"]: item for item in evidence_records}
    source_ids_by_evidence = {item_id: item["source_id"] for item_id, item in evidence_index.items()}
    claims: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []

    for agent in ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"):
        analysis = state.get(f"{agent}_formal", {}) or {}
        validation = state.get(f"{agent}_validation", {}) or {}
        if not isinstance(analysis, dict) or not isinstance(validation, dict):
            continue
        currency = _text(analysis.get("currency"), 40)
        claims.extend(_component_claims(agent, analysis, currency))
        for raw in (validation.get("claims", []) if isinstance(validation.get("claims"), list) else [])[:MAX_LEDGER_CLAIMS]:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            claim_id = str(raw["id"])
            formula_info = _formula_for_claim(claim_id)
            dependencies = _dependencies(claim_id, analysis)
            method = "derived" if formula_info else "agent_assertion"
            formula = formula_info[0] if formula_info else None
            evidence_refs: list[str] = []
            source_refs: list[str] = []
            if agent == "researcher":
                for evidence_id, evidence in evidence_index.items():
                    if _claim_matches_evidence(claim_id, raw.get("value"), str(raw.get("unit", "")), evidence):
                        evidence_refs = [evidence_id]
                        source_refs = [source_ids_by_evidence[evidence_id]]
                        method = "reported"
                        break
            record = {
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claims) + 1:04d}",
                "value": raw.get("value"),
                "unit": _text(raw.get("unit"), 80),
                "claim_type": _claim_type(claim_id),
                "method": method,
                "formula": formula,
                "dependencies": dependencies,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
                "agent": agent,
                "confidence": _clamp_confidence(raw.get("confidence"), _analysis_confidence(analysis)),
                "status": "validation_error" if validation.get("errors") else "validated",
            }
            claims.append(record)
            if method == "derived":
                transformations.append({
                    "transformation_id": f"TX-{len(transformations) + 1:04d}",
                    "output_claim_id": claim_id,
                    "operation": "deterministic_formula",
                    "formula": formula,
                    "dependency_claims": dependencies,
                    "agent": agent,
                    "deterministic": True,
                    "created_at": captured_at,
                })

    cto = state.get("cto_formal", {}) or {}
    if isinstance(cto, dict) and isinstance(cto.get("development_phases"), list):
        phases = [x for x in cto["development_phases"][:30] if isinstance(x, dict) and _finite_number(x.get("weeks")) is not None]
        if phases:
            claim_id = "technical.development_phase_sum_weeks"
            dependencies = _dependencies(claim_id, cto)
            claims.append({
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claims) + 1:04d}",
                "value": round(sum(float(x["weeks"]) for x in phases), 3),
                "unit": "weeks",
                "claim_type": "technical_metric",
                "method": "derived",
                "formula": "sum(technical.development_phase.<n>.weeks)",
                "dependencies": dependencies,
                "evidence_refs": [], "source_refs": [], "agent": "cto",
                "confidence": _analysis_confidence(cto),
                "status": "validation_error" if (state.get("cto_validation", {}) or {}).get("errors") else "validated",
            })
            transformations.append({"transformation_id": f"TX-{len(transformations) + 1:04d}", "output_claim_id": claim_id, "operation": "deterministic_formula", "formula": "sum(technical.development_phase.<n>.weeks)", "dependency_claims": dependencies, "agent": "cto", "deterministic": True, "created_at": captured_at})

    claim_ids = sorted({str(x["claim_id"]) for x in claims if x.get("claim_id")})
    contradictions = [str(x["id"]) for x in state.get("deterministic_contradictions", []) or [] if isinstance(x, dict) and x.get("id")]
    decisions = [{
        "decision_id": "board.recommendation",
        "decision_type": "board_recommendation",
        "agent": "ceo",
        "decision_text": _text(state.get("final_board_report"), 2400),
        "claim_refs": claim_ids,
        "contradiction_refs": contradictions,
        "consistency_status": _text(state.get("consistency_status"), 80) or "NOT_RUN",
        "created_at": captured_at,
    }]
    adjudication = state.get("contradiction_adjudication", {}) or {}
    for issue in (adjudication.get("issues", []) if isinstance(adjudication, dict) and isinstance(adjudication.get("issues"), list) else [])[:MAX_LEDGER_DECISIONS - 1]:
        if isinstance(issue, dict) and issue.get("id"):
            decisions.append({"decision_id": f"contradiction.{issue['id']}", "decision_type": "contradiction_adjudication", "agent": "ceo", "decision_text": _text(issue.get("resolution") or issue.get("rationale"), 1500), "claim_refs": [str(issue["claim_id"])] if issue.get("claim_id") else claim_ids[:20], "contradiction_refs": [str(issue["id"])], "verdict": _text(issue.get("verdict"), 80) or "INSUFFICIENT_EVIDENCE", "confidence": _clamp_confidence(issue.get("confidence"), 0.5), "created_at": captured_at})

    total = len(claims)
    sourced = sum(1 for x in claims if x.get("source_refs"))
    derived = sum(1 for x in claims if x.get("method") == "derived")
    asserted = sum(1 for x in claims if x.get("method") == "agent_assertion")
    invalid = sum(1 for x in claims if x.get("status") == "validation_error")
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": captured_at,
        "claims": claims[:MAX_LEDGER_CLAIMS],
        "evidence": evidence_records[:MAX_LEDGER_EVIDENCE],
        "sources": sources[:MAX_LEDGER_SOURCES],
        "transformations": transformations[:MAX_LEDGER_TRANSFORMATIONS],
        "decisions": decisions[:MAX_LEDGER_DECISIONS],
        "summary": {
            "total_claims": total,
            "sourced_claims": sourced,
            "derived_claims": derived,
            "agent_assertions": asserted,
            "validation_error_claims": invalid,
            "evidence_records": len(evidence_records),
            "source_records": len(sources),
            "transformation_records": len(transformations),
            "decision_records": len(decisions),
            "evidence_coverage_ratio": round(sourced / total, 3) if total else 0.0,
            "unsupported_claims": max(total - sourced - derived, 0),
        },
    }


def validate_provenance_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate lineage references and provenance contract invariants."""
    errors: list[str] = []
    warnings: list[str] = []
    claims = ledger.get("claims", []) if isinstance(ledger.get("claims", []), list) else []
    evidence = ledger.get("evidence", []) if isinstance(ledger.get("evidence", []), list) else []
    sources = ledger.get("sources", []) if isinstance(ledger.get("sources", []), list) else []
    transformations = ledger.get("transformations", []) if isinstance(ledger.get("transformations", []), list) else []
    decisions = ledger.get("decisions", []) if isinstance(ledger.get("decisions", []), list) else []
    claim_ids = {str(x.get("claim_id")) for x in claims if isinstance(x, dict) and x.get("claim_id")}
    evidence_ids = {str(x.get("evidence_id")) for x in evidence if isinstance(x, dict) and x.get("evidence_id")}
    source_ids = {str(x.get("source_id")) for x in sources if isinstance(x, dict) and x.get("source_id")}

    for index, claim in enumerate(claims, 1):
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            errors.append(f"claim[{index}] must contain claim_id")
            continue
        cid = str(claim["claim_id"])
        if claim.get("method") == "derived" and not claim.get("formula"):
            errors.append(f"derived claim {cid} missing formula")
        for dependency in claim.get("dependencies", []) or []:
            if dependency not in claim_ids:
                errors.append(f"claim {cid} references missing dependency {dependency}")
        for evidence_id in claim.get("evidence_refs", []) or []:
            if evidence_id not in evidence_ids:
                errors.append(f"claim {cid} references missing evidence {evidence_id}")
        for source_id in claim.get("source_refs", []) or []:
            if source_id not in source_ids:
                errors.append(f"claim {cid} references missing source {source_id}")
        confidence = _finite_number(claim.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            errors.append(f"claim {cid} has invalid confidence")

    evidence_source_ids = {str(x.get("source_id")) for x in evidence if isinstance(x, dict) and x.get("source_id")}
    if not evidence_source_ids.issubset(source_ids):
        errors.append("evidence contains references to missing source records")
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source must be an object")
            continue
        if not source.get("url"):
            errors.append(f"source {source.get('source_id')} missing url")
        retrieval = source.get("retrieval_metadata", {})
        if not isinstance(retrieval, dict):
            errors.append(f"source {source.get('source_id')} has invalid retrieval_metadata")
            continue
        if retrieval.get("retrieval_timestamp_recorded") and not source.get("retrieved_at"):
            errors.append(f"source {source.get('source_id')} marks retrieval timestamp recorded but has no retrieved_at")

    for transformation in transformations:
        if not isinstance(transformation, dict):
            errors.append("transformation must be an object")
            continue
        if transformation.get("output_claim_id") not in claim_ids:
            errors.append(f"transformation references missing output {transformation.get('output_claim_id')}")
        for dependency in transformation.get("dependency_claims", []) or []:
            if dependency not in claim_ids:
                errors.append(f"transformation references missing dependency {dependency}")

    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append("decision must be an object")
            continue
        missing = [cid for cid in decision.get("claim_refs", []) or [] if cid not in claim_ids]
        if missing:
            errors.append(f"decision {decision.get('decision_id')} references missing claims: {missing[:3]}")

    if ledger.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("unsupported provenance schema version")
    if ledger.get("summary", {}).get("total_claims") != len(claims):
        warnings.append("summary.total_claims differs from bounded claims list")
    return {"valid": not errors, "errors": errors, "warnings": warnings}
