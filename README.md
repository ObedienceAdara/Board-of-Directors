# Board of Directors AI

A dependency-aware multi-agent business-analysis system that simulates an executive board while separating **LLM judgment** from **deterministic business validation**.

The current v3 pipeline produces human-readable reports plus machine-checkable analysis, runs departments whenever their actual dependencies are ready, detects cross-department contradictions before the final CEO decision, and uses an LLM only to adjudicate those detected conflicts.

## v3 Architecture

```text
Business Brief
     |
     v
7-way Panel Reactions (parallel)
     |
     v
CEO Task Allocation
     |
     v
Dynamic Dependency Scheduler
     |
     +--> Researcher
             |
             +--> CFO -----------+
             |                    |
             +--> CTO --------+   |
                              |   |
                              +--> CMO --------+
                              |               |
                              +--> COO        |
                              |               +--> Head of Sales
                              |               |
                              +--------------> PM
                                      |
                                      v
                         Local deterministic validation
                                      |
                                      v
                            CEO quality gate / revision
                                      |
                                      v
                       All formal analyses complete
                                      |
                                      v
                         Deterministic consistency pass
                                      |
                                      v
                         LLM contradiction adjudication
                                      |
                                      v
                            CEO final synthesis
                                      |
                           +----------+----------+
                           |                     |
                          PDF                 Notion
```

The scheduler does **not** use artificial global tiers. It uses the actual declared dependency graph:

| Agent | Dependencies |
|---|---|
| Researcher | none |
| CFO | Researcher |
| CTO | Researcher |
| CMO | Researcher, CFO |
| COO | Researcher, CFO, CTO |
| Head of Sales | Researcher, CFO, CMO |
| PM | Researcher, CTO, CMO |

This means, for example, that CMO can begin as soon as Researcher and CFO pass even if CTO is still running.

## Agents

| Agent | Formal responsibility |
|---|---|
| CEO | agenda, quality gates, contradiction adjudication, final synthesis |
| Researcher | market sizing, evidence, competitors, regulatory context |
| CFO | startup costs, operating burn, scenarios, unit economics, break-even |
| CTO | build feasibility, stack, engineering cost, infrastructure, timeline |
| CMO | marketing budget, channel allocation, launch timing, ICP/positioning |
| Head of Sales | pricing, revenue target, funnel math, sales channels |
| COO | headcount, payroll, vendors, support model, operating KPIs |
| PM | MVP feature prioritization, effort/impact, roadmap and metrics |

## Formal Analysis Contract

Every department returns exactly this top-level structure:

```json
{
  "report": "human-readable markdown",
  "analysis": {
    "...": "structured domain facts"
  }
}
```

The `report` is what a founder reads. The `analysis` is what software checks.

### Deterministic checks currently implemented

**Researcher**
- TAM, SAM and SOM cannot violate TAM >= SAM >= SOM.
- Evidence records require claims and record source URLs where available.

**CFO**
- Startup-cost line items are summed by software.
- CAC and LTV must be positive/valid.
- Reported LTV:CAC must equal LTV / CAC within tolerance.
- Revenue scenario values cannot be negative.
- Break-even month cannot be negative.

**CTO**
- Development phase durations must be positive.
- MVP time must be positive.
- Engineering and infrastructure costs cannot be negative.
- Phase-duration arithmetic is computed independently.

**CMO**
- Channel allocations must sum to the declared marketing budget.

**Head of Sales**
- Price and revenue targets must be valid.
- Lead-to-customer rate must be between 0 and 1.
- Required annual customers are derived from revenue target / price and checked against the declared value.

**COO**
- Payroll is derived from headcount x annual salary for every role.
- Declared annual payroll must reconcile to the derived total.
- Monthly payroll is derived deterministically from annual payroll.

**PM**
- Every MVP feature must have a numeric impact and positive effort.
- A deterministic impact/effort priority score is calculated.

## Formal Cross-Department Consistency

After every department has passed its local quality gate, v3 executes a separate global consistency phase.

It checks relationships that individual department validation cannot see:

- CFO monthly operating budget vs CTO infrastructure + COO payroll.
- CFO base-case annual revenue vs Sales annual revenue target.
- CFO marketing budget vs CMO marketing budget.
- Researcher SOM vs Sales annual revenue target.
- CTO MVP weeks vs CMO launch window.
- Business-brief budget vs CFO startup-cost total.

The detector emits explicit contradiction candidates such as:

```json
{
  "id": "CD-001",
  "category": "budget_capacity",
  "severity": "high",
  "agents": ["cfo", "cto", "coo"],
  "statement": "CFO monthly operating budget is lower than the CTO infrastructure cost plus COO payroll.",
  "evidence": {
    "cfo_monthly_operating_cost": 1000,
    "cto_monthly_infrastructure_cost": 800,
    "coo_monthly_payroll": 500,
    "minimum_required": 1300
  }
}
```

