from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from backend.app.agents.technical_agent import TechnicalAgent
from backend.app.llm import LLMMessage, LLMResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    CompanyProfile,
    DataQualitySummary,
    IndicatorBundle,
    MarketDataBundle,
    PriceBar,
    TechnicalLevel,
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
                    "view": "slightly_bullish",
                    "confidence": 0.68,
                    "summary": "Trend signals are constructive but not decisive.",
                    "key_signals": ["RSI is neutral", "Price is above SMA 20"],
                    "support_levels": [
                        {
                            "price": 100.0,
                            "reason": "Recent pullback found support near this level.",
                            "strength": "moderate",
                        },
                        {
                            "price": 95.5,
                            "reason": "Lower swing low from the prior range.",
                            "strength": "weak",
                        },
                    ],
                    "resistance_levels": [
                        {
                            "price": 110.0,
                            "reason": "Near-term overhead supply from the last rally.",
                            "strength": "moderate",
                        }
                    ],
                    "warnings": ["Support and resistance are estimates."],
                }
            ),
            input_tokens=120,
            output_tokens=45,
            estimated_cost_usd=0.002,
            warnings=["No pricing configured for fake/fake-model."],
        )


def make_context(*, indicators: IndicatorBundle | None = None) -> AnalysisContext:
    return AnalysisContext(
        run_id="run_technical",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="Focus on trend quality.",
        ),
        indicators=indicators,
    )


def test_technical_agent_calls_llm_and_saves_output_to_context() -> None:
    indicators = IndicatorBundle(
        symbol="AAPL",
        horizon="1m",
        moving_averages={"20": 101.0, "50": 99.0},
        support_levels=[100.0, 95.5],
        resistance_levels=[110.0],
        warnings=["Support/resistance levels are simple estimated levels."],
    )
    context = make_context(indicators=indicators)
    context.data_quality = DataQualitySummary(score=0.81)
    context.market_data = MarketDataBundle(
        symbol="AAPL",
        market="US",
        company_profile=CompanyProfile(name="Apple Inc."),
        price_history=[
            PriceBar(timestamp="2026-06-16T00:00:00Z", close=101.5),
            PriceBar(timestamp="2026-06-17T00:00:00Z", close=102.0),
            PriceBar(timestamp="2026-06-18T00:00:00Z", close=103.25),
            PriceBar(timestamp="2026-06-19T00:00:00Z", close=102.8),
            PriceBar(timestamp="2026-06-20T00:00:00Z", close=104.1),
        ],
        warnings=["Price history is delayed by one session."],
    )
    provider = FakeLLMProvider()

    result = asyncio.run(TechnicalAgent(llm_provider=provider).run(context))

    assert result.status == "completed"
    assert result.provider == "fake"
    assert result.output == context.technical_output
    assert isinstance(context.technical_output, TechnicalAgentOutput)
    assert context.technical_output.view == "slightly_bullish"
    assert context.technical_output.support_levels == [
        TechnicalLevel(
            price=100.0,
            reason="Recent pullback found support near this level.",
            strength="moderate",
        ),
        TechnicalLevel(
            price=95.5,
            reason="Lower swing low from the prior range.",
            strength="weak",
        ),
    ]
    assert context.agent_results == [result]
    assert context.total_cost_usd == 0.002
    assert provider.calls[0]["output_schema"] is TechnicalAgentOutput
    assert provider.calls[0]["agent_name"] == "technical_agent"
    assert '"support_levels": [' in provider.calls[0]["messages"][1]["content"]
    assert "Focus on trend quality." in provider.calls[0]["messages"][1]["content"]
    assert '"data_quality_score": 0.81' in provider.calls[0]["messages"][1]["content"]
    assert "Analyze the following technical data for AAPL." in provider.calls[0]["messages"][1]["content"]
    assert "- Company name: Apple Inc." in provider.calls[0]["messages"][1]["content"]
    assert "- Latest close price: 104.10" in provider.calls[0]["messages"][1]["content"]
    assert "- Support levels: 100.00, 95.50" in provider.calls[0]["messages"][1]["content"]
    assert "{symbol}" not in provider.calls[0]["messages"][1]["content"]
    assert "{recent_price_summary}" not in provider.calls[0]["messages"][1]["content"]


def test_technical_agent_returns_partial_output_when_indicators_are_missing() -> None:
    context = make_context(indicators=None)

    result = asyncio.run(TechnicalAgent().run(context))

    assert result.status == "partial"
    assert result.provider == "local"
    assert result.model == "deterministic"
    assert isinstance(context.technical_output, TechnicalAgentOutput)
    assert context.technical_output.view == "insufficient_data"
    assert context.technical_output.confidence == 0
    assert result.warnings == ["Technical indicators are missing from context."]
