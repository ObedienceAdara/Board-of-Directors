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
   +--> analysis/            formal validation + consistency
   +--> models/              shared typed state
   +--> tools/               Tavily / Notion / PDF integrations
   +--> reports/             decision-grade report model
   +--> utils/               runtime truth/status helpers
   |
   v
LangGraph execution envelope
```

## Package responsibilities

`app/` owns the application pipeline and HTTP API.

`agents/` is the stable import boundary for board-agent behavior. The detailed v3 implementation remains in `formal_agents.py` during this refactor so behavior is preserved before Phase 1.

`analysis/` exposes formal-analysis and deterministic consistency interfaces. The existing root engines remain the canonical implementation until the next deeper migration.

`orchestration/` exposes the dynamic-readiness scheduler.

`models/` contains `BoardState`, `BusinessBrief`, and shared agent definitions.

`tools/` isolates external integrations: Tavily search, Notion delivery, and PDF rendering.

`reports/` converts the full internal state into a bounded strategic report model. The PDF is intentionally not a dump of raw departmental transcripts.

`utils/` contains cross-cutting runtime status checks.

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
