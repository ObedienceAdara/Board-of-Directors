# Board of Directors — Architecture

## Runtime layers

```text
HTTP / CLI
   |
   v
app/api.py + app/pipeline.py
   |
   +--> agents/              LLM board roles
   +--> orchestration/       dependency scheduling
   +--> analysis/            formal validation + consistency + provenance
   +--> models/              shared typed state + provenance ledger schema
   +--> tools/               Tavily / Notion / PDF integrations
   +--> reports/             decision-grade report model
   +--> utils/               cross-cutting runtime status helpers
   |
   v
LangGraph execution envelope
```

## Package responsibilities

`app/` owns the application pipeline and HTTP API.

`agents/` is the stable import boundary for board-agent behavior. The detailed v3 implementation remains in `formal_agents.py` during this refactor so behavior is preserved before deeper migration.

`analysis/` exposes formal-analysis, deterministic consistency, and provenance interfaces. The existing root engines remain the canonical implementation until the next deeper migration.

`orchestration/` exposes the dynamic-readiness scheduler.

`models/` contains `BoardState`, `BusinessBrief`, agent definitions, and the Phase 1 provenance ledger schema.

`tools/` isolates external integrations: Tavily search, Notion delivery, and PDF rendering.

`reports/` converts the full internal state into a bounded strategic report model. The PDF is intentionally not a dump of raw departmental transcripts.

`utils/` contains cross-cutting runtime status checks.

## Phase 1 — Evidence provenance

Every normalized claim is represented as a lineage record. The intended chain is:

```text
claim
  |
  +--> evidence reference
  |      |
  |      +--> source
  |             |
  |             +--> retrieval metadata
  |
  +--> transformation / formula
  |      |
  |      +--> dependency claim IDs
  |
  +--> responsible agent
  |
  +--> board decision references
```

The ledger explicitly distinguishes:

- `reported`: the claim is matched to an evidence item carrying a source URL and retrieval metadata.
- `derived`: the claim is produced by a deterministic formula with dependency claim IDs and a transformation record.
- `agent_assertion`: the claim is an analyst/model assertion without external source linkage. It is not upgraded into a fact merely because it is plausible.

Research evidence preserves source URL, title, publisher, excerpt, retrieval timestamp, provider, query when available, and search rank. Derived financial, sales, payroll, marketing-allocation, and technical timeline claims receive component-level lineage so the calculation can be reconstructed.

The runtime stores three related artifacts:

- `provenance_ledger`: claims, evidence, sources, transformations, and decisions.
- `provenance_validation`: deterministic integrity checks for internal references and confidence ranges.
- `provenance_summary`: coverage and count metrics used by the report and API response.

The provenance stage runs after CEO synthesis, so the final recommendation itself can be linked back to the claims and contradictions that informed it. The executive PDF exposes a bounded provenance-integrity summary while Notion receives the complete bounded ledger.

## PDF design

The generated report is now deliberately fixed at 12 pages: one cover plus 11 decision pages.

1. Executive Decision Brief
2. The Opportunity
3. Financial Case
4. Technical Feasibility
5. Go-To-Market
6. Operating Model
7. Product & MVP
8. Risks & Contradictions
9. First 90 Days
10. Assumptions & Evidence
11. Final Board Recommendation

Long internal reports are selectively compressed into decision-relevant bullets. Full department reports remain available in state/Notion rather than consuming the executive PDF.

## Compatibility

`main.py` remains the stable entrypoint. Existing usage such as `import main` and `main.run_board_meeting(...)` is preserved.
