# Adding A New Provider

This guide covers extending OpenAlpha with a new market-data, news, or LLM provider.

## Design Rule

Keep provider-specific behavior behind the provider interface. Agent outputs and persisted report shapes should stay provider-agnostic.

## Market Data Providers

Base interface:

- `backend/app/marketdata/base.py`

Core contract:

- subclass `MarketDataProvider`
- implement `get_price_history()`
- optionally implement `get_company_facts()`
- declare `provider_name`
- declare `capabilities`

Returned result types:

- `PriceHistoryResult`
- `CompanyFactsResult`

Important fields:

- `provider`
- `status`
- `source`
- `warnings`
- normalized `PriceBar` / company-facts content

Registration point:

- `get_market_data_provider()` in `backend/app/marketdata/base.py`

If your provider should become part of the default price-history fallback chain, update `DataCollectorAgent._resolve_price_providers()`.

## News Providers

Base interface:

- `backend/app/news/base.py`

Core contract:

- subclass `NewsProvider`
- implement `get_news()`
- return `NewsProviderResult`

Article/result types:

- `NewsArticle`
- `NewsProviderResult`

Normalization expectations:

- provide clean article title/source/provider values
- normalize symbols
- set `published_at` when possible
- include `url` and `summary` when available
- use `warnings` for rate limits, partial parsing, and relevance caveats

Registration points:

- `get_default_news_providers()` if it should be in the default aggregate set
- or inject a custom provider list into `NewsService`

Warning behavior:

- the aggregate news service should be able to survive single-provider failures
- prefer returning `missing` or `partial` results rather than raising for every soft problem

## LLM Providers

Base interface:

- `backend/app/llm/base.py`

Core contract:

- subclass `BaseLLMProvider`
- implement `generate()`
- implement `generate_json()`
- define `provider_name`

Important behaviors to support:

- model resolution
- message normalization
- structured output validation
- retry handling for retryable failures
- token usage accounting
- cost calculation

### `generate()`

Should return an `LLMResult` containing:

- `provider`
- `model`
- `agent_name`
- `content`
- raw content/response when useful
- token usage
- estimated cost
- warnings and parsing errors

### `generate_json()`

Should:

- ask the remote model for structured output
- validate against the provided schema
- raise `LLMResponseValidationError` for invalid JSON or schema mismatch

Prefer using the shared validation helpers:

- `validate_json_content()`
- `validate_json_dict()`

### Cost Calculation

Implement `calculate_cost()` so report and performance views can show realistic totals.

If pricing is unknown:

- return `0.0`
- include a warning

## Settings, Discovery, And Registration

Current registration/discovery points:

- market data: `get_market_data_provider()`
- news defaults: `get_default_news_providers()`
- LLMs: explicit provider factory methods inside each agent today

Important current limitation:

- LLM providers are not centrally registered yet
- each active LLM-backed agent currently does its own provider-name switch and only supports `openai`

If you add a new LLM provider, you must update every active LLM-backed agent factory or introduce a shared factory and migrate the agents to it.

## Expected Warning And Fallback Behavior

Provider additions should preserve OpenAlpha's current resilience model:

- missing optional data should usually degrade to warnings and `partial`
- invalid auth/quota/configuration for LLMs may be fatal
- soft network/provider failures should be retryable when appropriate

Do not force hard failure for optional coverage that the rest of the pipeline can survive.

## Avoid Leaking Provider-Specific Shapes

Do not let provider-native JSON shapes escape into:

- agent output schemas
- `AnalysisContext`
- persisted report sections

Translate provider output into repo-owned schema types instead.

## Tests To Add

Add focused tests under `backend/tests/`:

- provider parsing/normalization
- error and warning handling
- registration lookup
- optional dependency behavior if applicable
- integration with the collector/news service/agent path

## Docs To Update

Update:

- [docs/providers.md](/C:/Users/ernos/OpenAlpha/docs/providers.md)
- [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md) if provider flow changes
- [README.md](/C:/Users/ernos/OpenAlpha/README.md) if the user-visible setup changes
