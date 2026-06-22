from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field
from sqlmodel import Session

from backend.app.agents.bear_case_agent import BearCaseAgent
from backend.app.agents.bull_case_agent import BullCaseAgent
from backend.app.agents.data_collector_agent import DataCollectorAgent
from backend.app.agents.news_sentiment_agent import NewsSentimentAgent
from backend.app.agents.report_writer_agent import ReportWriterAgent
from backend.app.agents.risk_review_agent import RiskReviewAgent
from backend.app.agents.technical_agent import TechnicalAgent
from backend.app.agents.thesis_agent import ThesisAgent
from backend.app.db.models import AgentOutput, AnalysisRun, CostTrace as CostTraceModel
from backend.app.db.models import Report
from backend.app.db.session import engine
from backend.app.orchestrator.schemas import (
    AgentName,
    AgentResult,
    AnalysisRequest,
    AnalysisContext as SchemaAnalysisContext,
    CostTrace,
    OpenAlphaSchema,
    utc_now,
)

logger = logging.getLogger(__name__)


AnalysisEventType = Literal[
    "analysis_started",
    "agent_started",
    "agent_finished",
    "agent_failed",
    "analysis_completed",
    "analysis_failed",
]

RUNTIME_OUTPUT_FIELDS: dict[AgentName, str] = {
    "technical_agent": "technical_output",
    "news_sentiment_agent": "news_sentiment_output",
    "bull_case_agent": "bull_case_output",
    "bear_case_agent": "bear_case_output",
    "risk_review_agent": "risk_review_output",
    "thesis_agent": "thesis_output",
    "report_writer_agent": "final_report",
}


class AnalysisEvent(OpenAlphaSchema):
    type: AnalysisEventType
    run_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    agent_name: AgentName | None = None
    status: str | None = None
    message: str | None = None
    error_message: str | None = None


class AnalysisEventEmitter:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[AnalysisEvent], None]] = []
        self._events: list[AnalysisEvent] = []

    def subscribe(
        self, callback: Callable[[AnalysisEvent], None]
    ) -> Callable[[], None]:
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    def emit(self, event: AnalysisEvent) -> None:
        self._events.append(event)
        for callback in list(self._subscribers):
            callback(event)

    def history(self, run_id: str | None = None) -> list[AnalysisEvent]:
        if run_id is None:
            return list(self._events)
        return [event for event in self._events if event.run_id == run_id]


class AnalysisContext(SchemaAnalysisContext):
    @classmethod
    def from_request(
        cls, request: AnalysisRequest, run_id: str | None = None
    ) -> "AnalysisContext":
        now = utc_now()
        return cls(
            run_id=run_id or uuid4().hex,
            request=request,
            created_at=now,
            updated_at=now,
        )

    def mark_warning(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)
            self.updated_at = utc_now()

    def latest_agent_result(self, agent_name: AgentName) -> AgentResult | None:
        for result in reversed(self.agent_results):
            if result.agent_name == agent_name:
                return result
        return None

    @property
    def failed_agent_names(self) -> list[AgentName]:
        return [
            result.agent_name
            for result in self.agent_results
            if result.status == "failed"
        ]

    @property
    def missing_output_agent_names(self) -> list[AgentName]:
        return [
            agent_name
            for agent_name, field_name in RUNTIME_OUTPUT_FIELDS.items()
            if getattr(self, field_name) is None
        ]


