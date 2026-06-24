from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.db.models import CostTrace, Report
from backend.app.main import create_app
from backend.app.marketdata.base import MarketDataProvider, PriceHistoryResult
from backend.app.orchestrator.schemas import DataSource, PriceBar
from backend.app.services.performance_service import PerformanceService


class StubPriceProvider(MarketDataProvider):
    provider_name = "stub"
    capabilities = ("historical_ohlcv",)

    def __init__(self, bars_by_symbol: dict[str, list[PriceBar]]) -> None:
        super().__init__()
        self._bars_by_symbol = bars_by_symbol

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: str = "1d",
    ) -> PriceHistoryResult:
        bars = [
            bar
            for bar in self._bars_by_symbol.get(symbol, [])
            if start is None or bar.timestamp.date() >= start
        ]
        return PriceHistoryResult(
            symbol=symbol,
            provider=self.provider_name,
            status="available" if bars else "missing",
            bars=bars,
            source=DataSource(
                name="Historical OHLCV",
                provider=self.provider_name,
                status="available" if bars else "missing",
            ),
            warnings=[],
        )


def build_test_service() -> PerformanceService:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session_factory = lambda: Session(engine)

    with session_factory() as session:
        session.add_all(
            [
                Report(
                    id="report_1",
                    analysis_run_id="run_1",
                    symbol="AAPL",
                    market="US",
                    horizon="3m",
                    overall_view="bullish",
                    confidence=0.7,
                    risk_level="moderate",
                    report_json={},
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                Report(
                    id="report_2",
                    analysis_run_id="run_2",
                    symbol="TSLA",
                    market="US",
                    horizon="1m",
                    overall_view="slightly_bearish",
                    confidence=0.6,
                    risk_level="high",
                    report_json={},
                    created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                ),
                Report(
                    id="report_3",
                    analysis_run_id="run_3",
                    symbol="SAP",
                    market="GLOBAL",
                    horizon="1y",
                    overall_view="neutral",
                    confidence=0.5,
                    risk_level="low",
                    report_json={},
                    created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                ),
                Report(
                    id="report_4",
                    analysis_run_id="run_4",
                    symbol="NFLX",
                    market="US",
                    horizon="1w",
                    overall_view="bearish",
                    confidence=0.5,
                    risk_level="medium",
                    report_json={},
                    created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                ),
                Report(
                    id="report_5",
                    analysis_run_id="run_5",
                    symbol="MSFT",
                    market="US",
                    horizon="1m",
                    overall_view="slightly_bearish",
                    confidence=0.5,
                    risk_level="medium",
                    report_json={},
                    created_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
                ),
            ]
        )
        session.add_all(
            [
                CostTrace(
                    id="trace_1",
                    analysis_run_id="run_1",
                    agent_name="thesis_agent",
                    provider="openai",
                    model="gpt-4o",
                    input_tokens=10,
                    output_tokens=10,
                    cost_usd=0.01,
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                CostTrace(
                    id="trace_2",
                    analysis_run_id="run_2",
                    agent_name="report_writer_agent",
                    provider="openai",
                    model="gpt-4.1-mini",
                    input_tokens=10,
                    output_tokens=10,
                    cost_usd=0.01,
                    created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                ),
                CostTrace(
                    id="trace_3",
                    analysis_run_id="run_3",
                    agent_name="data_collector",
                    provider="deterministic",
                    model="deterministic",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                ),
                CostTrace(
                    id="trace_4",
                    analysis_run_id="run_4",
                    agent_name="thesis_agent",
                    provider="openai",
                    model="gpt-4o",
                    input_tokens=10,
                    output_tokens=10,
                    cost_usd=0.01,
                    created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                ),
                CostTrace(
                    id="trace_5",
                    analysis_run_id="run_5",
                    agent_name="thesis_agent",
                    provider="openai",
                    model="gpt-4.1-mini",
                    input_tokens=10,
                    output_tokens=10,
                    cost_usd=0.01,
                    created_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

    bars_by_symbol = {
        "AAPL": [
            PriceBar(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), close=100),
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=120),
        ],
        "TSLA": [
            PriceBar(timestamp=datetime(2026, 2, 2, tzinfo=timezone.utc), close=100),
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=80),
        ],
        "SAP": [
            PriceBar(timestamp=datetime(2026, 5, 2, tzinfo=timezone.utc), close=100),
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=110),
        ],
        "MSFT": [
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=100),
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=100),
        ],
        "SPY": [
            PriceBar(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), close=100),
            PriceBar(timestamp=datetime(2026, 2, 2, tzinfo=timezone.utc), close=110),
            PriceBar(timestamp=datetime(2026, 6, 20, tzinfo=timezone.utc), close=121),
        ],
    }
    provider = StubPriceProvider(bars_by_symbol)

    return PerformanceService(
        session_factory=session_factory,
        price_providers=[provider],
        now_provider=lambda: datetime(2026, 6, 22, tzinfo=timezone.utc),
    )


@pytest.mark.anyio
async def test_performance_service_computes_summary_and_breakdowns() -> None:
    service = build_test_service()

    response = await service.get_performance()

    assert response.summary.total_reports == 5
    assert response.summary.evaluated_reports == 4
    assert response.summary.direction_correctness == 1.0
    assert response.summary.relative_performance == pytest.approx(-0.10333333333333335, abs=1e-9)
    assert response.summary.average_hold_days == pytest.approx(91.75)

    by_model = {item.label: item for item in response.by_model}
    assert by_model["gpt-4o"].evaluated_count == 1
    assert by_model["gpt-4o"].correctness_rate == 1.0
    assert by_model["gpt-4.1-mini"].average_return == pytest.approx(-0.1)
    assert by_model["deterministic"].average_alpha is None

    by_horizon = {item.label: item for item in response.by_horizon}
    assert by_horizon["1y"].correctness_rate is None
    assert by_horizon["1w"].evaluated_count == 0
    assert by_horizon["1m"].correctness_rate == 1.0

    recent = {item.report_id: item for item in response.recent_evaluations}
    assert recent["report_3"].evaluation_status == "interim"
    assert recent["report_3"].direction_result == "not_scored"
    assert recent["report_3"].alpha is None
    assert recent["report_4"].realized_return is None
    assert recent["report_2"].direction_result == "correct"
    assert recent["report_5"].realized_return == 0.0
    assert recent["report_5"].direction_result == "not_scored"


@pytest.mark.anyio
async def test_performance_endpoint_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_test_service()
    monkeypatch.setattr("backend.app.api.routes.performance.performance_service", service)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/performance")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_reports"] == 5
    assert data["summary"]["evaluated_reports"] == 4
    assert len(data["by_model"]) == 3
    assert len(data["recent_evaluations"]) == 5
    assert data["recent_evaluations"][0]["report_id"] == "report_5"
