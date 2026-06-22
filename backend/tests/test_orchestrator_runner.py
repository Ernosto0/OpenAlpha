from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.agents.base import AgentExecutionPayload, BaseAgent
from backend.app.db.models import AgentOutput, AnalysisRun, CostTrace, Report
from backend.app.llm import LLMProviderError
from backend.app.orchestrator.base import AnalysisEventEmitter, AnalysisRunner
from backend.app.orchestrator.schemas import (
    AgentSummaries,
    AnalysisRequest,
    BearCaseAgentOutput,
    BullCaseAgentOutput,
    DataCollectorOutput,
    DataQualitySummary,
    FinalReport,
    FinalReportCostBreakdown,
    FinalReportDataQualitySection,
    FinalReportRiskSection,
    MarketDataBundle,
    NewsSentimentOutput,
    RiskReviewAgentOutput,
    TechnicalAgentOutput,
    ThesisAgentOutput,
)


class ScriptedAgent(BaseAgent[Any]):
    def __init__(
        self,
        *,
        name: Any,
        output_schema: type[Any] | None,
        output: Any = None,
        status: str = "completed",
        delay: float = 0,
        error: Exception | None = None,
        estimated_cost_usd: float = 0.01,
    ) -> None:
        super().__init__(name=name, provider="test", model="test-model")
        self.output_schema = output_schema
        self.output = output
        self.status = status
        self.delay = delay
        self.error = error
        self.estimated_cost_usd = estimated_cost_usd

    async def execute(self, context: Any) -> AgentExecutionPayload:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return AgentExecutionPayload(
            status=self.status,
            provider="test",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=self.estimated_cost_usd,
            output=self.output,
        )


class BrokenAgent:
    name = "risk_review_agent"

    async def run(self, context: Any) -> Any:
        raise RuntimeError("orchestrator exploded")


def make_request() -> AnalysisRequest:
    return AnalysisRequest(symbol="AAPL", horizon="1m", llm_model="gpt-4.1-mini")


def make_report() -> FinalReport:
    return FinalReport(
        title="Equity Research Report: AAPL",
        symbol="AAPL",
        company_name="Apple Inc.",
        market="US",
        created_at=datetime.now(timezone.utc),
        overall_view="neutral",
        confidence=0.55,
        horizon="1m",
        executive_summary="A balanced summary.",
        investment_thesis="A balanced thesis.",
        base_case="A steady base case.",
        bull_case_summary="Upside depends on better momentum.",
        bear_case_summary="Downside grows if execution weakens.",
        what_to_watch=["Price trend", "News flow"],
        agent_summaries=AgentSummaries(
            technical="Technical signals are mixed.",
            news_sentiment="News tone is balanced.",
            bull_case="There is a reasonable upside case.",
            bear_case="There is a reasonable downside case.",
            risk_review="Risk remains manageable.",
        ),
        risk_section=FinalReportRiskSection(
            risk_level="moderate",
            risk_score=45,
            main_risks=["Execution risk"],
            invalidation_conditions=["Loss of support"],
            confidence_adjustment=-0.1,
        ),
        data_quality_section=FinalReportDataQualitySection(
            data_quality_score=0.8,
            price_data_status="available",
            news_data_status="available",
            company_profile_status="available",
            providers=["test"],
        ),
        source_section=[],
        cost_breakdown=FinalReportCostBreakdown(total_estimated_cost_usd=0.08, items=[]),
        warnings=[],
        report_markdown="# AAPL\n\nBalanced report.",
    )


