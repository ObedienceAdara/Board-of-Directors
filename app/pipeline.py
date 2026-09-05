"""Board-of-Directors execution pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Mapping, cast

from langgraph.graph import END, START, StateGraph

from agents import ceo_adjudicate_contradictions, ceo_assemble_report, ceo_assign_tasks, ceo_evaluate_agent, panel_reaction, run_department
from analysis import compact_json, consistency_bundle
from models import BoardState, build_provenance_ledger, validate_provenance_ledger
from orchestration import AGENT_ORDER, DynamicReadinessScheduler
from reports import build_executive_report
from tools import create_notion_board, create_notion_page, generate_pdf
from utils import assess_run


def run_panel(state: BoardState) -> dict[str, Any]:
    panel_state = cast(dict[str, Any], state)
    result: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=7, thread_name_prefix="board-panel") as pool:
        futures = {pool.submit(panel_reaction, panel_state, agent, agent.replace("_", " ").title()): agent for agent in AGENT_ORDER}
        for future in as_completed(futures):
            result.update(future.result())
    return result


def initialize_state(brief: dict[str, Any]) -> BoardState:
    state: dict[str, Any] = {"brief": brief}
    for agent in AGENT_ORDER:
        state[f"{agent}_panel"] = ""
        state[f"{agent}_formal"] = {}
        state[f"{agent}_validation"] = {}
        state[f"{agent}_retrieval_trace"] = []
        state[f"{agent}_revisions"] = 0
        state[f"{agent}_passed"] = False
        state[f"{agent}_feedback"] = ""
        state[f"{agent}_execution_error"] = ""
        state[f"{agent}_forced_accept"] = False
        state[f"{agent}_evaluation"] = {}
    state.update({
        "ceo_task_assignments": "", "research_report": "", "financial_plan": "", "tech_plan": "",
        "marketing_plan": "", "operations_plan": "", "sales_strategy": "", "product_roadmap": "",
        "scheduler_status": {}, "scheduler_events": [], "revision_summary": {}, "formal_snapshot": {},
        "deterministic_contradictions": [], "contradiction_adjudication": {}, "consistency_status": "NOT_RUN",
        "provenance_ledger": {}, "provenance_validation": {}, "provenance_summary": {},
        "final_board_report": "", "notion_board_url": "", "pdf_path": "", "pipeline_errors": [], "output_errors": [],
    })
    return cast(BoardState, state)


def run_formal_board(state: BoardState) -> BoardState:
    scheduler = DynamicReadinessScheduler(
        runner=lambda agent, snapshot: run_department(agent, snapshot),
        evaluator=lambda agent, snapshot: ceo_evaluate_agent(agent, snapshot), max_workers=7, max_revisions=3,
    )
    return cast(BoardState, scheduler.run(cast(dict[str, Any], state)))


def _run_stage(state: BoardState, stage: str, fn: Callable[[BoardState], Mapping[str, Any]]) -> BoardState:
    try:
        cast(dict[str, Any], state).update(dict(fn(state)))
    except Exception as exc:
        state.setdefault("pipeline_errors", []).append({"stage": stage, "message": str(exc)})
    return state


def _deterministic_consistency(state: BoardState) -> dict[str, Any]:
    formal = {agent: cast(dict[str, Any], state.get(f"{agent}_formal", {})) for agent in AGENT_ORDER}
    validations = {agent: cast(dict[str, Any], state.get(f"{agent}_validation", {})) for agent in AGENT_ORDER}
    snapshot = consistency_bundle(state["brief"], formal, validations)
    return {"formal_snapshot": snapshot, "deterministic_contradictions": snapshot.get("cross_domain_contradictions", [])}


def _build_provenance(state: BoardState) -> dict[str, Any]:
    ledger = build_provenance_ledger(cast(dict[str, Any], state))
    validation = validate_provenance_ledger(ledger)
    if not validation.get("valid", False):
        raise ValueError("Provenance integrity validation failed: " + "; ".join(validation.get("errors", [])))
    return {"provenance_ledger": ledger, "provenance_validation": validation, "provenance_summary": ledger.get("summary", {})}


def run_full_pipeline(state: BoardState) -> BoardState:
    stages: list[tuple[str, Callable[[BoardState], Mapping[str, Any]]]] = [
        ("panel", lambda current: run_panel(current)), ("ceo_task_assignment", ceo_assign_tasks),
        ("formal_scheduler", run_formal_board), ("deterministic_consistency", _deterministic_consistency),
        ("contradiction_adjudication", ceo_adjudicate_contradictions), ("ceo_synthesis", ceo_assemble_report),
        ("provenance", _build_provenance),
    ]
    for stage, fn in stages:
        state = _run_stage(state, stage, fn)
        if state.get("pipeline_errors"):
            break
    return state


def _notion_sections(state: BoardState) -> list[tuple[str, str]]:
    return [
        ("Business Brief", compact_json(state.get("brief", {}), 6000)),
        ("Research Report", str(state.get("research_report", ""))),
        ("Financial Plan", str(state.get("financial_plan", ""))),
        ("Technical Architecture", str(state.get("tech_plan", ""))),
        ("Go-To-Market Strategy", str(state.get("marketing_plan", ""))),
        ("Sales Strategy", str(state.get("sales_strategy", ""))),
        ("Operations Plan", str(state.get("operations_plan", ""))),
        ("Product Roadmap", str(state.get("product_roadmap", ""))),
        ("Formal Consistency Snapshot", compact_json(state.get("formal_snapshot", {}), 18000)),
        ("Contradiction Adjudication", compact_json(state.get("contradiction_adjudication", {}), 12000)),
        ("Evidence & Provenance Ledger", compact_json(state.get("provenance_ledger", {}), 26000)),
        ("Provenance Validation", compact_json(state.get("provenance_validation", {}), 6000)),
        ("Execution & Revision Summary", compact_json({"status": state.get("scheduler_status", {}), "revision_summary": state.get("revision_summary", {})}, 10000)),
        ("CEO Board Recommendation", str(state.get("final_board_report", ""))),
    ]


def node_output(state: BoardState) -> BoardState:
    idea_title = str(state.get("brief", {}).get("idea", "Business Idea"))[:80]
    board_title = f"Board Report — {idea_title} — {datetime.now().strftime('%Y-%m-%d')}"
    sections = _notion_sections(state)
    try:
        notion_id = create_notion_board(board_title)
        if notion_id:
            child_urls = [create_notion_page(notion_id, title, content) for title, content in sections]
            state["notion_board_url"] = next((url for url in child_urls if url), f"https://notion.so/{notion_id.replace('-', '')}")
        else:
            state.setdefault("output_errors", []).append({"stage": "notion", "message": "Notion credentials/configuration unavailable."})
    except Exception as exc:
        state.setdefault("output_errors", []).append({"stage": "notion", "message": str(exc)})
    try:
        report_model = build_executive_report(cast(dict[str, Any], state))
        filename = f"board_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        generate_pdf(report_model, filename)
        state["pdf_path"] = filename
    except Exception as exc:
        state.setdefault("output_errors", []).append({"stage": "pdf", "message": str(exc)})
    return state


def build_board_graph():
    graph = StateGraph(BoardState)
    graph.add_node("board_pipeline", run_full_pipeline)
    graph.add_node("output", node_output)
    graph.add_edge(START, "board_pipeline")
    graph.add_edge("board_pipeline", "output")
    graph.add_edge("output", END)
    return graph.compile()


board_graph = build_board_graph()


def run_board_meeting(brief: dict[str, Any]) -> dict[str, Any]:
    try:
        state = board_graph.invoke(initialize_state(brief))
        runtime = assess_run(cast(dict[str, Any], state))
    except Exception as exc:
        state = initialize_state(brief)
        state["pipeline_errors"] = [{"stage": "board_graph", "message": str(exc)}]
        runtime = assess_run(cast(dict[str, Any], state))
    return {
        "status": runtime["status"], "success": runtime["success"], "final_report": state.get("final_board_report", ""),
        "notion_board_url": state.get("notion_board_url", ""), "pdf_path": state.get("pdf_path", ""),
        "revision_summary": state.get("revision_summary", {}), "consistency_status": state.get("consistency_status", "NOT_RUN"),
        "deterministic_contradictions": state.get("deterministic_contradictions", []), "contradiction_adjudication": state.get("contradiction_adjudication", {}),
        "formal_snapshot": state.get("formal_snapshot", {}), "provenance_ledger": state.get("provenance_ledger", {}),
        "provenance_validation": state.get("provenance_validation", {}), "provenance_summary": state.get("provenance_summary", {}),
        "scheduler_status": state.get("scheduler_status", {}), "scheduler_events": state.get("scheduler_events", []),
        "errors": runtime["errors"], "warnings": runtime["warnings"],
    }
