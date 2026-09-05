"""Evidence and decision provenance for Board of Directors.

The ledger is deliberately conservative: source-backed status requires an
explicit evidence-to-source match, while retrieval metadata comes from the
search tool's observed trace whenever available. Missing metadata remains
missing rather than being inferred.
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
AGENTS = ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
    elif isinstance(value, str):
        try:
            n = float(value.replace(",", "").replace("$", "").strip())
        except ValueError:
            return None
    else:
        return None
    return n if math.isfinite(n) else None


def _text(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _confidence(value: Any, default: float = 0.7) -> float:
    n = _number(value)
    return round(max(0.0, min(1.0, default if n is None else n)), 3)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12].upper()}"


def _claim_type(claim_id: str) -> str:
    return {
        "market": "market_size", "finance": "financial_metric", "unit_economics": "unit_economics",
        "technical": "technical_metric", "marketing": "marketing_metric", "sales": "sales_metric",
        "pricing": "pricing", "operations": "operating_metric", "product": "product_metric",
    }.get(claim_id.split(".", 1)[0], "business_metric")


def _formula(claim_id: str) -> tuple[str, list[str]] | None:
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
    confidence = _confidence(analysis.get("confidence"))
    records: list[dict[str, Any]] = []
    if agent == "cfo" and isinstance(analysis.get("startup_costs"), list):
        for i, item in enumerate(analysis["startup_costs"][:50], 1):
            if isinstance(item, dict) and _number(item.get("amount")) is not None:
                records.append({"claim_id": f"finance.startup_cost.item.{i}", "value": float(item["amount"]), "unit": currency, "claim_type": "cost_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("name"), 200)})
    if agent == "coo" and isinstance(analysis.get("headcount_plan"), list):
        for i, item in enumerate(analysis["headcount_plan"][:50], 1):
            if not isinstance(item, dict):
                continue
            count, salary = _number(item.get("count")), _number(item.get("annual_salary"))
            if count is not None and salary is not None:
                records.append({"claim_id": f"operations.payroll.item.{i}", "value": count * salary, "unit": currency, "claim_type": "payroll_component", "method": "derived", "formula": f"{count:g} * {salary:g}", "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("role"), 200)})
    if agent == "cmo" and isinstance(analysis.get("channel_allocations"), list):
        for i, item in enumerate(analysis["channel_allocations"][:50], 1):
            if isinstance(item, dict) and _number(item.get("amount")) is not None:
                records.append({"claim_id": f"marketing.channel.{i}.amount", "value": float(item["amount"]), "unit": currency, "claim_type": "marketing_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("channel"), 200)})
    if agent == "cto" and isinstance(analysis.get("development_phases"), list):
        for i, item in enumerate(analysis["development_phases"][:30], 1):
            if isinstance(item, dict) and _number(item.get("weeks")) is not None:
                records.append({"claim_id": f"technical.development_phase.{i}.weeks", "value": float(item["weeks"]), "unit": "weeks", "claim_type": "timeline_component", "method": "agent_assertion", "formula": None, "dependencies": [], "evidence_refs": [], "source_refs": [], "agent": agent, "confidence": confidence, "status": "validated", "component_name": _text(item.get("name"), 200)})
    return records


def _dependencies(claim_id: str, analysis: dict[str, Any]) -> list[str]:
    entry = _formula(claim_id)
    if entry is None:
        return []
    _, direct = entry
    if direct:
        return direct
    data = {
        "finance.startup_cost": ("startup_costs", "finance.startup_cost.item", "amount"),
        "operations.annual_payroll": ("headcount_plan", "operations.payroll.item", "annual_salary"),
        "marketing.channel_allocation_total": ("channel_allocations", "marketing.channel", "amount"),
        "technical.development_phase_sum_weeks": ("development_phases", "technical.development_phase", "weeks"),
    }.get(claim_id)
    if data is None:
        return []
    items_key, prefix, value_key = data
    items = analysis.get(items_key, [])
    if not isinstance(items, list):
        return []
    result = []
    for i, item in enumerate(items[:50], 1):
        if isinstance(item, dict) and _number(item.get(value_key)) is not None:
            if claim_id == "operations.annual_payroll" and _number(item.get("count")) is None:
                continue
            result.append(f"{prefix}.{i}" if not prefix.endswith("item") else f"{prefix}.{i}")
    return result


def _observed_trace(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for agent in AGENTS:
        trace = state.get(f"{agent}_retrieval_trace", [])
        if not isinstance(trace, list):
            continue
        for item in trace:
            if not isinstance(item, dict):
                continue
            url = _text(item.get("url"), 1200)
            if url and url not in by_url:
                by_url[url] = item
    return by_url


def _evidence_from_state(state: dict[str, Any], captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    observed = _observed_trace(state)
    sources_by_id: dict[str, dict[str, Any]] = {}
    evidence_records: list[dict[str, Any]] = []
    evidence_counter = 0
    for agent in AGENTS:
        analysis = state.get(f"{agent}_formal", {}) or {}
        evidence = analysis.get("evidence", []) if isinstance(analysis, dict) else []
        if not isinstance(evidence, list):
            continue
        for item in evidence[:60]:
            if not isinstance(item, dict):
                continue
            url = _text(item.get("source_url"), 1200)
            if not url:
                continue
            evidence_counter += 1
            observed_item = observed.get(url, {})
            title = _text(observed_item.get("title") or item.get("source_title") or item.get("title") or item.get("source_name"), 400) or url
            source_id = _stable_id("SRC", url)
            source = {
                "source_id": source_id,
                "url": url,
                "title": title,
                "publisher": _text(observed_item.get("publisher") or item.get("publisher") or item.get("source_publisher") or item.get("source_name"), 300) or None,
                "retrieved_at": _text(observed_item.get("retrieved_at"), 80) or None,
                "retrieval_metadata": {
                    "provider": _text(observed_item.get("provider"), 80) or None,
                    "query": _text(observed_item.get("query"), 700) or None,
                    "rank": observed_item.get("rank") if isinstance(observed_item.get("rank"), int) else None,
                    "score": observed_item.get("score"),
                    "published_at": observed_item.get("published_at"),
                    "retrieval_observed_by_tool": bool(observed_item),
                    "retrieval_timestamp_recorded": bool(observed_item.get("retrieved_at")),
                    "captured_at": captured_at,
                },
            }
            sources_by_id[source_id] = source
            evidence_id = f"EVID-{evidence_counter:04d}"
            evidence_records.append({
                "evidence_id": evidence_id,
                "source_id": source_id,
                "agent": agent,
                "claim_id": _text(item.get("claim_id"), 180) or None,
                "evidence_type": "source_excerpt",
                "claim_text": _text(item.get("claim"), 700),
                "value": item.get("value"),
                "unit": _text(item.get("unit"), 80),
                "excerpt": _text(item.get("evidence_excerpt") or item.get("retrieved_context") or item.get("context"), 1800),
                "captured_at": captured_at,
            })
    return list(sources_by_id.values())[:MAX_LEDGER_SOURCES], evidence_records[:MAX_LEDGER_EVIDENCE], observed


def _match_evidence(claim_id: str, value: Any, unit: str, evidence: dict[str, Any]) -> bool:
    explicit = _text(evidence.get("claim_id"), 180)
    if explicit:
        return explicit == claim_id
    text = " ".join(_text(evidence.get(k), 700).lower() for k in ("claim_text", "excerpt"))
    tokens = [x for x in claim_id.rsplit(".", 1)[-1].replace("_", " ").split() if len(x) > 2]
    n1, n2 = _number(value), _number(evidence.get("value"))
    close = n1 is not None and n2 is not None and abs(n1 - n2) <= max(abs(n1), 1.0) * 0.001
    eu = _text(evidence.get("unit"), 80).lower()
    unit_ok = not unit or not eu or unit.lower() == eu
    text_ok = bool(tokens) and sum(x in text for x in tokens) >= max(1, len(tokens) - 1)
    return close and unit_ok and text_ok


def build_provenance_ledger(state: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    captured_at = generated_at or utc_now()
    sources, evidence, _ = _evidence_from_state(state, captured_at)
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    source_by_id = {item["source_id"]: item for item in sources}
    claims: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []

    for agent in AGENTS:
        analysis = state.get(f"{agent}_formal", {}) or {}
        validation = state.get(f"{agent}_validation", {}) or {}
        if not isinstance(analysis, dict) or not isinstance(validation, dict):
            continue
        currency = _text(analysis.get("currency"), 40)
        claims.extend(_component_claims(agent, analysis, currency))
        raw_claims = validation.get("claims", []) if isinstance(validation.get("claims"), list) else []
        for raw in raw_claims[:MAX_LEDGER_CLAIMS]:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            claim_id = str(raw["id"])
            formula_info = _formula(claim_id)
            dependencies = _dependencies(claim_id, analysis)
            method = "derived" if formula_info else "agent_assertion"
            formula = formula_info[0] if formula_info else None
            evidence_refs, source_refs = [], []
            for evidence_id, ev in evidence_by_id.items():
                if ev.get("agent") == agent and _match_evidence(claim_id, raw.get("value"), str(raw.get("unit", "")), ev):
                    evidence_refs = [evidence_id]
                    source_id = ev.get("source_id")
                    if source_id in source_by_id:
                        source_refs = [source_id]
                    method = "reported"
                    break
            claims.append({
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
                "confidence": _confidence(raw.get("confidence"), _confidence(analysis.get("confidence"))),
                "status": "validation_error" if validation.get("errors") else "validated",
            })
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
    phases = cto.get("development_phases") if isinstance(cto, dict) else None
    if isinstance(phases, list):
        valid_phases = [x for x in phases[:30] if isinstance(x, dict) and _number(x.get("weeks")) is not None]
        if valid_phases:
            claim_id = "technical.development_phase_sum_weeks"
            deps = _dependencies(claim_id, cto)
            claims.append({"claim_id": claim_id, "claim_instance_id": f"CLAIM-{len(claims) + 1:04d}", "value": round(sum(float(x["weeks"]) for x in valid_phases), 3), "unit": "weeks", "claim_type": "technical_metric", "method": "derived", "formula": "sum(technical.development_phase.<n>.weeks)", "dependencies": deps, "evidence_refs": [], "source_refs": [], "agent": "cto", "confidence": _confidence(cto.get("confidence")), "status": "validation_error" if (state.get("cto_validation", {}) or {}).get("errors") else "validated"})
            transformations.append({"transformation_id": f"TX-{len(transformations) + 1:04d}", "output_claim_id": claim_id, "operation": "deterministic_formula", "formula": "sum(technical.development_phase.<n>.weeks)", "dependency_claims": deps, "agent": "cto", "deterministic": True, "created_at": captured_at})

    claim_ids = sorted({str(x["claim_id"]) for x in claims if x.get("claim_id")})
    contradictions = [str(x["id"]) for x in state.get("deterministic_contradictions", []) or [] if isinstance(x, dict) and x.get("id")]
    decisions = [{"decision_id": "board.recommendation", "decision_type": "board_recommendation", "agent": "ceo", "decision_text": _text(state.get("final_board_report"), 2400), "claim_refs": claim_ids, "contradiction_refs": contradictions, "consistency_status": _text(state.get("consistency_status"), 80) or "NOT_RUN", "created_at": captured_at}]
    adjudication = state.get("contradiction_adjudication", {}) or {}
    issues = adjudication.get("issues", []) if isinstance(adjudication, dict) else []
    if isinstance(issues, list):
        for issue in issues[:MAX_LEDGER_DECISIONS - 1]:
            if isinstance(issue, dict) and issue.get("id"):
                decisions.append({"decision_id": f"contradiction.{issue['id']}", "decision_type": "contradiction_adjudication", "agent": "ceo", "decision_text": _text(issue.get("resolution") or issue.get("rationale"), 1500), "claim_refs": [str(issue["claim_id"])] if issue.get("claim_id") else claim_ids[:20], "contradiction_refs": [str(issue["id"])], "verdict": _text(issue.get("verdict"), 80) or "INSUFFICIENT_EVIDENCE", "confidence": _confidence(issue.get("confidence"), 0.5), "created_at": captured_at})

    total = len(claims)
    sourced = sum(1 for x in claims if x.get("source_refs"))
    derived = sum(1 for x in claims if x.get("method") == "derived")
    asserted = sum(1 for x in claims if x.get("method") == "agent_assertion")
    invalid = sum(1 for x in claims if x.get("status") == "validation_error")
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": captured_at,
        "claims": claims[:MAX_LEDGER_CLAIMS],
        "evidence": evidence,
        "sources": list(source_by_id.values())[:MAX_LEDGER_SOURCES],
        "transformations": transformations[:MAX_LEDGER_TRANSFORMATIONS],
        "decisions": decisions[:MAX_LEDGER_DECISIONS],
        "summary": {
            "total_claims": total, "sourced_claims": sourced, "derived_claims": derived,
            "agent_assertions": asserted, "validation_error_claims": invalid,
            "evidence_records": len(evidence), "source_records": len(source_by_id),
            "transformation_records": len(transformations), "decision_records": len(decisions),
            "evidence_coverage_ratio": round(sourced / total, 3) if total else 0.0,
            "unsupported_claims": max(total - sourced - derived, 0),
        },
    }


def validate_provenance_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate the internal graph of provenance references."""
    errors: list[str] = []
    warnings: list[str] = []
    claims = ledger.get("claims", []) if isinstance(ledger.get("claims"), list) else []
    evidence = ledger.get("evidence", []) if isinstance(ledger.get("evidence"), list) else []
    sources = ledger.get("sources", []) if isinstance(ledger.get("sources"), list) else []
    transformations = ledger.get("transformations", []) if isinstance(ledger.get("transformations"), list) else []
    decisions = ledger.get("decisions", []) if isinstance(ledger.get("decisions"), list) else []
    claim_ids = {str(x.get("claim_id")) for x in claims if isinstance(x, dict) and x.get("claim_id")}
    evidence_ids = {str(x.get("evidence_id")) for x in evidence if isinstance(x, dict) and x.get("evidence_id")}
    source_ids = {str(x.get("source_id")) for x in sources if isinstance(x, dict) and x.get("source_id")}

    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            errors.append("claim missing claim_id")
            continue
        cid = str(claim["claim_id"])
        if claim.get("method") == "derived" and not claim.get("formula"):
            errors.append(f"derived claim {cid} missing formula")
        for dep in claim.get("dependencies", []) or []:
            if dep not in claim_ids:
                errors.append(f"claim {cid} references missing dependency {dep}")
        for eid in claim.get("evidence_refs", []) or []:
            if eid not in evidence_ids:
                errors.append(f"claim {cid} references missing evidence {eid}")
        for sid in claim.get("source_refs", []) or []:
            if sid not in source_ids:
                errors.append(f"claim {cid} references missing source {sid}")
        c = _number(claim.get("confidence"))
        if c is None or not 0 <= c <= 1:
            errors.append(f"claim {cid} has invalid confidence")

    for ev in evidence:
        if not isinstance(ev, dict):
            errors.append("evidence must be an object")
            continue
        if ev.get("source_id") not in source_ids:
            errors.append(f"evidence references missing source {ev.get('source_id')}")
    for source in sources:
        if not isinstance(source, dict) or not source.get("url"):
            errors.append("source missing url")
    for tx in transformations:
        if not isinstance(tx, dict):
            errors.append("transformation must be an object")
            continue
        if tx.get("output_claim_id") not in claim_ids:
            errors.append(f"transformation references missing output {tx.get('output_claim_id')}")
        for dep in tx.get("dependency_claims", []) or []:
            if dep not in claim_ids:
                errors.append(f"transformation references missing dependency {dep}")
    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append("decision must be an object")
            continue
        missing = [cid for cid in decision.get("claim_refs", []) or [] if cid not in claim_ids]
        if missing:
            errors.append(f"decision {decision.get('decision_id')} references missing claims: {missing[:3]}")
    if ledger.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("unsupported provenance schema version")
    return {"valid": not errors, "errors": errors, "warnings": warnings}