class AnalysisRunner:
    def __init__(
        self,
        *,
        session: Session | None = None,
        session_factory: Callable[[], Session] | None = None,
        event_emitter: AnalysisEventEmitter | None = None,
        data_collector_agent: Any | None = None,
        technical_agent: Any | None = None,
        news_sentiment_agent: Any | None = None,
        bull_case_agent: Any | None = None,
        bear_case_agent: Any | None = None,
        risk_review_agent: Any | None = None,
        thesis_agent: Any | None = None,
        report_writer_agent: Any | None = None,
    ) -> None:
        self._session = session
        self._session_factory = session_factory or (lambda: Session(engine))
        self.event_emitter = event_emitter or AnalysisEventEmitter()
        self.agents: dict[AgentName, Any] = {
            "data_collector": data_collector_agent or DataCollectorAgent(),
            "technical_agent": technical_agent or TechnicalAgent(),
            "news_sentiment_agent": news_sentiment_agent or NewsSentimentAgent(),
            "bull_case_agent": bull_case_agent or BullCaseAgent(),
            "bear_case_agent": bear_case_agent or BearCaseAgent(),
            "risk_review_agent": risk_review_agent or RiskReviewAgent(),
            "thesis_agent": thesis_agent or ThesisAgent(),
            "report_writer_agent": report_writer_agent or ReportWriterAgent(),
        }
        self._persisted_result_count = 0
        self._persisted_cost_trace_count = 0
        self._report_persisted = False

    async def run(
        self, request: AnalysisRequest, run_id: str | None = None
    ) -> AnalysisContext:
        context = AnalysisContext.from_request(request, run_id=run_id)
        session, owns_session = self._open_session()
        self._reset_persistence_state()
        logger.info(
            "Analysis run started",
            extra={"run_id": context.run_id, "symbol": request.symbol},
        )

        try:
            run_row = session.get(AnalysisRun, context.run_id)
            if run_row is None:
                run_row = AnalysisRun(
                    id=context.run_id,
                    symbol=request.symbol,
                    market=request.market,
                    horizon=request.horizon,
                    depth=request.depth,
                    language=request.language,
                    status="pending",
                    started_at=context.created_at,
                )
                session.add(run_row)
                session.commit()

            run_row.symbol = request.symbol
            run_row.market = request.market
            run_row.horizon = request.horizon
            run_row.depth = request.depth
            run_row.language = request.language
            run_row.started_at = run_row.started_at or context.created_at
            run_row.status = "running"
            session.add(run_row)
            session.commit()

            self.event_emitter.emit(
                AnalysisEvent(
                    type="analysis_started",
                    run_id=context.run_id,
                    status="running",
                    message=f"Analysis started for {request.symbol}.",
                )
            )

            await self._run_agent(context, session, "data_collector")
            await self._run_parallel_stage(
                context,
                session,
                ("technical_agent", "news_sentiment_agent"),
            )
            await self._run_parallel_stage(
                context,
                session,
                ("bull_case_agent", "bear_case_agent"),
            )
            await self._run_agent(context, session, "risk_review_agent")
            await self._run_agent(context, session, "thesis_agent")
            await self._run_agent(context, session, "report_writer_agent")

            if context.final_report is None:
                raise RuntimeError("analysis completed without a final report")

            self._persist_report(session, context, run_row)
            self._finalize_run(
                session=session,
                run_row=run_row,
                context=context,
                status="completed",
                error_message=None,
            )
            self.event_emitter.emit(
                AnalysisEvent(
                    type="analysis_completed",
                    run_id=context.run_id,
                    status="completed",
                    message=f"Analysis completed for {request.symbol}.",
                )
            )
            logger.info(
                "Analysis run completed",
                extra={"run_id": context.run_id, "symbol": request.symbol},
            )
            return context
        except Exception as exc:
            self._mark_run_failed(
                session=session,
                run_row=run_row,
                context=context,
                error_message=str(exc),
            )
            self.event_emitter.emit(
                AnalysisEvent(
                    type="analysis_failed",
                    run_id=context.run_id,
                    status="failed",
                    message=f"Analysis failed for {request.symbol}.",
                    error_message=str(exc),
                )
            )
            logger.exception(
                "Analysis run failed",
                extra={"run_id": context.run_id, "symbol": request.symbol},
            )
            raise
        finally:
            if owns_session:
                session.close()

    def _open_session(self) -> tuple[Session, bool]:
        if self._session is not None:
            return self._session, False
        return self._session_factory(), True

    def _reset_persistence_state(self) -> None:
        self._persisted_result_count = 0
        self._persisted_cost_trace_count = 0
        self._report_persisted = False

    async def _run_parallel_stage(
        self,
        context: AnalysisContext,
        session: Session,
        agent_names: tuple[AgentName, AgentName],
    ) -> None:
        await asyncio.gather(
            *(self._run_agent(context, session, agent_name) for agent_name in agent_names),
            return_exceptions=False,
        )

    async def _run_agent(
        self,
        context: AnalysisContext,
        session: Session,
        agent_name: AgentName,
    ) -> AgentResult:
        agent = self.agents[agent_name]
        logger.info(
            "Orchestrator starting agent",
            extra={"run_id": context.run_id, "agent_name": agent_name},
        )
        self.event_emitter.emit(
            AnalysisEvent(
                type="agent_started",
                run_id=context.run_id,
                agent_name=agent_name,
                status="running",
                message=f"{agent_name} started.",
            )
        )
        result: AgentResult = await agent.run(context)
        self._sync_runtime_outputs(context, result)
        self._persist_new_state(session, context)
        if result.status == "failed":
            logger.warning(
                "Orchestrator agent failed",
                extra={"run_id": context.run_id, "agent_name": agent_name},
            )
        else:
            logger.info(
                "Orchestrator agent finished",
                extra={"run_id": context.run_id, "agent_name": agent_name},
            )
        self.event_emitter.emit(
            AnalysisEvent(
                type="agent_failed" if result.status == "failed" else "agent_finished",
                run_id=context.run_id,
                agent_name=agent_name,
                status=result.status,
                message=f"{agent_name} {result.status}.",
                error_message=result.error_message,
            )
        )
        if result.fatal_error:
            raise RuntimeError(result.error_message or f"{agent_name} failed fatally")
        return result

    def _sync_runtime_outputs(
        self, context: AnalysisContext, result: AgentResult
    ) -> None:
        field_name = RUNTIME_OUTPUT_FIELDS.get(result.agent_name)
        if field_name and result.output is not None and getattr(context, field_name) is None:
            setattr(context, field_name, result.output)

    def _persist_new_state(self, session: Session, context: AnalysisContext) -> None:
        while self._persisted_result_count < len(context.agent_results):
            result = context.agent_results[self._persisted_result_count]
            session.add(self._build_agent_output_row(context.run_id, result))
            self._persisted_result_count += 1

        while self._persisted_cost_trace_count < len(context.cost_traces):
            trace = context.cost_traces[self._persisted_cost_trace_count]
            session.add(self._build_cost_trace_row(context.run_id, trace))
            self._persisted_cost_trace_count += 1

        session.commit()

    def _persist_report(
        self,
        session: Session,
        context: AnalysisContext,
        run_row: AnalysisRun,
    ) -> None:
        if self._report_persisted or context.final_report is None:
            return

        report = context.final_report
        session.add(
            Report(
                analysis_run_id=context.run_id,
                symbol=report.symbol,
                market=report.market,
                horizon=report.horizon,
                overall_view=report.overall_view,
                confidence=report.confidence,
                risk_level=report.risk_section.risk_level,
                report_json=report.model_dump(mode="json"),
                created_at=report.created_at,
            )
        )
        run_row.data_quality_score = report.data_quality_section.data_quality_score
        session.commit()
        self._report_persisted = True

    def _finalize_run(
        self,
        *,
        session: Session,
        run_row: AnalysisRun,
        context: AnalysisContext,
        status: str,
        error_message: str | None,
    ) -> None:
        run_row.status = status
        run_row.finished_at = utc_now()
        context.updated_at = run_row.finished_at
        run_row.total_cost_usd = context.total_cost_usd
        run_row.data_quality_score = (
            context.final_report.data_quality_section.data_quality_score
            if context.final_report is not None
            else context.data_quality.score if context.data_quality is not None else None
        )
        run_row.error_message = error_message
        session.add(run_row)
        session.commit()
        session.refresh(run_row)

    def _mark_run_failed(
        self,
        *,
        session: Session,
        run_row: AnalysisRun,
        context: AnalysisContext,
        error_message: str,
    ) -> None:
        try:
            session.rollback()
        except Exception:
            return

        run_row.status = "failed"
        run_row.finished_at = utc_now()
        run_row.total_cost_usd = context.total_cost_usd
        run_row.data_quality_score = (
            context.final_report.data_quality_section.data_quality_score
            if context.final_report is not None
            else context.data_quality.score if context.data_quality is not None else None
        )
        run_row.error_message = error_message
        session.add(run_row)
        session.commit()

    def _build_agent_output_row(
        self, run_id: str, result: AgentResult
    ) -> AgentOutput:
        output_json = None
        if result.output is not None:
            if hasattr(result.output, "model_dump"):
                output_json = result.output.model_dump(mode="json")
            else:
                output_json = result.output

        return AgentOutput(
            analysis_run_id=run_id,
            agent_name=result.agent_name,
            status=result.status,
            output_json=output_json,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.estimated_cost_usd,
            started_at=result.started_at,
            finished_at=result.finished_at,
            error_message=result.error_message,
        )

    def _build_cost_trace_row(self, run_id: str, trace: CostTrace) -> CostTraceModel:
        return CostTraceModel(
            analysis_run_id=run_id,
            agent_name=trace.agent_name,
            provider=trace.provider,
            model=trace.model,
            input_tokens=trace.input_tokens,
            output_tokens=trace.output_tokens,
            cost_usd=trace.estimated_cost_usd,
            created_at=trace.created_at,
        )


__all__ = [
    "AnalysisContext",
    "AnalysisEvent",
    "AnalysisEventEmitter",
    "AnalysisEventType",
    "AnalysisRunner",
]
