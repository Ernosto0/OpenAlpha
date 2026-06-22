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
    assert context.latest_agent_result("report_writer_agent") == result
