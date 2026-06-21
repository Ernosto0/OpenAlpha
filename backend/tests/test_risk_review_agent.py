from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from backend.app.agents.risk_review_agent import RiskReviewAgent
from backend.app.llm import LLMMessage, LLMResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    BearCaseAgentOutput,
    BullCaseAgentOutput,
    CompanyProfile,
    DataQualitySummary,
    MarketDataBundle,
    NewsSentimentOutput,
    PriceBar,
    RiskReviewAgentOutput,
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
                    "risk_level": "high",
                    "risk_score": 68,
                    "main_risks": [
                        "Technical and news evidence are not fully aligned.",
                        "Data quality is usable but not strong enough to remove uncertainty.",
                        "The bear case remains credible if weakness persists.",
                    ],
                    "invalidation_conditions": [
                        "A stronger trend confirmation would reduce the current risk profile.",
                        "More constructive company-specific news would weaken the bearish pressure.",
                        "Cleaner data coverage would reduce uncertainty around the setup.",
                    ],
                    "confidence_adjustment": -0.15,
                }
            ),
            input_tokens=155,
            output_tokens=60,
            estimated_cost_usd=0.0035,
            warnings=["No pricing configured for fake/fake-model."],
        )


def make_context(
    *,
    technical_output: TechnicalAgentOutput | None = None,
    news_output: NewsSentimentOutput | None = None,
    bull_output: BullCaseAgentOutput | None = None,
    bear_output: BearCaseAgentOutput | None = None,
    data_quality: DataQualitySummary | None = None,
) -> AnalysisContext:
    return AnalysisContext(
        run_id="run_risk_review",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="Focus on what could invalidate the current setup.",
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
        technical_output=technical_output,
        news_sentiment_output=news_output,
        bull_case_output=bull_output,
        bear_case_output=bear_output,
        data_quality=data_quality,
    )


def test_risk_review_agent_calls_llm_and_saves_output_to_context() -> None:
    context = make_context(
        technical_output=TechnicalAgentOutput(
            view="slightly_bearish",
            confidence=0.58,
            summary="Momentum is mixed and price is near a sensitive level.",
            key_signals=["Recent bounce lacked strong confirmation."],
        ),
        news_output=NewsSentimentOutput(
            view="neutral",
            confidence=0.46,
            sentiment_summary="Recent coverage is mixed and not decisive.",
            important_news=[],
        ),
        bull_output=BullCaseAgentOutput(
            bull_case="The upside case depends on trend stabilization.",
            main_arguments=["Support has not fully failed."],
            upside_conditions=["Constructive follow-through would strengthen the upside case."],
        ),
        bear_output=BearCaseAgentOutput(
            bear_case="The downside case remains credible if weakness continues.",
            main_risks=["Momentum remains fragile."],
            downside_conditions=["Further technical deterioration would reinforce downside risk."],
        ),
        data_quality=DataQualitySummary(
            price_data_status="available",
            news_data_status="partial",
            fundamentals_status="partial",
            provider_names=["default_price_provider", "news_service"],
            warnings=["News coverage is partial because one provider timed out."],
            score=0.69,
        ),
    )
    provider = FakeLLMProvider()

    result = asyncio.run(RiskReviewAgent(llm_provider=provider).run(context))

    assert result.status == "completed"
    assert result.provider == "fake"
    assert result.output == context.risk_review_output
    assert isinstance(context.risk_review_output, RiskReviewAgentOutput)
    assert context.risk_review_output.risk_level == "high"
    assert context.risk_review_output.confidence_adjustment == -0.15
    assert context.agent_results == [result]
    assert context.total_cost_usd == 0.0035
    assert provider.calls[0]["output_schema"] is RiskReviewAgentOutput
    assert provider.calls[0]["agent_name"] == "risk_review_agent"
    assert "Review the risk profile for AAPL" in provider.calls[0]["messages"][1]["content"]
    assert "- Company name: Apple Inc." in provider.calls[0]["messages"][1]["content"]
    assert '"bull_case_output": {' in provider.calls[0]["messages"][1]["content"]
    assert '"bear_case_output": {' in provider.calls[0]["messages"][1]["content"]
    assert "Focus on what could invalidate the current setup." in provider.calls[0]["messages"][1]["content"]


def test_risk_review_agent_returns_partial_output_when_inputs_are_missing() -> None:
    context = make_context(
        technical_output=None,
        news_output=None,
        bull_output=None,
        bear_output=None,
        data_quality=None,
    )

    result = asyncio.run(RiskReviewAgent().run(context))

    assert result.status == "partial"
    assert result.provider == "local"
    assert result.model == "deterministic"
    assert isinstance(context.risk_review_output, RiskReviewAgentOutput)
    assert context.risk_review_output.risk_level == "insufficient_data"
    assert context.risk_review_output.risk_score == 85
    assert result.warnings == [
        "Risk review was generated without usable upstream inputs."
    ]
