# Board of Directors AI

A multi-agent AI system that simulates a full executive board analyzing any business idea. Each agent plays a specialized role, produces a department report, gets evaluated by the CEO, and revises if needed — all automatically. Final output is a structured PDF report and an optional Notion board.

---

## Changelog

### v2.3 — initial panel + contradiction-hunting
- **Added:** Tier 0 — before the CEO assigns any formal tasks, all 7 departments give a quick gut-reaction (100-150 words, one parallel LLM call each) to the raw brief: does this make sense from their angle, what's the biggest red flag, what would they focus on. The CEO's task-assignment prompt now receives these reactions and is instructed to write sharper, more targeted directives when multiple departments flag the same risk — instead of assigning generic tasks blind. Runs as a genuine 7-way parallel fan-out/fan-in (verified as a distinct pattern from the tiered gates before implementation — a one-shot fan-in with no retry loop behaves differently from the tier gates and was tested separately).
- **Strengthened:** the final assembly prompt now explicitly instructs the CEO to cross-check every department's report against the others for real contradictions (budget vs. infrastructure cost vs. hiring plan, conflicting timelines, a channel one department relied on that another already ruled out) — not just list gaps. The report's 4th section is now "Cross-Department Contradictions" instead of the softer "Critical Dependencies," and the CEO must say explicitly if it checked and found nothing, rather than leaving the section thin by omission.
- **Not done, deliberately:** bidirectional revision loops (agents revising each other's work after the fact) were considered and explicitly not built — it breaks the forward-only invariant the parallel gate pattern depends on, and needs real cascade/staleness tracking to do safely. Deferred until there's confirmed customer signal it's worth the risk.

### v2.2 — parallel execution
- **Changed:** department agents now run in parallel tiers instead of one long sequential chain, based on what each agent's prompt actually depends on:
  - Tier 1: Researcher (solo)
  - Tier 2: CFO ∥ CTO
  - Tier 3: CMO ∥ COO
  - Tier 4: Sales ∥ PM
- **Fixed (the real reason this needed a state redesign, not just new graph edges):** the old schema had one shared `evaluations` dict and one shared `revision_counts` dict that every agent's eval step read-modified-wrote. Safe under strict sequential execution; breaks silently under parallel execution, since two concurrent branches can read the same snapshot and one's update overwrites the other's with no error. Flattened into one `{agent}_revisions` / `{agent}_passed` / `{agent}_feedback` triplet per agent — each parallel branch now only ever writes keys no sibling touches.
- **Fixed:** every node function returned `{**state, "key": val}` — a full spread of the entire state, not just the field it changed. Under parallel execution this made every node "write" to every key on every run, including keys it never touched, which LangGraph correctly rejects as a conflicting concurrent write (`InvalidUpdateError`) the moment two siblings run in the same step. All node functions now return only the keys they actually change.
- **Added:** a "gate" node per parallel tier — both branches in a tier route there after every evaluation; the gate inspects state and either retries whichever agent(s) haven't passed yet, or advances once both have. Verified against LangGraph directly before use: naive multi-source conditional edges into a shared target fire on every individual arrival rather than waiting for all siblings, so the gate + explicit state-check pattern was used instead of relying on edge-based fan-in as a barrier.

### v2.1 — hardening pass
- **Fixed:** live web search results were injected into prompts with no sanitization (brief fields were sanitized, search results weren't). Now redacted for injection phrases and wrapped in an explicit untrusted-data frame.
- **Fixed:** the CEO's ALIGNMENT criterion had no other department's output to check against during evaluation. Now receives a summary of everything completed so far.
- **Fixed:** no retry or fallback on any LLM call — a single failed API call mid-run crashed the entire board meeting. All LLM calls now retry and degrade to a labeled fallback instead of crashing.
- **Fixed:** Notion/PDF generation failures could discard already-completed department reports. Now isolated so a delivery failure doesn't lose the analysis.
- **Fixed:** stale OpenRouter/Gemini references in comments and `.env.example` from an earlier version — the system runs on Groq only.
- **Removed:** unused `current_phase` state field (set once, never read).
- **Added:** pinned dependency versions, test coverage for sanitization/retry logic and the parallel execution path.

---

## Agents

| Agent | Role |
|---|---|
| CEO | Assigns tasks, evaluates all outputs, assembles final report |
| Researcher | Market size, competitors, trends, regulatory landscape |
| CFO | Startup costs, revenue projections, unit economics, break-even |
| CTO | Tech stack, architecture, MVP scope, dev timeline |
| CMO | ICP, positioning, channel strategy, 90-day launch plan |
| Head of Sales | Sales model, pricing, objection handling, revenue targets |
| COO | Operations model, hiring plan, vendor dependencies, KPIs |
| PM | Product vision, user personas, MVP features, product roadmap |

---

## How It Works

1. You submit a business brief (idea, market, budget, timeline, constraints)
2. **Tier 0:** all 7 departments give a quick gut-reaction to the raw brief in parallel — does it make sense from their angle, biggest red flag, what they'd focus on
3. The CEO reads the brief and the panel's reactions, and assigns a specific, panel-informed task directive to each department
4. Agents run in 4 dependency-ordered tiers, parallel within each tier:
   - **Tier 1:** Researcher (needs only the brief)
   - **Tier 2:** CFO ∥ CTO (both only need Researcher's output)
   - **Tier 3:** CMO ∥ COO (need CFO/CTO's output)
   - **Tier 4:** Sales ∥ PM (need CMO's output)

   Each agent pulls live web research via Tavily as it runs.
5. After each agent, the CEO evaluates the output against 4 criteria: specificity, depth, alignment (checked against every other completed department, not just the brief), and actionability
6. If an output fails, that agent revises it (up to 3 times) — independently of its sibling in the same tier, which may pass immediately or need its own separate revisions. A tier only advances once every agent in it has passed or hit the cap.
7. The CEO assembles a final board report — actively cross-checking every department's numbers and timelines against each other for real contradictions, not just listing gaps — with a GO / NO-GO / PIVOT recommendation
8. Output is saved as a PDF and optionally pushed to a Notion database

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
copy .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | LLM inference via Groq — get it at [console.groq.com](https://console.groq.com) |
| `TAVILY_API_KEY` | Yes | Web search — get it at [app.tavily.com](https://app.tavily.com) |
| `API_SECRET_KEY` | Recommended | Protects the REST API with `X-API-Key` header auth |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing — get it at [smith.langchain.com](https://smith.langchain.com) |
| `LANGCHAIN_TRACING_V2` | Optional | Set to `true` to enable LangSmith tracing |
| `NOTION_API_KEY` | Optional | Notion integration token for board output |
| `NOTION_DATABASE_ID` | Optional | Target Notion database ID |
| `RATE_LIMIT_PER_MINUTE` | Optional | API rate limit per IP (default: 10) |

---

## Running

### CLI — demo run

Runs the built-in Shopify SaaS example brief:

```bash
python main.py
```

### API server

```bash
python main.py serve
```

Server starts at `http://localhost:8000`

- Docs → `http://localhost:8000/docs`
- Playground → `http://localhost:8000/board-meeting/playground`

### API call

```bash
POST http://localhost:8000/board-meeting/invoke
X-API-Key: your_secret_key

{
  "input": {
    "brief": {
      "idea": "Your business idea",
      "target_market": "Who you're selling to",
      "budget": "$50,000",
      "founder_background": "Your background",
      "timeline": "MVP in 3 months",
      "constraints": "Bootstrapped, must reach revenue in 6 months"
    }
  }
}
```

---

## Output

Every run produces:

- **PDF report** — saved to the working directory as `board_report_YYYYMMDD_HHMMSS.pdf`
- **Notion board** — a parent page with one child page per department (requires Notion credentials)

The PDF includes:
- Cover page
- Executive summary
- One section per department report
- CEO final recommendation (GO / NO-GO / PIVOT)
- Appendix with revision log

---

## Model Configuration

All agents default to `llama-3.3-70b-versatile` on Groq. You can override any agent's model via env vars:

```env
CEO_MODEL=llama-3.3-70b-versatile
CFO_MODEL=llama-3.3-70b-versatile
CTO_MODEL=llama-3.3-70b-versatile
CMO_MODEL=llama-3.3-70b-versatile
SALES_MODEL=llama-3.3-70b-versatile
COO_MODEL=llama-3.3-70b-versatile
PM_MODEL=llama-3.3-70b-versatile
RESEARCHER_MODEL=llama-3.3-70b-versatile
```

---

## Project Structure

```
├── main.py           # LangGraph pipeline (tiered parallel execution), FastAPI server
├── agents.py         # All 8 agent functions + sanitization + retry logic
├── prompts.py        # All agent system prompts
├── state.py          # Shared BoardState TypedDict (flattened per-agent fields)
├── tools.py          # Tavily search, Notion API, PDF generation
├── tests/
│   ├── test_sanitization.py   # Sanitization, framing, retry logic
│   └── test_parallel_e2e.py   # Real end-to-end run with staggered revisions
├── requirements.txt  # Pinned dependencies
└── .env.example      # Environment variable template
```

---

## Security

- All brief fields are sanitized before being injected into prompts (length limits, injection pattern blocking)
- **Live web search results are sanitized too** — injection phrases are redacted and every search result is wrapped in an explicit "untrusted data" frame before it reaches an agent's prompt, so a compromised or adversarial webpage can't hijack the pipeline. Previously only brief fields were sanitized; search results were injected raw.
- REST API protected by `X-API-Key` header authentication
- Per-IP rate limiting on all API endpoints
- Server binds to `127.0.0.1` by default (localhost only)

## Reliability

- Every LLM call goes through a retry wrapper (`safe_invoke`) that retries transient failures and degrades to a clearly-labeled fallback message instead of crashing the run. A single flaky API call mid-run no longer loses the entire board meeting.
- Notion and PDF output generation are isolated in their own try/except blocks — if either fails, the department reports already computed are still returned instead of being discarded.
- The CEO's ALIGNMENT criterion now receives a summary of every other department's completed output, so it has something real to check cross-department consistency against (previously it only ever saw the brief and the single output being evaluated).

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

- `test_sanitization.py` — sanitization, untrusted-data framing, and retry/fallback logic. Pure functions, no API keys needed (dummy env values are set automatically).
- `test_parallel_e2e.py` — runs the real `run_board_meeting()` end to end through the actual compiled graph, with only the LLM/search/Notion/PDF calls mocked. Drives a staggered revision schedule across every agent (e.g. CFO needs 3 passes, CTO needs 1) to verify the tiered parallel structure handles asymmetric branch lengths correctly and every agent's revision count lands exactly where expected.

Neither test suite needs real credentials. They don't cover live LLM output quality, real search results, or actual Notion/PDF delivery — those need real credentials to exercise.
