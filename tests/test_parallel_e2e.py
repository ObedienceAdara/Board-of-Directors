"""Integration tests for the v3 dependency-readiness scheduler."""

import threading
import time

from scheduler import DynamicReadinessScheduler


def test_newly_ready_agent_launches_without_waiting_for_unrelated_branch():
    started = {}
    finished = {}
    lock = threading.Lock()

    def runner(agent, state):
        with lock:
            started[agent] = time.monotonic()
        if agent == "cto":
            time.sleep(0.20)
        else:
            time.sleep(0.01)
        with lock:
            finished[agent] = time.monotonic()
        return {f"{agent}_formal": {"ok": True}, f"{agent}_report": f"{agent} report"}

    def evaluator(agent, state):
        return {"passed": True, "feedback": "", "scores": {}}

    scheduler = DynamicReadinessScheduler(runner, evaluator, max_workers=7, max_revisions=1)
    result = scheduler.run({"brief": {"idea": "test"}})

    assert result["scheduler_status"] == {a: "passed" for a in scheduler.dependencies}
    assert all(a in started for a in scheduler.dependencies)
    assert started["cmo"] < finished["cto"]
    assert result["revision_summary"] == {a: 1 for a in scheduler.dependencies}


def test_failed_agent_retries_without_rerunning_independent_sibling():
    calls = {a: 0 for a in ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]}

    def runner(agent, state):
        calls[agent] += 1
        return {f"{agent}_formal": {"ok": True}, f"{agent}_report": "ok"}

    def evaluator(agent, state):
        if agent == "cfo" and calls[agent] < 3:
            return {"passed": False, "feedback": "fix", "scores": {}}
        return {"passed": True, "feedback": "", "scores": {}}

    scheduler = DynamicReadinessScheduler(runner, evaluator, max_workers=7, max_revisions=3)
    result = scheduler.run({"brief": {"idea": "test"}})

    assert result["scheduler_status"]["cfo"] == "passed"
    assert calls["cfo"] == 3
    assert calls["cto"] == 1
