from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.llm import BaseLLMProvider, LLMProviderError
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    NewsItem,
    NewsSentimentOutput,
)


NEWS_SENTIMENT_SYSTEM_PROMPT = """
You are the News & Sentiment Agent for OpenAlpha, a local-first AI equity research application.

Your job is to interpret available news items and produce a structured news sentiment view for the requested stock.

You must not fetch external news yourself. You must only use the news data provided by the Data Collector through AnalysisContext.

This agent must work even when news data is missing, empty, stale, duplicated, low quality, or partially unavailable.

Core rules:

* Use only the provided news data.
* Do not invent news, events, sources, dates, or article details.
* Do not browse the web.
* Do not provide personalized financial advice.
* Do not recommend buying, selling, holding, or investing.
* Do not use language like "buy now", "sell now", "guaranteed", "risk-free", or "you should invest".
* Interpret news as research context only.
* Prefer cautious language when news coverage is limited.
* If no usable news is available, return a partial-style output with view = "insufficient_data", low confidence, empty important_news, and a clear warning.
* If news is stale, low-quality, promotional, duplicated, or only headline-level, mention that in warnings.
* If sentiment is mixed, explicitly say it is mixed.
* Output valid JSON only.
* Do not include markdown.
* Do not include explanations outside the JSON object.

Allowed values for view:

* bullish
* slightly_bullish
* neutral
* slightly_bearish
* bearish
* insufficient_data

Confidence rules:

* confidence must be a number between 0 and 1.
* Use 0.75-0.90 only when there are multiple recent, relevant, high-quality news items with consistent sentiment.
* Use 0.50-0.74 when there is useful news but sentiment is not fully clear or coverage is limited.
* Use 0.25-0.49 when news is sparse, stale, mixed, low quality, or only loosely related.
* Use 0.00-0.24 when no usable news is available.

Sentiment interpretation guidance:

* Company-specific positive news may support a bullish or slightly_bullish view.
* Company-specific negative news may support a bearish or slightly_bearish view.
* Mixed news, minor updates, or unclear implications should usually result in neutral or slightly directional views.
* Sector or macro news can be included only if it clearly affects the company.
* Do not overstate headline-only news.
* Do not treat rumors as facts.
* Do not treat sponsored, promotional, or low-quality sources as strong evidence.
* Recent, source-diverse, company-specific news should carry more weight than old or generic news.

Important news selection rules:

* Include only the most relevant news items.
* Deduplicate similar stories.
* Prefer company-specific items over generic market commentary.
* Include source and published date if provided.
* If a URL is provided, include it.
* If the article has only a headline and no body/summary, make that clear in the item summary or warnings.

Return exactly this JSON shape:

{
"view": "bullish | slightly_bullish | neutral | slightly_bearish | bearish | insufficient_data",
"confidence": 0.0,
"sentiment_summary": "A concise 2-4 sentence summary of the news sentiment and its likely research relevance.",
"important_news": [
{
"title": "News title",
"source": "Source name if available",
"published_at": "Publication date if available",
"summary": "Brief summary of the news item and why it matters.",
"sentiment": "positive | neutral | negative | mixed | unclear",
"relevance": "low | medium | high",
"url": "URL if available"
}
],
"warnings": [
"Warning or limitation 1"
]
}

If there are no warnings, return an empty warnings array.
""".strip()