Only then does the CEO adjudication model decide whether each detected issue is a **TRUE_CONTRADICTION**, **ACCEPTABLE_DIFFERENCE**, or **INSUFFICIENT_EVIDENCE**, and provide a resolution.

This separation matters: the LLM is not trusted to decide whether 800 + 500 is greater than 1000.

## Dynamic Readiness Scheduler

`DynamicReadinessScheduler` is a dependency-driven concurrent executor.

It maintains per-agent statuses:

```text
pending -> running -> passed
                   \-> retry -> running
```

When one agent passes, every currently blocked agent is re-evaluated for readiness. A newly-ready agent is dispatched immediately, without waiting for unrelated work to finish.

Revision limits remain per agent. A CFO needing three attempts does not force a one-pass CTO to rerun.

The scheduler records dispatch, completion, evaluation, retry and forced-accept events in `scheduler_events` for observability.

## Output

Every successful run can produce:

- human-readable department reports
- deterministic validation results
- formal consistency snapshot
- deterministic contradiction candidates
- LLM contradiction adjudication
- CEO final recommendation
- PDF report
- optional Notion board
- revision and scheduler event log

The public runner returns:

```text
final_report
notion_board_url
pdf_path
revision_summary
consistency_status
deterministic_contradictions
contradiction_adjudication
formal_snapshot
scheduler_status
scheduler_events
```

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure:

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | LLM inference |
| `TAVILY_API_KEY` | Yes for live research | Web research |
| `API_SECRET_KEY` | Recommended | API authentication |
| `RATE_LIMIT_PER_MINUTE` | Optional | In-memory request limit |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Optional | Enable LangSmith tracing |
| `LANGCHAIN_PROJECT` | Optional | Trace project name |
| `NOTION_API_KEY` | Optional | Notion output |
| `NOTION_DATABASE_ID` | Optional | Notion target database |

Each agent can use a different model through:

```env
CEO_MODEL=llama-3.3-70b-versatile
RESEARCHER_MODEL=llama-3.3-70b-versatile
CFO_MODEL=llama-3.3-70b-versatile
CTO_MODEL=llama-3.3-70b-versatile
CMO_MODEL=llama-3.3-70b-versatile
SALES_MODEL=llama-3.3-70b-versatile
COO_MODEL=llama-3.3-70b-versatile
PM_MODEL=llama-3.3-70b-versatile
```

## Running

CLI demo:

```bash
python main.py
```

API server:

```bash
python main.py serve
```

Then open:

```text
http://localhost:8000/docs
http://localhost:8000/board-meeting/playground
```

## Testing

Run the complete test suite:

```bash
pytest tests/ -v
```

The v3 tests cover:

- prompt-input and web-content sanitization
- retry/fallback behavior
- deterministic financial, market, marketing and payroll validation
- cross-domain contradiction detection
- dynamic readiness (a newly-ready agent launches before an unrelated slow branch completes)
- independent revision loops

Tests intentionally do not require real Groq/Tavily/Notion credentials for deterministic scheduler/engine coverage.

## Project Structure

```text
├── main.py                  # LangGraph API envelope + pipeline entry point
├── formal_agents.py         # v3 structured-output agents and CEO functions
├── agents.py                # backwards-compatible facade to formal_agents.py
├── analysis_engine.py       # deterministic domain validation + canonical claims
├── consistency_engine.py    # deterministic cross-department contradiction detector
├── scheduler.py             # dependency-readiness concurrent scheduler
├── prompts.py               # structured JSON contracts for every agent
├── tools.py                 # Tavily, Notion, PDF utilities
├── state.py                 # typed v3 execution state
├── tests/
│   ├── test_sanitization.py
│   ├── test_parallel_e2e.py
│   └── test_formal_analysis.py
├── requirements.txt
└── .env.example
```

## Important Limitations

v3 is materially stronger than the previous prompt-only architecture, but it is still decision-support software rather than a guaranteed-truth engine.

Deterministic validation can prove arithmetic relationships between supplied numbers; it cannot prove that the supplied numbers are true. Web evidence still requires source-quality judgment. LLM adjudication can classify a detected conflict incorrectly, so the system preserves the deterministic evidence alongside the verdict.

The current global stage is intentionally **adjudication without automatic bidirectional repair**. If the CEO concludes that two reports conflict, the contradiction and recommended resolution are recorded for the final decision instead of silently mutating upstream reports. A future version can add selective invalidation and dependency-aware re-analysis once stale-state semantics are formalized.
