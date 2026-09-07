"""Dynamic dependency-readiness scheduler for the formal board stage."""

from __future__ import annotations

from concurrent.futures import Future, FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any, Callable

AGENT_ORDER = ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "researcher": (), "cfo": ("researcher",), "cto": ("researcher",), "cmo": ("researcher", "cfo"),
    "coo": ("researcher", "cfo", "cto"), "head_of_sales": ("researcher", "cfo", "cmo"), "pm": ("researcher", "cto", "cmo"),
}


class SchedulerExecutionError(RuntimeError):
    """Execution failed before an agent produced an output."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DynamicReadinessScheduler:
    """Run independent agents concurrently and launch newly-ready work immediately."""

    def __init__(self, runner: Callable[[str, dict[str, Any]], dict[str, Any]], evaluator: Callable[[str, dict[str, Any]], dict[str, Any]], *, max_workers: int = 7, max_revisions: int = 3, dependencies: dict[str, tuple[str, ...]] | None = None) -> None:
        self.runner = runner
        self.evaluator = evaluator
        self.max_workers = max(1, max_workers)
        self.max_revisions = max(1, max_revisions)
        self.dependencies = dependencies or DEPENDENCIES
        self._validate_graph()

    def _validate_graph(self) -> None:
        unknown_agents = set(self.dependencies) - set(AGENT_ORDER)
        if unknown_agents:
            raise ValueError(f"Scheduler dependencies contain unknown agents: {sorted(unknown_agents)}")
        for agent in AGENT_ORDER:
            unknown = set(self.dependencies.get(agent, ())) - set(AGENT_ORDER)
            if unknown:
                raise ValueError(f"Agent '{agent}' has unknown dependencies: {sorted(unknown)}")
            if agent in self.dependencies.get(agent, ()):
                raise ValueError(f"Agent '{agent}' cannot depend on itself")
        visiting: set[str] = set(); visited: set[str] = set()
        def visit(agent: str) -> None:
            if agent in visiting:
                raise ValueError(f"Scheduler dependency cycle detected at '{agent}'")
            if agent in visited:
                return
            visiting.add(agent)
            for dep in self.dependencies.get(agent, ()): visit(dep)
            visiting.remove(agent); visited.add(agent)
        for agent in AGENT_ORDER: visit(agent)

    def _ready(self, agent: str, status: dict[str, str]) -> bool:
        return status.get(agent) in {"pending", "retry"} and all(status.get(dep) == "passed" for dep in self.dependencies.get(agent, ()))

    def _blocked_dependants(self, failed_agent: str, status: dict[str, str], events: list[dict[str, Any]]) -> None:
        queue = [failed_agent]; seen = {failed_agent}
        while queue:
            upstream = queue.pop(0)
            for dependant in AGENT_ORDER:
                if upstream not in self.dependencies.get(dependant, ()) or status.get(dependant) not in {"pending", "retry"}: continue
                status[dependant] = "blocked"
                blockers = [dep for dep in self.dependencies.get(dependant, ()) if status.get(dep) in {"failed", "blocked"}]
                events.append({"event": "blocked", "agent": dependant, "blocked_by": blockers or [upstream], "timestamp": now_iso()})
                if dependant not in seen: seen.add(dependant); queue.append(dependant)

    @staticmethod
    def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def _record_failure(self, state: dict[str, Any], status: dict[str, str], events: list[dict[str, Any]], agent: str, revision: int, message: str, retryable: bool) -> None:
        state[f"{agent}_passed"] = False
        state[f"{agent}_feedback"] = message
        state[f"{agent}_execution_error"] = message
        if retryable and revision < self.max_revisions:
            status[agent] = "retry"
            events.append({"event": "retry", "agent": agent, "revision": revision, "reason": message, "timestamp": now_iso()})
        else:
            status[agent] = "failed"
            state[f"{agent}_forced_accept"] = False
            self._blocked_dependants(agent, status, events)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        status = {agent: "pending" for agent in AGENT_ORDER}
        revisions = {agent: 0 for agent in AGENT_ORDER}
        events: list[dict[str, Any]] = []
        running: dict[Future[Any], tuple[str, int]] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="board-agent") as pool:
            while True:
                for agent in AGENT_ORDER:
                    if len(running) >= self.max_workers or not self._ready(agent, status): continue
                    status[agent] = "running"; revisions[agent] += 1; revision = revisions[agent]
                    running[pool.submit(self.runner, agent, self._snapshot(state))] = (agent, revision)
                    events.append({"event": "dispatch", "agent": agent, "revision": revision, "dependencies": list(self.dependencies.get(agent, ())), "timestamp": now_iso()})
                if not running:
                    unresolved = [a for a in AGENT_ORDER if status[a] in {"pending", "retry"}]
                    if unresolved:
                        blockers = {a: list(self.dependencies.get(a, ())) for a in unresolved}
                        raise RuntimeError(f"Scheduler deadlock; unresolved agents: {unresolved}; blockers: {blockers}")
                    break
                done, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for future in done:
                    agent, revision = running.pop(future)
                    try:
                        result = future.result()
                        if not isinstance(result, dict): raise SchedulerExecutionError("Agent runner must return a dictionary", retryable=False)
                    except Exception as exc:
                        error = str(exc); retryable = bool(getattr(exc, "retryable", True))
                        events.append({"event": "execution_error", "agent": agent, "revision": revision, "error": error, "retryable": retryable, "timestamp": now_iso()})
                        self._record_failure(state, status, events, agent, revision, error, retryable)
                        events.append({"event": "execution_failure", "agent": agent, "revision": revision, "evaluation_skipped": True, "status": status[agent], "timestamp": now_iso()})
                        continue
                    state.update(result); state[f"{agent}_revisions"] = revision; state[f"{agent}_execution_error"] = ""
                    try:
                        evaluation = self.evaluator(agent, self._snapshot(state))
                        if not isinstance(evaluation, dict): raise SchedulerExecutionError("Evaluator must return a dictionary", retryable=False)
                    except Exception as exc:
                        error = str(exc); retryable = bool(getattr(exc, "retryable", True))
                        events.append({"event": "evaluation_error", "agent": agent, "revision": revision, "error": error, "retryable": retryable, "timestamp": now_iso()})
                        self._record_failure(state, status, events, agent, revision, f"Evaluator failed: {error}", retryable)
                        continue
                    state[f"{agent}_evaluation"] = evaluation
                    passed = bool(evaluation.get("passed", False)); feedback = str(evaluation.get("feedback", "")); state[f"{agent}_feedback"] = feedback
                    if passed:
                        status[agent] = "passed"; state[f"{agent}_passed"] = True
                    elif revision < self.max_revisions:
                        status[agent] = "retry"; state[f"{agent}_passed"] = False
                        events.append({"event": "retry", "agent": agent, "revision": revision, "reason": feedback or "Evaluator rejected output", "timestamp": now_iso()})
                    else:
                        status[agent] = "failed"; state[f"{agent}_passed"] = False; state[f"{agent}_forced_accept"] = False; self._blocked_dependants(agent, status, events)
                        events.append({"event": "failed", "agent": agent, "revision": revision, "reason": feedback or "Evaluator rejected output after maximum revisions.", "timestamp": now_iso()})
                    events.append({"event": "evaluation", "agent": agent, "revision": revision, "passed": passed, "forced_accept": False, "status": status[agent], "timestamp": now_iso()})
        state["scheduler_status"] = status; state["revision_summary"] = revisions; state["scheduler_events"] = events
        state["scheduler_blocked_agents"] = [agent for agent, value in status.items() if value == "blocked"]; state["scheduler_failed_agents"] = [agent for agent, value in status.items() if value == "failed"]
        return state
