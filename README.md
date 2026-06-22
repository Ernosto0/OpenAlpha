# OpenAlpha

OpenAlpha is a local-first AI equity research workstation for public stocks.

It runs on your machine, launches a multi-agent research pipeline, shows each agent step in real time, stores every report in SQLite, and tracks how past calls performed against the market.

![OpenAlpha performance tracking](docs/assets/openalpha4.png)

## Why OpenAlpha

- Local-first: FastAPI, React/Vite, and SQLite run on your machine. No hosted OpenAlpha account is required.
- Auditable: you can inspect agent progression, outputs, sources, data-quality warnings, and estimated LLM cost traces.
- Practical: one CLI command boots the backend and frontend together and prepares the local database.
- Measurable: saved reports are evaluated later so you can see whether the AI's directional views were actually right.

## Quick Start

Prerequisites:

- Python `3.10+`
- Node.js with `npm`

From the repository root:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
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

If a preferred port is already taken, `openalpha run .` automatically searches for the next available local port.

## What You Can Do Today

- Launch a research run from the dashboard or analysis page with a symbol, market, horizon, depth, provider, model, and optional research focus.
- Watch the live execution graph as the current pipeline runs:
  `data_collector -> technical/news -> bull/bear -> risk -> thesis -> report_writer`
- Review the final persisted report with summary, thesis, bull and bear cases, risk scoring, data quality, sources, and cost telemetry.
- Browse historical reports in the local report store.
- Evaluate past reports on the performance page, including direction correctness and relative performance versus `SPY` for US equities.

![OpenAlpha analysis execution trace](docs/assets/openalpha2.png)

![OpenAlpha reports and audit history](docs/assets/openalpha3.png)

## Supported Providers

### LLM Providers

| Provider | Status | Notes |
| --- | --- | --- |
| OpenAI | Supported | Full runtime support, settings persistence, and credential testing |
| Claude | Supported | Full runtime support, settings persistence, and credential testing |
| Gemini | Supported | Full runtime support, settings persistence, and credential testing |
| Ollama | Partial | Settings are stored in the UI, but active local runtime support is not implemented yet |

### Data Sources

OpenAlpha already ships with multiple built-in provider surfaces for market data and news aggregation, including:

- Market data: `stooq`, `yahoo`, `yfinance`, `sec_edgar`, `user_api`
- News: `gdelt`, `rss`, `yahoo_finance_rss`, `sec_edgar_news`

See [providers.md](docs/providers.md) for the current implementation details and limitations.

## Limitations

- OpenAlpha is an MVP research workstation, not a brokerage, execution engine, or portfolio manager.
- It is not a real-time institutional market terminal.
- Ollama/local runtime support is not active yet, even though the settings UI exposes local configuration fields.
- The repo also contains aspirational design notes in [agent.md](agent.md); the source of truth for the shipped implementation is the code and the docs linked below.

## Documentation

- [Installation Guide](docs/installation-guide.md)
- [Architecture](docs/architecture.md)
- [Agents](docs/agents.md)
- [Providers](docs/providers.md)
- [Adding a New Agent](docs/adding-a-new-agent.md)
- [Adding a New Provider](docs/adding-a-new-provider.md)

## Contributing

- [Contributing Guide](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)

## Disclaimer

OpenAlpha is an equity research tool for research and educational purposes only. It is not personalized financial advice, investment advice, or a recommendation to buy or sell any security.
