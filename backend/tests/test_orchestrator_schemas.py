from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.orchestrator.schemas import (
    DISCLAIMER,
    AgentResult,
    AnalysisContext,
    AnalysisRequest,
    BearCaseAgentOutput,
    DataQualitySummary,
    FinalReport,
    MarketDataBundle,
    RiskReviewAgentOutput,
    ThesisAgentOutput,
)


def test_analysis_request_normalizes_symbol_and_defaults() -> None:
    request = AnalysisRequest(
        symbol=" aapl ",
        horizon="1m",
        llm_model="gpt-4.1-mini",
    )

    assert request.symbol == "AAPL"
    assert request.market == "US"
    assert request.depth == "standard"
    assert request.language == "en"
    assert request.llm_provider == "openai"


def test_analysis_request_rejects_unknown_ai_horizon() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(symbol="AAPL", horizon="2y", llm_model="gpt-4.1-mini")


def test_agent_result_captures_cost_and_rejects_negative_tokens() -> None:
    result = AgentResult(
        agent_name="technical_agent",
        status="completed",
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=100,
        output_tokens=40,
        estimated_cost_usd=0.01,
    )

    assert result.agent_name == "technical_agent"
    assert result.estimated_cost_usd == 0.01

    with pytest.raises(ValidationError):
        AgentResult(
            agent_name="technical_agent",
            status="completed",
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=-1,
        )


def test_analysis_context_totals_cost_traces() -> None:
    context = AnalysisContext(
        run_id="run_1",
        request=AnalysisRequest(
            symbol="MSFT",
            horizon="3m",
            llm_model="gpt-4.1-mini",
        ),
        cost_traces=[
            {
                "agent_name": "technical_agent",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "estimated_cost_usd": 0.02,
            },
            {
                "agent_name": "news_sentiment_agent",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "estimated_cost_usd": 0.03,
            },
        ],
    )

    assert context.total_cost_usd == pytest.approx(0.05)


def test_analysis_context_supports_bear_case_output() -> None:
    context = AnalysisContext(
        run_id="run_bear_1",
        request=AnalysisRequest(
            symbol="MSFT",
            horizon="3m",
            llm_model="gpt-4.1-mini",
        ),
        bear_case_output=BearCaseAgentOutput(
            bear_case="The downside case is conditional and evidence-based.",
            main_risks=["Momentum may continue to weaken."],
            downside_conditions=["Further negative news would strengthen the downside case."],
        ),
    )

    assert context.bear_case_output is not None
    assert context.bear_case_output.main_risks == [
        "Momentum may continue to weaken."
    ]


def test_analysis_context_supports_risk_review_output() -> None:
    context = AnalysisContext(
        run_id="run_risk_1",
        request=AnalysisRequest(
            symbol="MSFT",
            horizon="3m",
            llm_model="gpt-4.1-mini",
        ),
        risk_review_output=RiskReviewAgentOutput(
            risk_level="high",
            risk_score=67,
            main_risks=["The setup depends on mixed evidence."],
            invalidation_conditions=["Loss of support would weaken the current research view."],
            confidence_adjustment=-0.15,
        ),
    )

    assert context.risk_review_output is not None
    assert context.risk_review_output.risk_score == 67


def test_analysis_context_supports_thesis_output() -> None:
    context = AnalysisContext(
        run_id="run_thesis_1",
        request=AnalysisRequest(
            symbol="MSFT",
            horizon="3m",
            llm_model="gpt-4.1-mini",
        ),
        thesis_output=ThesisAgentOutput(
            overall_view="neutral",
            confidence=0.52,
            horizon="3m",
            thesis="The final research view is balanced and evidence is mixed.",
            base_case="The most likely path is modest movement with ongoing uncertainty.",
            bull_case_summary="Upside would depend on stronger confirmation from price action and sentiment.",
            bear_case_summary="Downside remains possible if weakness persists or new risks appear.",
            what_to_watch=["Trend confirmation", "Company-specific news flow"],
        ),
    )

    assert context.thesis_output is not None
    assert context.thesis_output.overall_view == "neutral"


def test_final_report_supports_v1_ai_views_and_disclaimer() -> None:
    request = AnalysisRequest(
        symbol="tsla",
        horizon="1w",
        depth="quick",
        llm_model="gpt-4.1-mini",
    )
    report = FinalReport(
        report_id="report_1",
        run_id="run_1",
        request=request,
        symbol="tsla",
        market=request.market,
        horizon=request.horizon,
        depth=request.depth,
        language=request.language,
        ai_view="insufficient_data",
        confidence=0,
        risk_level="insufficient_data",
        investment_thesis="Insufficient reliable data to form a thesis.",
        data_quality=DataQualitySummary(score=0.2),
        provider=request.llm_provider,
        model=request.llm_model,
        market_data=MarketDataBundle(symbol="tsla", market="US"),
        generated_at=datetime.now(timezone.utc),
    )

    assert report.symbol == "TSLA"
    assert report.ai_view == "insufficient_data"
    assert report.disclaimer == DISCLAIMER

    invalid_report = report.model_dump()
    invalid_report["ai_view"] = "buy_now"

    with pytest.raises(ValidationError):
        FinalReport.model_validate(invalid_report)
