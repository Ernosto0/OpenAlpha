# Architecture

This document describes the current OpenAlpha implementation, not the aspirational design in `agent.md`.

## Overview

OpenAlpha is a local-first app with three primary runtime layers:

- FastAPI backend in `backend/app/`
- React/Vite frontend in `frontend/src/`
- SQLite persistence in `openalpha.db`

Core runtime entrypoints:

- backend app factory: `backend/app/main.py`
- backend router composition: `backend/app/router.py`
- CLI launcher: `openalpha/cli.py`
- frontend analysis UI: `frontend/src/pages/analysis-page.tsx`

## Request Flow

Typical user flow:

1. The frontend loads settings from `GET /api/settings`.
2. The user submits an analysis request to `POST /api/analysis/run`.
3. The backend creates an `analysis_runs` row and starts an async orchestrator task.
4. `AnalysisRunner` executes the active agent graph.
5. Each agent appends runtime results to `AnalysisContext`.
6. The orchestrator persists new `agent_outputs` and `cost_traces` as the run progresses.
7. The final report is persisted into `reports.report_json`.
8. The frontend polls `GET /api/analysis/{run_id}` and may also subscribe to `GET /api/analysis/{run_id}/events` or `WS /ws/analysis/{run_id}`.
9. Once a `report_id` exists, the frontend loads the persisted report via `GET /api/reports/{report_id}`.
10. Performance views aggregate saved reports with fresh price history through `GET /api/performance`.

## Active Analysis Graph

The current orchestrator lives in `backend/app/orchestrator/base.py`.

Execution order:

1. `data_collector`
2. parallel: `technical_agent` and `news_sentiment_agent`
3. parallel: `bull_case_agent` and `bear_case_agent`
4. `risk_review_agent`
5. `thesis_agent`
6. `report_writer_agent`

In shorthand:

```text
data_collector -> technical/news -> bull/bear -> risk -> thesis -> report_writer
```

The active graph does not include `fundamental_agent` or `critic_agent`. Those names exist in schemas, but they are not wired into `AnalysisRunner.agents`.

## Backend Components

### FastAPI API

Route modules:

- `backend/app/api/routes/system.py`
- `backend/app/api/routes/settings.py`
- `backend/app/api/routes/analysis.py`
- `backend/app/api/routes/reports.py`
- `backend/app/api/routes/performance.py`

Important endpoints:

- `GET /`
- `GET /api/health`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/providers/llm/test`
- `POST /api/analysis/run`
- `GET /api/analysis/{run_id}`
- `GET /api/analysis/{run_id}/events`
- `WS /ws/analysis/{run_id}`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `DELETE /api/reports/{report_id}`
- `GET /api/performance`

### Orchestrator

Primary classes:

- `AnalysisRunner`
- `AnalysisContext`
- `AnalysisEvent`
- `AnalysisEventEmitter`

Responsibilities:

- build the runtime context from `AnalysisRequest`
- run agents in the current graph
- emit lifecycle events
- persist run metadata, agent outputs, cost traces, and final reports
- mark runs `completed` or `failed`

### Services

- `SettingsService`: local provider settings persistence and OpenAI test call
- `AnalysisManager`: async run lifecycle plus event history/websocket streaming
- `ReportService`: list, detail, and delete persisted reports
- `PerformanceService`: retrospective scoring using saved reports and refreshed price history

## Persistence Model

SQLite tables defined in `backend/app/db/models.py`:

- `settings`
- `analysis_runs`
- `agent_outputs`
- `reports`
- `cost_traces`

Persisted entities of note:

- local app and provider settings
- analysis run metadata
- per-agent outputs and statuses
- final report JSON payloads
- cost trace rows for each agent step

The final report persisted in `reports.report_json` matches the `FinalReport` schema in `backend/app/orchestrator/schemas.py`.

## Frontend Runtime Model

The frontend is a React 18 app with React Router and Vite.

Important pages:

- dashboard: `frontend/src/pages/dashboard-page.tsx`
- analysis: `frontend/src/pages/analysis-page.tsx`
- reports list/detail
- performance
- settings

The analysis page uses both polling and websocket updates:

- initial run detail refresh through `/api/analysis/{run_id}`
- event history through `/api/analysis/{run_id}/events`
- live stream through `/ws/analysis/{run_id}`

## Real-Time Updates

OpenAlpha has two current real-time mechanisms:

- polling for run detail and report availability
- websocket streaming for `AnalysisEvent` updates

If websocket delivery is interrupted, the frontend falls back to continued polling.

## LLM Runtime Reality

Current state:

- the UI exposes `OpenAI`, `Claude`, `Gemini`, and `Ollama`
- settings persistence supports all four provider names
- provider credential testing is implemented for `OpenAI`, `Claude`, and `Gemini`
- active agent provider factories instantiate `OpenAIProvider`, `AnthropicProvider`, and `GeminiProvider`

Result:

- OpenAI-backed runs are supported
- Claude-backed runs are supported
- Gemini-backed runs are supported
- Ollama/local is currently a partial/planned surface, not a working runtime path

## Performance Evaluation Model

`PerformanceService` evaluates saved reports against later price history.

Current behavior:

- uses saved `reports`
- refetches price history through the default market-data providers
- benchmarks US reports against `SPY`
- scores directional correctness for bullish and bearish views
- treats neutral or insufficient-data outputs as `not_scored`

## See Also

- [docs/agents.md](agents.md)
- [docs/providers.md](providers.md)
- [docs/adding-a-new-agent.md](adding-a-new-agent.md)
- [docs/adding-a-new-provider.md](adding-a-new-provider.md)
