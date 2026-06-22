# OpenAlpha

OpenAlpha is a local-first AI equity research workstation.

It runs a FastAPI backend, a React/Vite frontend, and a SQLite database on your machine so you can generate AI-assisted stock research reports, inspect each agent step, and review historical report performance without depending on a hosted OpenAlpha service.

## What OpenAlpha Is

- A local development app for AI-assisted equity research.
- A multi-agent analysis pipeline that collects market data, interprets technicals and news, builds bull and bear cases, scores risk, writes a thesis, and persists a final report.
- A transparent workstation: runs are stored in `openalpha.db`, agent outputs are visible, report sources are surfaced, and estimated LLM cost traces are retained.
- A current-codebase MVP focused on public equities research, not a complete institutional research platform.

## What OpenAlpha Is Not

- Not a brokerage, trading system, portfolio manager, or execution engine.
- Not a real-time market terminal.
- Not a fully offline LLM workstation yet. factories currently support `OpenAI`, 'Claude', 'Gemini' only.
- Not the full aspirational architecture described in [agent.md](/C:/Users/ernos/OpenAlpha/agent.md). The documentation in this repo describes the implementation that exists today.

Capture workflow for replacing them later:

1. Start the app with `openalpha run .`.
2. Open the dashboard, analysis run page, and a persisted report detail page.
3. Save PNG captures into `docs/assets/` using the filenames above.
4. Replace this section with embedded markdown images once real captures exist.

See [docs/assets/README.md](/C:/Users/ernos/OpenAlpha/docs/assets/README.md) for the placeholder asset list.

## Quick Start

Install the Python package in editable mode, install the frontend dependencies, then run both services together:

```powershell
pip install -e .
cd frontend
npm.cmd install
cd ..
openalpha run .
```

Default local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/api/health`

Full setup details: [docs/installation-guide.md](/C:/Users/ernos/OpenAlpha/docs/installation-guide.md)

## Add An API Key In Settings

1. Start OpenAlpha.
2. Open `Settings`.
3. Paste an OpenAI API key into `OpenAI API Key`.
4. Click `Apply Settings`.
5. Click `Test OpenAI` to verify the key.

Current-state note:

- The settings UI also exposes `Ollama Base URL`, `Ollama Model`, and `Test Ollama`.
- The backend stores those values locally, but live Ollama testing is not implemented and the runtime agents do not yet instantiate an Ollama provider.

Provider details: [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)

## Run An Analysis

1. Open `Analysis`.
2. Enter a stock symbol such as `AAPL`.
3. Choose `Market`, `Time Horizon`, `Analysis Depth`, `LLM Provider`, `Model`, and optional research focus.
4. Click `Run Analysis`.
5. Monitor the execution trace as the current runtime graph runs:
   `data_collector -> technical/news -> bull/bear -> risk -> thesis -> report_writer`
6. Open the persisted report once the run reaches `completed`.

Important API surfaces behind the UI:

- `GET /api/settings`
- `POST /api/providers/llm/test`
- `POST /api/analysis/run`
- `GET /api/analysis/{run_id}`
- `GET /api/analysis/{run_id}/events`
- `WS /ws/analysis/{run_id}`
- `GET /api/reports`
- `GET /api/performance`

Architecture details: [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md)

## Example Persisted Report Shape

OpenAlpha stores final reports as JSON in `reports.report_json` inside `openalpha.db`. The stored shape matches the `FinalReport` schema used by the backend and UI. The example below shows the real persisted field layout used by the app.

```json
{
  "title": "Equity Research Report: AAPL",
  "symbol": "AAPL",
  "company_name": "Apple Inc.",
  "market": "US",
  "created_at": "2026-06-20T12:00:00Z",
  "overall_view": "neutral",
  "confidence": 0.64,
  "horizon": "3m",
  "executive_summary": "Apple remains resilient, but near-term execution risk matters.",
  "investment_thesis": "The business remains strong, with earnings risk as the main near-term variable.",
  "base_case": "Base case assumes stable services growth and manageable hardware softness.",
  "bull_case_summary": "New product momentum and margins improve faster than expected.",
  "bear_case_summary": "Demand weakness and margin pressure weigh on the next few quarters.",
  "what_to_watch": [
    "Next earnings release",
    "iPhone demand indicators"
  ],
  "risk_section": {
    "risk_level": "high",
    "risk_score": 68,
    "main_risks": [
      "Earnings miss",
      "Margin compression"
    ],
    "invalidation_conditions": [
      "Revenue growth re-accelerates"
    ],
    "confidence_adjustment": -0.12
  },
  "data_quality_section": {
    "data_quality_score": 0.64,
    "price_data_status": "available",
    "news_data_status": "partial",
    "company_profile_status": "available",
    "missing_data": [
      "full fundamentals"
    ],
    "providers": [
      "yahoo",
      "gdelt"
    ],
    "warnings": [
      "News coverage is partial."
    ]
  },
  "source_section": [
    {
      "name": "Price History",
      "type": "price",
      "provider": "yahoo",
      "url": "https://example.com/prices",
      "used_for": "Technical context"
    }
  ],
  "cost_breakdown": {
    "total_estimated_cost_usd": 0.028,
    "items": [
      {
        "agent_name": "thesis_agent",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "input_tokens": 120,
        "output_tokens": 80,
        "estimated_cost_usd": 0.028
      }
    ]
  },
  "disclaimer": "This report is generated by an AI system for research and educational purposes only. It is not personalized financial advice, investment advice, or a recommendation to buy or sell any security. Always conduct your own research and consider consulting a licensed financial professional before making investment decisions."
}
```

Related docs:

- [docs/agents.md](/C:/Users/ernos/OpenAlpha/docs/agents.md)
- [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)
- [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md)

## Disclaimer

OpenAlpha is an equity research tool, not a financial advisor. Generated reports are for research and educational purposes only. They are not personalized financial advice, investment advice, or a recommendation to buy or sell any security.

## Contributing

Entry points:

- [CONTRIBUTING.md](/C:/Users/ernos/OpenAlpha/CONTRIBUTING.md)
- [ROADMAP.md](/C:/Users/ernos/OpenAlpha/ROADMAP.md)
- [docs/installation-guide.md](/C:/Users/ernos/OpenAlpha/docs/installation-guide.md)
- [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md)
- [docs/agents.md](/C:/Users/ernos/OpenAlpha/docs/agents.md)
- [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)
- [docs/adding-a-new-agent.md](/C:/Users/ernos/OpenAlpha/docs/adding-a-new-agent.md)
- [docs/adding-a-new-provider.md](/C:/Users/ernos/OpenAlpha/docs/adding-a-new-provider.md)
