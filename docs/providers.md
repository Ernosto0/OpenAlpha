# Providers

This document describes the provider surfaces that currently exist in the codebase and how they behave in practice.

## Summary

OpenAlpha has three provider categories:

- market data providers
- news providers and the aggregate news service
- LLM providers

Current runtime truth:

- market data has several implemented providers
- news uses a multi-provider aggregation service
- the shipped remote LLM runtimes are OpenAI, Claude, and Gemini
- Ollama is a first-class local runtime provider using the canonical provider id `ollama` while still accepting legacy `local` settings payloads during rollout

## Market Data Providers

Factory: `backend/app/marketdata/base.py`

Known provider names:

- `stooq`
- `yahoo`
- `yfinance`
- `sec_edgar`
- `user_api`

### `stooq`

Implementation:

- `backend/app/marketdata/providers/stooq_provider.py`

Current role:

- default market-data provider for price history

Characteristics:

- free/unofficial data source
- used first in the data-collector price-history chain

### `yahoo`

Implementation:

- `backend/app/marketdata/providers/yahoo_provider.py`

Current role:

- fallback price-history provider

Characteristics:

- unofficial endpoint usage
- code and tests explicitly warn about unofficial status

### `yfinance`

Implementation:

- `backend/app/marketdata/providers/yfinance_provider.py`

Current role:

- optional provider surfaced by the factory

Characteristics:

- requires the optional `yfinance` dependency
- raises configuration errors if that package is unavailable

### `sec_edgar`

Implementation:

- `backend/app/marketdata/providers/sec_provider.py`

Current role:

- company profile
- financial snapshot
- filing and company-facts support

Characteristics:

- official SEC-derived data
- used by `DataCollectorAgent` as the default facts provider

### `user_api`

Implementation:

- `backend/app/marketdata/providers/user_api_provider.py`

Current role:

- callback-driven custom provider for local extension/testing

Characteristics:

- useful for integration with private data sources
- no hosted registry or plugin system yet

## News Providers And Aggregation

Aggregation service:

- `backend/app/news/base.py`

Default provider list:

- `gdelt`
- `rss`
- `yahoo_finance_rss`
- `sec_edgar_news`

The `NewsService`:

- queries all configured providers
- preserves warnings from partial failures
- deduplicates overlapping items
- scores relevance using the symbol and optional custom question
- returns `available`, `partial`, or `missing`

### Implemented Default News Providers

#### `gdelt`

- implementation: `backend/app/news/providers/gdelt_provider.py`
- broad web/news aggregation
- useful for headline discovery

#### `rss`

- implementation: `backend/app/news/providers/rss_provider.py`
- curated RSS parsing path
- good for lightweight fallback coverage

#### `yahoo_finance_rss`

- implementation: `backend/app/news/providers/yahoo_finance_rss_provider.py`
- symbol-specific RSS feed
- treated as unofficial

#### `sec_edgar_news`

- implementation: `backend/app/news/providers/sec_edgar_provider.py`
- converts official SEC filing activity into news-style events
- useful for company-specific filing awareness

### Placeholder Or Partial News Providers

These modules exist but currently act as non-implemented placeholders:

- `alpha_vantage`
- `finnhub`
- `fmp`
- `polygon`

They return missing/not-implemented style responses rather than live news in the current codebase.

## LLM Providers

Base contract:

- `backend/app/llm/base.py`

Implemented providers:

- `OpenAIProvider` in `backend/app/llm/providers/openai_provider.py`
- `AnthropicProvider` in `backend/app/llm/providers/anthropic_provider.py`
- `GeminiProvider` in `backend/app/llm/providers/gemini_provider.py`

Current behavior:

- agents call `generate_json()` for structured outputs
- token usage and estimated cost are captured when the provider returns usage data
- pricing is configured for a small set of OpenAI, Claude, and Gemini models

Remote runtime support exists across the active LLM-backed agents for OpenAI, Claude, and Gemini.

## Ollama And Local Runtime Status

The settings and frontend layers support:

- provider name `local`
- Ollama base URL
- Ollama model
- default provider switching in the UI

But current runtime limitations are important:

- `POST /api/providers/llm/test` returns `untested` for `local`
- active agent factories reject the `local` provider name
- there is no shipped Ollama LLM provider implementation in `backend/app/llm/providers/`

Result:

- OpenAlpha currently presents Ollama as a stored configuration surface, not a working agent runtime

## Fallback And Warning Behavior

### Market Data

- `DataCollectorAgent` tries the default price provider, then Yahoo
- price history absence causes a `partial` collector result
- facts/news failures append warnings without necessarily aborting the run

### News

- the aggregate `NewsService` preserves provider-level failures as warnings
- successful providers can still yield an overall `partial` news result

### LLM

- non-fatal LLM failures usually trigger deterministic agent fallback outputs
- auth/quota/configuration failures may be treated as fatal and stop the run
- fallback outputs are intentionally cautious and often use `insufficient_data`

## Data Quality Implications

Provider choice and provider failure directly affect:

- `data_quality.score`
- report warnings
- missing-data fields
- final confidence via the risk/thesis layers

Examples:

- no price history means technical interpretation becomes partial or unavailable
- no usable news lowers confidence and can push the final thesis toward mixed or insufficient-data states
- placeholder paid news providers do not add live coverage today
- using unofficial sources like Yahoo endpoints should be treated as pragmatic, not canonical

## Related Docs

- [docs/architecture.md](architecture.md)
- [docs/adding-a-new-provider.md](adding-a-new-provider.md)
