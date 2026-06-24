from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from statistics import mean
from typing import Literal

from sqlmodel import Session, select

from backend.app.db.models import CostTrace, Report
from backend.app.db.session import engine
from backend.app.marketdata.base import (
    MarketDataProvider,
    PriceHistoryResult,
    get_default_market_data_provider,
    get_market_data_provider,
)
from backend.app.orchestrator.schemas import OpenAlphaSchema, PriceBar


PerformanceDirectionResult = Literal["correct", "incorrect", "not_scored"]
PerformanceEvaluationStatus = Literal["interim", "matured"]

HORIZON_DAYS: dict[str, int] = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}

UP_VIEWS = {"bullish", "slightly_bullish"}
DOWN_VIEWS = {"bearish", "slightly_bearish"}
PREFERRED_MODEL_AGENTS = ("report_writer_agent", "thesis_agent")


class PerformanceSummaryResponse(OpenAlphaSchema):
    direction_correctness: float | None = None
    relative_performance: float | None = None
    evaluated_reports: int
    total_reports: int
    average_hold_days: float | None = None


class PerformanceBreakdownItemResponse(OpenAlphaSchema):
    label: str
    correctness_rate: float | None = None
    evaluated_count: int
    average_return: float | None = None
    average_alpha: float | None = None


class PerformanceEvaluationItemResponse(OpenAlphaSchema):
    report_id: str
    symbol: str
    market: str
    horizon: str
    overall_view: str
    model: str
    report_created_at: datetime
    evaluation_status: PerformanceEvaluationStatus
    days_elapsed: int
    target_days: int
    entry_price: float | None = None
    latest_price: float | None = None
    realized_return: float | None = None
    benchmark_symbol: str | None = None
    benchmark_return: float | None = None
    alpha: float | None = None
    direction_result: PerformanceDirectionResult


class PerformanceResponse(OpenAlphaSchema):
    summary: PerformanceSummaryResponse
    by_model: list[PerformanceBreakdownItemResponse]
    by_horizon: list[PerformanceBreakdownItemResponse]
    recent_evaluations: list[PerformanceEvaluationItemResponse]


@dataclass
class EvaluatedReport:
    report_id: str
    symbol: str
    market: str
    horizon: str
    overall_view: str
    model: str
    report_created_at: datetime
    evaluation_status: PerformanceEvaluationStatus
    days_elapsed: int
    target_days: int
    entry_price: float | None
    latest_price: float | None
    realized_return: float | None
    benchmark_symbol: str | None
    benchmark_return: float | None
    alpha: float | None
    direction_result: PerformanceDirectionResult