def make_runner(
    emitter: AnalysisEventEmitter,
    session_factory: Any,
    *,
    technical_error: Exception | None = None,
    broken_risk: bool = False,
) -> AnalysisRunner:
    return AnalysisRunner(
        session_factory=session_factory,
        event_emitter=emitter,
        data_collector_agent=ScriptedAgent(
            name="data_collector",
            output_schema=DataCollectorOutput,
            output=DataCollectorOutput(
                market_data=MarketDataBundle(symbol="AAPL", market="US"),
                data_quality=DataQualitySummary(
                    price_data_status="available",
                    news_data_status="available",
                    fundamentals_status="available",
                    score=0.8,
                ),
            ),
            delay=0.01,
        ),
        technical_agent=ScriptedAgent(
            name="technical_agent",
            output_schema=TechnicalAgentOutput,
            output=TechnicalAgentOutput(
                view="neutral",
                confidence=0.5,
                summary="Mixed technical setup.",
            ),
            delay=0.05,
            error=technical_error,
        ),
        news_sentiment_agent=ScriptedAgent(
            name="news_sentiment_agent",
            output_schema=NewsSentimentOutput,
            output=NewsSentimentOutput(
                view="neutral",
                confidence=0.45,
                sentiment_summary="Mixed news.",
            ),
            delay=0.05,
        ),
        bull_case_agent=ScriptedAgent(
            name="bull_case_agent",
            output_schema=BullCaseAgentOutput,
            output=BullCaseAgentOutput(
                bull_case="Constructive upside scenario.",
                main_arguments=["Momentum improves"],
                upside_conditions=["Execution stays solid"],
            ),
            delay=0.05,
        ),
        bear_case_agent=ScriptedAgent(
            name="bear_case_agent",
            output_schema=BearCaseAgentOutput,
            output=BearCaseAgentOutput(
                bear_case="Credible downside scenario.",
                main_risks=["Demand softens"],
                downside_conditions=["Margins compress"],
            ),
            delay=0.05,
        ),
        risk_review_agent=BrokenAgent()
        if broken_risk
        else ScriptedAgent(
            name="risk_review_agent",
            output_schema=RiskReviewAgentOutput,
            output=RiskReviewAgentOutput(
                risk_level="moderate",
                risk_score=45,
                main_risks=["Execution risk"],
                invalidation_conditions=["Loss of support"],
                confidence_adjustment=-0.1,
            ),
        ),
        thesis_agent=ScriptedAgent(
            name="thesis_agent",
            output_schema=ThesisAgentOutput,
            output=ThesisAgentOutput(
                overall_view="neutral",
                confidence=0.55,
                horizon="1m",
                thesis="Balanced thesis.",
                base_case="Steady outcome remains most likely.",
                bull_case_summary="Upside if conditions improve.",
                bear_case_summary="Downside if conditions worsen.",
                what_to_watch=["Trend", "News"],
            ),
        ),
        report_writer_agent=ScriptedAgent(
            name="report_writer_agent",
            output_schema=FinalReport,
            output=make_report(),
        ),
    )


def make_session_factory() -> tuple[Any, Any]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine, lambda: Session(engine)


def event_index(events: list[Any], event_type: str, agent_name: str | None = None) -> int:
    for index, event in enumerate(events):
        if event.type == event_type and event.agent_name == agent_name:
            return index
    raise AssertionError(f"missing event {event_type} for {agent_name}")


def test_analysis_runner_happy_path_persists_rows_and_stage_order() -> None:
    engine, session_factory = make_session_factory()
    emitter = AnalysisEventEmitter()
    runner = make_runner(emitter, session_factory)

    context = asyncio.run(runner.run(make_request()))
    events = emitter.history(context.run_id)

    assert context.final_report is not None
    assert [event.type for event in events][0] == "analysis_started"
    assert [event.type for event in events][-1] == "analysis_completed"

    collector_finished = event_index(events, "agent_finished", "data_collector")
    technical_started = event_index(events, "agent_started", "technical_agent")
    news_started = event_index(events, "agent_started", "news_sentiment_agent")
    technical_finished = event_index(events, "agent_finished", "technical_agent")
    news_finished = event_index(events, "agent_finished", "news_sentiment_agent")
    bull_started = event_index(events, "agent_started", "bull_case_agent")
    bear_started = event_index(events, "agent_started", "bear_case_agent")

    assert collector_finished < technical_started
    assert collector_finished < news_started
    assert technical_started < technical_finished
    assert news_started < news_finished
    assert technical_started < news_finished
    assert news_started < technical_finished
    assert technical_finished < bull_started
    assert news_finished < bear_started

    with Session(engine) as session:
        runs = session.exec(select(AnalysisRun)).all()
        agent_outputs = session.exec(select(AgentOutput)).all()
        cost_traces = session.exec(select(CostTrace)).all()
        reports = session.exec(select(Report)).all()

    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].error_message is None
    assert runs[0].data_quality_score == 0.8
    assert runs[0].total_cost_usd == 0.08
    assert len(agent_outputs) == 8
    assert len(cost_traces) == 8
    assert len(reports) == 1
    assert reports[0].report_json["symbol"] == "AAPL"


