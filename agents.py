"""
agents.py — All 8 board agents.

Fixes applied:
  - langchain_tavily.TavilySearch replaces deprecated TavilySearchResults
  - parse_search_results() handles all Tavily return types safely
  - JSON cleaning strips markdown fences before parsing
  - Token guards on all long inputs
"""

import os
import json

from langchain_openai           import ChatOpenAI
from langchain_core.prompts     import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from state   import BoardState
from prompts import (
    CEO_TASK_ASSIGNMENT_PROMPT,
    CEO_EVALUATE_PROMPT,
    CEO_ASSEMBLE_PROMPT,
    RESEARCHER_PROMPT,
    CFO_PROMPT,
    CTO_PROMPT,
    CMO_PROMPT,
    SALES_PROMPT,
    COO_PROMPT,
    PM_PROMPT,
)
from tools import get_search_tool, parse_search_results


# ══════════════════════════════════════════════════════════════
# LLM FACTORY
# ══════════════════════════════════════════════════════════════

def make_llm(model: str, temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=os.getenv("GROQ_API_KEY"),
        openai_api_base="https://api.groq.com/openai/v1",
        default_headers={
            "HTTP-Referer": "https://plexhedge.com",
            "X-Title":      "Plex Hedge Board of Directors AI"
        }
    )


# ── Model assignments ─────────────────────────────────────────
# Swap any of these for free models during testing.
# Free options on OpenRouter: google/gemini-2.0-flash-exp:free,
#   meta-llama/llama-3.3-70b-instruct:free, mistralai/mistral-7b-instruct:free
CEO_MODEL        = os.getenv("CEO_MODEL",        "llama-3.3-70b-versatile")
RESEARCHER_MODEL = os.getenv("RESEARCHER_MODEL", "llama-3.3-70b-versatile")
CFO_MODEL        = os.getenv("CFO_MODEL",        "llama-3.3-70b-versatile")
CTO_MODEL        = os.getenv("CTO_MODEL",        "llama-3.3-70b-versatile")
CMO_MODEL        = os.getenv("CMO_MODEL",        "llama-3.3-70b-versatile")
SALES_MODEL      = os.getenv("SALES_MODEL",      "llama-3.3-70b-versatile")
COO_MODEL        = os.getenv("COO_MODEL",        "llama-3.3-70b-versatile")
PM_MODEL         = os.getenv("PM_MODEL",         "llama-3.3-70b-versatile")

# Shared search tool
_search = get_search_tool(max_results=5)

# Output parser
parser = StrOutputParser()


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

# Max characters allowed per brief field
_FIELD_MAX_LENGTHS = {
    "idea":               500,
    "target_market":      300,
    "budget":             100,
    "founder_background": 300,
    "timeline":           100,
    "constraints":        300,
}

# Patterns that are common prompt injection attempts
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "you are now",
    "new instructions",
    "system:",
    "assistant:",
    "user:",
    "human:",
    "disregard",
    "forget everything",
    "jailbreak",
]


def sanitize_field(value: str, max_len: int) -> str:
    """
    Sanitize a single brief field:
    - Enforce max length
    - Collapse newlines/tabs to a single space (prevents prompt structure breaking)
    - Strip HTML/XML-like angle brackets
    - Block known prompt injection phrases (case-insensitive)
    """
    if not isinstance(value, str):
        value = str(value)

    # Truncate first
    value = value[:max_len]

    # Collapse whitespace control characters to a space
    value = value.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # Strip angle brackets used in XML/HTML injection
    value = value.replace("<", "").replace(">", "")

    # Block injection phrases
    lower = value.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in lower:
            raise ValueError(f"Brief field contains disallowed content: '{pattern}'")

    return value.strip()


def sanitize_brief(brief: dict) -> dict:
    """Sanitize all fields in the business brief."""
    sanitized = {}
    for field, max_len in _FIELD_MAX_LENGTHS.items():
        raw = brief.get(field, "")
        sanitized[field] = sanitize_field(raw, max_len)
    return sanitized


def brief_to_str(brief: dict) -> str:
    safe = sanitize_brief(brief)
    return (
        f"Idea: {safe.get('idea', '')}\n"
        f"Target Market: {safe.get('target_market', '')}\n"
        f"Budget: {safe.get('budget', '')}\n"
        f"Founder Background: {safe.get('founder_background', '')}\n"
        f"Timeline: {safe.get('timeline', '')}\n"
        f"Constraints: {safe.get('constraints', '')}"
    )


def clean_json(raw: str) -> str:
    """Strip markdown fences before JSON parsing."""
    return raw.replace("```json", "").replace("```", "").strip()


def get_task(state: BoardState, agent_key: str) -> str:
    try:
        obj = json.loads(clean_json(state.get("ceo_task_assignments", "{}")))
        return obj.get("tasks", {}).get(agent_key, "Perform your standard analysis.")
    except Exception:
        return "Perform your standard analysis."


