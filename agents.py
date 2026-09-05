"""Compatibility facade for the v3 formal agent engine.

The production implementation now lives in formal_agents.py. These wrappers
keep the original public function names usable by older callers while routing
them into the v3 structured-output pipeline.
"""

from formal_agents import (
    MODELS,
    REPORT_KEYS,
    VALIDATION_KEYS,
    build_formal_by_agent,
    brief_to_str,
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


def adjudicate_contradictions(state):
    from formal_agents import adjudicate_contradictions as _adjudicate
    return _adjudicate(state)


def __getattr__(name):
    """Fail clearly for functions removed during the v3 migration."""
    raise AttributeError(f"agents.{name} was replaced by the v3 formal engine in formal_agents.py")
