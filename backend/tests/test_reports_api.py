from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.db.models import AgentOutput, AnalysisRun, CostTrace, Report
from backend.app.main import create_app
from backend.app.orchestrator.schemas import (
    AgentSummaries,
    FinalReport,
    FinalReportCostBreakdown,
    FinalReportCostItem,
    FinalReportDataQualitySection,
    FinalReportRiskSection,
    FinalReportSourceItem,
)
from backend.app.services.report_service import ReportService


def build_test_service() -> ReportService:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session_factory = lambda: Session(engine)

    created_at = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    report = build_final_report(created_at)

    with session_factory() as session:
        session.add(
            AnalysisRun(
                id="run_123",
                symbol="AAPL",
                market="US",
                horizon="3m",
                depth="standard",
                language="en",
                status="completed",
                started_at=created_at,
                finished_at=created_at,
                total_cost_usd=0.028,
                data_quality_score=0.64,
            )
        )
        session.add(
            AgentOutput(
                id="agent_output_1",
                analysis_run_id="run_123",
                agent_name="data_collector",
                status="completed",
                output_json={"market_data": {"symbol": "AAPL"}},
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                started_at=created_at,
                finished_at=created_at,
            )
        )
        session.add(
            AgentOutput(
                id="agent_output_2",
                analysis_run_id="run_123",
                agent_name="thesis_agent",
                status="completed",
                output_json={"overall_view": "moderately_bullish"},
                input_tokens=120,
                output_tokens=80,
                cost_usd=0.018,
                started_at=created_at,
                finished_at=created_at,
            )
        )
        session.add(
            CostTrace(
                id="cost_trace_1",
                analysis_run_id="run_123",
                agent_name="data_collector",
                provider="local",
                model="deterministic",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                created_at=created_at,
            )
        )
        session.add(
            CostTrace(
                id="cost_trace_2",
                analysis_run_id="run_123",
                agent_name="thesis_agent",
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=120,
                output_tokens=80,
                cost_usd=0.028,
                created_at=created_at,
            )
        )
        session.add(
            Report(
                id="report_123",
                analysis_run_id="run_123",
                symbol="AAPL",
                market="US",
                horizon="3m",
                overall_view="moderately_bullish",
                confidence=0.64,
                risk_level="medium_high",
                report_json=report.model_dump(mode="json"),
                created_at=created_at,
            )
        )
        session.commit()

    return ReportService(session_factory=session_factory)


def build_final_report(created_at: datetime) -> FinalReport:
    return FinalReport(
        title="AAPL Equity Research Report",
        symbol="AAPL",
        company_name="Apple Inc.",
        market="US",
        created_at=created_at,
        overall_view="neutral",
        confidence=0.64,
        horizon="3m",
        executive_summary="Apple remains resilient, but near-term execution risk matters.",
        investment_thesis="The business remains strong, with earnings risk as the main near-term variable.",
        base_case="Base case assumes stable services growth and manageable hardware softness.",
        bull_case_summary="New product momentum and margins improve faster than expected.",
        bear_case_summary="Demand weakness and margin pressure weigh on the next few quarters.",
        what_to_watch=["Next earnings release", "iPhone demand indicators"],
        agent_summaries=AgentSummaries(
            technical="Trend is mixed.",
            news_sentiment="Sentiment is balanced.",
            bull_case="Ecosystem strength supports upside.",
            bear_case="Valuation leaves limited room for disappointment.",
            risk_review="Main risk is earnings execution.",
        ),
        risk_section=FinalReportRiskSection(
            risk_level="high",
            risk_score=68,
            main_risks=["Earnings miss", "Margin compression"],
            invalidation_conditions=["Revenue growth re-accelerates"],
            confidence_adjustment=-0.12,
        ),
        data_quality_section=FinalReportDataQualitySection(
            data_quality_score=0.64,
            price_data_status="available",
            news_data_status="partial",
            company_profile_status="available",
            missing_data=["full fundamentals"],
            providers=["yahoo", "gdelt"],
            warnings=["News coverage is partial."],
        ),
        source_section=[
            FinalReportSourceItem(
                name="Price History",
                type="price",
                provider="yahoo",
                url="https://example.com/prices",
                used_for="Technical context",
            ),
            FinalReportSourceItem(
                name="Recent Headlines",
                type="news",
                provider="gdelt",
                url="https://example.com/news",
                used_for="Sentiment context",
            ),
        ],
        cost_breakdown=FinalReportCostBreakdown(
            total_estimated_cost_usd=0.028,
            items=[
                FinalReportCostItem(
                    agent_name="data_collector",
                    provider="local",
                    model="deterministic",
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=0.0,
                ),
                FinalReportCostItem(
                    agent_name="thesis_agent",
                    provider="openai",
                    model="gpt-4.1-mini",
                    input_tokens=120,
                    output_tokens=80,
                    estimated_cost_usd=0.028,
                ),
            ],
        ),
        warnings=["Generated with partial news coverage."],
        report_markdown="# Apple\n\nNeutral view with elevated earnings risk.",
    )


@pytest.mark.anyio
async def test_report_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.reports.report_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        list_response = await client.get("/api/reports")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data == [
            {
                "id": "report_123",
                "symbol": "AAPL",
                "horizon": "3m",
                "overall_view": "moderately_bullish",
                "confidence": 0.64,
                "risk_level": "medium_high",
                "created_at": "2026-06-20T12:00:00Z",
            }
        ]

        detail_response = await client.get("/api/reports/report_123")
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["id"] == "report_123"
        assert detail_data["run_id"] == "run_123"
        assert detail_data["status"] == "completed"
        assert detail_data["final_report"]["symbol"] == "AAPL"
        assert len(detail_data["agent_outputs"]) == 2
        assert detail_data["cost_breakdown"]["total_cost_usd"] == 0.028
        assert len(detail_data["cost_breakdown"]["items"]) == 2
        assert detail_data["data_quality"]["data_quality_score"] == 0.64
        assert len(detail_data["sources"]) == 2
        assert detail_data["warnings"] == ["Generated with partial news coverage."]


@pytest.mark.anyio
async def test_delete_report_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.reports.report_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        delete_response = await client.delete("/api/reports/report_123")
        assert delete_response.status_code == 204

        detail_response = await client.get("/api/reports/report_123")
        list_response = await client.get("/api/reports")

    assert detail_response.status_code == 404
    assert list_response.json() == []


@pytest.mark.anyio
async def test_report_endpoints_return_404_for_missing_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.reports.report_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        detail_response = await client.get("/api/reports/does-not-exist")
        delete_response = await client.delete("/api/reports/does-not-exist")

    assert detail_response.status_code == 404
    assert delete_response.status_code == 404
