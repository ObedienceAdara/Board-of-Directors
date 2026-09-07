# Board of Directors AI

A dependency-aware multi-agent business-analysis system that simulates an executive board while separating **LLM judgment** from **deterministic business validation and evidence provenance**.

## v1.0 Stabilization Baseline

Version `1.0.0` freezes the current deliberative architecture as a measurable control system before the project adds autonomous execution.

## Phase 1 — Canonical Company State

Phase 1 introduces `CompanyState` as the single canonical representation of business reality. The board remains a deliberative system: agents read the canonical state, propose assumptions, and receive deterministic consequences; validated deterministic results are the only quantitative outputs promoted back into the world model.

```text
Business Brief
  -> CompanyState initialization
  -> 7-way panel reactions
  -> CEO task allocation
  -> dynamic dependency scheduler
  -> formal department analysis + local deterministic validation + CEO quality gate
  -> deterministic domain calculations
  -> CompanyState synchronization
  -> deterministic global consistency pass
  -> LLM contradiction adjudication
  -> CEO final synthesis
  -> evidence/provenance ledger
  -> decision-grade report
  -> PDF / Notion
```

The runtime still uses LangGraph as the outer execution envelope. The dynamic scheduler handles dependency-ready departmental work inside that envelope.

## Package Structure

```text
main.py
app/
  __init__.py
  api.py
  pipeline.py
agents/
  __init__.py
  board.py
analysis/
  __init__.py
  calculations.py
  consistency.py
  formal.py
  phase2.py
orchestration/
  __init__.py
  scheduler.py
models/
  __init__.py
  company.py              # canonical CompanyState
  decisions.py            # persistent decision records
  entities.py             # customers, employees, projects, risks, etc.
  events.py               # company observations/events
  objectives.py           # objectives, KPIs, constraints
  provenance.py           # provenance ledger builder + validator
  state.py                # transient BoardState + canonical-state boundary
  store.py                # versioned persistence protocol + JSON reference store
reports/
  __init__.py
  executive.py
tools/
  __init__.py
  search.py
  notion.py
  pdf.py
utils/
  __init__.py
  metrics.py
  runtime.py
formal_agents.py
analysis_engine.py
consistency_engine.py
scheduler.py
prompts.py
tests/
  unit/
  integration/
  regression/
  scenarios/
  evals/
docs/
  ARCHITECTURE.md
  BASELINE.md
  COMPANY_STATE.md
```

### Canonical state domains

`CompanyState` contains identity, objectives, strategy, finance, sales, marketing, product, engineering, operations, workforce, customers, projects, competitors, risks, decisions, events, policies, and memory.

See [`docs/COMPANY_STATE.md`](docs/COMPANY_STATE.md) for the authority model, revision semantics, persistence boundary, and agent interaction contract.

## Department Dependency Graph

| Agent | Dependencies |
|---|---|
| Researcher | none |
| CFO | Researcher |
| CTO | Researcher |
| CMO | Researcher, CFO |
| COO | Researcher, CFO, CTO |
| Head of Sales | Researcher, CFO, CMO |
| PM | Researcher, CTO, CMO |

## Formal Analysis

Every department emits a human-readable `report` plus a machine-checkable `analysis` object. Validators check domain invariants such as financial arithmetic, TAM/SAM/SOM hierarchy, timeline sanity, marketing-budget reconciliation, payroll derivation and impact/effort prioritization.

Global deterministic consistency checks then test cross-department relationships before LLM adjudication.

## Evidence & Provenance

Phase 1 adds a machine-readable ledger so important decisions can be audited beyond the text of an LLM response:

```text
claim
  -> evidence
  -> source
  -> retrieval metadata
  -> transformation / formula
  -> responsible agent
  -> decision
```

Each normalized claim is explicitly classified as:

- `reported`: matched to source-backed evidence.
- `derived`: produced by a deterministic formula with dependency claim IDs.
- `agent_assertion`: an analyst/model assertion without external source linkage.

The ledger preserves source URL, title, publisher, evidence excerpt and retrieval metadata when supplied; missing source information is left missing rather than guessed. Component-level lineage is materialized for financial totals, payroll, marketing allocations and technical phase sums. The board recommendation and contradiction adjudications link back to their contributing claim IDs.

`run_board_meeting(...)` exposes `provenance_ledger`, `provenance_validation`, and `provenance_summary`. The executive PDF surfaces bounded provenance-integrity metrics, while the Notion output contains the complete bounded ledger.

## Executive PDF

The PDF is an **executive decision document**, not an archive of every department transcript. It is deliberately bounded to **12 pages**.

## Baseline Metrics

A board run includes:

```text
decision_correctness
calculation_correctness
provenance_completeness
contradiction_detection
pipeline_latency_ms
llm_cost
failure_rate
```

Unknown dimensions are represented explicitly rather than fabricated. Decision correctness requires labeled outcomes, and LLM cost requires normalized provider telemetry; both remain unscored/unavailable in the current runtime.

## Outputs

A run returns the final report, canonical `company_state`, formal integrity information, contradiction candidates and adjudication, scheduler status/events, revision counts, provenance ledger/validation/coverage, baseline metrics, PDF path and optional Notion URL.

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

The suite covers formal validation, contradiction detection, retry/sanitization behavior, dynamic readiness, provenance lineage/integrity, API startup/route registration, mocked full-pipeline execution, deterministic Phase 2 control cases, workforce-ramp regression, baseline metric contracts, canonical CompanyState invariants, persistence round-trips and the fixed PDF page-count contract.

For a real external integration run, use the credentialed staging workflow in `.github/workflows/staging.yml`.

## Documentation

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for package responsibilities, provenance, and report design.
See [`docs/BASELINE.md`](docs/BASELINE.md) for Phase 0 reliability and evaluation.
See [`docs/COMPANY_STATE.md`](docs/COMPANY_STATE.md) for Phase 1 canonical world-state design.
