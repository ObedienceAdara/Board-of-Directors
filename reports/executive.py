"""Build a compact strategic report model from full board state."""

from __future__ import annotations

import re
from typing import Any


def _clean(text: Any) -> str:
    text = str(text or "")
    text = re.sub(r"```(?:markdown|md)?", "", text, flags=re.I)
    return text.replace("\r", "").strip()


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\n+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized)
    return [p.strip(" -•\t") for p in parts if len(p.strip()) >= 35]


def _extract(text: Any, limit: int = 4, max_chars: int = 1500) -> str:
    raw = _clean(text)
    if not raw:
        return "No usable analysis was produced."
    lines = [re.sub(r"^#{1,6}\s*", "", x).strip() for x in raw.splitlines()]
    bullets = [x.lstrip("-*• ").strip() for x in lines if x.lstrip().startswith(("-", "*", "•"))]
    candidates = bullets or _sentences(raw)
    chosen: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = re.sub(r"\s+", " ", item.lower())
        if key in seen or len(item) < 20:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= limit:
            break
    if not chosen:
        chosen = [re.sub(r"\s+", " ", raw)]
    return "\n".join(f"• {item}" for item in chosen)[:max_chars]


def _validated_claims(state: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for agent in ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"):
        validation = state.get(f"{agent}_validation", {}) or {}
        for item in validation.get("claims", []) if isinstance(validation, dict) else []:
            if isinstance(item, dict) and item.get("id"):
                claims.append({"agent": agent, **item})
    return claims


def _strategic_metrics(state: dict[str, Any]) -> list[tuple[str, str]]:
    preferred = {
        "finance.startup_cost": "Startup cost",
        "finance.monthly_operating_cost": "Monthly operating cost",
        "unit_economics.ltv_cac_ratio": "LTV:CAC",
        "finance.break_even_month": "Break-even",
        "technical.mvp_weeks": "MVP timeline",
        "sales.annual_revenue_target": "Revenue target",
        "sales.required_annual_customers": "Annual customers required",
        "marketing.budget": "Marketing budget",
        "operations.annual_payroll": "Annual payroll",
        "market.tam": "TAM",
        "market.sam": "SAM",
        "market.som": "SOM",
    }
    metrics: list[tuple[str, str]] = []
    seen: set[str] = set()
    for claim in _validated_claims(state):
        label = preferred.get(str(claim.get("id")))
        if not label or label in seen:
            continue
        seen.add(label)
        value = claim.get("value")
        unit = str(claim.get("unit", "")).strip()
        formatted = f"{value:g} {unit}".strip() if isinstance(value, (int, float)) else f"{value} {unit}".strip()
        metrics.append((label, formatted))
    return metrics[:12]


def _provenance_metrics(state: dict[str, Any]) -> str:
    summary = state.get("provenance_summary", {}) or {}
    if not isinstance(summary, dict) or not summary:
        return "• Provenance ledger not generated."
    total = summary.get("total_claims", 0)
    sourced = summary.get("sourced_claims", 0)
    derived = summary.get("derived_claims", 0)
    asserted = summary.get("agent_assertions", 0)
    decisions = summary.get("decision_records", 0)
    coverage = float(summary.get("evidence_coverage_ratio", 0.0)) * 100
    return (
        f"• Claims tracked: {total}\n"
        f"• Source-backed claims: {sourced}\n"
        f"• Deterministically derived claims: {derived}\n"
        f"• Agent assertions without external source linkage: {asserted}\n"
        f"• Evidence coverage: {coverage:.1f}%\n"
        f"• Decisions linked to lineage: {decisions}"
    )


def _risk_lines(state: dict[str, Any]) -> str:
    contradictions = state.get("deterministic_contradictions", []) or []
    adjudication = state.get("contradiction_adjudication", {}) or {}
    issues = adjudication.get("issues", []) if isinstance(adjudication, dict) else []
    lines: list[str] = []
    for item in contradictions[:4]:
        if isinstance(item, dict):
            lines.append(f"• {item.get('id', 'Conflict')}: {item.get('statement', 'Cross-domain inconsistency detected.')}")
    for item in issues[:4]:
        if isinstance(item, dict) and item.get("verdict") != "ACCEPTABLE_DIFFERENCE":
            lines.append(f"• {item.get('id', 'Issue')}: {item.get('resolution', item.get('rationale', 'Review required.'))}")
    return "\n".join(lines[:6]) or "• No material cross-domain contradictions were recorded."


def _first_90_days(state: dict[str, Any]) -> list[tuple[str, str]]:
    """Turn actual board outputs into an execution sequence instead of boilerplate."""
    pm = _extract(state.get("product_roadmap"), 3, 1000)
    tech = _extract(state.get("tech_plan"), 3, 1000)
    gtM = _extract(state.get("marketing_plan"), 3, 1000)
    sales = _extract(state.get("sales_strategy"), 3, 900)
    ops = _extract(state.get("operations_plan"), 2, 700)
    finance = _extract(state.get("financial_plan"), 2, 700)
    return [
        ("0–30 days", f"{pm}\n{tech}\n• Establish the financial and customer-validation baseline.\n{finance}"),
        ("31–60 days", f"{gtM}\n{sales}\n• Run a controlled launch with measurable acquisition and conversion targets."),
        ("61–90 days", f"{ops}\n• Review observed economics, product adoption and delivery capacity.\n• Scale the strongest validated path, revise weak assumptions, or stop."),
    ]


def build_executive_report(state: dict[str, Any]) -> dict[str, Any]:
    brief = state.get("brief", {}) or {}
    idea = str(brief.get("idea", "Business Idea"))
    metrics = _strategic_metrics(state)
    metric_text = "\n".join(f"• {label}: {value}" for label, value in metrics) or "• No normalized metrics available."
    final_report = _clean(state.get("final_board_report", ""))
    consistency = str(state.get("consistency_status", "NOT_RUN"))
    scheduler = state.get("scheduler_status", {}) or {}
    passed = sum(1 for value in scheduler.values() if value == "passed")
    total = len(scheduler)

    pages = [
        {"title": "Executive Decision Brief", "subtitle": "What the board believes, what matters most, and what to do next", "blocks": [("Decision", _extract(final_report, 4, 1900)), ("Key Metrics", metric_text), ("Board Integrity", f"Consistency: {consistency}. Department execution: {passed}/{total} passed.")]},
        {"title": "The Opportunity", "subtitle": "Market attractiveness and strategic rationale", "blocks": [("Market evidence", _extract(state.get("research_report"), 5, 2000)), ("Founder / fit", _extract(brief.get("founder_background"), 2, 700))]},
        {"title": "Financial Case", "subtitle": "Economics, capital requirements, and viability", "blocks": [("Financial view", _extract(state.get("financial_plan"), 6, 2200)), ("Normalized metrics", metric_text)]},
        {"title": "Technical Feasibility", "subtitle": "Architecture, constraints, delivery risk and MVP boundary", "blocks": [("Engineering view", _extract(state.get("tech_plan"), 6, 2200))]},
        {"title": "Go-To-Market", "subtitle": "Positioning, channels and demand generation", "blocks": [("Marketing view", _extract(state.get("marketing_plan"), 6, 2200)), ("Sales engine", _extract(state.get("sales_strategy"), 4, 1500))]},
        {"title": "Operating Model", "subtitle": "People, process, capacity and execution model", "blocks": [("Operations view", _extract(state.get("operations_plan"), 6, 2200)), ("Capacity signals", _extract(state.get("product_roadmap"), 2, 800))]},
        {"title": "Product & MVP", "subtitle": "What should be built first and what should wait", "blocks": [("Product view", _extract(state.get("product_roadmap"), 7, 2500))]},
        {"title": "Risks & Contradictions", "subtitle": "The assumptions most likely to invalidate the plan", "blocks": [("Cross-functional risk register", _risk_lines(state)), ("CEO synthesis", _extract(final_report, 3, 1200))]},
        {"title": "First 90 Days", "subtitle": "Execution sequence derived from the board analysis", "blocks": _first_90_days(state)},
        {"title": "Assumptions & Evidence", "subtitle": "What is known, inferred and still uncertain", "blocks": [("Provenance integrity", _provenance_metrics(state)), ("Source / evidence posture", _extract(state.get("research_report"), 5, 1900)), ("Open questions", _extract(state.get("contradiction_adjudication"), 4, 1300))]},
        {"title": "Final Board Recommendation", "subtitle": "The decision page", "blocks": [("Recommendation", _extract(final_report, 7, 2600)), ("Non-negotiables", "• Do not treat unsupported assumptions as facts.\n• Resolve material contradictions before committing significant capital.\n• Re-run the board when core pricing, budget, timeline or market assumptions change.\n• Preserve claim-to-source and claim-to-formula lineage when numbers are changed.")]},
    ]
    return {"idea": idea, "pages": pages}
