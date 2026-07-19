"""
============================================================
 Board of Directors AI System — v2
 Stack:  LangChain + LangGraph + LangSmith + LangServe
 LLM:    Groq (llama-3.3-70b-versatile default; configurable per
         agent via env vars — see console.groq.com/docs/models)
 Output: Notion Board + PDF

 Install:
   pip install -r requirements.txt

 Run (CLI demo):
   python main.py

 Run (API server):
   python main.py serve

 API call:
   POST http://localhost:8000/board-meeting/invoke
   {
     "input": {
       "brief": {
         "idea": "...",
         "target_market": "...",
         "budget": "...",
         "founder_background": "...",
         "timeline": "...",
         "constraints": "..."
       }
     }
   }
============================================================
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# LangSmith auto-tracing via env vars:
#   LANGCHAIN_TRACING_V2=true
#   LANGCHAIN_API_KEY=your_key
#   LANGCHAIN_PROJECT=BoardOfDirectors

from langgraph.graph import StateGraph, START, END

from state  import BoardState, EVALUATED_AGENTS
from agents import (
    panel_reaction,
    ceo_assign_tasks,
    ceo_evaluate_agent,
    ceo_assemble_report,
    researcher_agent,
    cfo_agent,
    cto_agent,
    cmo_agent,
    sales_agent,
    coo_agent,
    pm_agent,
    RESEARCHER_MODEL,
    CFO_MODEL,
    CTO_MODEL,
    CMO_MODEL,
    SALES_MODEL,
    COO_MODEL,
    PM_MODEL,
)
from tools import create_notion_board, create_notion_page, generate_pdf


# ══════════════════════════════════════════════════════════════
# GRAPH NODES
# ══════════════════════════════════════════════════════════════

def node_panel_researcher(state):
    return panel_reaction(state, "researcher",    "Researcher",    RESEARCHER_MODEL)

def node_panel_cfo(state):
    return panel_reaction(state, "cfo",           "CFO",           CFO_MODEL)

def node_panel_cto(state):
    return panel_reaction(state, "cto",           "CTO",           CTO_MODEL)

def node_panel_cmo(state):
    return panel_reaction(state, "cmo",           "CMO",           CMO_MODEL)

def node_panel_coo(state):
    return panel_reaction(state, "coo",           "COO",           COO_MODEL)

def node_panel_sales(state):
    return panel_reaction(state, "head_of_sales", "Head of Sales", SALES_MODEL)

def node_panel_pm(state):
    return panel_reaction(state, "pm",            "PM",            PM_MODEL)


def node_ceo_assign(state):          return ceo_assign_tasks(state)
def node_researcher(state):          return researcher_agent(state)
def node_cfo(state):                 return cfo_agent(state)
def node_cto(state):                 return cto_agent(state)
def node_cmo(state):                 return cmo_agent(state)
def node_sales(state):               return sales_agent(state)
def node_coo(state):                 return coo_agent(state)
def node_pm(state):                  return pm_agent(state)
def node_ceo_assemble(state):        return ceo_assemble_report(state)

def node_eval_researcher(state):
    return ceo_evaluate_agent(state, "researcher",    "Researcher",    "research_report")

def node_eval_cfo(state):
    return ceo_evaluate_agent(state, "cfo",           "CFO",           "financial_plan")

def node_eval_cto(state):
    return ceo_evaluate_agent(state, "cto",           "CTO",           "tech_plan")

def node_eval_cmo(state):
    return ceo_evaluate_agent(state, "cmo",           "CMO",           "marketing_plan")

def node_eval_sales(state):
    return ceo_evaluate_agent(state, "head_of_sales", "Head of Sales", "sales_strategy")

def node_eval_coo(state):
    return ceo_evaluate_agent(state, "coo",           "COO",           "operations_plan")

def node_eval_pm(state):
    return ceo_evaluate_agent(state, "pm",            "PM",            "product_roadmap")


def node_output(state: BoardState) -> BoardState:
    """Generate Notion board and PDF."""
    print("\n📤 Generating outputs...")

    brief       = state["brief"]
    idea_title  = brief.get("idea", "Business Idea")[:60]
    board_title = f"Board Report — {idea_title} — {datetime.now().strftime('%Y-%m-%d')}"

    sections = [
        ("📋 Business Brief",          json.dumps(brief, indent=2)),
        ("🔬 Research Report",          state.get("research_report",   "")),
        ("💰 Financial Plan",           state.get("financial_plan",    "")),
        ("💻 Technical Architecture",   state.get("tech_plan",         "")),
        ("📣 Go-To-Market Strategy",    state.get("marketing_plan",    "")),
        ("🛒 Sales Strategy",           state.get("sales_strategy",    "")),
        ("⚙️  Operations Plan",         state.get("operations_plan",   "")),
        ("📋 Product Roadmap",          state.get("product_roadmap",   "")),
        ("👑 CEO Board Recommendation", state.get("final_board_report","")),
    ]

    # ── Notion ──────────────────────────────────────────────
    # All 8 department reports already exist in `state` at this point —
    # they're the valuable output. A Notion or PDF failure here should
    # never throw away analysis a customer is paying for, so both are
    # isolated in their own try/except instead of crashing node_output.
    notion_url = ""
    try:
        notion_board_id = create_notion_board(board_title)
        if notion_board_id:
            for title, content in sections:
                create_notion_page(notion_board_id, title, content)
            notion_url = f"https://notion.so/{notion_board_id.replace('-', '')}"
    except Exception as e:
        print(f"   ⚠️  Notion output failed, continuing without it: {e}")

    # ── PDF ─────────────────────────────────────────────────
    # Revision counts now live at flattened per-agent keys (e.g.
    # "cfo_revisions") rather than one shared dict — rebuild the log
    # LangGraph's join-safe schema requires from those individual keys.
    revision_log = [
        {"agent": agent, "revisions": state.get(f"{agent}_revisions", 0)}
        for agent in EVALUATED_AGENTS
    ]

    pdf_sections = [
        {"title": title, "content": content}
        for title, content in sections[1:]  # Skip brief — cover page handles it
    ]

    pdf_filename = ""
    try:
        pdf_filename = f"board_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        generate_pdf({
            "idea":              idea_title,
            "date":              datetime.now().strftime("%Y-%m-%d %H:%M"),
            "executive_summary": state.get("final_board_report", "")[:3000],
            "sections":          pdf_sections,
            "revision_log":      revision_log
        }, pdf_filename)
    except Exception as e:
        print(f"   ⚠️  PDF generation failed: {e}")
        pdf_filename = ""

    print(f"\n{'='*60}")
    print("🏁 BOARD MEETING COMPLETE")
    print(f"{'='*60}")
    if notion_url:
        print(f"📋 Notion → {notion_url}")
    if pdf_filename:
        print(f"📄 PDF    → {pdf_filename}")
    if not notion_url and not pdf_filename:
        print("⚠️  Both Notion and PDF output failed — see errors above. "
              "All department reports are still available in the returned state.")

    return {"notion_board_url": notion_url, "pdf_path": pdf_filename}


# ══════════════════════════════════════════════════════════════
# CONDITIONAL ROUTERS — tiered fan-out with gate barriers
# ══════════════════════════════════════════════════════════════
#
# Real dependencies between agents (from what each prompt actually reads):
#   Researcher <- brief only
#   CFO, CTO   <- Researcher
#   CMO, COO   <- CFO (CMO), CFO + CTO (COO)
#   Sales, PM  <- CMO + CFO (Sales), CMO + CTO (PM)
#
# That collapses into 4 tiers, each gated on the tier before it finishing:
#   Tier 1: Researcher (solo)
#   Tier 2: CFO ∥ CTO
#   Tier 3: CMO ∥ COO
#   Tier 4: Sales ∥ PM
#
# Each pair runs through a "gate" node — both branches unconditionally
# route there after every evaluation, and the gate's router inspects
# state to decide: retry whichever agent(s) haven't passed yet (as a
# variable-length list), or advance once both have. This was chosen
# over trying to make LangGraph's edge-based fan-in act as a barrier
# directly, which was tested and found to fire on every individual
# arrival rather than waiting for all siblings — the gate pattern was
# verified correct against asymmetric, independently-looping branches
# before being wired in here.

def _passed(state: BoardState, agent: str) -> bool:
    return bool(state.get(f"{agent}_passed", False))


def route_researcher(state: BoardState):
    if not _passed(state, "researcher"):
        return ["researcher"]
    return ["cfo", "cto"]           # fan out to Tier 2


def route_gate_tier2(state: BoardState):
    done = {a: _passed(state, a) for a in ("cfo", "cto")}
    if all(done.values()):
        return ["cmo", "coo"]       # fan out to Tier 3
    return [a for a, ok in done.items() if not ok]


def route_gate_tier3(state: BoardState):
    done = {a: _passed(state, a) for a in ("cmo", "coo")}
    if all(done.values()):
        return ["sales", "pm"]      # fan out to Tier 4
    return [a for a, ok in done.items() if not ok]


def route_gate_tier4(state: BoardState):
    done = {
        "sales": _passed(state, "head_of_sales"),
        "pm":    _passed(state, "pm"),
    }
    if all(done.values()):
        return ["ceo_assemble"]
    return [a for a, ok in done.items() if not ok]


def node_gate(state: BoardState) -> BoardState:
    """Pure barrier node — both branches in a tier route here after every
    evaluation; it makes no state changes itself, it only exists so the
    router functions above have a single shared point to fire from."""
    return {}


# ══════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ══════════════════════════════════════════════════════════════

def build_board_graph():
    g = StateGraph(BoardState)

    # Register all nodes
    g.add_node("panel_researcher",    node_panel_researcher)
    g.add_node("panel_cfo",           node_panel_cfo)
    g.add_node("panel_cto",           node_panel_cto)
    g.add_node("panel_cmo",           node_panel_cmo)
    g.add_node("panel_coo",           node_panel_coo)
    g.add_node("panel_sales",         node_panel_sales)
    g.add_node("panel_pm",            node_panel_pm)

    g.add_node("ceo_assign",      node_ceo_assign)
    g.add_node("researcher",      node_researcher)
    g.add_node("eval_researcher", node_eval_researcher)

    g.add_node("cfo",             node_cfo)
    g.add_node("eval_cfo",        node_eval_cfo)
    g.add_node("cto",             node_cto)
    g.add_node("eval_cto",        node_eval_cto)
    g.add_node("gate_tier2",      node_gate)

    g.add_node("cmo",             node_cmo)
    g.add_node("eval_cmo",        node_eval_cmo)
    g.add_node("coo",             node_coo)
    g.add_node("eval_coo",        node_eval_coo)
    g.add_node("gate_tier3",      node_gate)

    g.add_node("sales",           node_sales)
    g.add_node("eval_sales",      node_eval_sales)
    g.add_node("pm",              node_pm)
    g.add_node("eval_pm",         node_eval_pm)
    g.add_node("gate_tier4",      node_gate)

    g.add_node("ceo_assemble",    node_ceo_assemble)
    g.add_node("output",          node_output)

    # ── Tier 0: initial panel — 7-way fan-out from start, one-shot
    #    (no retry loop, so the plain static-edge fan-in barrier that
    #    verified correctly for this exact shape applies here) ──────
    for panel_node in ("panel_researcher", "panel_cfo", "panel_cto",
                        "panel_cmo", "panel_coo", "panel_sales", "panel_pm"):
        g.add_edge(START, panel_node)
        g.add_edge(panel_node, "ceo_assign")

    g.add_edge("ceo_assign", "researcher")

    # ── Tier 1: Researcher (solo) ────────────────────────────
    g.add_edge("researcher", "eval_researcher")
    g.add_conditional_edges(
        "eval_researcher", route_researcher,
        {"researcher": "researcher", "cfo": "cfo", "cto": "cto"}
    )

    # ── Tier 2: CFO ∥ CTO ─────────────────────────────────────
    g.add_edge("cfo", "eval_cfo")
    g.add_edge("eval_cfo", "gate_tier2")
    g.add_edge("cto", "eval_cto")
    g.add_edge("eval_cto", "gate_tier2")
    g.add_conditional_edges(
        "gate_tier2", route_gate_tier2,
        {"cfo": "cfo", "cto": "cto", "cmo": "cmo", "coo": "coo"}
    )

    # ── Tier 3: CMO ∥ COO ─────────────────────────────────────
    g.add_edge("cmo", "eval_cmo")
    g.add_edge("eval_cmo", "gate_tier3")
    g.add_edge("coo", "eval_coo")
    g.add_edge("eval_coo", "gate_tier3")
    g.add_conditional_edges(
        "gate_tier3", route_gate_tier3,
        {"cmo": "cmo", "coo": "coo", "sales": "sales", "pm": "pm"}
    )

    # ── Tier 4: Sales ∥ PM ────────────────────────────────────
    g.add_edge("sales", "eval_sales")
    g.add_edge("eval_sales", "gate_tier4")
    g.add_edge("pm", "eval_pm")
    g.add_edge("eval_pm", "gate_tier4")
    g.add_conditional_edges(
        "gate_tier4", route_gate_tier4,
        {"sales": "sales", "pm": "pm", "ceo_assemble": "ceo_assemble"}
    )

    # ── Final ────────────────────────────────────────────────
    g.add_edge("ceo_assemble", "output")
    g.add_edge("output",       END)

    return g.compile()


board_graph = build_board_graph()


# ══════════════════════════════════════════════════════════════
# PUBLIC RUNNER
# ══════════════════════════════════════════════════════════════

def run_board_meeting(brief: dict) -> dict:
    """
    Run the full board meeting for a business idea.

    brief = {
      "idea":               "...",
      "target_market":      "...",
      "budget":             "...",
      "founder_background": "...",
      "timeline":           "...",
      "constraints":        "..."
    }
    """
    print(f"\n{'='*60}")
    print("🏢 BOARD OF DIRECTORS — MEETING CALLED TO ORDER")
    print(f"{'='*60}")
    print(f"💡 Idea: {brief.get('idea', '')[:80]}")

    initial_state = BoardState(
        brief=brief,
        researcher_panel="", cfo_panel="", cto_panel="", cmo_panel="",
        coo_panel="", head_of_sales_panel="", pm_panel="",
        research_report="",
        financial_plan="",
        tech_plan="",
        marketing_plan="",
        operations_plan="",
        sales_strategy="",
        product_roadmap="",
        ceo_task_assignments="",
        final_board_report="",
        researcher_revisions=0,    researcher_passed=False,    researcher_feedback="",
        cfo_revisions=0,           cfo_passed=False,           cfo_feedback="",
        cto_revisions=0,           cto_passed=False,           cto_feedback="",
        cmo_revisions=0,           cmo_passed=False,           cmo_feedback="",
        coo_revisions=0,           coo_passed=False,           coo_feedback="",
        head_of_sales_revisions=0, head_of_sales_passed=False, head_of_sales_feedback="",
        pm_revisions=0,            pm_passed=False,            pm_feedback="",
        notion_board_url="",
        pdf_path="",
    )

    final_state = board_graph.invoke(initial_state)

    return {
        "final_report":     final_state["final_board_report"],
        "notion_board_url": final_state["notion_board_url"],
        "pdf_path":         final_state["pdf_path"],
        "revision_summary": {
            agent: final_state.get(f"{agent}_revisions", 0)
            for agent in EVALUATED_AGENTS
        }
    }


# ══════════════════════════════════════════════════════════════
# LANGSERVE — REST API
# ══════════════════════════════════════════════════════════════

import time
from collections import defaultdict
from fastapi               import FastAPI, Request
from fastapi.responses     import JSONResponse
from langserve             import add_routes
from langchain_core.runnables import RunnableLambda

# ── Auth + rate limit config ─────────────────────────────────
_API_SECRET_KEY    = os.getenv("API_SECRET_KEY", "")
_RATE_LIMIT        = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
_EXEMPT_PATHS      = {"/", "/docs", "/openapi.json", "/redoc"}

# In-memory rate limit store: { ip: [timestamp, ...] }
_request_log: dict = defaultdict(list)


app = FastAPI(
    title="Plex Hedge — Board of Directors AI",
    description="Multi-agent AI board: CEO, CFO, CTO, CMO, Sales, COO, PM, Researcher",
    version="2.0.0"
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Skip auth + rate limiting for non-sensitive paths
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)

    # ── API Key check ────────────────────────────────────────
    if _API_SECRET_KEY:
        incoming_key = request.headers.get("X-API-Key", "")
        if incoming_key != _API_SECRET_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."}
            )

    # ── Rate limiting ────────────────────────────────────────
    client_ip  = request.client.host if request.client else "unknown"
    now        = time.time()
    window     = now - 60  # 1-minute sliding window

    # Purge timestamps outside the window
    _request_log[client_ip] = [t for t in _request_log[client_ip] if t > window]

    if len(_request_log[client_ip]) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Max {_RATE_LIMIT} requests per minute."}
        )

    _request_log[client_ip].append(now)
    return await call_next(request)

board_runnable = RunnableLambda(
    lambda inputs: run_board_meeting(inputs["brief"])
)

add_routes(app, board_runnable, path="/board-meeting")

@app.get("/")
async def root():
    return {
        "status":     "running",
        "version":    "2.0.0",
        "agents":     ["CEO", "Researcher", "CFO", "CTO", "CMO", "Head of Sales", "COO", "PM"],
        "docs":       "/docs",
        "playground": "/board-meeting/playground"
    }


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import uvicorn
        print("\n🌐 Starting Board of Directors API...")
        print("   Playground → http://localhost:8000/board-meeting/playground")
        print("   Docs       → http://localhost:8000/docs")
        uvicorn.run(app, host="127.0.0.1", port=8000)

    else:
        # Demo run
        demo_brief = {
            "idea":               "A SaaS platform that automates post-purchase email sequences for Shopify stores using AI to reduce churn and increase repeat purchases",
            "target_market":      "E-commerce brands doing $500K–$5M/year on Shopify with no dedicated email marketing team",
            "budget":             "$50,000 initial capital",
            "founder_background": "Solo technical founder, 2 years software experience, basic marketing knowledge",
            "timeline":           "MVP in 3 months",
            "constraints":        "Bootstrapped, no investors, must generate revenue within 6 months"
        }
        run_board_meeting(demo_brief)
