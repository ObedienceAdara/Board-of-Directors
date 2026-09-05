# Board of Directors AI

A dependency-aware multi-agent business-analysis system that simulates an executive board while separating **LLM judgment** from **deterministic business validation**.

## v3 Upgrade

The v3 implementation introduces three major architectural changes:

1. **Formal departmental analysis** — every department now emits a human-readable `report` plus a machine-checkable `analysis` object. Domain validators independently check arithmetic and structural invariants.
2. **Formal global consistency** — deterministic cross-department checks run before an LLM adjudicator. The adjudicator classifies each detected conflict as a true contradiction, acceptable difference, or insufficient evidence and records the resolution.
3. **Dynamic readiness scheduling** — agents launch when their actual dependencies have passed. There are no fixed global tiers; independent branches can progress at different speeds and revision counts.

## Architecture

```text
Business Brief
  -> 7-way panel reactions
  -> CEO task allocation
  -> dynamic dependency scheduler
  -> formal department analysis + local deterministic validation + CEO quality gate
  -> deterministic global consistency pass
  -> LLM contradiction adjudication
  -> CEO final synthesis
  -> PDF / Notion
```

### Dependency graph

| Agent | Dependencies |
|---|---|
| Researcher | none |
| CFO | Researcher |
| CTO | Researcher |
| CMO | Researcher, CFO |
| COO | Researcher, CFO, CTO |
| Head of Sales | Researcher, CFO, CMO |
| PM | Researcher, CTO, CMO |

### Formal contract

Every department returns:

```json
{
  "report": "human-readable markdown",
  "analysis": {}
}
```

The report is for people; the analysis object is for software.

### Deterministic checks

- Research: TAM >= SAM >= SOM and evidence structure.
- CFO: cost sums, unit-economics arithmetic, non-negative scenarios, break-even validity.
- CTO: positive phase durations and engineering/infrastructure cost sanity.
- CMO: channel allocations equal marketing budget.
- Sales: price/revenue validity and required-customer derivation.
- COO: payroll derived from headcount x salary.
- PM: impact/effort validity and deterministic prioritization.

### Global consistency checks

The consistency engine checks relationships individual department validators cannot see:

- CFO operating budget vs CTO infrastructure + COO payroll.
- CFO base-case revenue vs Sales annual target.
- CFO marketing budget vs CMO budget.
- Researcher SOM vs Sales revenue target.
- CTO MVP timeline vs CMO launch timeline.
- Founder budget vs CFO startup-cost total.

The resulting contradiction candidates are then adjudicated by the CEO model. Arithmetic validation remains authoritative; the LLM cannot make a failed calculation become mathematically valid.

### Dynamic scheduling

`DynamicReadinessScheduler` uses actual data dependencies and a concurrent executor. When a branch passes, newly-ready agents are dispatched immediately. An agent needing three revisions does not hold an unrelated sibling hostage.

Scheduler events record dispatch, completion, evaluation, retries and forced acceptance.

## Outputs

A run returns the final report plus formal integrity information, deterministic contradiction candidates, adjudication results, scheduler status/events, revision counts, PDF path and optional Notion URL.

## Setup

```bash
pip install -r requirements.txt
```

Configure `GROQ_API_KEY`, `TAVILY_API_KEY`, and the optional API/Notion/LangSmith settings from `.env.example`.

## Running

```bash
python main.py
python main.py serve
```

API docs: `http://localhost:8000/docs`

## Testing

```bash
pytest tests/ -v
```

Tests cover deterministic validation, contradiction detection, sanitization/retry behavior, independent revisions and dynamic readiness.

## Project Structure

```text
main.py
formal_agents.py
agents.py
analysis_engine.py
consistency_engine.py
scheduler.py
prompts.py
tools.py
state.py
tests/
requirements.txt
.env.example
```

## Limitations

Deterministic validation verifies relationships among supplied values; it cannot establish that a sourced number is true. Web evidence still requires source-quality judgment. Global adjudication is recorded rather than automatically propagating backward into upstream reports; selective invalidation/re-analysis is reserved for a future staleness-aware architecture.