def test_analysis_runner_completes_with_partial_failures_and_persists_failed_output() -> None:
    engine, session_factory = make_session_factory()
    emitter = AnalysisEventEmitter()
    runner = make_runner(
        emitter,
        session_factory,
        technical_error=RuntimeError("technical model failed"),
    )

    context = asyncio.run(runner.run(make_request()))
    failed_result = context.latest_agent_result("technical_agent")

    assert context.final_report is not None
    assert failed_result is not None
    assert failed_result.status == "failed"
    assert failed_result.error_message == "technical model failed"

    with Session(engine) as session:
        run = session.exec(select(AnalysisRun)).one()
        technical_output = session.exec(
            select(AgentOutput).where(AgentOutput.agent_name == "technical_agent")
        ).one()
        report = session.exec(select(Report)).one()

    assert run.status == "completed"
    assert technical_output.status == "failed"
    assert technical_output.error_message == "technical model failed"
    assert report.report_json["overall_view"] == "neutral"
    assert event_index(
        emitter.history(context.run_id), "agent_finished", "report_writer_agent"
    ) > event_index(
        emitter.history(context.run_id), "agent_failed", "technical_agent"
    )


def test_analysis_runner_stops_on_fatal_llm_error() -> None:
    engine, session_factory = make_session_factory()
    emitter = AnalysisEventEmitter()
    runner = make_runner(
        emitter,
        session_factory,
        technical_error=LLMProviderError(
            "OpenAI API returned HTTP 429: quota exceeded",
            status_code=429,
        ),
    )

    with pytest.raises(RuntimeError, match="quota exceeded"):
        asyncio.run(runner.run(make_request()))

    with Session(engine) as session:
        run = session.exec(select(AnalysisRun)).one()
        reports = session.exec(select(Report)).all()
        agent_outputs = session.exec(select(AgentOutput)).all()

    assert run.status == "failed"
    assert "quota exceeded" in (run.error_message or "")
    assert reports == []
    assert any(
        output.agent_name == "data_collector" and output.status == "completed"
        for output in agent_outputs
    )
    fatal_outputs = [
        output for output in agent_outputs if output.agent_name == "technical_agent"
    ]
    assert len(fatal_outputs) == 1
    assert fatal_outputs[0].status == "failed"
    assert "quota exceeded" in (fatal_outputs[0].error_message or "")
    assert emitter.history()[-1].type == "analysis_failed"


def test_analysis_runner_marks_run_failed_on_fatal_orchestration_error() -> None:
    engine, session_factory = make_session_factory()
    emitter = AnalysisEventEmitter()
    runner = make_runner(emitter, session_factory, broken_risk=True)

    try:
        asyncio.run(runner.run(make_request()))
    except RuntimeError as exc:
        assert str(exc) == "orchestrator exploded"
    else:
        raise AssertionError("expected fatal orchestration failure")

    with Session(engine) as session:
        run = session.exec(select(AnalysisRun)).one()
        reports = session.exec(select(Report)).all()
        agent_outputs = session.exec(select(AgentOutput)).all()

    assert run.status == "failed"
    assert run.error_message == "orchestrator exploded"
    assert reports == []
    assert len(agent_outputs) == 5
    assert emitter.history()[-1].type == "analysis_failed"