def get_feedback(state: BoardState, agent_name: str) -> str:
    evals = state.get("evaluations", {})
    if agent_name in evals:
        return evals[agent_name].get("feedback", "")
    return ""


def do_search(query: str) -> str:
    """Run a search and return safely parsed results."""
    try:
        results = _search.invoke(query)
        return parse_search_results(results)
    except Exception as e:
        return f"Search error: {e}"


def multi_search(queries: list[str]) -> str:
    """Run multiple searches and concatenate results."""
    all_results = []
    for q in queries[:3]:
        all_results.append(do_search(str(q)))
    return "\n\n---\n\n".join(all_results)


def get_search_queries(brief_str: str, task: str, model: str) -> list[str]:
    """Ask the LLM to generate 3 targeted search queries."""
    llm = make_llm(model)
    prompt = ChatPromptTemplate.from_template(
        "Generate 3 specific web search queries to research this business task.\n"
        "Return ONLY a JSON list of strings. No markdown. No explanation.\n\n"
        "Business: {brief}\nTask: {task}"
    )
    chain = prompt | llm | parser
    try:
        raw     = chain.invoke({"brief": brief_str[:500], "task": task[:300]})
        queries = json.loads(clean_json(raw))
        return queries if isinstance(queries, list) else [task]
    except Exception:
        return [task]


# ══════════════════════════════════════════════════════════════
# CEO AGENT
# ══════════════════════════════════════════════════════════════

def ceo_assign_tasks(state: BoardState) -> BoardState:
    print("\n👑 CEO — Assigning tasks to all departments...")
    llm    = make_llm(CEO_MODEL)
    prompt = ChatPromptTemplate.from_template(CEO_TASK_ASSIGNMENT_PROMPT)
    chain  = prompt | llm | parser
    result = chain.invoke({"brief": brief_to_str(state["brief"])})

    return {
        **state,
        "ceo_task_assignments": clean_json(result),
        "evaluations":          {},
        "revision_counts":      {},
        "needs_revision":       []
    }


def ceo_evaluate_agent(
    state: BoardState,
    agent_name: str,
    agent_role: str,
    output_key: str
) -> BoardState:
    print(f"\n👑 CEO — Evaluating {agent_role}...")
    llm    = make_llm(CEO_MODEL)
    prompt = ChatPromptTemplate.from_template(CEO_EVALUATE_PROMPT)
    chain  = prompt | llm | parser

    output = state.get(output_key, "")
    result = chain.invoke({
        "agent_role": agent_role,
        "brief":      brief_to_str(state["brief"]),
        "output":     output[:3000]
    })

    try:
        eval_obj = json.loads(clean_json(result))
    except Exception:
        eval_obj = {"passed": True, "feedback": "", "scores": {}}

    passed   = eval_obj.get("passed", True)
    feedback = eval_obj.get("feedback", "")

    # Hard cap: accept after 3 revisions
    revision_counts = dict(state.get("revision_counts", {}))
    current_count   = revision_counts.get(agent_name, 0)
    if current_count >= 3:
        passed   = True
        feedback = ""
        print(f"   ⚠️  Max revisions hit for {agent_role}. Accepting.")

    evaluations = dict(state.get("evaluations", {}))
    evaluations[agent_name] = {
        "passed":     passed,
        "feedback":   feedback,
        "iterations": current_count
    }

    needs_revision = list(state.get("needs_revision", []))
    if not passed:
        if agent_name not in needs_revision:
            needs_revision.append(agent_name)
        print(f"   ❌ Needs revision: {feedback[:120]}...")
    else:
        if agent_name in needs_revision:
            needs_revision.remove(agent_name)
        print(f"   ✅ Approved.")

    return {
        **state,
        "evaluations":     evaluations,
        "revision_counts": revision_counts,
        "needs_revision":  needs_revision
    }


def ceo_assemble_report(state: BoardState) -> BoardState:
    print("\n👑 CEO — Assembling final board report...")
    llm    = make_llm(CEO_MODEL)
    prompt = ChatPromptTemplate.from_template(CEO_ASSEMBLE_PROMPT)
    chain  = prompt | llm | parser

    report = chain.invoke({
        "brief":           brief_to_str(state["brief"]),
        "research_report": state.get("research_report",  "")[:2000],
        "financial_plan":  state.get("financial_plan",   "")[:2000],
        "tech_plan":       state.get("tech_plan",        "")[:2000],
        "marketing_plan":  state.get("marketing_plan",   "")[:2000],
        "sales_strategy":  state.get("sales_strategy",   "")[:2000],
        "operations_plan": state.get("operations_plan",  "")[:2000],
        "product_roadmap": state.get("product_roadmap",  "")[:2000],
    })

    return {**state, "final_board_report": report}


# ══════════════════════════════════════════════════════════════
# RESEARCHER
# ══════════════════════════════════════════════════════════════

