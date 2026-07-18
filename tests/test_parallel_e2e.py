"""
tests/test_parallel_e2e.py

End-to-end test of the REAL production code path (run_board_meeting ->
the actual compiled board_graph) with only the LLM, search, and external
delivery calls mocked out. This exercises the actual agents.py/main.py/
state.py code that ships, not a simplified simulation of it.

Staggers revision counts across agents (cfo needs 3 passes, pm needs 3,
everything else passes on the first try) to stress the exact asymmetric-
branch-length scenario the tiered parallel structure has to handle
correctly.
"""
import os
os.environ.setdefault("TAVILY_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")

import json
from unittest.mock import patch

import agents
import main

NEEDED_PASSES = {
    "researcher": 1, "cfo": 3, "cto": 1, "cmo": 2,
    "coo": 1, "head_of_sales": 1, "pm": 3,
}

_eval_call_counts = {}


def fake_safe_invoke(chain, inputs, fallback, retries=2, backoff=1.5):
    """
    Stand in for every LLM call in the pipeline. Distinguishes CEO task
    assignment / evaluation / assembly calls from department-report calls
    by the shape of `inputs`, and drives the staggered pass/fail schedule
    for evaluations.
    """
    # CEO task assignment call
    if set(inputs.keys()) == {"brief"}:
        return json.dumps({
            "opportunity_summary": "test",
            "tasks": {k: "test task" for k in NEEDED_PASSES if k != "researcher"} | {"researcher": "test task"}
        })

    # CEO evaluation call (has agent_role + other_departments)
    if "other_departments" in inputs:
        role_to_key = {
            "Researcher": "researcher", "CFO": "cfo", "CTO": "cto", "CMO": "cmo",
            "COO": "coo", "Head of Sales": "head_of_sales", "PM": "pm",
        }
        key = role_to_key[inputs["agent_role"]]
        _eval_call_counts[key] = _eval_call_counts.get(key, 0) + 1
        passed = _eval_call_counts[key] >= NEEDED_PASSES[key]
        return json.dumps({"passed": passed, "feedback": "" if passed else "needs more detail", "scores": {}})

    # CEO assemble call (has research_report etc, no agent_role)
    if "research_report" in inputs and "agent_role" not in inputs:
        return "FINAL BOARD REPORT: GO."

    # Department report generation (researcher/cfo/cto/cmo/sales/coo/pm)
    return "placeholder department output"


def fake_multi_search(queries):
    return "placeholder search data"


def fake_get_search_queries(brief_str, task, model):
    return ["q1", "q2", "q3"]


def fake_create_notion_board(title):
    return ""  # simulate no Notion configured — exercises the try/except path


def fake_generate_pdf(data, filename):
    return None


def test_full_board_meeting_with_staggered_revisions():
    _eval_call_counts.clear()

    brief = {
        "idea": "A test business idea",
        "target_market": "Test market",
        "budget": "$10k",
        "founder_background": "Test founder",
        "timeline": "3 months",
        "constraints": "None",
    }

    with patch.object(agents, "safe_invoke", fake_safe_invoke), \
         patch.object(agents, "multi_search", fake_multi_search), \
         patch.object(agents, "get_search_queries", fake_get_search_queries), \
         patch("main.create_notion_board", fake_create_notion_board), \
         patch("main.generate_pdf", fake_generate_pdf):

        result = main.run_board_meeting(brief)

    print("\n=== REVISION SUMMARY ===")
    for agent, count in result["revision_summary"].items():
        print(f"  {agent}: {count} (needed {NEEDED_PASSES[agent]})")

    assert result["final_report"] == "FINAL BOARD REPORT: GO."

    for agent, needed in NEEDED_PASSES.items():
        assert result["revision_summary"][agent] == needed, (
            f"{agent} ran {result['revision_summary'][agent]} times, expected {needed}"
        )

    print("\n✅ Full production code path (run_board_meeting -> real compiled "
          "graph) completed correctly with staggered, asymmetric revision "
          "counts across every agent.")


if __name__ == "__main__":
    test_full_board_meeting_with_staggered_revisions()
