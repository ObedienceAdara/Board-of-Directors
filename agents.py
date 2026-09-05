"""Compatibility facade for the v3 formal agent engine.

The production implementation now lives in formal_agents.py. These wrappers
keep the original public function names usable by older callers while routing
them into the v3 structured-output pipeline.
"""

from formal_agents import MODELS, run_department

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
