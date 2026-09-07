"""Evidence and decision provenance for Board of Directors."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

PROVENANCE_SCHEMA_VERSION = "1.1"
MAX_LEDGER_CLAIMS = 240
MAX_LEDGER_EVIDENCE = 240
MAX_LEDGER_SOURCES = 160
MAX_LEDGER_TRANSFORMATIONS = 120
MAX_LEDGER_DECISIONS = 40
AGENTS = ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        return n if math.isfinite(n) else None
    return None


def _confidence(value: Any, default: float = 0.7) -> float:
    n = _number(value)
    return round(min(1.0, max(0.0, default if n is None else n)), 3)


def _text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12].upper()}"


def _claim_type(claim_id: str) -> str:
    prefix = claim_id.split(".", 1)[0]
    return {"market": "market_size", "finance": "financial_metric", "unit_economics": "unit_economics", "technical": "technical_metric", "marketing": "marketing_metric", "sales": "sales_metric", "pricing": "pricing", "operations": "operating_metric", "product": "product_metric"}.get(prefix, "business_metric")


def _formula(claim_id: str) -> tuple[str, list[str]] | None:
    return {
        "sales.required_annual_customers": ("sales.annual_revenue_target / pricing.primary_price", ["sales.annual_revenue_target", "pricing.primary_price"]),
        "operations.monthly_payroll": ("operations.annual_payroll / 12", ["operations.annual_payroll"]),
        "finance.startup_cost": ("sum(finance.startup_cost.item.<n>)", []),
        "operations.annual_payroll": ("sum(operations.payroll.item.<n>)", []),
        "marketing.channel_allocation_total": ("sum(marketing.channel.<n>.amount)", []),
        "technical.development_phase_sum_weeks": ("sum(technical.development_phase.<n>.weeks)", []),
    }.get(claim_id)


def _dependencies(claim_id: str, analysis: dict[str, Any]) -> list[str]:
    formula = _formula(claim_id)
    if formula and formula[1]:
        return list(formula[1])
    if claim_id == "finance.startup_cost":
        return [f"finance.startup_cost.item.{i}" for i, item in enumerate(analysis.get("startup_costs", [])[:50], 1) if isinstance(item, dict) and _number(item.get("amount")) is not None]
    if claim_id == "operations.annual_payroll":
        return [f"operations.payroll.item.{i}" for i, item in enumerate(analysis.get("headcount_plan", [])[:50], 1) if isinstance(item, dict) and _number(item.get("count")) is not None and _number(item.get("annual_salary")) is not None]
    if claim_id == "marketing.channel_allocation_total":
        return [f"marketing.channel.{i}.amount" for i, item in enumerate(analysis.get("channel_allocations", [])[:50], 1) if isinstance(item, dict) and _number(item.get("amount")) is not None]
    if claim_id == "technical.development_phase_sum_weeks":
        return [f"technical.development_phase.{i}.weeks" for i, item in enumerate(analysis.get("development_phases", [])[:30], 1) if isinstance(item, dict) and _number(item.get("weeks")) is not None]
    return []


def _trace_index(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {agent: [item for item in (state.get(f"{agent}_retrieval_trace", []) or []) if isinstance(item, dict)] for agent in AGENTS}


def build_provenance_ledger(state: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    captured_at = generated_at or _utc_now()
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    source_by_id: dict[str, dict[str, Any]] = {}
    traces = _trace_index(state)

    def add_source(url: str, title: str, publisher: str | None, retrieved_at: str | None, metadata: dict[str, Any]) -> str:
        sid = _source_key(url)
        current = source_by_id.get(sid)
        if current is None:
            source_by_id[sid] = {"source_id": sid, "url": url, "title": title or url, "publisher": publisher, "retrieved_at": retrieved_at, "retrieval_metadata": metadata}
        else:
            current["title"] = current.get("title") or title or url
            current["publisher"] = current.get("publisher") or publisher
            current["retrieved_at"] = current.get("retrieved_at") or retrieved_at
        return sid

    def add_evidence(agent: str, item: dict[str, Any], evidence_id: str) -> None:
        url = _text(item.get("source_url"), 1200)
        if not url:
            return
        trace = next((t for t in traces.get(agent, []) if str(t.get("url", "")).strip() == url), None)
        title = _text((trace or {}).get("title") or item.get("source_title") or item.get("source_name"), 400) or url
        publisher = _text((trace or {}).get("publisher") or item.get("source_name"), 300) or None
        retrieved_at = _text((trace or {}).get("retrieved_at") or item.get("retrieved_at"), 80) or None
        metadata = {"provider": (trace or {}).get("provider") or item.get("provider"), "query": (trace or {}).get("query") or item.get("query"), "rank": (trace or {}).get("rank") or item.get("rank"), "score": (trace or {}).get("score"), "published_at": (trace or {}).get("published_at"), "retrieval_method": "live_web_search" if trace else "model_reported_metadata", "trace_observed": bool(trace), "retrieval_timestamp_recorded": bool(retrieved_at), "captured_at": captured_at}
        sid = add_source(url, title, publisher, retrieved_at, metadata)
        evidence.append({"evidence_id": evidence_id, "source_id": sid, "agent": agent, "evidence_type": "source_excerpt", "claim_id": item.get("claim_id"), "claim_text": _text(item.get("claim"), 700), "value": item.get("value"), "unit": _text(item.get("unit"), 80), "excerpt": _text(item.get("evidence_excerpt") or item.get("context"), 1800), "observed_excerpt": _text((trace or {}).get("content"), 1800), "captured_at": captured_at})

    for agent in AGENTS:
        analysis = state.get(f"{agent}_formal", {}) or {}
        validation = state.get(f"{agent}_validation", {}) or {}
        if not isinstance(analysis, dict) or not isinstance(validation, dict):
            continue
        currency = _text(analysis.get("currency"), 40)
        confidence = _confidence(analysis.get("confidence"))
        if isinstance(analysis.get("startup_costs"), list) and agent == "cfo":
            for i, item in enumerate(analysis["startup_costs"][:50], 1):
                if isinstance(item, dict) and _number(item.get("amount")) is not None:
                    claims.append({"claim_id": f"finance.startup_cost.item.{i}", "value": float(item["amount"]), "unit": currency, "claim_type": "cost_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated" if not validation.get("errors") else "validation_error"})
        if isinstance(analysis.get("headcount_plan"), list) and agent == "coo":
            for i, item in enumerate(analysis["headcount_plan"][:50], 1):
                if isinstance(item, dict) and _number(item.get("count")) is not None and _number(item.get("annual_salary")) is not None:
                    claims.append({"claim_id": f"operations.payroll.item.{i}", "value": float(item["count"]) * float(item["annual_salary"]), "unit": currency, "claim_type": "payroll_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated" if not validation.get("errors") else "validation_error"})
        if isinstance(analysis.get("channel_allocations"), list) and agent == "cmo":
            for i, item in enumerate(analysis["channel_allocations"][:50], 1):
                if isinstance(item, dict) and _number(item.get("amount")) is not None:
                    claims.append({"claim_id": f"marketing.channel.{i}.amount", "value": float(item["amount"]), "unit": currency, "claim_type": "marketing_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated" if not validation.get("errors") else "validation_error"})
        if isinstance(analysis.get("development_phases"), list) and agent == "cto":
            for i, item in enumerate(analysis["development_phases"][:30], 1):
                if isinstance(item, dict) and _number(item.get("weeks")) is not None:
                    claims.append({"claim_id": f"technical.development_phase.{i}.weeks", "value": float(item["weeks"]), "unit": "weeks", "claim_type": "timeline_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated" if not validation.get("errors") else "validation_error"})
        for i, item in enumerate((analysis.get("evidence", []) or [])[:60], 1):
            if isinstance(item, dict):
                add_evidence(agent, item, f"EVID-{agent.upper()}-{i:04d}")
        raw_claims = validation.get("claims", []) if isinstance(validation.get("claims"), list) else []
        for raw in raw_claims[:MAX_LEDGER_CLAIMS]:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            claim_id = str(raw["id"])
            formula_info = _formula(claim_id)
            deps = _dependencies(claim_id, analysis)
            matched = next((ev for ev in evidence if ev.get("agent") == agent and ev.get("claim_id") == claim_id), None)
            method = "reported" if matched else ("derived" if formula_info else "agent_assertion")
            source_refs = [str(matched["source_id"])] if matched else []
            evidence_refs = [str(matched["evidence_id"])] if matched else []
            claims.append({"claim_id": claim_id, "claim_instance_id": f"CLAIM-{len(claims)+1:04d}", "value": raw.get("value"), "unit": _text(raw.get("unit"), 80), "claim_type": _claim_type(claim_id), "method": method, "formula": formula_info[0] if formula_info else None, "dependencies": deps, "evidence_refs": evidence_refs, "source_refs": source_refs, "agent": agent, "confidence": _confidence(raw.get("confidence"), confidence), "status": "validation_error" if validation.get("errors") else "validated"})
            if formula_info:
                transformations.append({"transformation_id": f"TX-{len(transformations)+1:04d}", "output_claim_id": claim_id, "operation": "deterministic_formula", "formula": formula_info[0], "dependency_claims": deps, "agent": agent, "deterministic": True, "created_at": captured_at})

    cto = state.get("cto_formal", {}) or {}
    phases = cto.get("development_phases") if isinstance(cto, dict) else None
    if isinstance(phases, list) and any(isinstance(p, dict) and _number(p.get("weeks")) is not None for p in phases):
        deps = _dependencies("technical.development_phase_sum_weeks", cto)
        claims.append({"claim_id": "technical.development_phase_sum_weeks", "claim_instance_id": f"CLAIM-{len(claims)+1:04d}", "value": round(sum(float(p["weeks"]) for p in phases[:30] if isinstance(p, dict) and _number(p.get("weeks")) is not None), 3), "unit": "weeks", "claim_type": "technical_metric", "method": "derived", "formula": "sum(technical.development_phase.<n>.weeks)", "dependencies": deps, "evidence_refs": [], "source_refs": [], "agent": "cto", "confidence": _confidence(cto.get("confidence")), "status": "validated"})
        transformations.append({"transformation_id": f"TX-{len(transformations)+1:04d}", "output_claim_id": "technical.development_phase_sum_weeks", "operation": "deterministic_formula", "formula": "sum(technical.development_phase.<n>.weeks)", "dependency_claims": deps, "agent": "cto", "deterministic": True, "created_at": captured_at})

    bounded_claims = claims[:MAX_LEDGER_CLAIMS]
    bounded_evidence = evidence[:MAX_LEDGER_EVIDENCE]
    bounded_sources = list(source_by_id.values())[:MAX_LEDGER_SOURCES]
    bounded_transformations = transformations[:MAX_LEDGER_TRANSFORMATIONS]
    claim_ids = {str(item.get("claim_id")) for item in bounded_claims if item.get("claim_id")}
    decisions: list[dict[str, Any]] = [{"decision_id": "board.recommendation", "decision_type": "board_recommendation", "agent": "ceo", "decision_text": _text(state.get("final_board_report"), 2400), "claim_refs": sorted(claim_ids), "contradiction_refs": [str(x["id"]) for x in state.get("deterministic_contradictions", []) or [] if isinstance(x, dict) and x.get("id")], "consistency_status": _text(state.get("consistency_status"), 80) or "NOT_RUN", "created_at": captured_at}]
    adjudication = state.get("contradiction_adjudication", {}) or {}
    for issue in (adjudication.get("issues", []) if isinstance(adjudication, dict) else [])[: MAX_LEDGER_DECISIONS - 1]:
        if isinstance(issue, dict) and issue.get("id"):
            decisions.append({"decision_id": f"contradiction.{issue['id']}", "decision_type": "contradiction_adjudication", "agent": "ceo", "decision_text": _text(issue.get("resolution") or issue.get("rationale"), 1500), "claim_refs": [str(issue["claim_id"])] if issue.get("claim_id") and str(issue["claim_id"]) in claim_ids else [], "contradiction_refs": [str(issue["id"])], "verdict": _text(issue.get("verdict"), 80) or "INSUFFICIENT_EVIDENCE", "confidence": _confidence(issue.get("confidence"), 0.5), "created_at": captured_at})
    sourced = sum(1 for item in bounded_claims if item.get("source_refs"))
    derived = sum(1 for item in bounded_claims if item.get("method") == "derived")
    asserted = sum(1 for item in bounded_claims if item.get("method") == "agent_assertion")
    invalid = sum(1 for item in bounded_claims if item.get("status") == "validation_error")
    return {"schema_version": PROVENANCE_SCHEMA_VERSION, "generated_at": captured_at, "claims": bounded_claims, "evidence": bounded_evidence, "sources": bounded_sources, "transformations": bounded_transformations, "decisions": decisions[:MAX_LEDGER_DECISIONS], "summary": {"total_claims": len(bounded_claims), "sourced_claims": sourced, "derived_claims": derived, "agent_assertions": asserted, "validation_error_claims": invalid, "evidence_records": len(bounded_evidence), "source_records": len(bounded_sources), "transformation_records": len(bounded_transformations), "decision_records": min(len(decisions), MAX_LEDGER_DECISIONS), "evidence_coverage_ratio": round(sourced / len(bounded_claims), 3) if bounded_claims else 0.0, "unsupported_claims": max(len(bounded_claims) - sourced - derived, 0)}}


def _source_key(url: str) -> str:
    return _stable_id("SRC", url.strip())


def validate_provenance_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    claims = ledger.get("claims", []) if isinstance(ledger.get("claims"), list) else []
    evidence = ledger.get("evidence", []) if isinstance(ledger.get("evidence"), list) else []
    sources = ledger.get("sources", []) if isinstance(ledger.get("sources"), list) else []
    transformations = ledger.get("transformations", []) if isinstance(ledger.get("transformations"), list) else []
    decisions = ledger.get("decisions", []) if isinstance(ledger.get("decisions"), list) else []
    claim_ids = {str(x.get("claim_id")) for x in claims if isinstance(x, dict) and x.get("claim_id")}
    source_ids = {str(x.get("source_id")) for x in sources if isinstance(x, dict) and x.get("source_id")}
    evidence_ids = {str(x.get("evidence_id")) for x in evidence if isinstance(x, dict) and x.get("evidence_id")}
    for item in claims:
        if not isinstance(item, dict) or not item.get("claim_id"):
            errors.append("Every claim must have claim_id")
            continue
        for ref in item.get("evidence_refs", []) or []:
            if str(ref) not in evidence_ids: errors.append(f"Claim {item['claim_id']} references missing evidence {ref}")
        for ref in item.get("source_refs", []) or []:
            if str(ref) not in source_ids: errors.append(f"Claim {item['claim_id']} references missing source {ref}")
        for dep in item.get("dependencies", []) or []:
            if str(dep) not in claim_ids: errors.append(f"Claim {item['claim_id']} references missing dependency {dep}")
        confidence = _number(item.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1: errors.append(f"Claim {item['claim_id']} has invalid confidence")
    for ev in evidence:
        if not isinstance(ev, dict) or not ev.get("evidence_id") or str(ev.get("source_id")) not in source_ids:
            errors.append("Every evidence record must reference an existing source")
        if ev.get("claim_id") and str(ev["claim_id"]) not in claim_ids:
            warnings.append(f"Evidence {ev.get('evidence_id')} names a claim not present in the bounded ledger")
    for tx in transformations:
        if not isinstance(tx, dict) or str(tx.get("output_claim_id")) not in claim_ids: errors.append("Every transformation must reference an existing output claim")
        for dep in tx.get("dependency_claims", []) or []:
            if str(dep) not in claim_ids: errors.append(f"Transformation references missing dependency {dep}")
    for decision in decisions:
        for ref in decision.get("claim_refs", []) or []:
            if str(ref) not in claim_ids: errors.append(f"Decision references missing claim {ref}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}
