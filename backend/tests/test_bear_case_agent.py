from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from backend.app.agents.bear_case_agent import BearCaseAgent
from backend.app.llm import LLMMessage, LLMResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    BearCaseAgentOutput,
    CompanyProfile,
    DataQualitySummary,
    MarketDataBundle,
    NewsSentimentOutput,
    PriceBar,
    TechnicalAgentOutput,
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
                    "bear_case": (
                        "The downside case rests on mixed-to-weak technical structure "
                        "and negative headline pressure that could cap upside. If the "
                        "reported weakness persists without offsetting positive "
                        "confirmation, the setup could deteriorate further."
                    ),
                    "main_risks": [
                        "Technical momentum is soft relative to the recent range.",
                        "Recent news flow includes company-specific pressure.",
                        "The evidence set is useful but still limited in scope.",
                    ],
                    "downside_conditions": [
                        "Further technical deterioration would strengthen the downside setup.",
                        "Additional negative company-specific news would add pressure.",
                        "Failure of sentiment to improve would keep the bear case credible.",
                    ],
                }
            ),
            input_tokens=135,
            output_tokens=50,
            estimated_cost_usd=0.0025,
            warnings=["No pricing configured for fake/fake-model."],
        )


def make_context(
    *,
    technical_output: TechnicalAgentOutput | None = None,
    news_output: NewsSentimentOutput | None = None,
) -> AnalysisContext:
    return AnalysisContext(
        run_id="run_bear_case",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="Focus on downside risk if recent weakness persists.",
        ),
        market_data=MarketDataBundle(
            symbol="AAPL",
            market="US",
            company_profile=CompanyProfile(name="Apple Inc."),
            price_history=[
                PriceBar(timestamp="2026-06-18T00:00:00Z", close=201.2),
                PriceBar(timestamp="2026-06-19T00:00:00Z", close=199.9),
                PriceBar(timestamp="2026-06-20T00:00:00Z", close=198.4),
            ],
            warnings=["Price history is delayed by one session."],
        ),
        data_quality=DataQualitySummary(score=0.78),
        technical_output=technical_output,
        news_sentiment_output=news_output,
    )


def test_bear_case_agent_calls_llm_and_saves_output_to_context() -> None:
    context = make_context(
        technical_output=TechnicalAgentOutput(
            view="slightly_bearish",
            confidence=0.61,
            summary="Momentum is soft and the trend has weakened near resistance.",
            key_signals=[
                "Price failed to sustain a recent rebound.",
                "Momentum indicators are mixed to negative.",
            ],
        ),
        news_output=NewsSentimentOutput(
            view="slightly_bearish",
            confidence=0.58,
            sentiment_summary="Recent coverage carries some negative company-specific pressure.",
            important_news=[],
        ),
    )
    provider = FakeLLMProvider()

    result = asyncio.run(BearCaseAgent(llm_provider=provider).run(context))

    assert result.status == "completed"
    assert result.provider == "fake"
    assert result.output == context.bear_case_output
    assert isinstance(context.bear_case_output, BearCaseAgentOutput)
    assert context.bear_case_output.main_risks[0] == (
        "Technical momentum is soft relative to the recent range."
    )
    assert context.agent_results == [result]
    assert context.total_cost_usd == 0.0025
    assert provider.calls[0]["output_schema"] is BearCaseAgentOutput
    assert provider.calls[0]["agent_name"] == "bear_case_agent"
    assert "Build a bear case for AAPL" in provider.calls[0]["messages"][1]["content"]
    assert "- Company name: Apple Inc." in provider.calls[0]["messages"][1]["content"]
    assert '"technical_output": {' in provider.calls[0]["messages"][1]["content"]
    assert '"news_sentiment_output": {' in provider.calls[0]["messages"][1]["content"]
    assert "Focus on downside risk if recent weakness persists." in provider.calls[0]["messages"][1]["content"]


def test_bear_case_agent_returns_partial_output_when_inputs_are_missing() -> None:
    context = make_context(technical_output=None, news_output=None)

    result = asyncio.run(BearCaseAgent().run(context))

    assert result.status == "partial"
    assert result.provider == "local"
    assert result.model == "deterministic"
    assert isinstance(context.bear_case_output, BearCaseAgentOutput)
    assert "cannot be formed" in context.bear_case_output.bear_case
    assert result.warnings == [
        "Bear case was generated without upstream inputs because technical and news outputs are missing."
    ]
