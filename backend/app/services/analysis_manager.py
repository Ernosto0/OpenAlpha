from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from fastapi import WebSocket
from sqlmodel import Session, select

from backend.app.db.models import AgentOutput, AnalysisRun, Report
from backend.app.db.session import engine
from backend.app.orchestrator.base import AnalysisEvent, AnalysisEventEmitter, AnalysisRunner
from backend.app.orchestrator.schemas import AnalysisRequest, OpenAlphaSchema, utc_now


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed"}
TERMINAL_EVENT_TYPES = {"analysis_completed", "analysis_failed"}


class AnalysisRunAcceptedResponse(OpenAlphaSchema):
    run_id: str
    status: str


class AnalysisAgentOutputResponse(OpenAlphaSchema):
    agent_name: str
    status: str
    output_json: dict | None = None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRunDetailResponse(OpenAlphaSchema):
    run_id: str
    status: str
    symbol: str
    market: str
    horizon: str
    depth: str
    language: str
    total_cost_usd: float
    data_quality_score: float | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    agent_outputs: list[AnalysisAgentOutputResponse]
    report_id: str | None = None


class AnalysisRunEventsResponse(OpenAlphaSchema):
    run_id: str
    events: list[AnalysisEvent]


class AnalysisManager:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        runner_factory: Callable[[AnalysisEventEmitter], AnalysisRunner] | None = None,
        event_emitter: AnalysisEventEmitter | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))
        self._event_emitter = event_emitter or AnalysisEventEmitter()
        self._runner_factory = runner_factory or self._default_runner_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start_run(
        self, request: AnalysisRequest
    ) -> AnalysisRunAcceptedResponse:
        run_id = uuid4().hex
        with self._session_factory() as session:
            session.add(
                AnalysisRun(
                    id=run_id,
                    symbol=request.symbol,
                    market=request.market,
                    horizon=request.horizon,
                    depth=request.depth,
                    language=request.language,
                    status="pending",
                )
            )
            session.commit()
        task = asyncio.create_task(self._execute_run(run_id, request))
        self._tasks[run_id] = task
        task.add_done_callback(
            lambda finished_task, rid=run_id: self._cleanup_task(rid, finished_task)
        )
        return AnalysisRunAcceptedResponse(run_id=run_id, status="running")

    async def get_run_detail(
        self, run_id: str
    ) -> AnalysisRunDetailResponse | None:
        with self._session_factory() as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                return None

            outputs = session.exec(
                select(AgentOutput)
                .where(AgentOutput.analysis_run_id == run_id)
                .order_by(AgentOutput.started_at, AgentOutput.id)
            ).all()
            report = session.exec(
                select(Report)
                .where(Report.analysis_run_id == run_id)
                .order_by(Report.created_at.desc(), Report.id.desc())
            ).first()

        return AnalysisRunDetailResponse(
            run_id=run.id,
            status=run.status,
            symbol=run.symbol,
            market=run.market,
            horizon=run.horizon,
            depth=run.depth,
            language=run.language,
            total_cost_usd=run.total_cost_usd,
            data_quality_score=run.data_quality_score,
            finished_at=run.finished_at,
            error_message=run.error_message,
            agent_outputs=[
                AnalysisAgentOutputResponse(
                    agent_name=output.agent_name,
                    status=output.status,
                    output_json=output.output_json,
                    input_tokens=output.input_tokens,
                    output_tokens=output.output_tokens,
                    cost_usd=output.cost_usd,
                    started_at=output.started_at,
                    finished_at=output.finished_at,
                    error_message=output.error_message,
                )
                for output in outputs
            ],
            report_id=report.id if report is not None else None,
        )

    async def get_events(self, run_id: str) -> AnalysisRunEventsResponse | None:
        events = self._event_emitter.history(run_id)
        if events:
            return AnalysisRunEventsResponse(run_id=run_id, events=events)

        detail = await self.get_run_detail(run_id)
        if detail is None:
            return None

        return AnalysisRunEventsResponse(
            run_id=run_id,
            events=self._reconstruct_events(detail),
        )

    async def stream_events(self, run_id: str, websocket: WebSocket) -> None:
        detail = await self.get_run_detail(run_id)
        history = self._event_emitter.history(run_id)
        if detail is None and not history:
            await websocket.close(code=1008, reason="Unknown analysis run.")
            return

        await websocket.accept()
        initial_events = history or (self._reconstruct_events(detail) if detail else [])
        for event in initial_events:
            await websocket.send_json(event.model_dump(mode="json"))

        queue: asyncio.Queue[AnalysisEvent] = asyncio.Queue()

        def on_event(event: AnalysisEvent) -> None:
            if event.run_id == run_id:
                queue.put_nowait(event)

        unsubscribe = self._event_emitter.subscribe(on_event)
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
                if event.type in TERMINAL_EVENT_TYPES:
                    break
        finally:
            unsubscribe()
            await websocket.close()

    def _default_runner_factory(
        self, event_emitter: AnalysisEventEmitter
    ) -> AnalysisRunner:
        return AnalysisRunner(
            session_factory=self._session_factory,
            event_emitter=event_emitter,
        )

    async def _execute_run(self, run_id: str, request: AnalysisRequest) -> None:
        runner = self._runner_factory(self._event_emitter)
        try:
            await runner.run(request, run_id=run_id)
        except Exception:
            logger.exception("Analysis run %s failed", run_id)

    def _cleanup_task(self, run_id: str, task: asyncio.Task[None]) -> None:
        self._tasks.pop(run_id, None)
        try:
            task.result()
        except Exception:
            logger.exception("Analysis task %s ended with an error", run_id)

    def _reconstruct_events(
        self, detail: AnalysisRunDetailResponse
    ) -> list[AnalysisEvent]:
        events: list[AnalysisEvent] = []
        if detail.agent_outputs:
            started_at = detail.agent_outputs[0].started_at
        else:
            started_at = detail.finished_at or utc_now()

        events.append(
            AnalysisEvent(
                type="analysis_started",
                run_id=detail.run_id,
                timestamp=started_at,
                status=(
                    "running"
                    if detail.status not in TERMINAL_STATUSES
                    else detail.status
                ),
                message=f"Analysis started for {detail.symbol}.",
            )
        )

        for output in detail.agent_outputs:
            events.append(
                AnalysisEvent(
                    type="agent_started",
                    run_id=detail.run_id,
                    timestamp=output.started_at,
                    agent_name=output.agent_name,
                    status="running",
                    message=f"{output.agent_name} started.",
                )
            )
            events.append(
                AnalysisEvent(
                    type="agent_failed" if output.status == "failed" else "agent_finished",
                    run_id=detail.run_id,
                    timestamp=output.finished_at or output.started_at,
                    agent_name=output.agent_name,
                    status=output.status,
                    message=f"{output.agent_name} {output.status}.",
                    error_message=output.error_message,
                )
            )

        if detail.status == "completed":
            events.append(
                AnalysisEvent(
                    type="analysis_completed",
                    run_id=detail.run_id,
                    timestamp=detail.finished_at or started_at,
                    status="completed",
                    message=f"Analysis completed for {detail.symbol}.",
                )
            )
        elif detail.status == "failed":
            events.append(
                AnalysisEvent(
                    type="analysis_failed",
                    run_id=detail.run_id,
                    timestamp=detail.finished_at or started_at,
                    status="failed",
                    message=f"Analysis failed for {detail.symbol}.",
                    error_message=detail.error_message,
                )
            )

        return events


analysis_manager = AnalysisManager()


__all__ = [
    "AnalysisAgentOutputResponse",
    "AnalysisManager",
    "AnalysisRunAcceptedResponse",
    "AnalysisRunDetailResponse",
    "AnalysisRunEventsResponse",
    "analysis_manager",
]
