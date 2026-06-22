# Agents

This document describes the current runtime agents in the active OpenAlpha orchestrator.

Common runtime behavior comes from `BaseAgent` in `backend/app/agents/base.py`:

- every agent exposes `name`
- most agents expose `output_schema`
- each agent implements `execute(context)`
- `BaseAgent.run()` records an `AgentResult` and a `CostTrace`
- LLM errors may either produce deterministic fallback output or stop the analysis if the error is treated as fatal

## Shared Input Surface

All agents operate on `AnalysisContext` from `backend/app/orchestrator/schemas.py`.

Important fields:

- `request`
- `market_data`
- `indicators`
- `technical_output`
- `news_sentiment_output`
- `bull_case_output`
- `bear_case_output`
- `risk_review_output`
- `thesis_output`
- `final_report`
- `data_quality`
- `agent_results`
- `cost_traces`
- `warnings`

## `data_collector`

Implementation: `backend/app/agents/data_collector_agent.py`

Purpose:

- fetch price history
- fetch company profile and financial snapshot
- aggregate news
- compute technical indicators deterministically
- construct data-quality metadata

Inputs:

- `request.symbol`
- `request.market`
- `request.horizon`
- `request.language`
- optional `request.custom_question` for news relevance scoring

Output schema:

- `DataCollectorOutput`

Writes to context:

- `market_data`
- `indicators`
- `data_quality`
- `warnings`

Provider/runtime behavior:

- deterministic only
- price-history fallback chain is default provider then Yahoo
- company facts default to `SECProvider`
- news uses `NewsService`

Failure and partial behavior:

- returns `partial` when price history is missing
- profile, financials, and news are optional and may degrade quality without aborting the run
- indicator generation is skipped if price history is unavailable

## `technical_agent`

Implementation: `backend/app/agents/technical_agent.py`

Purpose:

- interpret precomputed technical indicators
- produce a structured technical view

Inputs:

- `indicators`
- `market_data`
- `data_quality`
- `warnings`

Output schema:

- `TechnicalAgentOutput`

Writes to context:

- `technical_output`

Failure and partial behavior:

- if indicators are missing, returns deterministic `partial` output with `insufficient_data`
- if the LLM call fails with a non-fatal error, returns deterministic fallback output
- if the LLM call fails with a fatal auth/quota/configuration error, the analysis can stop

Deterministic fallback:

- yes

## `news_sentiment_agent`

Implementation: `backend/app/agents/news_sentiment_agent.py`

Purpose:

- interpret collected news items
- summarize sentiment and relevance

Inputs:

- `market_data.news`
- `data_quality`
- `warnings`

Output schema:

- `NewsSentimentOutput`

Writes to context:

- `news_sentiment_output`

Failure and partial behavior:

- if there is no usable news, returns deterministic `partial` output
- if the LLM call fails non-fatally, returns deterministic fallback output

Deterministic fallback:

- yes

## `bull_case_agent`

Implementation: `backend/app/agents/bull_case_agent.py`

Purpose:

- build the strongest reasonable upside case from upstream agent outputs

Inputs:

- `technical_output`
- `news_sentiment_output`
- `data_quality`
- `market_data`

Output schema:

- `BullCaseAgentOutput`

Writes to context:

- `bull_case_output`

Failure and partial behavior:

- if both technical and news outputs are missing, returns deterministic `partial`
- if the LLM call fails non-fatally, returns deterministic fallback output

Deterministic fallback:

- yes

## `bear_case_agent`

Implementation: `backend/app/agents/bear_case_agent.py`

Purpose:

- build the strongest reasonable downside case from upstream agent outputs

Inputs:

- `technical_output`
- `news_sentiment_output`
- `data_quality`
- `market_data`

Output schema:

- `BearCaseAgentOutput`

Writes to context:

- `bear_case_output`

Failure and partial behavior:

- if both technical and news outputs are missing, returns deterministic `partial`
- if the LLM call fails non-fatally, returns deterministic fallback output

Deterministic fallback:

- yes

## `risk_review_agent`

Implementation: `backend/app/agents/risk_review_agent.py`

Purpose:

- assign a research risk level
- score risk numerically
- generate invalidation conditions
- reduce confidence when evidence or data quality is weak

Inputs:

- `technical_output`
- `news_sentiment_output`
- `bull_case_output`
- `bear_case_output`
- `data_quality`
- `market_data`
- `warnings`

Output schema:

- `RiskReviewAgentOutput`

Writes to context:

- `risk_review_output`

Failure and partial behavior:

- if there are no usable inputs, returns deterministic `partial`
- if the LLM call fails non-fatally, returns deterministic fallback output

Deterministic fallback:

- yes

## `thesis_agent`

Implementation: `backend/app/agents/thesis_agent.py`

Purpose:

- synthesize the full research thesis
- choose the final AI view
- set final confidence
- generate the what-to-watch list

Inputs:

- `market_data`
- `data_quality`
- `technical_output`
- `news_sentiment_output`
- `bull_case_output`
- `bear_case_output`
- `risk_review_output`
- prior `agent_results`

Output schema:

- `ThesisAgentOutput`

Writes to context:

- `thesis_output`

Failure and partial behavior:

- if there are no usable inputs, returns deterministic `partial`
- if the LLM call fails non-fatally, returns deterministic fallback output

Deterministic fallback:

- yes

## `report_writer_agent`

Implementation: `backend/app/agents/report_writer_agent.py`

Purpose:

- convert the completed context into the persisted `FinalReport`
- preserve source, warning, and cost metadata in a user-facing format

Inputs:

- `market_data`
- `data_quality`
- `technical_output`
- `news_sentiment_output`
- `bull_case_output`
- `bear_case_output`
- `risk_review_output`
- `thesis_output`
- `cost_traces`
- prior `agent_results`

Output schema:

- `FinalReport`

Writes to context:

- `final_report`

Failure and partial behavior:

- if `thesis_output` is missing, returns a deterministic fallback report
- if the LLM call fails non-fatally, returns a deterministic fallback report
- the fallback report still preserves risk, data-quality, source, and cost sections using current context state

Deterministic fallback:

- yes

## Schema-Only, Inactive Agent Names

The schema layer defines additional agent names and output types:

- `fundamental_agent`
- `critic_agent`

Current state:

- they exist in `AgentName` and schema definitions
- they are not instantiated in `AnalysisRunner.agents`
- they do not run in the active orchestrator graph
- there are no active persistence or UI timeline slots for them beyond schema compatibility

## LLM Provider Support Across Agents

Every current LLM-backed agent creates an LLM provider by normalizing `request.llm_provider` and accepting only `openai`.

Current implication:

- `technical_agent`
- `news_sentiment_agent`
- `bull_case_agent`
- `bear_case_agent`
- `risk_review_agent`
- `thesis_agent`
- `report_writer_agent`

all support OpenAI only in the shipped runtime.

## Related Docs

- [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)
- [docs/adding-a-new-agent.md](/C:/Users/ernos/OpenAlpha/docs/adding-a-new-agent.md)
