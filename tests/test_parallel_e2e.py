"""Integration tests for the dependency-readiness scheduler."""

import threading
import time

import pytest

from scheduler import DynamicReadinessScheduler, SchedulerExecutionError


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


def test_permanent_execution_failure_blocks_all_transitive_dependants_without_deadlock():
    def runner(agent, state):
        if agent == "researcher":
            raise SchedulerExecutionError("invalid credentials", retryable=False)
        raise AssertionError(f"{agent} should not have been dispatched")

    def evaluator(agent, state):
        raise AssertionError("failed execution must never be evaluated")

    scheduler = DynamicReadinessScheduler(runner, evaluator, max_workers=7, max_revisions=3)
    result = scheduler.run({"brief": {"idea": "test"}})

    assert result["scheduler_status"]["researcher"] == "failed"
    assert all(result["scheduler_status"][agent] == "blocked" for agent in scheduler.dependencies if agent != "researcher")
    assert result["scheduler_blocked_agents"] == [agent for agent in scheduler.dependencies if agent != "researcher"]


def test_retryable_evaluator_failure_is_retried_and_then_passes():
    evaluations = {"researcher": 0}

    def runner(agent, state):
        return {f"{agent}_formal": {"ok": True}, f"{agent}_report": "ok"}

    def evaluator(agent, state):
        evaluations[agent] = evaluations.get(agent, 0) + 1
        if agent == "researcher" and evaluations[agent] == 1:
            raise SchedulerExecutionError("temporary evaluator timeout", retryable=True)
        return {"passed": True, "feedback": "", "scores": {}}

    scheduler = DynamicReadinessScheduler(runner, evaluator, max_workers=7, max_revisions=2)
    result = scheduler.run({"brief": {"idea": "test"}})

    assert result["scheduler_status"]["researcher"] == "passed"
    assert evaluations["researcher"] == 2
    assert any(event.get("event") == "evaluation_error" and event.get("agent") == "researcher" for event in result["scheduler_events"])


def test_scheduler_rejects_unknown_dependency_graph():
    with pytest.raises(ValueError, match="unknown dependencies"):
        DynamicReadinessScheduler(lambda _a, _s: {}, lambda _a, _s: {"passed": True}, dependencies={"researcher": ("missing",)})
