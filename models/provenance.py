"""Evidence and decision provenance for Board of Directors."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

PROVENANCE_SCHEMA_VERSION = "1.0"
MAX_LEDGER_CLAIMS = 240
MAX_LEDGER_EVIDENCE = 240
MAX_LEDGER_SOURCES = 160
MAX_LEDGER_TRANSFORMATIONS = 120
MAX_LEDGER_DECISIONS = 40


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _confidence(value: Any, default: float = 0.7) -> float:
    number = _number(value)
    if number is None:
        number = default
    return round(min(1.0, max(0.0, number)), 3)


def _text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12].upper()}"


def _claim_type(claim_id: str) -> str:
    prefix = claim_id.split(".", 1)[0]
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
    }.get(prefix, "business_metric")


def _formula(claim_id: str) -> tuple[str, list[str]] | None:
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
        "finance.startup_cost": ("sum(finance.startup_cost.item.<n>)", []),
        "operations.annual_payroll": ("sum(operations.payroll.item.<n>)", []),
        "marketing.channel_allocation_total": ("sum(marketing.channel.<n>.amount)", []),
        "technical.development_phase_sum_weeks": (
            "sum(technical.development_phase.<n>.weeks)",
            [],
        ),
    }
    return formulas.get(claim_id)


def _dependencies(claim_id: str, analysis: dict[str, Any]) -> list[str]:
    formula = _formula(claim_id)
    if formula and formula[1]:
        return list(formula[1])
    if claim_id == "finance.startup_cost":
        return [
            f"finance.startup_cost.item.{index}"
            for index, item in enumerate(analysis.get("startup_costs", [])[:50], start=1)
            if isinstance(item, dict) and _number(item.get("amount")) is not None
        ]
    if claim_id == "operations.annual_payroll":
        return [
            f"operations.payroll.item.{index}"
            for index, item in enumerate(analysis.get("headcount_plan", [])[:50], start=1)
            if isinstance(item, dict)
            and _number(item.get("count")) is not None
            and _number(item.get("annual_salary")) is not None
        ]
    if claim_id == "marketing.channel_allocation_total":
        return [
            f"marketing.channel.{index}.amount"
            for index, item in enumerate(analysis.get("channel_allocations", [])[:50], start=1)
            if isinstance(item, dict) and _number(item.get("amount")) is not None
        ]
    if claim_id == "technical.development_phase_sum_weeks":
        return [
            f"technical.development_phase.{index}.weeks"
            for index, item in enumerate(analysis.get("development_phases", [])[:30], start=1)
            if isinstance(item, dict) and _number(item.get("weeks")) is not None
        ]
    return []


def _match_evidence(claim_id: str, value: Any, unit: str, evidence: dict[str, Any]) -> bool:
    explicit_claim = _text(evidence.get("claim_id"), 200)
    if explicit_claim and explicit_claim != claim_id:
        return False
    evidence_claim = _text(evidence.get("claim_text"), 700).lower()
    expected = _number(value)
    observed = _number(evidence.get("value"))
    observed_unit = _text(evidence.get("unit"), 80).lower()
    if expected is not None and observed is not None:
        same_unit = not unit or not observed_unit or unit.lower() == observed_unit
        if same_unit and abs(expected - observed) <= max(abs(expected), 1.0) * 0.001:
            return True
    leaf = claim_id.rsplit(".", 1)[-1].replace("_", " ").lower()
    tokens = [token for token in leaf.split() if len(token) > 2]
    return bool(tokens) and sum(token in evidence_claim for token in tokens) >= max(1, len(tokens) - 1)


def _source_key(url: str, title: str = "") -> str:
    del title
    return _stable_id("SRC", url.strip())


def _trace_index(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for agent in ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"):
        raw = state.get(f"{agent}_retrieval_trace", [])
        if isinstance(raw, list):
            traces[agent] = [item for item in raw if isinstance(item, dict)]
    return traces


def build_provenance_ledger(state: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    """Build a bounded provenance ledger from completed board state."""
    captured_at = generated_at or _utc_now()
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    source_by_id: dict[str, dict[str, Any]] = {}
    evidence_by_id: dict[str, dict[str, Any]] = {}
    traces = _trace_index(state)

    def add_source(
        url: str,
        title: str,
        publisher: str | None,
        retrieved_at: str | None,
        retrieval_metadata: dict[str, Any],
    ) -> str:
        source_id = _source_key(url)
        existing = source_by_id.get(source_id)
        if existing is None:
            source_by_id[source_id] = {
                "source_id": source_id,
                "url": url,
                "title": title or url,
                "publisher": publisher,
                "retrieved_at": retrieved_at,
                "retrieval_metadata": retrieval_metadata,
            }
        else:
            if existing.get("title") in (None, "", existing.get("url")) and title:
                existing["title"] = title
            if not existing.get("publisher") and publisher:
                existing["publisher"] = publisher
            if not existing.get("retrieved_at") and retrieved_at:
                existing["retrieved_at"] = retrieved_at
                existing["retrieval_metadata"] = retrieval_metadata
        return source_id

    def add_evidence(agent: str, item: dict[str, Any], evidence_id: str) -> None:
        url = _text(item.get("source_url"), 1200)
        if not url:
            return

        matching_trace = next(
            (trace for trace in traces.get(agent, []) if str(trace.get("url", "")).strip() == url),
            None,
        )
        if matching_trace:
            trace_title = _text(matching_trace.get("title"), 400)
            title = trace_title or _text(
                item.get("source_title") or item.get("title") or item.get("source_name"),
                400,
            ) or url
            retrieved_at = _text(matching_trace.get("retrieved_at"), 80) or None
            retrieval_metadata = {
                "provider": matching_trace.get("provider") or "tavily",
                "query": matching_trace.get("query"),
                "rank": matching_trace.get("rank"),
                "score": matching_trace.get("score"),
                "published_at": matching_trace.get("published_at"),
                "retrieval_method": "live_web_search",
                "retrieval_timestamp_recorded": bool(retrieved_at),
                "trace_observed": True,
                "captured_at": captured_at,
            }
            publisher = _text(matching_trace.get("publisher"), 300) or None
            observed_excerpt = _text(matching_trace.get("content"), 1800)
            excerpt_origin = "agent_submitted_plus_tool_observed" if observed_excerpt else "agent_submitted"
        else:
            title = _text(item.get("source_title") or item.get("title") or item.get("source_name"), 400) or url
            retrieved_at = _text(item.get("retrieved_at"), 80) or None
            retrieval_metadata = {
                "provider": _text(item.get("provider"), 80) or None,
                "query": _text(item.get("query"), 700) or None,
                "rank": item.get("rank") if isinstance(item.get("rank"), int) else None,
                "retrieval_method": "model_reported_metadata",
                "retrieval_timestamp_recorded": bool(retrieved_at),
                "trace_observed": False,
                "captured_at": captured_at,
            }
            publisher = _text(item.get("publisher") or item.get("source_publisher") or item.get("source_name"), 300) or None
            observed_excerpt = ""
            excerpt_origin = "agent_submitted"

        source_id = add_source(url, title, publisher, retrieved_at, retrieval_metadata)
        record = {
            "evidence_id": evidence_id,
            "source_id": source_id,
            "agent": agent,
            "evidence_type": "source_excerpt",
            "claim_id": item.get("claim_id"),
            "claim_text": _text(item.get("claim"), 700),
            "value": item.get("value"),
            "unit": _text(item.get("unit"), 80),
            "excerpt": _text(item.get("evidence_excerpt") or item.get("context"), 1800),
            "observed_excerpt": observed_excerpt,
            "excerpt_origin": excerpt_origin,
            "captured_at": captured_at,
        }
        evidence.append(record)
        evidence_by_id[evidence_id] = record

    for agent in ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"):
        analysis = state.get(f"{agent}_formal", {}) or {}
        validation = state.get(f"{agent}_validation", {}) or {}
        if not isinstance(analysis, dict) or not isinstance(validation, dict):
            continue
        currency = _text(analysis.get("currency"), 40)
        confidence = _confidence(analysis.get("confidence"))

        if agent == "cfo" and isinstance(analysis.get("startup_costs"), list):
            for index, item in enumerate(analysis["startup_costs"][:50], start=1):
                if isinstance(item, dict) and _number(item.get("amount")) is not None:
                    claims.append({
                        "claim_id": f"finance.startup_cost.item.{index}",
                        "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                        "value": float(item["amount"]),
                        "unit": currency,
                        "claim_type": "cost_component",
                        "method": "agent_assertion",
                        "formula": None,
                        "dependencies": [],
                        "evidence_refs": [],
                        "source_refs": [],
                        "agent": agent,
                        "confidence": confidence,
                        "status": "validated" if not validation.get("errors") else "validation_error",
                        "component_name": _text(item.get("name"), 200),
                    })
        if agent == "coo" and isinstance(analysis.get("headcount_plan"), list):
            for index, item in enumerate(analysis["headcount_plan"][:50], start=1):
                if isinstance(item, dict):
                    count = _number(item.get("count"))
                    salary = _number(item.get("annual_salary"))
                    if count is not None and salary is not None:
                        claims.append({
                            "claim_id": f"operations.payroll.item.{index}",
                            "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                            "value": count * salary,
                            "unit": currency,
                            "claim_type": "payroll_component",
                            "method": "derived",
                            "formula": f"{count:g} * {salary:g}",
                            "dependencies": [],
                            "evidence_refs": [],
                            "source_refs": [],
                            "agent": agent,
                            "confidence": confidence,
                            "status": "validated" if not validation.get("errors") else "validation_error",
                            "component_name": _text(item.get("role"), 200),
                        })
        if agent == "cmo" and isinstance(analysis.get("channel_allocations"), list):
            for index, item in enumerate(analysis["channel_allocations"][:50], start=1):
                if isinstance(item, dict) and _number(item.get("amount")) is not None:
                    claims.append({
                        "claim_id": f"marketing.channel.{index}.amount",
                        "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                        "value": float(item["amount"]),
                        "unit": currency,
                        "claim_type": "marketing_component",
                        "method": "agent_assertion",
                        "formula": None,
                        "dependencies": [],
                        "evidence_refs": [],
                        "source_refs": [],
                        "agent": agent,
                        "confidence": confidence,
                        "status": "validated" if not validation.get("errors") else "validation_error",
                        "component_name": _text(item.get("channel"), 200),
                    })
        if agent == "cto" and isinstance(analysis.get("development_phases"), list):
            for index, item in enumerate(analysis["development_phases"][:30], start=1):
                if isinstance(item, dict) and _number(item.get("weeks")) is not None:
                    claims.append({
                        "claim_id": f"technical.development_phase.{index}.weeks",
                        "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                        "value": float(item["weeks"]),
                        "unit": "weeks",
                        "claim_type": "timeline_component",
                        "method": "agent_assertion",
                        "formula": None,
                        "dependencies": [],
                        "evidence_refs": [],
                        "source_refs": [],
                        "agent": agent,
                        "confidence": confidence,
                        "status": "validated" if not validation.get("errors") else "validation_error",
                        "component_name": _text(item.get("name"), 200),
                    })

        if isinstance(analysis.get("evidence"), list):
            for index, item in enumerate(analysis["evidence"][:60], start=1):
                if isinstance(item, dict):
                    add_evidence(agent, item, f"EVID-{agent.upper()}-{index:04d}")

        raw_claims = validation.get("claims", []) if isinstance(validation.get("claims"), list) else []
        for raw in raw_claims[:MAX_LEDGER_CLAIMS]:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            claim_id = str(raw["id"])
            formula_info = _formula(claim_id)
            dependencies = _dependencies(claim_id, analysis)
            method = "derived" if formula_info else "agent_assertion"
            formula = formula_info[0] if formula_info else None
            evidence_refs: list[str] = []
            source_refs: list[str] = []
            for evidence_id, ev in evidence_by_id.items():
                if ev.get("agent") != agent:
                    continue
                if _match_evidence(claim_id, raw.get("value"), str(raw.get("unit", "")), ev):
                    evidence_refs = [evidence_id]
                    source_id = ev.get("source_id")
                    if isinstance(source_id, str) and source_id in source_by_id:
                        source_refs = [source_id]
                    method = "reported"
                    break
            claims.append({
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                "value": raw.get("value"),
                "unit": _text(raw.get("unit"), 80),
                "claim_type": _claim_type(claim_id),
                "method": method,
                "formula": formula,
                "dependencies": dependencies,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
                "agent": agent,
                "confidence": _confidence(raw.get("confidence"), confidence),
                "status": "validation_error" if validation.get("errors") else "validated",
            })
            if method == "derived":
                transformations.append({
                    "transformation_id": f"TX-{len(transformations)+1:04d}",
                    "output_claim_id": claim_id,
                    "operation": "deterministic_formula",
                    "formula": formula,
                    "dependency_claims": dependencies,
                    "agent": agent,
                    "deterministic": True,
                    "created_at": captured_at,
                })

    cto = state.get("cto_formal", {}) or {}
    phases = cto.get("development_phases") if isinstance(cto, dict) else None
    if isinstance(phases, list):
        valid_phases = [
            item for item in phases[:30]
            if isinstance(item, dict) and _number(item.get("weeks")) is not None
        ]
        if valid_phases:
            claim_id = "technical.development_phase_sum_weeks"
            deps = _dependencies(claim_id, cto)
            claims.append({
                "claim_id": claim_id,
                "claim_instance_id": f"CLAIM-{len(claims)+1:04d}",
                "value": round(sum(float(item["weeks"]) for item in valid_phases), 3),
                "unit": "weeks",
                "claim_type": "technical_metric",
                "method": "derived",
                "formula": "sum(technical.development_phase.<n>.weeks)",
                "dependencies": deps,
                "evidence_refs": [],
                "source_refs": [],
                "agent": "cto",
                "confidence": _confidence(cto.get("confidence")),
                "status": "validation_error" if (state.get("cto_validation", {}) or {}).get("errors") else "validated",
            })
            transformations.append({
                "transformation_id": f"TX-{len(transformations)+1:04d}",
                "output_claim_id": claim_id,
                "operation": "deterministic_formula",
                "formula": "sum(technical.development_phase.<n>.weeks)",
                "dependency_claims": deps,
                "agent": "cto",
                "deterministic": True,
                "created_at": captured_at,
            })

    claim_ids = sorted({str(item["claim_id"]) for item in claims if item.get("claim_id")})
    contradiction_refs = [
        str(item["id"])
        for item in state.get("deterministic_contradictions", []) or []
        if isinstance(item, dict) and item.get("id")
    ]
    decisions: list[dict[str, Any]] = [{
        "decision_id": "board.recommendation",
        "decision_type": "board_recommendation",
        "agent": "ceo",
        "decision_text": _text(state.get("final_board_report"), 2400),
        "claim_refs": claim_ids,
        "contradiction_refs": contradiction_refs,
        "consistency_status": _text(state.get("consistency_status"), 80) or "NOT_RUN",
        "created_at": captured_at,
    }]
    adjudication = state.get("contradiction_adjudication", {}) or {}
    issues = adjudication.get("issues", []) if isinstance(adjudication, dict) else []
    if isinstance(issues, list):
        for issue in issues[: MAX_LEDGER_DECISIONS - 1]:
            if isinstance(issue, dict) and issue.get("id"):
                decisions.append({
                    "decision_id": f"contradiction.{issue['id']}",
                    "decision_type": "contradiction_adjudication",
                    "agent": "ceo",
                    "decision_text": _text(issue.get("resolution") or issue.get("rationale"), 1500),
                    "claim_refs": [str(issue["claim_id"])] if issue.get("claim_id") else claim_ids[:20],
                    "contradiction_refs": [str(issue["id"])],
                    "verdict": _text(issue.get("verdict"), 80) or "INSUFFICIENT_EVIDENCE",
                    "confidence": _confidence(issue.get("confidence"), 0.5),
                    "created_at": captured_at,
                })

    total = len(claims)
    sourced = sum(1 for item in claims if item.get("source_refs"))
    derived = sum(1 for item in claims if item.get("method") == "derived")
    asserted = sum(1 for item in claims if item.get("method") == "agent_assertion")
    invalid = sum(1 for item in claims if item.get("status") == "validation_error")
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": captured_at,
        "claims": claims[:MAX_LEDGER_CLAIMS],
        "evidence": evidence[:MAX_LEDGER_EVIDENCE],
        "sources": list(source_by_id.values())[:MAX_LEDGER_SOURCES],
        "transformations": transformations[:MAX_LEDGER_TRANSFORMATIONS],
        "decisions": decisions[:MAX_LEDGER_DECISIONS],
        "summary": {
            "total_claims": total,
            "sourced_claims": sourced,
            "derived_claims": derived,
            "agent_assertions": asserted,
            "validation_error_claims": invalid,
            "evidence_records": len(evidence),
            "source_records": len(source_by_id),
            "transformation_records": len(transformations),
            "decision_records": len(decisions),
            "evidence_coverage_ratio": round(sourced / total, 3) if total else 0.0,
            "unsupported_claims": max(total - sourced - derived, 0),
        },
    }


def validate_provenance_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate internal lineage references without external calls."""
    errors: list[str] = []
    warnings: list[str] = []
    claims = ledger.get("claims", [])
    evidence = ledger.get("evidence", [])
    sources = ledger.get("sources", [])
    transformations = ledger.get("transformations", [])
    decisions = ledger.get("decisions", [])
    claim_ids = {
        str(item.get("claim_id"))
        for item in claims
        if isinstance(item, dict) and item.get("claim_id")
    }
    evidence_ids = {
        str(item.get("evidence_id"))
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    }
    source_ids = {
        str(item.get("source_id"))
        for item in sources
        if isinstance(item, dict) and item.get("source_id")
    }
    if ledger.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("unsupported provenance schema version")
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            errors.append("claim must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not claim_id:
            errors.append("claim missing claim_id")
        if claim.get("method") == "derived" and not claim.get("formula"):
            errors.append(f"derived claim {claim_id} missing formula")
        for dependency in claim.get("dependencies", []) or []:
            if dependency not in claim_ids:
                errors.append(f"claim {claim_id} references missing dependency {dependency}")
        for evidence_id in claim.get("evidence_refs", []) or []:
            if evidence_id not in evidence_ids:
                errors.append(f"claim {claim_id} references missing evidence {evidence_id}")
        for source_id in claim.get("source_refs", []) or []:
            if source_id not in source_ids:
                errors.append(f"claim {claim_id} references missing source {source_id}")
        confidence = _number(claim.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            errors.append(f"claim {claim_id} has invalid confidence")
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
        missing = [
            claim_id
            for claim_id in decision.get("claim_refs", []) or []
            if claim_id not in claim_ids
        ]
        if missing:
            warnings.append(
                f"decision {decision.get('decision_id')} references claims not present in bounded ledger: {missing[:3]}"
            )
    return {"valid": not errors, "errors": errors, "warnings": warnings}
