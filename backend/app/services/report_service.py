from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import Field, ValidationError
from sqlmodel import Session, select

from backend.app.db.models import AgentOutput, AnalysisRun, CostTrace, Report
from backend.app.db.session import engine
from backend.app.orchestrator.schemas import (
    FinalReport,
    FinalReportDataQualitySection,
    FinalReportSourceItem,
    OpenAlphaSchema,
)
from backend.app.services.analysis_manager import AnalysisAgentOutputResponse


class ReportListItemResponse(OpenAlphaSchema):
    id: str
    symbol: str
    horizon: str
    overall_view: str
    confidence: float | None = None
    risk_level: str | None = None
    created_at: datetime


class ReportCostItemResponse(OpenAlphaSchema):
    agent_name: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_type: str
    duration_ms: int
    warnings: list[str] = Field(default_factory=list)
    parsing_errors: list[str] = Field(default_factory=list)
    created_at: datetime


class ReportCostBreakdownResponse(OpenAlphaSchema):
    total_cost_usd: float
    items: list[ReportCostItemResponse]


class ReportDetailResponse(OpenAlphaSchema):
    id: str
    run_id: str
    status: str
    symbol: str
    market: str
    horizon: str
    overall_view: str
    confidence: float | None = None
    risk_level: str | None = None
    created_at: datetime
    final_report: dict[str, Any]
    agent_outputs: list[AnalysisAgentOutputResponse]
    cost_breakdown: ReportCostBreakdownResponse
    data_quality: FinalReportDataQualitySection | None = None
    sources: list[FinalReportSourceItem]
    warnings: list[str]


class ReportService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))

    async def list_reports(self) -> list[ReportListItemResponse]:
        with self._session_factory() as session:
            reports = session.exec(
                select(Report).order_by(Report.created_at.desc(), Report.id.desc())
            ).all()

        return [
            ReportListItemResponse(
                id=report.id,
                symbol=report.symbol,
                horizon=report.horizon,
                overall_view=report.overall_view,
                confidence=report.confidence,
                risk_level=report.risk_level,
                created_at=self._normalize_datetime(report.created_at),
            )
            for report in reports
        ]

    async def get_report_detail(self, report_id: str) -> ReportDetailResponse | None:
        with self._session_factory() as session:
            report = session.get(Report, report_id)
            if report is None:
                return None

            run = session.get(AnalysisRun, report.analysis_run_id)
            outputs = session.exec(
                select(AgentOutput)
                .where(AgentOutput.analysis_run_id == report.analysis_run_id)
                .order_by(AgentOutput.started_at, AgentOutput.id)
            ).all()
            traces = session.exec(
                select(CostTrace)
                .where(CostTrace.analysis_run_id == report.analysis_run_id)
                .order_by(CostTrace.created_at, CostTrace.id)
            ).all()

        final_report = self._safe_parse_final_report(report.report_json)
        return ReportDetailResponse(
            id=report.id,
            run_id=report.analysis_run_id,
            status=run.status if run is not None else "unknown",
            symbol=report.symbol,
            market=report.market,
            horizon=report.horizon,
            overall_view=report.overall_view,
            confidence=report.confidence,
            risk_level=report.risk_level,
            created_at=self._normalize_datetime(report.created_at),
            final_report=report.report_json,
            agent_outputs=[
                AnalysisAgentOutputResponse(
                    agent_name=output.agent_name,
                    status=output.status,
                    provider=output.provider,
                    model=output.model,
                    output_json=output.output_json,
                    input_tokens=output.input_tokens,
                    output_tokens=output.output_tokens,
                    cost_usd=output.cost_usd,
                    cost_type=output.cost_type,
                    duration_ms=output.duration_ms,
                    warnings=list(output.warnings_json or []),
                    parsing_errors=list(output.parsing_errors_json or []),
                    started_at=output.started_at,
                    finished_at=output.finished_at,
                    error_message=output.error_message,
                )
                for output in outputs
            ],
            cost_breakdown=ReportCostBreakdownResponse(
                total_cost_usd=sum(trace.cost_usd for trace in traces),
                items=[
                    ReportCostItemResponse(
                        agent_name=trace.agent_name,
                        provider=trace.provider,
                        model=trace.model,
                        input_tokens=trace.input_tokens,
                        output_tokens=trace.output_tokens,
                        cost_usd=trace.cost_usd,
                        cost_type=trace.cost_type,
                        duration_ms=trace.duration_ms,
                        warnings=list(trace.warnings_json or []),
                        parsing_errors=list(trace.parsing_errors_json or []),
                        created_at=self._normalize_datetime(trace.created_at),
                    )
                    for trace in traces
                ],
            ),
            data_quality=final_report.data_quality_section if final_report else None,
            sources=list(final_report.source_section) if final_report else [],
            warnings=list(final_report.warnings) if final_report else [],
        )

    async def delete_report(self, report_id: str) -> bool:
        with self._session_factory() as session:
            report = session.get(Report, report_id)
            if report is None:
                return False

            session.delete(report)
            session.commit()
            return True

    def _safe_parse_final_report(self, payload: dict[str, Any]) -> FinalReport | None:
        try:
            return FinalReport.model_validate(payload)
        except ValidationError:
            return None

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


report_service = ReportService()


__all__ = [
    "ReportCostBreakdownResponse",
    "ReportCostItemResponse",
    "ReportDetailResponse",
    "ReportListItemResponse",
    "ReportService",
    "report_service",
]
