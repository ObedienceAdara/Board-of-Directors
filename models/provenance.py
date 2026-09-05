"""Evidence and decision provenance models for the board.

The ledger keeps a machine-readable chain from a claim to its evidence/source,
retrieval context, deterministic transformation, responsible agent, and the
decision(s) that consume it. Missing provenance is represented explicitly;
this module never fabricates a source URL or retrieval event.
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
    return None


def _clamp_confidence(value: Any, default: float = 0.7) -> float:
    number = _finite_number(value)
    if number is None:
        number = default
    return round(max(0.0, min(1.0, number)), 3)


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _analysis_confidence(analysis: dict[str, Any]) -> float:
    return _clamp_confidence(analysis.get("confidence"), default=0.7)


def _claim_type(claim_id: str) -> str:
    prefix = claim_id.split(".", 1)[0]
    mapping = {
        "market": "market_size",
        "finance": "financial_metric",
        "unit_economics": "unit_economics",
        "technical": "technical_metric",
        "marketing": "marketing_metric",
        "sales": "sales_metric",
        "pricing": "pricing",
        "operations": "operating_metric",
        "product": "product_metric",
    }
    return mapping.get(prefix, "business_metric")


def _source_identity(url: str, title: str = "") -> str:
    return _stable_id("SRC", f"{url.strip()}|{title.strip()}")


def _make_source(
    evidence: dict[str, Any],
    *,
    retrieved_at: str,
    provider: str,
    query: str | None,
    rank: int | None,
) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    url = _text(evidence.get("source_url"), 1200)
    if not url:
        return None, None
    title = _text(evidence.get("source_title") or evidence.get("title") or evidence.get("source_name"), 400)
    publisher = _text(evidence.get("publisher") or evidence.get("source_publisher") or evidence.get("source_name"), 300)
    source_id = _source_identity(url, title)
    source = {
        "source_id": source_id,
        "url": url,
        "title": title or url,
        "publisher": publisher or None,
        "retrieved_at": retrieved_at,
        "retrieval_metadata": {
            "provider": provider,
            "query": _text(query, 700) if query else None,
            "rank": rank,
            "retrieval_method": "live_web_search" if provider else "external_source",
        },
    }
    evidence_record = {
        "evidence_id": "",
        "source_id": source_id,
        "evidence_type": "source_excerpt",
        "claim_text": _text(evidence.get("claim"), 700),
        "value": evidence.get("value"),
        "unit": _text(evidence.get("unit"), 80),
        "excerpt": _text(evidence.get("evidence_excerpt") or evidence.get("retrieved_context") or evidence.get("context"), 1800),
        "captured_at": retrieved_at,
    }
    return source, evidence_record


def _research_evidence(analysis: dict[str, Any], generated_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    claim_hints: list[dict[str, Any]] = []
    evidence = analysis.get("evidence", [])
    if not isinstance(evidence, list):
        return sources, evidence_records, claim_hints

    seen_sources: set[str] = set()
    for index, item in enumerate(evidence[:60], start=1):
        if not isinstance(item, dict):
            continue
        source, evidence_record = _make_source(
            item,
            retrieved_at=_text(item.get("retrieved_at"), 80) or generated_at,
            provider=_text(item.get("provider"), 80) or "tavily",
            query=_text(item.get("query"), 700) or None,
            rank=item.get("rank") if isinstance(item.get("rank"), int) else None,
        )
        if source is None or evidence_record is None:
            claim_hints.append({"evidence": item, "evidence_id": None})
            continue
        evidence_id = f"EVID-{index:04d}"
        evidence_record["evidence_id"] = evidence_id
        evidence_records.append(evidence_record)
        if source["source_id"] not in seen_sources:
            seen_sources.add(source["source_id"])
            sources.append(source)
        claim_hints.append({"evidence": item, "evidence_id": evidence_id, "source_id": source["source_id"]})
    return sources[:MAX_LEDGER_SOURCES], evidence_records[:MAX_LEDGER_EVIDENCE], claim_hints


def _claim_matches_evidence(claim_id: str, value: Any, unit: str, evidence: dict[str, Any]) -> bool:
    ev_claim = _text(evidence.get("claim"), 700).lower()
    ev_value = evidence.get("value")
    ev_unit = _text(evidence.get("unit"), 80).lower()
    number = _finite_number(value)
    evidence_number = _finite_number(ev_value)
    if number is not None and evidence_number is not None and abs(number - evidence_number) <= max(abs(number), 1.0) * 0.001:
        if not unit or not ev_unit or unit.lower() == ev_unit:
            return True
    last = claim_id.rsplit(".", 1)[-1].replace("_", " ").lower()
    tokens = [token for token in last.split() if len(token) > 2]
    return bool(tokens) and sum(token in ev_claim for token in tokens) >= max(1, len(tokens) - 1)


def _formula_for_claim(claim_id: str) -> tuple[str, list[str]] | None:
    formulas: dict[str, tuple[str, list[str]]] = {
        "sales.required_annual_customers": (
            "sales.annual_revenue_target / pricing.primary_price",
            ["sales.annual_revenue_target", "pricing.primary_price"],
        ),
        "unit_economics.ltv_cac_ratio": (
            "unit_economics.ltv / unit_economics.cac",
            ["unit_economics.ltv", "unit_economics.cac"],
        ),
        "operations.monthly_payroll": (
            "operations.annual_payroll / 12",
            ["operations.annual_payroll"],
        ),
        "finance.startup_cost": (
            "sum(finance.startup_cost.item.<n>)",
            [],
        ),
        "operations.annual_payroll": (
            "sum(operations.payroll.item.<n>)",
            [],
        ),
        "marketing.channel_allocation_total": (
            "sum(marketing.channel.<n>.amount)",
            [],
        ),
        "technical.development_phase_sum_weeks": (
            "sum(technical.development_phase.<n>.weeks)",
            [],
        ),
    }
    return formulas.get(claim_id)


def _component_claims(agent: str, analysis: dict[str, Any], base_currency: str) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    startup = analysis.get("startup_costs")
    if agent == "cfo" and isinstance(startup, list):
        for index, item in enumerate(startup[:50], start=1):
            if isinstance(item, dict) and _finite_number(item.get("amount")) is not None:
                components.append({
                    "claim_id": f"finance.startup_cost.item.{index}",
                    "value": float(item["amount"]), "unit": base_currency, "claim_type": "cost_component",
                    "method": "agent_assertion", "agent": agent, "confidence": _analysis_confidence(analysis),
                    "evidence_refs": [], "source_refs": [], "dependencies": [], "formula": None,
                    "component_name": _text(item.get("name"), 200),
                })
    hires = analysis.get("headcount_plan")
    if agent == "coo" and isinstance(hires, list):
        for index, item in enumerate(hires[:50], start=1):
            if not isinstance(item, dict):
                continue
            count = _finite_number(item.get("count"))
            salary = _finite_number(item.get("annual_salary"))
            if count is None or salary is None:
                continue
            components.append({
                "claim_id": f"operations.payroll.item.{index}",
                "value": count * salary, "unit": base_currency, "claim_type": "payroll_component",
                "method": "derived", "agent": agent, "confidence": _analysis_confidence(analysis),
                "evidence_refs": [], "source_refs": [], "dependencies": [],
                "formula": f"{count:g} * {salary:g}", "component_name": _text(item.get("role"), 200),
            })
    allocations = analysis.get("channel_allocations")
    if agent == "cmo" and isinstance(allocations, list):
        for index, item in enumerate(allocations[:50], start=1):
            if isinstance(item, dict) and _finite_number(item.get("amount")) is not None:
                components.append({
                    "claim_id": f"marketing.channel.{index}.amount",
                    "value": float(item["amount"]), "unit": base_currency, "claim_type": "marketing_component",
                    "method": "agent_assertion", "agent": agent, "confidence": _analysis_confidence(analysis),
                    "evidence_refs": [], "source_refs": [], "dependencies": [], "formula": None,
                    "component_name": _text(item.get("channel"), 200),
                })
    phases = analysis.get("development_phases")
    if agent == "cto" and isinstance(phases, list):
        for index, item in enumerate(phases[:30], start=1):
            if isinstance(item, dict) and _finite_number(item.get("weeks")) is not None:
                components.append({
                    "claim_id": f"technical.development_phase.{index}.weeks",
                    "value": float(item["weeks"]), "unit": "weeks", "claim_type": "timeline_component",
                    "method": "agent_assertion", "agent": agent, "confidence": _analysis_confidence(analysis),
                    "evidence_refs": [], "source_refs": [], "dependencies": [], "formula": None,
                    "component_name": _text(item.get("name"), 200),
                })
    return components


def _materialize_derived_dependencies(claim_id: str, agent: str, analysis: dict[str, Any]) -> list[str]:
    formula = _formula_for_claim(claim_id)
    if formula is None:
        return []
    _, dependencies = formula
    if dependencies:
        return dependencies
    if claim_id == "finance.startup_cost":
        return [f"finance.startup_cost.item.{i}" for i, item in enumerate(analysis.get("startup_costs", [])[:50], start=1) if isinstance(item, dict) and _finite_number(item.get("amount")) is not None]
    if claim_id == "operations.annual_payroll":
        return [f"operations.payroll.item.{i}" for i, item in enumerate(analysis.get("headcount_plan", [])[:50], start=1) if isinstance(item, dict) and _finite_number(item.get("count")) is not None and _finite_number(item.get("annual_salary")) is not None]
    if claim_id == "marketing.channel_allocation_total":
        return [f"marketing.channel.{i}.amount" for i, item in enumerate(analysis.get("channel_allocations", [])[:50], start=1) if isinstance(item, dict) and _finite_number(item.get("amount")) is not None]
    if claim_id == "technical.development_phase_sum_weeks":
        return [f"technical.development_phase.{i}.weeks" for i, item in enumerate(analysis.get("development_phases", [])[:30], start=1) if isinstance(item, dict) and _finite_number(item.get("weeks")) is not None]
    return []


def build_provenance_ledger(state: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    """Build a complete provenance ledger from a completed board state."""
    timestamp = generated_at or utc_now()
    claim_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    decision_records: list[dict[str, Any]] = []

    research_analysis = state.get("researcher_formal", {}) or {}
    research_sources, research_evidence, claim_hints = _research_evidence(research_analysis, timestamp)
    source_records.extend(research_sources)
    evidence_records.extend(research_evidence)
    hint_index = [item for item in claim_hints if item.get("evidence_id")]

    agents = ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm")
    for agent in agents:
        validation = state.get(f"{agent}_validation", {}) or {}
        analysis = state.get(f"{agent}_formal", {}) or {}
        if not isinstance(validation, dict) or not isinstance(analysis, dict):
            continue
        confidence = _analysis_confidence(analysis)
        currency = _text(analysis.get("currency"), 40)
        component_records = _component_claims(agent, analysis, currency)
        claim_records.extend(component_records)

        claims = validation.get("claims", [])
        if not isinstance(claims, list):
            continue
        for raw_claim in claims[:MAX_LEDGER_CLAIMS]:
            if not isinstance(raw_claim, dict) or not raw_claim.get("id"):
                continue
            claim_id = str(raw_claim["id"])
            method = "agent_assertion"
            formula: str | None = None
            dependencies = _materialize_derived_dependencies(claim_id, agent, analysis)
            formula_info = _formula_for_claim(claim_id)
            if formula_info is not None:
                formula = formula_info[0]
                if not dependencies:
                    dependencies = formula_info[1]
                method = "derived"

            matched_evidence = None
            if agent == "researcher":
                for hint in hint_index:
                    ev = hint.get("evidence", {})
                    if isinstance(ev, dict) and _claim_matches_evidence(claim_id, raw_claim.get("value"), str(raw_claim.get("unit", "")), ev):
                        matched_evidence = hint
                        break
            if matched_evidence is not None:
                method = "reported"
                evidence_id = matched_evidence.get("evidence_id")
                evidence_refs = [evidence_id] if evidence_id else []
                source_refs = [matched_evidence.get("source_id")] if matched_evidence.get("source_id") else []
            else:
                evidence_refs = []
                source_refs = []

            status = "validated"
            if validation.get("errors"):
                status = "validation_error"
            record = {
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claim_records) + 1:04d}",
                "value": raw_claim.get("value"),
                "unit": _text(raw_claim.get("unit"), 80),
                "claim_type": _claim_type(claim_id),
                "method": method,
                "formula": formula,
                "dependencies": dependencies,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
                "agent": agent,
                "confidence": _clamp_confidence(raw_claim.get("confidence"), default=confidence),
                "status": status,
            }
            claim_records.append(record)
            if method == "derived":
                transformations.append({
                    "transformation_id": f"TX-{len(transformations) + 1:04d}",
                    "output_claim_id": claim_id,
                    "operation": "deterministic_formula",
                    "formula": formula,
                    "dependency_claims": dependencies,
                    "agent": agent,
                    "deterministic": True,
                    "created_at": timestamp,
                })

    # Materialize a derived phase-sum claim when the CTO provided phase data.
    cto_analysis = state.get("cto_formal", {}) or {}
    if isinstance(cto_analysis, dict) and isinstance(cto_analysis.get("development_phases"), list) and cto_analysis.get("development_phases"):
        phases = [item for item in cto_analysis["development_phases"] if isinstance(item, dict) and _finite_number(item.get("weeks")) is not None][:30]
        if phases:
            claim_id = "technical.development_phase_sum_weeks"
            dependencies = _materialize_derived_dependencies(claim_id, "cto", cto_analysis)
            claim_records.append({
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claim_records) + 1:04d}",
                "value": round(sum(float(item["weeks"]) for item in phases), 3),
                "unit": "weeks",
                "claim_type": "technical_metric",
                "method": "derived",
                "formula": "sum(technical.development_phase.<n>.weeks)",
                "dependencies": dependencies,
                "evidence_refs": [],
                "source_refs": [],
                "agent": "cto",
                "confidence": _analysis_confidence(cto_analysis),
                "status": "validated" if not (state.get("cto_validation", {}) or {}).get("errors") else "validation_error",
            })
            transformations.append({
                "transformation_id": f"TX-{len(transformations) + 1:04d}",
                "output_claim_id": claim_id,
                "operation": "deterministic_formula",
                "formula": "sum(technical.development_phase.<n>.weeks)",
                "dependency_claims": dependencies,
                "agent": "cto",
                "deterministic": True,
                "created_at": timestamp,
            })

    # Deduplicate sources/evidence by stable IDs while preserving first occurrence.
    source_by_id = {item["source_id"]: item for item in source_records if item.get("source_id")}
    evidence_by_id = {item["evidence_id"]: item for item in evidence_records if item.get("evidence_id")}

    contradiction_ids: list[str] = []
    for item in state.get("deterministic_contradictions", []) or []:
        if isinstance(item, dict) and item.get("id"):
            contradiction_ids.append(str(item["id"]))

    logical_claim_ids = sorted({str(item["claim_id"]) for item in claim_records if item.get("claim_id")})
    final_report = _text(state.get("final_board_report"), 2400)
    decision_records.append({
        "decision_id": "board.recommendation",
        "decision_type": "board_recommendation",
        "agent": "ceo",
        "decision_text": final_report,
        "claim_refs": logical_claim_ids,
        "contradiction_refs": contradiction_ids,
        "consistency_status": _text(state.get("consistency_status"), 80) or "NOT_RUN",
        "created_at": timestamp,
    })

    adjudication = state.get("contradiction_adjudication", {}) or {}
    if isinstance(adjudication, dict):
        issues = adjudication.get("issues", [])
        if isinstance(issues, list):
            for issue in issues[:MAX_LEDGER_DECISIONS - 1]:
                if not isinstance(issue, dict) or not issue.get("id"):
                    continue
                decision_records.append({
                    "decision_id": f"contradiction.{issue['id']}",
                    "decision_type": "contradiction_adjudication",
                    "agent": "ceo",
                    "decision_text": _text(issue.get("resolution") or issue.get("rationale"), 1500),
                    "claim_refs": [str(issue.get("claim_id"))] if issue.get("claim_id") else logical_claim_ids[:20],
                    "contradiction_refs": [str(issue["id"])],
                    "verdict": _text(issue.get("verdict"), 80) or "INSUFFICIENT_EVIDENCE",
                    "confidence": _clamp_confidence(issue.get("confidence"), default=0.5),
                    "created_at": timestamp,
                })

    total_claims = len(claim_records)
    sourced_claims = sum(1 for item in claim_records if item.get("source_refs"))
    derived_claims = sum(1 for item in claim_records if item.get("method") == "derived")
    asserted_claims = sum(1 for item in claim_records if item.get("method") == "agent_assertion")
    validation_errors = sum(1 for item in claim_records if item.get("status") == "validation_error")
    evidence_coverage = round(sourced_claims / total_claims, 3) if total_claims else 0.0

    ledger = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": timestamp,
        "claims": claim_records[:MAX_LEDGER_CLAIMS],
        "evidence": evidence_records[:MAX_LEDGER_EVIDENCE],
        "sources": list(source_by_id.values())[:MAX_LEDGER_SOURCES],
        "transformations": transformations[:MAX_LEDGER_TRANSFORMATIONS],
        "decisions": decision_records[:MAX_LEDGER_DECISIONS],
        "summary": {
            "total_claims": total_claims,
            "sourced_claims": sourced_claims,
            "derived_claims": derived_claims,
            "agent_assertions": asserted_claims,
            "validation_error_claims": validation_errors,
            "evidence_records": len(evidence_by_id),
            "source_records": len(source_by_id),
            "transformation_records": len(transformations),
            "decision_records": len(decision_records),
            "evidence_coverage_ratio": evidence_coverage,
            "unsupported_claims": max(total_claims - sourced_claims - derived_claims, 0),
        },
    }
    return ledger


def validate_provenance_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate internal lineage references without calling external services."""
    errors: list[str] = []
    warnings: list[str] = []
    claims = ledger.get("claims", [])
    evidence = ledger.get("evidence", [])
    sources = ledger.get("sources", [])
    transformations = ledger.get("transformations", [])
    decisions = ledger.get("decisions", [])
    claim_ids = {str(item.get("claim_id")) for item in claims if isinstance(item, dict) and item.get("claim_id")}
    evidence_ids = {str(item.get("evidence_id")) for item in evidence if isinstance(item, dict) and item.get("evidence_id")}
    source_ids = {str(item.get("source_id")) for item in sources if isinstance(item, dict) and item.get("source_id")}

    for index, claim in enumerate(claims if isinstance(claims, list) else [], start=1):
        if not isinstance(claim, dict):
            errors.append(f"claim[{index}] must be an object")
            continue
        if not claim.get("claim_id"):
            errors.append(f"claim[{index}] missing claim_id")
        if claim.get("method") == "derived" and not claim.get("formula"):
            errors.append(f"derived claim {claim.get('claim_id')} missing formula")
        for dependency in claim.get("dependencies", []) or []:
            if dependency not in claim_ids:
                errors.append(f"claim {claim.get('claim_id')} references missing dependency {dependency}")
        for evidence_id in claim.get("evidence_refs", []) or []:
            if evidence_id not in evidence_ids:
                errors.append(f"claim {claim.get('claim_id')} references missing evidence {evidence_id}")
        for source_id in claim.get("source_refs", []) or []:
            if source_id not in source_ids:
                errors.append(f"claim {claim.get('claim_id')} references missing source {source_id}")
        confidence = _finite_number(claim.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            errors.append(f"claim {claim.get('claim_id')} has invalid confidence")

    for transformation in transformations if isinstance(transformations, list) else []:
        if not isinstance(transformation, dict):
            errors.append("transformation must be an object")
            continue
        if transformation.get("output_claim_id") not in claim_ids:
            errors.append(f"transformation references missing output {transformation.get('output_claim_id')}")
        for dependency in transformation.get("dependency_claims", []) or []:
            if dependency not in claim_ids:
                errors.append(f"transformation references missing dependency {dependency}")

    for decision in decisions if isinstance(decisions, list) else []:
        if not isinstance(decision, dict):
            errors.append("decision must be an object")
            continue
        missing = [claim_id for claim_id in decision.get("claim_refs", []) or [] if claim_id not in claim_ids]
        if missing:
            warnings.append(f"decision {decision.get('decision_id')} references claims not present in bounded ledger: {missing[:3]}")

    if ledger.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("unsupported provenance schema version")

    return {"valid": not errors, "errors": errors, "warnings": warnings}
