"""Dynamic readiness scheduler for the board's formal analysis stage.

Unlike fixed tiers, agents become eligible as soon as *their own* declared
input dependencies have passed. Independent work is submitted concurrently,
and newly-unblocked work is submitted immediately as its predecessor finishes.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from typing import Callable, Any

AGENT_ORDER = ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]

# Dependencies are logical requirements, not artificial stages.
# An agent can start as soon as every named dependency has passed.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "researcher": (),
    "cfo": ("researcher",),
    "cto": ("researcher",),
    "cmo": ("researcher", "cfo"),
    "coo": ("researcher", "cfo", "cto"),
    "head_of_sales": ("researcher", "cfo", "cmo"),
    "pm": ("researcher", "cto", "cmo"),
}


@dataclass
class AgentRun:
    agent: str
    revision: int
    output: Any


class DynamicReadinessScheduler:
    """Dependency-aware concurrent scheduler with revision support."""

    def __init__(
        self,
        runner: Callable[[str, dict[str, Any]], Any],
        evaluator: Callable[[str, dict[str, Any]], dict[str, Any]],
        *,
        max_workers: int = 7,
        max_revisions: int = 3,
        dependencies: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.runner = runner
        self.evaluator = evaluator
        self.max_workers = max_workers
        self.max_revisions = max_revisions
        self.dependencies = dependencies or DEPENDENCIES

    def _ready(self, agent: str, state: dict[str, Any], status: dict[str, str]) -> bool:
        if status.get(agent) not in {"pending", "retry"}:
            return False
        return all(status.get(dep) == "passed" for dep in self.dependencies.get(agent, ()))

    @staticmethod
    def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
        # Values are mostly immutable strings/dicts. Shallow copying prevents
        # concurrent workers from accidentally mutating the scheduler's live dict.
        return dict(state)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        status = {agent: "pending" for agent in AGENT_ORDER}
        revisions = {agent: 0 for agent in AGENT_ORDER}
        running: dict[Future[Any], str] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="board-agent") as pool:
            while True:
                # Dispatch every currently ready agent. Because readiness is
                # dependency-based, this is not constrained by global tiers.
                for agent in AGENT_ORDER:
                    if len(running) >= self.max_workers:
                        break
                    if not self._ready(agent, state, status):
                        continue
                    status[agent] = "running"
                    revisions[agent] += 1
                    snapshot = self._snapshot(state)
                    future = pool.submit(self.runner, agent, snapshot)
                    running[future] = agent

                if not running:
                    pending = [a for a in AGENT_ORDER if status[a] in {"pending", "retry"}]
                    if not pending:
                        break
                    blocked = {a: self.dependencies.get(a, ()) for a in pending}
                    raise RuntimeError(f"Scheduler deadlock; unresolved dependencies: {blocked}")

                done, _ = wait(list(running), return_when=FIRST_COMPLETED)
                # Process all completions in this scheduling turn. New work is
                # dispatched on the next loop as soon as its dependency passes.
                for future in done:
                    agent = running.pop(future)
                    try:
                        output = future.result()
                        state.update(output)
                        state[f"{agent}_revisions"] = revisions[agent]
                    except Exception as exc:
                        state[f"{agent}_execution_error"] = str(exc)
                        output = {"error": str(exc)}

                    evaluation = self.evaluator(agent, self._snapshot(state))
                    state[f"{agent}_evaluation"] = evaluation

                    passed = bool(evaluation.get("passed", False))
                    feedback = str(evaluation.get("feedback", ""))
                    state[f"{agent}_feedback"] = feedback

                    if passed or revisions[agent] >= self.max_revisions:
                        status[agent] = "passed"
                        state[f"{agent}_passed"] = True
                        if not passed:
                            state[f"{agent}_forced_accept"] = True
                    else:
                        status[agent] = "retry"
                        state[f"{agent}_passed"] = False

        state["scheduler_status"] = status
        state["revision_summary"] = revisions
        return state