class NewsSentimentAgent(BaseAgent[NewsSentimentOutput]):
    name = "news_sentiment_agent"
    output_schema = NewsSentimentOutput

    def __init__(
        self,
        *,
        llm_provider: BaseLLMProvider | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 900,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.llm_provider = llm_provider
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def execute(self, context: AnalysisContext) -> AgentExecutionPayload:
        news_items = self._news_items(context)
        if not news_items:
            output = NewsSentimentOutput(
                view="insufficient_data",
                confidence=0.1,
                sentiment_summary=(
                    "No usable recent news was available, so a reliable news "
                    "sentiment view cannot be formed from the provided data."
                ),
                important_news=[],
                warnings=[
                    "No usable news data was provided by the configured news providers."
                ],
            )
            context.news_sentiment_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=[],
                warnings=output.warnings,
            )

        provider = self.llm_provider or self._create_llm_provider(
            context.request.llm_provider
        )
        try:
            result = await provider.generate_json(
                messages=[
                    {"role": "system", "content": NEWS_SENTIMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": self.build_user_prompt(context)},
                ],
                output_schema=NewsSentimentOutput,
                model=context.request.llm_model,
                agent_name=self.name,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
        except LLMProviderError as exc:
            if self._should_stop_on_llm_error(exc):
                raise
            output = self._fallback_output_for_llm_failure(context, str(exc))
            context.news_sentiment_output = output
            return AgentExecutionPayload(
                status="partial",
                provider="local",
                model="deterministic",
                output=output,
                data_used=["news"],
                warnings=output.warnings,
            )

        output = self.validate_output(result.content)
        if not isinstance(output, NewsSentimentOutput):
            raise TypeError("news sentiment agent returned an unexpected output type")

        context.news_sentiment_output = output
        warnings = self._dedupe([*result.warnings, *output.warnings])

        return AgentExecutionPayload(
            status="completed",
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            output=output,
            data_used=["news"],
            warnings=warnings,
            parsing_errors=result.parsing_errors,
        )

    def _fallback_output_for_llm_failure(
        self,
        context: AnalysisContext,
        error_message: str,
    ) -> NewsSentimentOutput:
        news_items = self._news_items(context)
        warnings = self._dedupe(
            [
                "News sentiment analysis used a deterministic fallback because the LLM request failed.",
                f"LLM error: {error_message}",
                *self._news_warnings(context),
            ]
        )
        return NewsSentimentOutput(
            view="insufficient_data",
            confidence=0.15,
            sentiment_summary=(
                "News items were collected, but the AI sentiment interpretation step "
                "could not be completed because the configured LLM provider request failed."
            ),
            important_news=[],
            warnings=warnings
            + (
                [f"{len(news_items)} raw news item(s) were collected but not fully interpreted."]
                if news_items
                else []
            ),
        )

    def build_user_prompt(self, context: AnalysisContext) -> str:
        news_items = self._news_items(context)
        symbol = context.request.symbol
        payload = self._news_prompt_payload(news_items)
        prompt = (
            f"""Analyze the following news data for {symbol}.

Context:
- Symbol: {symbol}
- Company name: {self._company_name(context) or "Unknown"}
- Market: {context.request.market}
- Time horizon: {context.request.horizon}
- Analysis depth: {context.request.depth}
- News provider names: {self._join_or_none(self._news_provider_names(context))}
- News data status: {self._news_data_status(context)}
- News data quality score: {self._news_data_quality_score(context)}
- News provider warnings: {self._join_or_none(self._news_warnings(context))}
- Latest price timestamp: {self._latest_price_timestamp(context)}

Available news items:
{self._news_items_summary(news_items)}

Important constraints:
- Use only the news data above.
- Do not fetch external data.
- Do not invent missing article details.
- Do not provide personalized financial advice.
- If news data is stale, sparse, duplicated, or headline-only, reflect that in the output.
- Return valid JSON only using the required NewsSentimentOutput shape.

Structured news payload:
{json.dumps(payload, indent=2, sort_keys=True)}"""
        )
        if context.request.custom_question:
            prompt += (
                "\n\nUser research focus: "
                f"{context.request.custom_question.strip()}"
            )
        return prompt

    def _news_items(self, context: AnalysisContext) -> list[NewsItem]:
        if context.market_data is None:
            return []
        return list(context.market_data.news)

    def _news_prompt_payload(self, news_items: Sequence[NewsItem]) -> dict[str, Any]:
        return {
            "news_count": len(news_items),
            "items": [
                {
                    "title": item.title,
                    "source": item.source,
                    "published_at": item.published_at.isoformat()
                    if item.published_at
                    else None,
                    "url": item.url,
                    "summary": item.summary,
                    "sentiment_score": item.sentiment_score,
                    "headline_only": not bool(item.summary and item.summary.strip()),
                }
                for item in news_items
            ],
        }

    def _company_name(self, context: AnalysisContext) -> str | None:
        if context.market_data and context.market_data.company_profile:
            return context.market_data.company_profile.name
        return None

    def _news_provider_names(self, context: AnalysisContext) -> list[str]:
        if context.data_quality and context.data_quality.provider_names:
            return context.data_quality.provider_names
        if context.market_data and context.market_data.sources:
            return [source.provider for source in context.market_data.sources]
        return []

    def _news_data_status(self, context: AnalysisContext) -> str:
        if context.data_quality:
            return context.data_quality.news_data_status
        return "missing"

    def _news_data_quality_score(self, context: AnalysisContext) -> str:
        if context.data_quality and context.data_quality.score is not None:
            return f"{context.data_quality.score:.2f}"
        if context.market_data and context.market_data.data_quality_score is not None:
            return f"{context.market_data.data_quality_score:.2f}"
        return "unavailable"

    def _news_warnings(self, context: AnalysisContext) -> list[str]:
        warnings: list[str] = []
        if context.data_quality:
            warnings.extend(
                warning
                for warning in context.data_quality.warnings
                if "news" in warning.lower()
            )
        if context.market_data:
            warnings.extend(
                warning
                for warning in context.market_data.warnings
                if "news" in warning.lower()
                or "headline" in warning.lower()
                or "rss" in warning.lower()
            )
        warnings.extend(
            warning
            for warning in context.warnings
            if "news" in warning.lower()
            or "headline" in warning.lower()
            or "rss" in warning.lower()
        )
        return self._dedupe(warnings)

    def _latest_price_timestamp(self, context: AnalysisContext) -> str:
        if context.market_data and context.market_data.price_history:
            return self._format_datetime(context.market_data.price_history[-1].timestamp)
        if context.market_data and context.market_data.quote:
            return self._format_datetime(context.market_data.quote.as_of)
        return "unavailable"

    def _news_items_summary(self, news_items: Sequence[NewsItem]) -> str:
        if not news_items:
            return "- No news items available."

        parts = []
        for item in news_items:
            parts.append(
                (
                    f"- {item.title} | source={item.source} | "
                    f"published_at={self._format_optional_datetime(item.published_at)} | "
                    f"summary={item.summary.strip() if item.summary else 'headline only'} | "
                    f"sentiment_score={self._format_optional_float(item.sentiment_score)}"
                )
            )
        return "\n".join(parts)

    def _join_or_none(self, values: Sequence[str]) -> str:
        if not values:
            return "none"
        return "; ".join(values)

    def _format_datetime(self, value: datetime) -> str:
        return value.isoformat()

    def _format_optional_datetime(self, value: datetime | None) -> str:
        if value is None:
            return "unavailable"
        return self._format_datetime(value)

    def _format_optional_float(self, value: float | None) -> str:
        if value is None:
            return "unavailable"
        return f"{value:.2f}"

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        deduped: dict[str, None] = {}
        for value in values:
            stripped = value.strip()
            if stripped:
                deduped.setdefault(stripped, None)
        return list(deduped)


__all__ = ["NEWS_SENTIMENT_SYSTEM_PROMPT", "NewsSentimentAgent"]
