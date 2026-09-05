"""Stable public agent API with compatibility exports for the v3 transition."""

from formal_agents import (
    MODELS,
    REPORT_KEYS,
    VALIDATION_KEYS,
    ROLES,
    adjudicate_contradictions,
    brief_to_str,
    build_formal_by_agent,
    ceo_adjudicate_contradictions,
    ceo_assemble_report,
    ceo_assign_tasks,
    ceo_evaluate_agent,
    clean_json,
    do_search,
    frame_untrusted,
    get_search_queries,
    make_llm,
    multi_search,
    other_departments_context,
    panel_reaction,
    run_department,
    safe_invoke,
    sanitize_brief,
    sanitize_field,
    sanitize_search_content,
)

CEO_MODEL = MODELS["ceo"]
RESEARCHER_MODEL = MODELS["researcher"]
CFO_MODEL = MODELS["cfo"]
CTO_MODEL = MODELS["cto"]
CMO_MODEL = MODELS["cmo"]
SALES_MODEL = MODELS["head_of_sales"]
COO_MODEL = MODELS["coo"]
PM_MODEL = MODELS["pm"]


def researcher_agent(state):
    return run_department("researcher", state)


def cfo_agent(state):
    return run_department("cfo", state)


def cto_agent(state):
    return run_department("cto", state)


def cmo_agent(state):
    return run_department("cmo", state)


def sales_agent(state):
    return run_department("head_of_sales", state)


def coo_agent(state):
    return run_department("coo", state)


def pm_agent(state):
    return run_department("pm", state)


__all__ = [
    "MODELS", "ROLES", "REPORT_KEYS", "VALIDATION_KEYS",
    "CEO_MODEL", "RESEARCHER_MODEL", "CFO_MODEL", "CTO_MODEL", "CMO_MODEL",
    "SALES_MODEL", "COO_MODEL", "PM_MODEL",
    "adjudicate_contradictions", "brief_to_str", "build_formal_by_agent",
    "ceo_adjudicate_contradictions", "ceo_assemble_report", "ceo_assign_tasks",
    "ceo_evaluate_agent", "clean_json", "do_search", "frame_untrusted",
    "get_search_queries", "make_llm", "multi_search", "other_departments_context",
    "panel_reaction", "run_department", "safe_invoke", "sanitize_brief",
    "sanitize_field", "sanitize_search_content", "researcher_agent", "cfo_agent",
    "cto_agent", "cmo_agent", "sales_agent", "coo_agent", "pm_agent",
]