class PerformanceService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        price_providers: list[MarketDataProvider] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))
        self._price_providers = price_providers or self._build_price_providers()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    async def get_performance(self) -> PerformanceResponse:
        with self._session_factory() as session:
            reports = session.exec(
                select(Report).order_by(Report.created_at.desc(), Report.id.desc())
            ).all()
            run_ids = [report.analysis_run_id for report in reports]
            traces = (
                session.exec(
                    select(CostTrace).where(CostTrace.analysis_run_id.in_(run_ids))
                ).all()
                if run_ids
                else []
            )

        evaluated_reports = await self._evaluate_reports(reports, traces)
        return PerformanceResponse(
            summary=self._build_summary(reports, evaluated_reports),
            by_model=self._build_breakdown(evaluated_reports, key="model"),
            by_horizon=self._build_breakdown(evaluated_reports, key="horizon"),
            recent_evaluations=[
                PerformanceEvaluationItemResponse(**item.__dict__)
                for item in evaluated_reports[:20]
            ],
        )

    async def _evaluate_reports(
        self,
        reports: list[Report],
        traces: list[CostTrace],
    ) -> list[EvaluatedReport]:
        if not reports:
            return []

        earliest_date = min(self._normalize_datetime(report.created_at).date() for report in reports)
        symbols = {report.symbol for report in reports}
        if any(report.market == "US" for report in reports):
            symbols.add("SPY")

        histories = await self._fetch_histories(symbols, earliest_date)
        traces_by_run_id: dict[str, list[CostTrace]] = {}
        for trace in traces:
            traces_by_run_id.setdefault(trace.analysis_run_id, []).append(trace)

        now = self._now_provider()
        rows: list[EvaluatedReport] = []
        for report in reports:
            normalized_created_at = self._normalize_datetime(report.created_at)
            target_days = HORIZON_DAYS.get(report.horizon, 0)
            days_elapsed = max((now.date() - normalized_created_at.date()).days, 0)
            evaluation_status: PerformanceEvaluationStatus = (
                "matured" if days_elapsed >= target_days else "interim"
            )

            stock_history = histories.get(report.symbol, [])
            entry_price = self._entry_price(stock_history, normalized_created_at.date())
            latest_price = stock_history[-1].close if stock_history else None
            realized_return = self._return(entry_price, latest_price)

            benchmark_symbol = "SPY" if report.market == "US" else None
            benchmark_history = histories.get("SPY", []) if benchmark_symbol else []
            benchmark_entry = (
                self._entry_price(benchmark_history, normalized_created_at.date())
                if benchmark_symbol
                else None
            )
            benchmark_latest = benchmark_history[-1].close if benchmark_history else None
            benchmark_return = self._return(benchmark_entry, benchmark_latest)
            alpha = (
                realized_return - benchmark_return
                if realized_return is not None and benchmark_return is not None
                else None
            )

            rows.append(
                EvaluatedReport(
                    report_id=report.id,
                    symbol=report.symbol,
                    market=report.market,
                    horizon=report.horizon,
                    overall_view=report.overall_view,
                    model=self._resolve_model(traces_by_run_id.get(report.analysis_run_id, [])),
                    report_created_at=normalized_created_at,
                    evaluation_status=evaluation_status,
                    days_elapsed=days_elapsed,
                    target_days=target_days,
                    entry_price=entry_price,
                    latest_price=latest_price,
                    realized_return=realized_return,
                    benchmark_symbol=benchmark_symbol,
                    benchmark_return=benchmark_return,
                    alpha=alpha,
                    direction_result=self._direction_result(report.overall_view, realized_return),
                )
            )

        return rows

    async def _fetch_histories(
        self,
        symbols: set[str],
        start_date: date,
    ) -> dict[str, list[PriceBar]]:
        results = await asyncio.gather(
            *(self._fetch_history(symbol, start_date) for symbol in symbols)
        )
        return {symbol: bars for symbol, bars in results}

    async def _fetch_history(
        self,
        symbol: str,
        start_date: date,
    ) -> tuple[str, list[PriceBar]]:
        for provider in self._price_providers:
            try:
                result = await provider.get_price_history(symbol, start=start_date)
            except Exception:
                continue

            if result.bars:
                return symbol, sorted(result.bars, key=lambda item: item.timestamp)

        return symbol, []

    def _build_summary(
        self,
        reports: list[Report],
        evaluated_reports: list[EvaluatedReport],
    ) -> PerformanceSummaryResponse:
        scored = [
            row for row in evaluated_reports if row.direction_result in {"correct", "incorrect"}
        ]
        rows_with_alpha = [row.alpha for row in evaluated_reports if row.alpha is not None]
        rows_with_prices = [
            row for row in evaluated_reports if row.realized_return is not None
        ]

        correctness = None
        if scored:
            correctness = sum(1 for row in scored if row.direction_result == "correct") / len(scored)

        return PerformanceSummaryResponse(
            direction_correctness=correctness,
            relative_performance=mean(rows_with_alpha) if rows_with_alpha else None,
            evaluated_reports=len(rows_with_prices),
            total_reports=len(reports),
            average_hold_days=(
                mean(row.days_elapsed for row in rows_with_prices)
                if rows_with_prices
                else None
            ),
        )

    def _build_breakdown(
        self,
        evaluated_reports: list[EvaluatedReport],
        *,
        key: Literal["model", "horizon"],
    ) -> list[PerformanceBreakdownItemResponse]:
        grouped: dict[str, list[EvaluatedReport]] = {}
        for row in evaluated_reports:
            grouped.setdefault(getattr(row, key), []).append(row)

        items: list[PerformanceBreakdownItemResponse] = []
        for label, rows in grouped.items():
            scored = [
                row for row in rows if row.direction_result in {"correct", "incorrect"}
            ]
            returns = [row.realized_return for row in rows if row.realized_return is not None]
            alphas = [row.alpha for row in rows if row.alpha is not None]
            correctness = None
            if scored:
                correctness = sum(
                    1 for row in scored if row.direction_result == "correct"
                ) / len(scored)

            items.append(
                PerformanceBreakdownItemResponse(
                    label=label,
                    correctness_rate=correctness,
                    evaluated_count=len(returns),
                    average_return=mean(returns) if returns else None,
                    average_alpha=mean(alphas) if alphas else None,
                )
            )

        if key == "horizon":
            items.sort(key=lambda item: HORIZON_DAYS.get(item.label, 10**9))
        else:
            items.sort(key=lambda item: (-item.evaluated_count, item.label))
        return items

    def _resolve_model(self, traces: list[CostTrace]) -> str:
        if not traces:
            return "unknown"

        non_local = [trace for trace in traces if trace.cost_type != "deterministic"]
        preferred = [
            trace
            for trace in non_local
            if trace.agent_name in PREFERRED_MODEL_AGENTS
        ]
        if preferred:
            return max(preferred, key=lambda trace: (trace.created_at, trace.id)).model
        if non_local:
            return max(non_local, key=lambda trace: (trace.created_at, trace.id)).model
        return max(traces, key=lambda trace: (trace.created_at, trace.id)).model

    def _direction_result(
        self,
        overall_view: str,
        realized_return: float | None,
    ) -> PerformanceDirectionResult:
        if realized_return is None:
            return "not_scored"
        if realized_return == 0:
            return "not_scored"
        if overall_view in UP_VIEWS:
            return "correct" if realized_return > 0 else "incorrect"
        if overall_view in DOWN_VIEWS:
            return "correct" if realized_return < 0 else "incorrect"
        return "not_scored"

    def _entry_price(self, bars: list[PriceBar], created_date: date) -> float | None:
        for bar in bars:
            if bar.timestamp.date() >= created_date:
                return bar.close
        return None

    def _return(
        self,
        entry_price: float | None,
        latest_price: float | None,
    ) -> float | None:
        if entry_price is None or latest_price is None or entry_price == 0:
            return None
        return (latest_price - entry_price) / entry_price

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _build_price_providers(self) -> list[MarketDataProvider]:
        providers: list[MarketDataProvider] = [get_default_market_data_provider()]
        yahoo = get_market_data_provider("yahoo")
        if all(provider.provider_name != yahoo.provider_name for provider in providers):
            providers.append(yahoo)
        return providers


performance_service = PerformanceService()


__all__ = [
    "PerformanceBreakdownItemResponse",
    "PerformanceEvaluationItemResponse",
    "PerformanceResponse",
    "PerformanceService",
    "PerformanceSummaryResponse",
    "performance_service",
]
