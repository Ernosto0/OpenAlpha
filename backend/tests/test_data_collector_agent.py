from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.app.agents.data_collector_agent import DataCollectorAgent
from backend.app.marketdata.base import (
    CompanyFactsResult,
    MarketDataProvider,
    PriceHistoryResult,
    PriceInterval,
)
from backend.app.news.base import NewsArticle, NewsProviderResult
from backend.app.orchestrator.schemas import (
    AnalysisContext,
    AnalysisRequest,
    CompanyProfile,
    DataCollectorOutput,
    DataSource,
    FinancialSnapshot,
    PriceBar,
)


def make_context() -> AnalysisContext:
    return AnalysisContext(
        run_id="run_1",
        request=AnalysisRequest(
            symbol="aapl",
            horizon="1m",
            llm_model="gpt-4.1-mini",
            custom_question="earnings",
        ),
    )


def example_bars() -> list[PriceBar]:
    return [
        PriceBar(
            timestamp=datetime(2024, 1, day, tzinfo=timezone.utc),
            open=100 + day,
            high=102 + day,
            low=99 + day,
            close=101 + day,
            volume=1000 + day,
        )
        for day in range(1, 31)
    ]


class StaticPriceProvider(MarketDataProvider):
    provider_name = "static_prices"
    capabilities = ("historical_ohlcv",)

    def __init__(self, bars: list[PriceBar] | None = None) -> None:
        super().__init__()
        self.bars = bars if bars is not None else example_bars()

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: Any = None,
        end: Any = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        return PriceHistoryResult(
            symbol=symbol,
            provider=self.provider_name,
            status="available" if self.bars else "missing",
            bars=self.bars,
            source=DataSource(
                name="Static prices",
                provider=self.provider_name,
                status="available" if self.bars else "missing",
            ),
        )


class FailingPriceProvider(StaticPriceProvider):
    provider_name = "failing_prices"

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: Any = None,
        end: Any = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        raise RuntimeError("price provider unavailable")


class StaticFactsProvider(MarketDataProvider):
    provider_name = "static_facts"
    capabilities = ("company_profile", "financials", "company_facts")

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: Any = None,
        end: Any = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        raise NotImplementedError

    async def get_company_facts(self, symbol: str) -> CompanyFactsResult:
        return CompanyFactsResult(
            symbol=symbol,
            provider=self.provider_name,
            status="available",
            source=DataSource(
                name="Static facts",
                provider=self.provider_name,
                status="available",
            ),
            profile=CompanyProfile(name="Apple Inc.", country="US"),
            financials=FinancialSnapshot(revenue=1000, net_income=200),
        )


class FailingFactsProvider(StaticFactsProvider):
    provider_name = "failing_facts"

    async def get_company_facts(self, symbol: str) -> CompanyFactsResult:
        raise RuntimeError("facts provider unavailable")


class StaticNewsService:
    async def get_news(
        self,
        symbol: str,
        *,
        query: str | None = None,
        limit: int = 20,
        language: str = "en",
    ) -> NewsProviderResult:
        return NewsProviderResult(
            provider="static_news",
            status="available",
            source=DataSource(
                name="Static news",
                provider="static_news",
                status="available",
            ),
            items=[
                NewsArticle(
                    title=f"{symbol} earnings update",
                    source="Example Markets",
                    provider="static_news",
                    published_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
                    symbols=[symbol],
                    summary=query,
                )
            ],
        )


class FailingNewsService:
    async def get_news(self, *_args: Any, **_kwargs: Any) -> NewsProviderResult:
        raise RuntimeError("news unavailable")


def test_data_collector_writes_context_and_returns_typed_output() -> None:
    context = make_context()
    agent = DataCollectorAgent(
        price_provider=StaticPriceProvider(),
        facts_provider=StaticFactsProvider(),
        news_service=StaticNewsService(),
    )

    result = asyncio.run(agent.run(context))

    assert result.status == "completed"
    assert result.provider == "local"
    assert result.model == "deterministic"
    assert result.output is not None
    assert isinstance(result.output, DataCollectorOutput)
    assert context.market_data is not None
    assert context.market_data.symbol == "AAPL"
    assert len(context.market_data.price_history) == 30
    assert context.indicators is not None
    assert context.data_quality is not None
    assert context.data_quality.score == pytest.approx(1.0)
    assert context.data_quality.provider_names == [
        "static_prices",
        "static_facts",
        "static_news",
    ]


def test_data_collector_missing_price_data_is_partial_without_failing() -> None:
    context = make_context()
    agent = DataCollectorAgent(
        price_provider=StaticPriceProvider(bars=[]),
        facts_provider=StaticFactsProvider(),
        news_service=StaticNewsService(),
    )

    result = asyncio.run(agent.run(context))

    assert result.status == "partial"
    assert result.error_message is None
    assert context.market_data is not None
    assert context.market_data.price_history == []
    assert context.indicators is None
    assert context.data_quality is not None
    assert context.data_quality.price_data_status == "missing"
    assert context.data_quality.score == pytest.approx(0.5)
    assert "price_history" in context.data_quality.missing_data


def test_data_collector_preserves_partial_optional_provider_results() -> None:
    context = make_context()
    agent = DataCollectorAgent(
        price_provider=StaticPriceProvider(),
        facts_provider=FailingFactsProvider(),
        news_service=FailingNewsService(),
    )

    result = asyncio.run(agent.run(context))

    assert result.status == "completed"
    assert context.market_data is not None
    assert len(context.market_data.price_history) == 30
    assert context.data_quality is not None
    assert context.data_quality.fundamentals_status == "missing"
    assert context.data_quality.news_data_status == "missing"
    assert context.data_quality.score == pytest.approx(0.5)
    assert any("facts provider unavailable" in warning for warning in result.warnings)
    assert any("news unavailable" in warning for warning in result.warnings)


def test_data_collector_records_zero_cost_trace() -> None:
    context = make_context()
    agent = DataCollectorAgent(
        price_provider=FailingPriceProvider(),
        facts_provider=FailingFactsProvider(),
        news_service=FailingNewsService(),
    )

    result = asyncio.run(agent.run(context))

    assert result.status == "partial"
    assert result.estimated_cost_usd == 0
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert len(context.cost_traces) == 1
    assert context.cost_traces[0].provider == "local"
    assert context.cost_traces[0].model == "deterministic"
    assert context.cost_traces[0].estimated_cost_usd == 0
