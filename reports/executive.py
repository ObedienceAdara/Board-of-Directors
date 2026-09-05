"""Build a compact, strategic report model from full board state.

The analysis engine may produce long departmental narratives. This layer turns
those artifacts into a bounded executive document without changing the source
analysis itself. The full artifacts remain available through Notion/state;
the PDF is intentionally optimized for decision-making.
"""

from __future__ import annotations

import re
from typing import Any

AGENT_SECTIONS = (
    ("researcher", "Opportunity & Market", "research_report"),
    ("cfo", "Financial Case", "financial_plan"),
    ("cto", "Technical Feasibility", "tech_plan"),
    ("cmo", "Go-To-Market", "marketing_plan"),
    ("head_of_sales", "Sales Engine", "sales_strategy"),
    ("coo", "Operating Model", "operations_plan"),
    ("pm", "Product & Roadmap", "product_roadmap"),
)


def _clean(text: Any) -> str:
    text = str(text or "")
    text = re.sub(r"```(?:markdown|md)?", "", text, flags=re.I)
    text = text.replace("\r", "")
    return text.strip()


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
        chosen = [re.sub(r"\s+", " ", raw)[:max_chars]]
    return "\n".join(f"• {item}" for item in chosen)[:max_chars]


def _claim_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for agent, payload in snapshot.items():
        if not isinstance(payload, dict):
            continue
        for claim in payload.get("claims", []) or []:
            if isinstance(claim, dict) and claim.get("id"):
                claims.append({"agent": agent, **claim})
    return claims


def _strategic_metrics(state: dict[str, Any]) -> list[tuple[str, str]]:
    formal = state.get("formal_snapshot", {}) or {}
    metrics: list[tuple[str, str]] = []
    claims = _claim_rows(formal)
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
    for claim in claims:
        label = preferred.get(str(claim.get("id")))
        if not label:
            continue
        value = claim.get("value")
        unit = str(claim.get("unit", "")).strip()
        metrics.append((label, f"{value:g} {unit}".strip() if isinstance(value, (int, float)) else f"{value} {unit}".strip()))
    return metrics[:12]


def _risk_lines(state: dict[str, Any]) -> str:
    contradictions = state.get("deterministic_contradictions", []) or []
    adjudication = state.get("contradiction_adjudication", {}) or {}
    issues = adjudication.get("issues", []) if isinstance(adjudication, dict) else []
    lines: list[str] = []
    for item in contradictions[:4]:
        if isinstance(item, dict):
            lines.append(f"• {item.get('id', 'Conflict')}: {item.get('message', item.get('description', 'Cross-domain inconsistency detected.'))}")
    for item in issues[:4]:
        if isinstance(item, dict) and item.get("verdict") != "ACCEPTABLE_DIFFERENCE":
            lines.append(f"• {item.get('id', 'Adjudicated issue')}: {item.get('resolution', item.get('rationale', 'Review required.'))}")
    return "\n".join(lines[:6]) or "• No material cross-domain contradictions were recorded."


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
        {
            "title": "Executive Decision Brief",
            "subtitle": "What the board believes, what matters most, and what to do next",
            "blocks": [
                ("Decision", _extract(final_report, 4, 1900)),
                ("Key Metrics", metric_text),
                ("Board Integrity", f"Consistency: {consistency}. Department execution: {passed}/{total} passed."),
            ],
        },
        {
            "title": "The Opportunity",
            "subtitle": "Market attractiveness and strategic rationale",
            "blocks": [("Market evidence", _extract(state.get("research_report"), 5, 2000)), ("Founder / fit", _extract(brief.get("founder_background"), 2, 700))],
        },
        {
            "title": "Financial Case",
            "subtitle": "Economics, capital requirements, and viability",
            "blocks": [("Financial view", _extract(state.get("financial_plan"), 6, 2200)), ("Normalized metrics", metric_text)],
        },
        {
            "title": "Technical Feasibility",
            "subtitle": "Architecture, constraints, delivery risk and MVP boundary",
            "blocks": [("Engineering view", _extract(state.get("tech_plan"), 6, 2200))],
        },
        {
            "title": "Go-To-Market",
            "subtitle": "Positioning, channels and demand generation",
            "blocks": [("Marketing view", _extract(state.get("marketing_plan"), 6, 2200)), ("Sales engine", _extract(state.get("sales_strategy"), 4, 1500))],
        },
        {
            "title": "Operating Model",
            "subtitle": "People, process, capacity and execution model",
            "blocks": [("Operations view", _extract(state.get("operations_plan"), 6, 2200)), ("Capacity signals", _extract(state.get("product_roadmap"), 2, 800))],
        },
        {
            "title": "Product & MVP",
            "subtitle": "What should be built first and what should wait",
            "blocks": [("Product view", _extract(state.get("product_roadmap"), 7, 2500))],
        },
        {
            "title": "Risks & Contradictions",
            "subtitle": "The assumptions most likely to invalidate the plan",
            "blocks": [("Cross-functional risk register", _risk_lines(state)), ("CEO synthesis", _extract(final_report, 3, 1200))],
        },
        {
            "title": "First 90 Days",
            "subtitle": "Execution sequence derived from the board analysis",
            "blocks": [
                ("0–30 days", "• Validate the riskiest customer and market assumptions.\n• Lock the smallest credible MVP.\n• Establish baseline unit economics and acquisition targets."),
                ("31–60 days", "• Ship MVP to a controlled cohort.\n• Measure activation, conversion and retention.\n• Replace weak assumptions with observed data."),
                ("61–90 days", "• Double down on the strongest acquisition channel.\n• Tighten operating capacity and costs.\n• Decide whether to scale, iterate or stop."),
            ],
        },
        {
            "title": "Assumptions & Evidence",
            "subtitle": "What is known, inferred and still uncertain",
            "blocks": [
                ("Source / evidence posture", _extract(state.get("research_report"), 5, 2100)),
                ("Open questions", _extract(state.get("contradiction_adjudication"), 4, 1500)),
            ],
        },
        {
            "title": "Final Board Recommendation",
            "subtitle": "The decision page",
            "blocks": [
                ("Recommendation", _extract(final_report, 7, 2600)),
                ("Non-negotiables", "• Do not treat unsupported assumptions as facts.\n• Resolve material contradictions before committing significant capital.\n• Re-run the board when core pricing, budget, timeline or market assumptions change."),
            ],
        },
    ]
    return {"idea": idea, "pages": pages}
