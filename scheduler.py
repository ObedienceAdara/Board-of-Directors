"""Dynamic dependency-readiness scheduler for the formal board stage."""

from __future__ import annotations

from concurrent.futures import Future, FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any, Callable

AGENT_ORDER = ["researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm"]

# Real data dependencies. No artificial global tiers.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "researcher": (),
    "cfo": ("researcher",),
    "cto": ("researcher",),
    "cmo": ("researcher", "cfo"),
    "coo": ("researcher", "cfo", "cto"),
    "head_of_sales": ("researcher", "cfo", "cmo"),
    "pm": ("researcher", "cto", "cmo"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DynamicReadinessScheduler:
    """Run independent agents concurrently and launch newly-ready work immediately."""

    def __init__(
        self,
        runner: Callable[[str, dict[str, Any]], dict[str, Any]],
        evaluator: Callable[[str, dict[str, Any]], dict[str, Any]],
        *,
        max_workers: int = 7,
        max_revisions: int = 3,
        dependencies: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.runner = runner
        self.evaluator = evaluator
        self.max_workers = max(1, max_workers)
        self.max_revisions = max(1, max_revisions)
        self.dependencies = dependencies or DEPENDENCIES

    def _ready(self, agent: str, status: dict[str, str]) -> bool:
        if status.get(agent) not in {"pending", "retry"}:
            return False
        return all(status.get(dep) == "passed" for dep in self.dependencies.get(agent, ()))

    @staticmethod
    def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        status = {agent: "pending" for agent in AGENT_ORDER}
        revisions = {agent: 0 for agent in AGENT_ORDER}
        events: list[dict[str, Any]] = []
        running: dict[Future[Any], tuple[str, int, str]] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="board-agent") as pool:
            while True:
                # Dynamic dispatch. A branch becoming ready is enough to launch
                # it; it does not wait for unrelated branches to finish.
                for agent in AGENT_ORDER:
                    if len(running) >= self.max_workers:
                        break
                    if not self._ready(agent, status):
                        continue
                    status[agent] = "running"
                    revisions[agent] += 1
                    revision = revisions[agent]
                    snapshot = self._snapshot(state)
                    future = pool.submit(self.runner, agent, snapshot)
                    running[future] = (agent, revision, now_iso())
                    events.append({
                        "event": "dispatch",
                        "agent": agent,
                        "revision": revision,
                        "dependencies": list(self.dependencies.get(agent, ())),
                        "timestamp": now_iso(),
                    })

                if not running:
                    unresolved = [a for a in AGENT_ORDER if status[a] in {"pending", "retry"}]
                    if unresolved:
                        raise RuntimeError(f"Scheduler deadlock; unresolved agents: {unresolved}")
                    break

                done, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for future in done:
                    agent, revision, dispatched_at = running.pop(future)
                    events.append({"event": "complete", "agent": agent, "revision": revision, "timestamp": now_iso()})
                    try:
                        output = future.result()
                    except Exception as exc:
                        output = {f"{agent}_execution_error": str(exc)}
                        events.append({"event": "execution_error", "agent": agent, "revision": revision, "error": str(exc), "timestamp": now_iso()})
                    state.update(output)
                    state[f"{agent}_revisions"] = revision

                    evaluation = self.evaluator(agent, self._snapshot(state))
                    state[f"{agent}_evaluation"] = evaluation
                    passed = bool(evaluation.get("passed", False))
                    feedback = str(evaluation.get("feedback", ""))
                    state[f"{agent}_feedback"] = feedback

                    if passed or revision >= self.max_revisions:
                        status[agent] = "passed"
                        state[f"{agent}_passed"] = True
                        if not passed:
                            state[f"{agent}_forced_accept"] = True
                    else:
                        status[agent] = "retry"
                        state[f"{agent}_passed"] = False

                    events.append({
                        "event": "evaluation",
                        "agent": agent,
                        "revision": revision,
                        "passed": passed,
                        "forced_accept": bool(state.get(f"{agent}_forced_accept", False)),
                        "timestamp": now_iso(),
                    })

        state["scheduler_status"] = status
        state["revision_summary"] = revisions
        state["scheduler_events"] = events
        return state
