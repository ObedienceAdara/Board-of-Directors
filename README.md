# Board of Directors AI

A dependency-aware multi-agent business-analysis system that simulates an executive board while separating **LLM judgment** from **deterministic business validation and evidence provenance**.

## v3 Architecture

```text
Business Brief
  -> 7-way panel reactions
  -> CEO task allocation
  -> dynamic dependency scheduler
  -> formal department analysis + local deterministic validation + CEO quality gate
  -> deterministic global consistency pass
  -> LLM contradiction adjudication
  -> CEO final synthesis
  -> evidence/provenance ledger
  -> decision-grade report model
  -> PDF / Notion
```

The runtime still uses LangGraph as the outer execution envelope. The dynamic scheduler handles dependency-ready departmental work inside that envelope.

## Package Structure

```text
main.py                         # stable CLI/import entrypoint
app/
  api.py                        # FastAPI + LangServe surface
  pipeline.py                   # application orchestration + delivery
agents/
  board.py                      # stable board-agent interface
analysis/
  formal.py                     # formal-analysis interface
  consistency.py                # cross-domain consistency interface
  provenance.py                 # evidence/lineage interface
orchestration/
  scheduler.py                  # dynamic-readiness scheduler interface
models/
  state.py                      # BoardState + BusinessBrief
  provenance.py                 # provenance ledger builder + validator
reports/
  executive.py                  # compact strategic report model
tools/
  search.py                     # Tavily integration
  notion.py                     # Notion integration
  pdf.py                        # ReportLab executive PDF renderer
utils/
  runtime.py                    # truthful runtime status
formal_agents.py                # current v3 agent implementation
analysis_engine.py              # current deterministic formal engine
consistency_engine.py           # current deterministic consistency engine
scheduler.py                    # current scheduler implementation
prompts.py                      # current prompt library
tests/
```

The package boundaries are intentionally explicit before the next deeper architectural phase. Existing root implementations remain compatible while the application imports the new boundaries.

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

The PDF is now an **executive decision document**, not an archive of every department transcript.

It is deliberately bounded to **12 pages**:

1. Cover
2. Executive Decision Brief
3. The Opportunity
4. Financial Case
5. Technical Feasibility
6. Go-To-Market
7. Operating Model
8. Product & MVP
9. Risks & Contradictions
10. First 90 Days
11. Assumptions & Evidence
12. Final Board Recommendation

The report layer selectively extracts high-value findings and normalized claims from the full state. Full department analysis remains available in the internal state and Notion output.

## Outputs

A run returns the final report, formal integrity information, contradiction candidates and adjudication, scheduler status/events, revision counts, provenance ledger/validation/coverage, PDF path and optional Notion URL.

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

The suite covers formal validation, contradiction detection, retry/sanitization behavior, dynamic readiness, provenance lineage/integrity, API startup/route registration, mocked full-pipeline execution and the fixed PDF page-count contract.

For a real external integration run, use the credentialed staging workflow in `.github/workflows/staging.yml`.

## Documentation

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the package responsibilities, provenance chain and report design.
