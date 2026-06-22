from __future__ import annotations

import asyncio

import pytest

from backend.app.agents.report_writer_agent import ReportWriterAgent
from backend.app.llm import LLMProviderError, LLMResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    CompanyProfile,
    DataQualitySummary,
    MarketDataBundle,
    PriceBar,
    RiskReviewAgentOutput,
    ThesisAgentOutput,
)


class FailingLLMProvider:
    provider_name = "fake"

    async def generate_json(self, **_kwargs: object) -> LLMResult:
        raise LLMProviderError(
            "OpenAI API returned HTTP 400: invalid response format",
            retryable=True,
        )


def make_context() -> AnalysisContext:
    context = AnalysisContext(
        run_id="run_report_writer",
        request=AnalysisRequest(
            symbol="AAPL",
            horizon="1m",
            llm_model="gpt-4.1-mini",
        ),
        market_data=MarketDataBundle(
            symbol="AAPL",
            market="US",
            company_profile=CompanyProfile(name="Apple Inc."),
        ),
        data_quality=DataQualitySummary(
            price_data_status="available",
            news_data_status="partial",
            fundamentals_status="available",
            provider_names=["test"],
            score=0.7,
        ),
    )
    context.thesis_output = ThesisAgentOutput(
        overall_view="neutral",
        confidence=0.4,
        horizon="1m",
        thesis="Balanced thesis.",
        base_case="Balanced base case.",
        bull_case_summary="Conditional upside case.",
        bear_case_summary="Conditional downside case.",
        what_to_watch=["Trend", "News"],
    )
    context.risk_review_output = RiskReviewAgentOutput(
        risk_level="moderate",
        risk_score=50,
        main_risks=["Execution risk"],
        invalidation_conditions=["Loss of support"],
        confidence_adjustment=-0.1,
    )
    return context


def test_report_writer_agent_returns_partial_report_when_llm_fails() -> None:
    context = make_context()

    result = asyncio.run(
        ReportWriterAgent(llm_provider=FailingLLMProvider()).run(context)
    )

    assert result.status == "partial"
    assert result.provider == "local"
    assert context.final_report is not None
    assert context.final_report.investment_thesis == "Balanced thesis."
    assert any("LLM request failed" in warning for warning in result.warnings)


def test_report_writer_agent_stops_when_quota_is_exceeded() -> None:
    context = make_context()

    class FatalLLMProvider:
        provider_name = "fake"

        async def generate_json(self, **_kwargs: object) -> LLMResult:
            raise LLMProviderError(
                "OpenAI API returned HTTP 429: quota exceeded",
                status_code=429,
            )

    result = asyncio.run(ReportWriterAgent(llm_provider=FatalLLMProvider()).run(context))

    assert result.status == "failed"
    assert result.fatal_error is True
    assert "quota exceeded" in (result.error_message or "")
    assert context.agent_results[-1] == result


def test_report_writer_prompt_truncates_large_market_payload() -> None:
    context = make_context()
    context.market_data.price_history = [
        PriceBar(timestamp=f"2026-04-{day:02d}T00:00:00Z", close=170 + day)
        for day in range(1, 26)
    ]

    class CapturingLLMProvider:
        provider_name = "fake"

        def __init__(self) -> None:
            self.calls: list[object] = []

        async def generate_json(self, **kwargs: object) -> LLMResult:
            self.calls.append(kwargs)
            raise LLMProviderError(
                "OpenAI API returned HTTP 400: invalid response format",
                retryable=True,
            )

    provider = CapturingLLMProvider()
    asyncio.run(ReportWriterAgent(llm_provider=provider).run(context))

    prompt = provider.calls[0]["messages"][1]["content"]
    assert provider.calls[0]["max_output_tokens"] == 5000
    assert '"price_history_count": 25' in prompt
    assert "2026-04-01T00:00:00Z" not in prompt
    assert "2026-04-25T00:00:00Z" in prompt
