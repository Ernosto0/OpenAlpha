# Roadmap

This roadmap reflects the current repo state and the gaps already implied by the code.

## Current MVP Capabilities

- local FastAPI backend plus React/Vite frontend
- SQLite persistence for settings, runs, agent outputs, reports, and cost traces
- multi-agent analysis graph:
  `data_collector -> technical/news -> bull/bear -> risk -> thesis -> report_writer`
- OpenAI-backed structured-output research pipeline
- market-data collection with provider fallback
- aggregated news collection with partial-result handling
- persisted final reports with source, warning, and cost metadata
- performance scoring against later price history

## Near-Term Gaps Already Visible In The Code

- the UI exposes `Ollama`, but runtime agent provider factories do not support it yet
- LLM provider creation is duplicated across agents instead of being centralized
- `fundamental_agent` and `critic_agent` exist in schemas but are not active
- placeholder paid news providers exist but are not implemented
- market-data provider selection is still mostly hard-coded
- local secret handling is partly database-driven and not yet especially robust
- some frontend text still shows encoding artifacts and rough edges

## Planned Additions

- true Ollama/local LLM execution support
- a shared LLM provider factory instead of per-agent switches
- more first-class market-data providers
- more fully implemented news providers
- richer evaluation metrics beyond simple directional correctness and alpha
- stronger local secret handling and clearer secret storage boundaries
- deeper report comparison and audit tooling
- broader agent graph evolution, potentially including fundamentals and critique stages
