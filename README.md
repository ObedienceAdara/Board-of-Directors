# Board of Directors AI

A multi-agent AI system that simulates a full executive board analyzing any business idea. Each agent plays a specialized role, produces a department report, gets evaluated by the CEO, and revises if needed — all automatically. Final output is a structured PDF report and an optional Notion board.

---

## Changelog — v2.1 hardening pass

- **Fixed:** live web search results were injected into prompts with no sanitization (brief fields were sanitized, search results weren't). Now redacted for injection phrases and wrapped in an explicit untrusted-data frame.
- **Fixed:** the CEO's ALIGNMENT criterion had no other department's output to check against during evaluation. Now receives a summary of everything completed so far.
- **Fixed:** no retry or fallback on any LLM call — a single failed API call mid-run crashed the entire board meeting. All LLM calls now retry and degrade to a labeled fallback instead of crashing.
- **Fixed:** Notion/PDF generation failures could discard already-completed department reports. Now isolated so a delivery failure doesn't lose the analysis.
- **Fixed:** stale OpenRouter/Gemini references in comments and `.env.example` from an earlier version — the system runs on Groq only.
- **Removed:** unused `current_phase` state field (set once, never read).
- **Added:** pinned dependency versions, basic test coverage for the sanitization/retry logic.

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
2. The CEO reads the brief and assigns a specific task to each department
3. Each agent runs in sequence, pulling live web research via Tavily
4. After each agent, the CEO evaluates the output against 4 criteria: specificity, depth, alignment, and actionability
5. If an output fails, the agent revises it (up to 3 times)
6. The CEO assembles a final board report with a GO / NO-GO / PIVOT recommendation
7. Output is saved as a PDF and optionally pushed to a Notion database

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
├── main.py           # LangGraph pipeline, FastAPI server, entry point
├── agents.py         # All 8 agent functions + sanitization + retry logic
├── prompts.py        # All agent system prompts
├── state.py          # Shared BoardState TypedDict
├── tools.py          # Tavily search, Notion API, PDF generation
├── tests/            # Unit tests (sanitization, framing, retry logic)
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

Tests cover the sanitization, framing, and retry logic with no API keys required (dummy env values are set automatically). They don't cover live LLM/search/Notion calls — those need real credentials to exercise.
