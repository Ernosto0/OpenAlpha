from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from backend.app.agents.thesis_agent import ThesisAgent
from backend.app.llm import LLMMessage, LLMProviderError, LLMResult
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
    ThesisAgentOutput,
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
                    "overall_view": "slightly_bullish",
                    "confidence": 0.57,
                    "horizon": "1m",
                    "thesis": (
                        "The final research view is modestly constructive, but it "
                        "still depends on mixed evidence resolving in a stronger "
                        "direction. Technicals are somewhat supportive while risk "
                        "and news inputs keep confidence contained."
                    ),
                    "base_case": (
                        "The most balanced scenario is a cautious, range-bound to "
                        "slightly constructive outcome if current evidence holds."
                    ),
                    "bull_case_summary": (
                        "Upside improves if price action confirms strength and "
                        "company-specific news remains supportive."
                    ),
                    "bear_case_summary": (
                        "Downside remains credible if the mixed setup weakens and "
                        "recent uncertainty turns more negative."
                    ),
                    "what_to_watch": [
                        "Whether price action confirms the current setup.",
                        "Whether company-specific news flow improves or deteriorates.",
                        "Whether risk factors highlighted upstream begin to resolve.",
                    ],
                }
            ),
            input_tokens=190,
            output_tokens=85,
            estimated_cost_usd=0.0042,
            warnings=["No pricing configured for fake/fake-model."],
        )


class FailingLLMProvider:
    provider_name = "fake"

    async def generate_json(self, **_kwargs: Any) -> LLMResult:
        raise LLMProviderError(
            "OpenAI API returned HTTP 400: invalid response format",
            retryable=True,
        )


def make_context(
    *,
    include_upstream_outputs: bool = True,
) -> AnalysisContext:
    context = AnalysisContext(
        run_id="run_thesis",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="Focus on whether the balanced case is improving or weakening.",
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
        data_quality=DataQualitySummary(
            price_data_status="available",
            news_data_status="partial",
            fundamentals_status="partial",
            provider_names=["default_price_provider", "news_service"],
            warnings=["News coverage is partial because one provider timed out."],
            score=0.71,
        ),
    )

    if include_upstream_outputs:
        context.technical_output = TechnicalAgentOutput(
            view="slightly_bullish",
            confidence=0.62,
            summary="Momentum is constructive but not decisive.",
            key_signals=["Recent price action has improved from support."],
        )
        context.news_sentiment_output = NewsSentimentOutput(
            view="neutral",
            confidence=0.43,
            sentiment_summary="Recent coverage is useful but still mixed.",
            important_news=[],
        )
        context.bull_case_output = BullCaseAgentOutput(
            bull_case="The upside case depends on continued confirmation.",
            main_arguments=["Some technical support remains intact."],
            upside_conditions=["Follow-through strength would support the upside case."],
        )
        context.bear_case_output = BearCaseAgentOutput(
            bear_case="The downside case remains possible if the setup weakens.",
            main_risks=["Mixed evidence still leaves room for downside."],
            downside_conditions=["Renewed weakness would strengthen the downside case."],
        )
        context.risk_review_output = RiskReviewAgentOutput(
            risk_level="high",
            risk_score=63,
            main_risks=["Evidence is mixed and confidence should stay moderated."],
            invalidation_conditions=["Loss of setup quality would weaken the current view."],
            confidence_adjustment=-0.15,
        )

    return context


def test_thesis_agent_calls_llm_and_saves_output_to_context() -> None:
    context = make_context(include_upstream_outputs=True)
    provider = FakeLLMProvider()

    result = asyncio.run(ThesisAgent(llm_provider=provider).run(context))

    assert result.status == "completed"
    assert result.provider == "fake"
    assert result.output == context.thesis_output
    assert isinstance(context.thesis_output, ThesisAgentOutput)
    assert context.thesis_output.overall_view == "slightly_bullish"
    assert context.thesis_output.horizon == "1m"
    assert context.agent_results == [result]
    assert context.total_cost_usd == 0.0042
    assert provider.calls[0]["output_schema"] is ThesisAgentOutput
    assert provider.calls[0]["agent_name"] == "thesis_agent"
    assert "Create a final AI research thesis for AAPL" in provider.calls[0]["messages"][1]["content"]
    assert "* Company name: Apple Inc." in provider.calls[0]["messages"][1]["content"]
    assert '"risk_review_output": {' in provider.calls[0]["messages"][1]["content"]
    assert '"technical_output": {' in provider.calls[0]["messages"][1]["content"]
    assert "Focus on whether the balanced case is improving or weakening." in provider.calls[0]["messages"][1]["content"]


def test_thesis_agent_returns_partial_output_when_inputs_are_missing() -> None:
    context = AnalysisContext(
        run_id="run_thesis_partial",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
        ),
    )

    result = asyncio.run(ThesisAgent().run(context))

    assert result.status == "partial"
    assert result.provider == "local"
    assert result.model == "deterministic"
    assert isinstance(context.thesis_output, ThesisAgentOutput)
    assert context.thesis_output.overall_view == "insufficient_data"
    assert context.thesis_output.base_case == (
        "No reliable base case can be formed from the provided data."
    )
    assert result.warnings == ["Thesis was generated without usable upstream inputs."]


def test_thesis_agent_returns_partial_output_when_llm_fails() -> None:
    context = make_context(include_upstream_outputs=True)

    result = asyncio.run(ThesisAgent(llm_provider=FailingLLMProvider()).run(context))

    assert result.status == "partial"
    assert result.provider == "local"
    assert context.thesis_output is not None
    assert context.thesis_output.overall_view == "insufficient_data"
    assert any("LLM request failed" in warning for warning in result.warnings)


def test_thesis_agent_stops_when_quota_is_exceeded() -> None:
    context = make_context(include_upstream_outputs=True)

    class FatalLLMProvider:
        provider_name = "fake"

        async def generate_json(self, **_kwargs: Any) -> LLMResult:
            raise LLMProviderError(
                "OpenAI API returned HTTP 429: quota exceeded",
                status_code=429,
            )

    result = asyncio.run(ThesisAgent(llm_provider=FatalLLMProvider()).run(context))

    assert result.status == "failed"
    assert result.fatal_error is True
    assert "quota exceeded" in (result.error_message or "")
    assert context.latest_agent_result("thesis_agent") == result
