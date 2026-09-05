"""Board of Directors AI — v3.

Architecture:
  Tier 0        -> parallel panel reactions
  CEO planner   -> targeted work orders
  Dynamic DAG   -> dependency-ready departments execute concurrently
  Local gates   -> deterministic validation + CEO quality gate + revisions
  Global pass   -> deterministic cross-domain contradiction detection
                    + LLM adjudication
  CEO synthesis -> final decision using the formal consistency record
  Delivery      -> PDF + optional Notion

LangGraph remains the outer execution envelope/API contract. The formal
analysis stage uses a dependency scheduler because fixed tiers artificially
wait for unrelated branches.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph
from langserve import add_routes

from formal_agents import (
    adjudicate_contradictions,
    ceo_adjudicate_contradictions,
    ceo_assemble_report,
    ceo_assign_tasks,
    ceo_evaluate_agent,
    panel_reaction,
    run_department,
    ROLES,
)
from scheduler import AGENT_ORDER, DynamicReadinessScheduler
from state import BoardState, EVALUATED_AGENTS
from tools import create_notion_board, create_notion_page, generate_pdf


def run_panel(state: dict[str, Any]) -> dict[str, Any]:
    """Seven-way one-shot panel fan-out."""
    result: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=7, thread_name_prefix="board-panel") as pool:
        futures = {pool.submit(panel_reaction, state, agent, ROLES[agent]): agent for agent in AGENT_ORDER}
        for future in as_completed(futures):
            result.update(future.result())
    return result


def initialize_state(brief: dict[str, Any]) -> BoardState:
    return BoardState(
        brief=brief,
        researcher_panel="", cfo_panel="", cto_panel="", cmo_panel="",
        coo_panel="", head_of_sales_panel="", pm_panel="", ceo_task_assignments="",
        research_report="", financial_plan="", tech_plan="", marketing_plan="",
        operations_plan="", sales_strategy="", product_roadmap="", final_board_report="",
        researcher_revisions=0, researcher_passed=False, researcher_feedback="",
        cfo_revisions=0, cfo_passed=False, cfo_feedback="",
        cto_revisions=0, cto_passed=False, cto_feedback="",
        cmo_revisions=0, cmo_passed=False, cmo_feedback="",
        coo_revisions=0, coo_passed=False, coo_feedback="",
        head_of_sales_revisions=0, head_of_sales_passed=False, head_of_sales_feedback="",
        pm_revisions=0, pm_passed=False, pm_feedback="",
        scheduler_status={}, scheduler_events=[], revision_summary={},
        formal_snapshot={}, deterministic_contradictions=[], contradiction_adjudication={},
        consistency_status="NOT_RUN", notion_board_url="", pdf_path="",
    )


def run_formal_board(state: BoardState) -> BoardState:
    """Execute the dependency DAG dynamically; no fixed tiers."""
    scheduler = DynamicReadinessScheduler(
        runner=lambda agent, snapshot: run_department(agent, snapshot),
        evaluator=lambda agent, snapshot: ceo_evaluate_agent(agent, snapshot),
        max_workers=7,
        max_revisions=3,
    )
    return scheduler.run(state)


def run_full_pipeline(state: BoardState) -> BoardState:
    print("\n" + "=" * 70)
    print("BOARD OF DIRECTORS AI v3 — FORMAL ANALYSIS ENGINE")
    print("=" * 70)

    print("\n[1/6] Initial panel — seven independent reactions")
    state.update(run_panel(state))

    print("\n[2/6] CEO — targeted task allocation")
    state.update(ceo_assign_tasks(state))

    print("\n[3/6] Dynamic readiness scheduler — formal departmental analysis")
    state = run_formal_board(state)

    print("\n[4/6] Deterministic global consistency pass")
    state.update(adjudicate_contradictions(state))

    print("\n[5/6] LLM contradiction adjudication")
    state.update(ceo_adjudicate_contradictions(state))

    print("\n[6/6] CEO final synthesis")
    state.update(ceo_assemble_report(state))
    return state


def node_output(state: BoardState) -> BoardState:
    brief = state["brief"]
    idea_title = str(brief.get("idea", "Business Idea"))[:60]
    board_title = f"Board Report — {idea_title} — {datetime.now().strftime('%Y-%m-%d')}"

    formal_text = json.dumps(state.get("formal_snapshot", {}), indent=2, ensure_ascii=False)
    contradiction_text = json.dumps(state.get("contradiction_adjudication", {}), indent=2, ensure_ascii=False)
    scheduler_text = json.dumps({
        "status": state.get("scheduler_status", {}),
        "revision_summary": state.get("revision_summary", {}),
        "events": state.get("scheduler_events", []),
    }, indent=2, ensure_ascii=False)

    sections = [
        ("Business Brief", json.dumps(brief, indent=2, ensure_ascii=False)),
        ("Research Report", state.get("research_report", "")),
        ("Financial Plan", state.get("financial_plan", "")),
        ("Technical Architecture", state.get("tech_plan", "")),
        ("Go-To-Market Strategy", state.get("marketing_plan", "")),
        ("Sales Strategy", state.get("sales_strategy", "")),
        ("Operations Plan", state.get("operations_plan", "")),
        ("Product Roadmap", state.get("product_roadmap", "")),
        ("Formal Consistency Snapshot", formal_text),
        ("Contradiction Adjudication", contradiction_text),
        ("Execution & Revision Summary", scheduler_text),
        ("CEO Board Recommendation", state.get("final_board_report", "")),
    ]

    notion_url = ""
    try:
        notion_board_id = create_notion_board(board_title)
        if notion_board_id:
            for title, content in sections:
                create_notion_page(notion_board_id, title, content)
            notion_url = f"https://notion.so/{notion_board_id.replace('-', '')}"
    except Exception as exc:
        print(f"Notion output failed: {exc}")

    pdf_filename = ""
    try:
        pdf_filename = f"board_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        generate_pdf({
            "idea": idea_title,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "executive_summary": state.get("final_board_report", "")[:3500],
            "sections": [{"title": title, "content": content} for title, content in sections[1:]],
            "revision_log": [
                {"agent": agent, "revisions": state.get(f"{agent}_revisions", 0)}
                for agent in EVALUATED_AGENTS
            ],
        }, pdf_filename)
    except Exception as exc:
        print(f"PDF output failed: {exc}")

    state["notion_board_url"] = notion_url
    state["pdf_path"] = pdf_filename
    return state


def build_board_graph():
    """LangGraph API envelope around the dynamic v3 controller."""
    graph = StateGraph(BoardState)
    graph.add_node("v3_pipeline", run_full_pipeline)
    graph.add_node("output", node_output)
    graph.add_edge(START, "v3_pipeline")
    graph.add_edge("v3_pipeline", "output")
    graph.add_edge("output", END)
    return graph.compile()


board_graph = build_board_graph()


def run_board_meeting(brief: dict[str, Any]) -> dict[str, Any]:
    final_state = board_graph.invoke(initialize_state(brief))
    return {
        "final_report": final_state.get("final_board_report", ""),
        "notion_board_url": final_state.get("notion_board_url", ""),
        "pdf_path": final_state.get("pdf_path", ""),
        "revision_summary": final_state.get("revision_summary", {}),
        "consistency_status": final_state.get("consistency_status", "NOT_RUN"),
        "deterministic_contradictions": final_state.get("deterministic_contradictions", []),
        "contradiction_adjudication": final_state.get("contradiction_adjudication", {}),
        "formal_snapshot": final_state.get("formal_snapshot", {}),
        "scheduler_status": final_state.get("scheduler_status", {}),
        "scheduler_events": final_state.get("scheduler_events", []),
    }


_API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
_RATE_LIMIT = max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
_EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}
_request_log: dict[str, list[float]] = defaultdict(list)

app = FastAPI(
    title="Plex Hedge — Board of Directors AI",
    description="Formal multi-agent business analysis with deterministic validation, global contradiction adjudication and dynamic scheduling",
    version="3.0.0",
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)
    if _API_SECRET_KEY and request.headers.get("X-API-Key", "") != _API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - 60
    _request_log[client_ip] = [t for t in _request_log[client_ip] if t > cutoff]
    if len(_request_log[client_ip]) >= _RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
    _request_log[client_ip].append(now)
    return await call_next(request)


board_runnable = RunnableLambda(lambda inputs: run_board_meeting(inputs["brief"]))
add_routes(app, board_runnable, path="/board-meeting")


@app.get("/")
async def root():
    return {
        "status": "running",
        "version": "3.0.0",
        "architecture": "dynamic-readiness + formal-validation + deterministic-contradiction-detection + LLM-adjudication",
        "agents": ["CEO", "Researcher", "CFO", "CTO", "CMO", "Head of Sales", "COO", "PM"],
        "docs": "/docs",
        "playground": "/board-meeting/playground",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        demo_brief = {
            "idea": "AI sales assistant for Nigerian SMEs that turns WhatsApp inquiries into qualified customers",
            "target_market": "Nigerian small and medium businesses selling through WhatsApp",
            "budget": "$10000",
            "founder_background": "Technical founder building AI products",
            "timeline": "MVP in 12 weeks",
            "constraints": "Bootstrapped; reach first revenue within 6 months",
        }
        print(run_board_meeting(demo_brief)["final_report"])
