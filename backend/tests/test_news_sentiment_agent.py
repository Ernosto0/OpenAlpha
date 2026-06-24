from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from backend.app.agents.news_sentiment_agent import NewsSentimentAgent
from backend.app.llm import LLMMessage, LLMProviderError, LLMResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    CompanyProfile,
    DataQualitySummary,
    MarketDataBundle,
    NewsItem,
    NewsSentimentOutput,
)


class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self,
        *,
        messages: Sequence[LLMMessage | Mapping[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        agent_name: str = "unknown",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        self.calls.append(
            {
                "messages": messages,
                "output_schema": output_schema,
                "model": model,
                "agent_name": agent_name,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        return LLMResult(
            provider=self.provider_name,
            model=model or "fake-model",
            agent_name=agent_name,
            content=output_schema.model_validate(
                {
                    "view": "slightly_bullish",
                    "confidence": 0.62,
                    "sentiment_summary": (
                        "Recent coverage leans constructive, but the sample is limited "
                        "and not fully decisive."
                    ),
                    "important_news": [
                        {
                            "title": "Apple expands AI features across devices",
                            "source": "Example News",
                            "published_at": "2026-06-20T09:00:00Z",
                            "summary": (
                                "The update supports product momentum and may help the "
                                "company's ecosystem narrative."
                            ),
                            "sentiment": "positive",
                            "relevance": "high",
                            "url": "https://example.com/apple-ai",
                        }
                    ],
                    "warnings": ["Coverage is limited to a small recent sample."],
                }
            ),
            input_tokens=140,
            output_tokens=55,
            estimated_cost_usd=0.003,
            warnings=["No pricing configured for fake/fake-model."],
        )


class FailingLLMProvider:
    provider_name = "fake"

    async def generate_json(self, **_kwargs: Any) -> LLMResult:
        raise LLMProviderError(
            "OpenAI API returned HTTP 400: invalid response format",
            retryable=True,
        )


def make_context(*, news: list[NewsItem] | None = None) -> AnalysisContext:
    return AnalysisContext(
        run_id="run_news",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="Focus on near-term product and regulatory news.",
        ),
        market_data=MarketDataBundle(
            symbol="AAPL",
            market="US",
            company_profile=CompanyProfile(name="Apple Inc."),
            news=news or [],
        ),
    )


def test_news_sentiment_agent_calls_llm_and_saves_output_to_context() -> None:
    context = make_context(
        news=[
            NewsItem(
                title="Apple expands AI features across devices",
                source="Example News",
                published_at="2026-06-20T09:00:00Z",
                url="https://example.com/apple-ai",
                summary="Apple introduced a wider AI rollout tied to its device base.",
                sentiment_score=0.6,
            ),
            NewsItem(
                title="Apple faces fresh scrutiny over app store practices",
                source="Example Wire",
                published_at="2026-06-19T12:30:00Z",
                summary="Regulatory pressure remains a headline risk for services.",
                sentiment_score=-0.3,
            ),
        ]
    )
    context.data_quality = DataQualitySummary(
        news_data_status="partial",
        provider_names=["news_service", "rss"],
        warnings=["News coverage is partial because one provider timed out."],
        score=0.72,
    )
    provider = FakeLLMProvider()

    result = asyncio.run(NewsSentimentAgent(llm_provider=provider).run(context))

    assert result.status == "completed"
    assert result.provider == "fake"
    assert result.output == context.news_sentiment_output
    assert isinstance(context.news_sentiment_output, NewsSentimentOutput)
    assert context.news_sentiment_output.view == "slightly_bullish"
    assert context.news_sentiment_output.important_news[0].sentiment == "positive"
    assert context.agent_results == [result]
    assert context.total_cost_usd == 0.003
    assert provider.calls[0]["output_schema"] is NewsSentimentOutput
    assert provider.calls[0]["agent_name"] == "news_sentiment_agent"
    assert "Analyze the following news data for AAPL." in provider.calls[0]["messages"][1]["content"]
    assert "- Company name: Apple Inc." in provider.calls[0]["messages"][1]["content"]
    assert "- News data status: partial" in provider.calls[0]["messages"][1]["content"]
    assert '"news_count": 2' in provider.calls[0]["messages"][1]["content"]
    assert "Focus on near-term product and regulatory news." in provider.calls[0]["messages"][1]["content"]


def test_news_sentiment_agent_returns_partial_output_when_news_is_missing() -> None:
    context = make_context(news=[])

    result = asyncio.run(NewsSentimentAgent().run(context))

    assert result.status == "partial"
    assert result.provider == "deterministic"
    assert result.model == "deterministic"
    assert isinstance(context.news_sentiment_output, NewsSentimentOutput)
    assert context.news_sentiment_output.view == "insufficient_data"
    assert context.news_sentiment_output.important_news == []
    assert result.warnings == [
        "No usable news data was provided by the configured news providers."
    ]


def test_news_sentiment_agent_returns_partial_output_when_llm_fails() -> None:
    context = make_context(
        news=[
            NewsItem(
                title="Apple expands AI features across devices",
                source="Example News",
                published_at="2026-06-20T09:00:00Z",
                summary="Apple introduced a wider AI rollout tied to its device base.",
            )
        ]
    )

    result = asyncio.run(
        NewsSentimentAgent(llm_provider=FailingLLMProvider()).run(context)
    )

    assert result.status == "partial"
    assert result.provider == "deterministic"
    assert context.news_sentiment_output is not None
    assert context.news_sentiment_output.view == "insufficient_data"
    assert any("LLM request failed" in warning for warning in result.warnings)


def test_news_sentiment_agent_stops_when_quota_is_exceeded() -> None:
    context = make_context(
        news=[
            NewsItem(
                title="Apple expands AI features across devices",
                source="Example News",
                published_at="2026-06-20T09:00:00Z",
                summary="Apple introduced a wider AI rollout tied to its device base.",
            )
        ]
    )

    class FatalLLMProvider:
        provider_name = "fake"

        async def generate_json(self, **_kwargs: Any) -> LLMResult:
            raise LLMProviderError(
                "OpenAI API returned HTTP 429: quota exceeded",
                status_code=429,
            )

    result = asyncio.run(
        NewsSentimentAgent(llm_provider=FatalLLMProvider()).run(context)
    )

    assert result.status == "failed"
    assert result.fatal_error is True
    assert "quota exceeded" in (result.error_message or "")
    assert context.latest_agent_result("news_sentiment_agent") == result