def researcher_agent(state: BoardState) -> BoardState:
    print("\n🔬 Researcher — Conducting market research...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "researcher")
    queries   = get_search_queries(brief_str, task, RESEARCHER_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(RESEARCHER_MODEL)
    prompt = ChatPromptTemplate.from_template(RESEARCHER_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":          brief_str,
        "task":           task,
        "feedback":       get_feedback(state, "researcher"),
        "search_results": search_results[:6000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["researcher"] = rc.get("researcher", 0) + 1
    return {**state, "research_report": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# CFO
# ══════════════════════════════════════════════════════════════

def cfo_agent(state: BoardState) -> BoardState:
    print("\n💰 CFO — Building financial model...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "cfo")
    queries   = get_search_queries(brief_str, task, CFO_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(CFO_MODEL)
    prompt = ChatPromptTemplate.from_template(CFO_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":           brief_str,
        "task":            task,
        "research_report": state.get("research_report", "")[:2000],
        "feedback":        get_feedback(state, "cfo"),
        "search_results":  search_results[:4000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["cfo"] = rc.get("cfo", 0) + 1
    return {**state, "financial_plan": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# CTO
# ══════════════════════════════════════════════════════════════

def cto_agent(state: BoardState) -> BoardState:
    print("\n💻 CTO — Designing technical architecture...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "cto")
    queries   = get_search_queries(brief_str, task, CTO_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(CTO_MODEL)
    prompt = ChatPromptTemplate.from_template(CTO_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":           brief_str,
        "task":            task,
        "research_report": state.get("research_report", "")[:2000],
        "feedback":        get_feedback(state, "cto"),
        "search_results":  search_results[:4000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["cto"] = rc.get("cto", 0) + 1
    return {**state, "tech_plan": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# CMO
# ══════════════════════════════════════════════════════════════

def cmo_agent(state: BoardState) -> BoardState:
    print("\n📣 CMO — Building go-to-market strategy...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "cmo")
    queries   = get_search_queries(brief_str, task, CMO_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(CMO_MODEL)
    prompt = ChatPromptTemplate.from_template(CMO_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":           brief_str,
        "task":            task,
        "research_report": state.get("research_report", "")[:2000],
        "financial_plan":  state.get("financial_plan",  "")[:1000],
        "feedback":        get_feedback(state, "cmo"),
        "search_results":  search_results[:4000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["cmo"] = rc.get("cmo", 0) + 1
    return {**state, "marketing_plan": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# HEAD OF SALES
# ══════════════════════════════════════════════════════════════

def sales_agent(state: BoardState) -> BoardState:
    print("\n🛒 Head of Sales — Crafting sales strategy...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "head_of_sales")
    queries   = get_search_queries(brief_str, task, SALES_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(SALES_MODEL)
    prompt = ChatPromptTemplate.from_template(SALES_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":           brief_str,
        "task":            task,
        "research_report": state.get("research_report", "")[:1500],
        "marketing_plan":  state.get("marketing_plan",  "")[:1500],
        "financial_plan":  state.get("financial_plan",  "")[:1000],
        "feedback":        get_feedback(state, "head_of_sales"),
        "search_results":  search_results[:4000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["head_of_sales"] = rc.get("head_of_sales", 0) + 1
    return {**state, "sales_strategy": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# COO
# ══════════════════════════════════════════════════════════════

def coo_agent(state: BoardState) -> BoardState:
    print("\n⚙️  COO — Building operations plan...")

    brief_str = brief_to_str(state["brief"])
    task      = get_task(state, "coo")
    queries   = get_search_queries(brief_str, task, COO_MODEL)
    search_results = multi_search(queries)

    llm    = make_llm(COO_MODEL)
    prompt = ChatPromptTemplate.from_template(COO_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":          brief_str,
        "task":           task,
        "tech_plan":      state.get("tech_plan",      "")[:1500],
        "financial_plan": state.get("financial_plan", "")[:1500],
        "feedback":       get_feedback(state, "coo"),
        "search_results": search_results[:4000]
    })

    rc = dict(state.get("revision_counts", {}))
    rc["coo"] = rc.get("coo", 0) + 1
    return {**state, "operations_plan": output, "revision_counts": rc}


# ══════════════════════════════════════════════════════════════
# PM
# ══════════════════════════════════════════════════════════════

def pm_agent(state: BoardState) -> BoardState:
    print("\n📋 PM — Defining product roadmap...")

    # PM synthesises — no web search needed
    llm    = make_llm(PM_MODEL)
    prompt = ChatPromptTemplate.from_template(PM_PROMPT)
    chain  = prompt | llm | parser

    output = chain.invoke({
        "brief":           brief_to_str(state["brief"]),
        "task":            get_task(state, "pm"),
        "research_report": state.get("research_report",  "")[:1500],
        "tech_plan":       state.get("tech_plan",        "")[:1500],
        "marketing_plan":  state.get("marketing_plan",   "")[:1500],
        "feedback":        get_feedback(state, "pm")
    })

    rc = dict(state.get("revision_counts", {}))
    rc["pm"] = rc.get("pm", 0) + 1
    return {**state, "product_roadmap": output, "revision_counts": rc}
