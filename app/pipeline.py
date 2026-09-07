"""Board-of-Directors execution pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Mapping, cast

from langgraph.graph import END, START, StateGraph

from agents import ceo_adjudicate_contradictions, ceo_assemble_report, ceo_assign_tasks, ceo_evaluate_agent, panel_reaction, run_department
from analysis import compact_json, consistency_bundle, run_phase2_calculations
from models import BoardState, build_provenance_ledger, validate_provenance_ledger
from orchestration import AGENT_ORDER, DynamicReadinessScheduler
from reports import build_executive_report
from tools import create_notion_board, create_notion_page, generate_pdf
from utils import assess_run


def run_panel(state: BoardState) -> dict[str, Any]:
    panel_state = cast(dict[str, Any], state); result: dict[str, Any] = {}; panel_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=7, thread_name_prefix="board-panel") as pool:
        futures = {pool.submit(panel_reaction, panel_state, agent, agent.replace("_", " ").title()): agent for agent in AGENT_ORDER}
        for future in as_completed(futures):
            agent = futures[future]
            try:
                output = future.result()
                if isinstance(output, dict): result.update(output)
                else: panel_errors.append({"agent": agent, "message": "Panel runner returned a non-dictionary result."})
            except Exception as exc:
                panel_errors.append({"agent": agent, "message": str(exc)}); result[f"{agent}_panel"] = ""; result[f"{agent}_panel_error"] = str(exc)
    if panel_errors: result["panel_errors"] = panel_errors
    return result


def initialize_state(brief: dict[str, Any]) -> BoardState:
    state: dict[str, Any] = {"brief": brief}
    for agent in AGENT_ORDER:
        state.update({f"{agent}_panel": "", f"{agent}_formal": {}, f"{agent}_validation": {}, f"{agent}_retrieval_trace": [], f"{agent}_revisions": 0, f"{agent}_passed": False, f"{agent}_feedback": "", f"{agent}_execution_error": "", f"{agent}_forced_accept": False, f"{agent}_evaluation": {}})
    state.update({"ceo_task_assignments": "", "research_report": "", "financial_plan": "", "tech_plan": "", "marketing_plan": "", "operations_plan": "", "sales_strategy": "", "product_roadmap": "", "scheduler_status": {}, "scheduler_events": [], "revision_summary": {}, "formal_snapshot": {}, "deterministic_contradictions": [], "contradiction_adjudication": {}, "consistency_status": "NOT_RUN", "phase2_calculations": {}, "phase2_input_quality": {}, "provenance_ledger": {}, "provenance_validation": {}, "provenance_summary": {}, "final_board_report": "", "notion_board_url": "", "notion_board_id": "", "pdf_path": "", "pipeline_errors": [], "output_errors": []})
    return cast(BoardState, state)


def run_formal_board(state: BoardState) -> BoardState:
    scheduler = DynamicReadinessScheduler(runner=lambda agent, snapshot: run_department(agent, snapshot), evaluator=lambda agent, snapshot: ceo_evaluate_agent(agent, snapshot), max_workers=7, max_revisions=3)
    return cast(BoardState, scheduler.run(cast(dict[str, Any], state)))


def _run_stage(state: BoardState, stage: str, fn: Callable[[BoardState], Mapping[str, Any]]) -> BoardState:
    try: state.update(dict(fn(state)))
    except Exception as exc: state.setdefault("pipeline_errors", []).append({"stage": stage, "message": str(exc)})
    return state


def _formal_stage_ok(state: BoardState) -> bool:
    statuses = state.get("scheduler_status", {}) or {}
    if not isinstance(statuses, dict) or any(statuses.get(agent) != "passed" for agent in AGENT_ORDER):
        state.setdefault("pipeline_errors", []).append({"stage": "formal_scheduler", "message": f"Formal board incomplete; failed={state.get('scheduler_failed_agents', [])}, blocked={state.get('scheduler_blocked_agents', [])}."}); return False
    return True


def _run_domain_calculations(state: BoardState) -> dict[str, Any]:
    result = run_phase2_calculations(cast(dict[str, Any], state)); return {"phase2_calculations": result, "phase2_input_quality": result.get("input_quality", {})}


def _deterministic_consistency(state: BoardState) -> dict[str, Any]:
    formal = {agent: cast(dict[str, Any], state.get(f"{agent}_formal", {})) for agent in AGENT_ORDER}; validations = {agent: cast(dict[str, Any], state.get(f"{agent}_validation", {})) for agent in AGENT_ORDER}
    snapshot = consistency_bundle(state["brief"], formal, validations); snapshot["phase2_calculations"] = cast(dict[str, Any], state.get("phase2_calculations", {})); snapshot["phase2_input_quality"] = cast(dict[str, Any], state.get("phase2_input_quality", {}))
    return {"formal_snapshot": snapshot, "deterministic_contradictions": snapshot.get("cross_domain_contradictions", []), "consistency_status": snapshot.get("integrity_status", "NOT_RUN")}


def _calculation_lineage(state: BoardState) -> list[dict[str, Any]]:
    calculations = state.get("phase2_calculations", {}); calculations = calculations if isinstance(calculations, dict) else {}
    domains = {name: calculations.get(name, {}) if isinstance(calculations.get(name, {}), dict) else {} for name in ("finance", "sales", "operations", "technical", "product")}
    values = {"finance.12_month_revenue": domains["finance"].get("12_month_revenue"), "finance.gross_margin": domains["finance"].get("gross_margin"), "finance.contribution_margin": domains["finance"].get("contribution_margin"), "finance.net_burn": domains["finance"].get("net_burn"), "finance.runway_months": domains["finance"].get("runway_months"), "finance.break_even_month": domains["finance"].get("break_even_month"), "sales.12_month_revenue": domains["sales"].get("12_month_revenue"), "sales.required_annual_sales": domains["sales"].get("required_annual_sales"), "operations.12_month_payroll": domains["operations"].get("12_month_payroll"), "technical.delivery_duration_weeks": domains["technical"].get("delivery_duration_weeks"), "product.priority_scores": [item.get("priority_score") for item in domains["product"].get("features", []) if isinstance(item, dict)]}
    formulas = {"finance.12_month_revenue": "sum(finance.months[*].revenue)", "finance.gross_margin": "(revenue-cogs)/revenue", "finance.contribution_margin": "revenue-cogs-marketing", "finance.net_burn": "operating_costs-revenue", "finance.runway_months": "cash-depletion simulation", "finance.break_even_month": "first forecast month with net_burn <= 0", "sales.12_month_revenue": "sum(sales.months[*].revenue)", "sales.required_annual_sales": "annual_revenue_target / annual_revenue_per_active_customer", "operations.12_month_payroll": "sum(monthly payroll after hire dates)", "technical.delivery_duration_weeks": "dependency-constrained shared-capacity schedule", "product.priority_scores": "impact/effort*strategic_weight*dependency_factor"}
    agent_inputs = {"finance": ["head_of_sales_formal", "cfo_formal", "coo_formal", "cto_formal", "cmo_formal"], "sales": ["head_of_sales_formal"], "operations": ["coo_formal"], "technical": ["cto_formal"], "product": ["pm_formal"]}
    rows = []
    for calculation_id, value in values.items():
        domain = calculation_id.split(".", 1)[0]; rows.append({"calculation_id": calculation_id, "domain": domain, "engine": domains[domain].get("model", "deterministic_unknown"), "value": value, "formula": formulas[calculation_id], "agent_inputs": agent_inputs[domain]})
    return rows


def _build_provenance(state: BoardState) -> dict[str, Any]:
    ledger = build_provenance_ledger(cast(dict[str, Any], state)); ledger["calculation_lineage"] = _calculation_lineage(state); validation = validate_provenance_ledger(ledger)
    if not validation.get("valid", False): raise ValueError("Provenance integrity validation failed: " + "; ".join(validation.get("errors", [])))
    return {"provenance_ledger": ledger, "provenance_validation": validation, "provenance_summary": ledger.get("summary", {})}


def run_full_pipeline(state: BoardState) -> BoardState:
    stages = [("panel", run_panel), ("ceo_task_assignment", ceo_assign_tasks), ("formal_scheduler", run_formal_board), ("domain_calculations", _run_domain_calculations), ("deterministic_consistency", _deterministic_consistency), ("contradiction_adjudication", ceo_adjudicate_contradictions), ("ceo_synthesis", ceo_assemble_report), ("provenance", _build_provenance)]
    for stage, fn in stages:
        state = _run_stage(state, stage, fn)
        if state.get("pipeline_errors"): break
        if stage == "formal_scheduler" and not _formal_stage_ok(state): break
    return state


def _notion_sections(state: BoardState) -> list[tuple[str, str]]:
    calculations = state.get("phase2_calculations", {}); calculations = calculations if isinstance(calculations, dict) else {}
    return [("Business Brief", compact_json(state.get("brief", {}), 6000)), ("Research Report", str(state.get("research_report", ""))), ("Financial Plan", str(state.get("financial_plan", ""))), ("Deterministic Financial & Scenario Model", compact_json(calculations.get("finance", {}), 22000)), ("Financial Scenario Analysis", compact_json(calculations.get("finance_scenarios", {}), 24000)), ("Sales Funnel Calculation", compact_json(calculations.get("sales", {}), 18000)), ("Workforce & Capacity Calculation", compact_json(calculations.get("operations", {}), 18000)), ("Technical Delivery Calculation", compact_json(calculations.get("technical", {}), 14000)), ("Product Priority Calculation", compact_json(calculations.get("product", {}), 16000)), ("Phase 2 Input Quality", compact_json(state.get("phase2_input_quality", {}), 8000)), ("Formal Consistency Snapshot", compact_json(state.get("formal_snapshot", {}), 18000)), ("Contradiction Adjudication", compact_json(state.get("contradiction_adjudication", {}), 12000)), ("Evidence & Provenance Ledger", compact_json(state.get("provenance_ledger", {}), 30000)), ("Provenance Validation", compact_json(state.get("provenance_validation", {}), 6000)), ("Execution & Revision Summary", compact_json({"status": state.get("scheduler_status", {}), "revision_summary": state.get("revision_summary", {})}, 10000)), ("CEO Board Recommendation", str(state.get("final_board_report", "")))]


def node_output(state: BoardState) -> BoardState:
    if state.get("pipeline_errors") or not str(state.get("final_board_report", "")).strip():
        state.setdefault("output_errors", []).append({"stage": "output", "message": "Outputs suppressed because the board pipeline did not complete successfully."}); return state
    idea_title = str(state.get("brief", {}).get("idea", "Business Idea"))[:80]; board_title = f"Board Report — {idea_title} — {datetime.now().strftime('%Y-%m-%d')}
    sections = _notion_sections(state)
    try:
        notion_id = create_notion_board(board_title)
        if notion_id:
            state["notion_board_id"] = notion_id
            urls: list[str] = []
            for title, content in sections:
                try:
                    url = create_notion_page(notion_id, title, content)
                    if url: urls.append(url)
                except Exception as exc:
                    state.setdefault("output_errors", []).append({"stage": f"notion:{title}", "message": str(exc)})
            state["notion_board_url"] = urls[0] if urls else f"https://www.notion.so/{notion_id.replace('-', '')}"
        else:
            print("Notion output skipped: integration disabled or not configured.")
    except Exception as exc:
        state.setdefault("output_errors", []).append({"stage": "notion", "message": str(exc)})
    try:
        report_model = build_executive_report(cast(dict[str, Any], state)); filename = f"board_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"; generate_pdf(report_model, filename); state["pdf_path"] = filename
    except Exception as exc: state.setdefault("output_errors", []).append({"stage": "pdf", "message": str(exc)})
    return state


def build_board_graph():
    graph = StateGraph(BoardState); graph.add_node("board_pipeline", run_full_pipeline); graph.add_node("output", node_output); graph.add_edge(START, "board_pipeline"); graph.add_edge("board_pipeline", "output"); graph.add_edge("output", END); return graph.compile()

board_graph = build_board_graph()


def run_board_meeting(brief: dict[str, Any]) -> dict[str, Any]:
    try: state = board_graph.invoke(initialize_state(brief)); runtime = assess_run(cast(dict[str, Any], state))
    except Exception as exc: state = initialize_state(brief); state["pipeline_errors"] = [{"stage": "board_graph", "message": str(exc)}]; runtime = assess_run(cast(dict[str, Any], state))
    return {"status": runtime["status"], "success": runtime["success"], "final_report": state.get("final_board_report", ""), "notion_board_url": state.get("notion_board_url", ""), "pdf_path": state.get("pdf_path", ""), "revision_summary": state.get("revision_summary", {}), "consistency_status": state.get("consistency_status", "NOT_RUN"), "deterministic_contradictions": state.get("deterministic_contradictions", []), "contradiction_adjudication": state.get("contradiction_adjudication", {}), "formal_snapshot": state.get("formal_snapshot", {}), "phase2_calculations": state.get("phase2_calculations", {}), "phase2_input_quality": state.get("phase2_input_quality", {}), "provenance_ledger": state.get("provenance_ledger", {}), "provenance_validation": state.get("provenance_validation", {}), "provenance_summary": state.get("provenance_summary", {}), "scheduler_status": state.get("scheduler_status", {}), "scheduler_events": state.get("scheduler_events", []), "errors": runtime["errors"], "warnings": runtime["warnings"]}
