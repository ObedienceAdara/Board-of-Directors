# Canonical Company State

Phase 1 introduces `CompanyState` as the authoritative representation of the business world.

## Authority model

```text
User brief
   |
   v
CompanyState initialization
   |
   +--> LLM board artifacts (proposals / assumptions)
   |
   +--> deterministic engines (validated consequences)
             |
             v
        CompanyState synchronization
```

The important boundary is that an LLM response does not become truth merely because it contains a number. Formal validation and deterministic calculation establish quantitative values before they are promoted into the canonical state.

## State domains

`CompanyState` contains:

- `identity`: company identity and market context.
- `objectives`: goals, KPIs, and constraints.
- `strategy`: strategic thesis, priorities, and assumptions.
- `finance`: cash, revenue, cost, margin, burn, runway, and forecast outputs.
- `sales`: funnel rates, targets, and pipeline summary.
- `marketing`: budgets, channels, and strategy.
- `product`: roadmap and ranked priorities.
- `engineering`: delivery schedule and capacity.
- `operations`: capacity and payroll.
- `workforce`: employees and headcount.
- `customers`: customer entities and canonical active-count snapshot.
- `projects`: project entities and dependencies.
- `competitors`: monitored competitors and threat levels.
- `risks`: structured risk register.
- `decisions`: persistent decision records and outcomes.
- `events`: observed events and state-change metadata.
- `policies`: autonomy and action-control settings.
- `memory`: bounded state-change history and organizational facts.

All models use Pydantic with `extra="forbid"` so accidental fields are rejected at the world-model boundary.

## Revisions

Every promoted state mutation uses `CompanyState.record_change(...)` and receives a monotonically increasing `revision`. The last 100 changes are retained in `memory.recent_state_changes`.

Each state change records its source (`brief`, `deterministic`, `agent`, `external`, or `system`), method, timestamp, and optional provenance reference.

## Persistence

`JsonCompanyStateStore` provides a local, atomic reference implementation with optimistic revision checks. The application can later replace it with a database-backed implementation of the same `CompanyStateStore` protocol without changing the schema.

Phase 1 does not make file persistence the default API behavior. This avoids silently introducing shared mutable server state while keeping a concrete persistence contract for the next architectural phases.

## Agent interaction

Current agents receive a serialized canonical state as read-only context. Their reports and formal analyses remain transient execution artifacts. The promotion path is:

```text
agent proposal
    -> formal validation
    -> deterministic calculation
    -> CompanyState synchronization
```

This is intentional. It prevents incompatible agent-local copies of cash, customers, headcount, revenue, pipeline, or other business facts from becoming competing sources of truth.

## Phase 1 invariants

1. There is one canonical company world model per company state instance.
2. User prose initializes context but does not invent quantitative facts.
3. LLM outputs cannot directly mutate canonical quantitative state.
4. Deterministic outputs are the authority for computed consequences.
5. Every promoted mutation is revisioned and auditable.
6. The state can be serialized and restored without changing its schema.
7. External execution remains disabled by policy (`recommend_only`).
