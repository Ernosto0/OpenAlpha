from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from backend.app.news import get_default_news_providers
from backend.app.news.base import (
    NewsArticle,
    NewsProviderResult,
    NewsService,
)
from backend.app.news.providers.alpha_vantage_provider import AlphaVantageNewsProvider
from backend.app.news.providers.finnhub_provider import FinnhubNewsProvider
from backend.app.news.providers.fmp_provider import FmpNewsProvider
from backend.app.news.providers.gdelt_provider import GDELTProvider
from backend.app.news.providers.polygon_provider import PolygonNewsProvider
from backend.app.news.providers.rss_provider import RSSProvider
from backend.app.news.providers.sec_edgar_provider import SecEdgarNewsProvider
from backend.app.news.providers.yahoo_finance_rss_provider import (
    YahooFinanceRssProvider,
)
from backend.app.orchestrator.schemas import DataSource


EXAMPLE_SYMBOL = "AAPL"


def test_default_news_providers_are_free_fallbacks() -> None:
    providers = get_default_news_providers()

    assert [provider.provider_name for provider in providers] == [
        "gdelt",
        "rss",
        "yahoo_finance_rss",
        "sec_edgar_news",
    ]


def test_gdelt_provider_parses_articles_for_example_stock() -> None:
    payload = {
        "articles": [
            {
                "title": "AAPL shares rise after earnings",
                "url": "https://example.com/aapl-earnings",
                "snippet": "Apple revenue beat investor expectations.",
                "sourceCommonName": "Example Markets",
                "domain": "example.com",
                "language": "English",
                "sourceCountry": "US",
                "seendate": "20240601T123000Z",
            }
        ]
    }

    calls: list[str] = []

    def transport(url: str, _headers: Any, _timeout: float) -> str:
        calls.append(url)
        return json.dumps(payload)

    provider = GDELTProvider(transport=transport)
    result = asyncio.run(
        provider.get_news(EXAMPLE_SYMBOL, query="earnings", limit=5)
    )

    assert result.provider == "gdelt"
    assert result.status == "available"
    assert result.items[0].title == "AAPL shares rise after earnings"
    assert result.items[0].symbols == [EXAMPLE_SYMBOL]
    assert result.items[0].published_at == datetime(
        2024, 6, 1, 12, 30, tzinfo=timezone.utc
    )
    assert "format=json" in calls[0]
    assert "maxrecords=15" in calls[0]


def test_curated_rss_provider_filters_relevant_items_for_example_stock() -> None:
    feed = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>AAPL unveils new product line</title>
        <link>https://example.com/aapl-product</link>
        <description>Apple shares moved in early trading.</description>
        <pubDate>Mon, 03 Jun 2024 14:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Broad market update</title>
        <link>https://example.com/market</link>
        <description>Indexes were mixed.</description>
      </item>
    </channel></rss>
    """

    provider = RSSProvider(
        feed_urls=["https://feeds.example.com/markets.xml"],
        transport=lambda *_args: feed,
    )
    result = asyncio.run(provider.get_news(EXAMPLE_SYMBOL, limit=10))

    assert result.provider == "rss"
    assert result.status == "available"
    assert len(result.items) == 1
    assert result.items[0].title == "AAPL unveils new product line"
    assert result.items[0].source == "feeds.example.com"
    assert result.items[0].symbols == [EXAMPLE_SYMBOL]


def test_yahoo_finance_rss_provider_builds_symbol_feed_and_warns_unofficial() -> None:
    feed = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Apple stock gains as AAPL demand improves</title>
        <link>https://finance.example.com/aapl</link>
        <source>Yahoo Finance</source>
        <description>Investors reacted to stronger sales.</description>
        <pubDate>Tue, 04 Jun 2024 15:30:00 GMT</pubDate>
      </item>
    </channel></rss>
    """
    calls: list[str] = []

    def transport(url: str, _headers: Any, _timeout: float) -> str:
        calls.append(url)
        return feed

    provider = YahooFinanceRssProvider(transport=transport)
    result = asyncio.run(provider.get_news("aapl", limit=1))

    assert result.provider == "yahoo_finance_rss"
    assert result.status == "available"
    assert result.items[0].provider == "yahoo_finance_rss"
    assert result.items[0].symbols == [EXAMPLE_SYMBOL]
    assert "s=AAPL" in calls[0]
    assert "unofficial" in result.warnings[0].lower()


def test_sec_edgar_news_provider_returns_recent_filings_as_news_events() -> None:
    def transport(url: str, _headers: Any, _timeout: float) -> str:
        if url.endswith("company_tickers.json"):
            return json.dumps(
                {
                    "0": {
                        "cik_str": 320193,
                        "ticker": EXAMPLE_SYMBOL,
                        "title": "Apple Inc.",
                    }
                }
            )
        return json.dumps(
            {
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000320193-24-000123"],
                        "form": ["10-Q"],
                        "filingDate": ["2024-05-03"],
                        "reportDate": ["2024-03-30"],
                        "primaryDocument": ["aapl-20240330.htm"],
                        "primaryDocDescription": ["Quarterly report"],
                    }
                }
            }
        )

    provider = SecEdgarNewsProvider(transport=transport)
    result = asyncio.run(provider.get_news(EXAMPLE_SYMBOL, limit=5))

    assert result.provider == "sec_edgar_news"
    assert result.status == "available"
    assert result.items[0].title == "Apple Inc. filed 10-Q: Quarterly report"
    assert result.items[0].source == "SEC EDGAR"
    assert result.items[0].event_type == "10-Q"
    assert result.items[0].url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/aapl-20240330.htm"
    )
    assert "official filings/events" in result.warnings[0].lower()


def test_placeholder_paid_news_provider_reports_missing_configuration() -> None:
    providers = [
        FinnhubNewsProvider(),
        AlphaVantageNewsProvider(),
        FmpNewsProvider(),
        PolygonNewsProvider(),
    ]

    for provider in providers:
        result = asyncio.run(provider.get_news(EXAMPLE_SYMBOL))

        assert result.provider == provider.provider_name
        assert result.status == "missing"
        assert result.items == []
        assert "not implemented" in result.warnings[0]


def test_news_service_dedupes_scores_and_preserves_partial_status() -> None:
    class StaticProvider:
        provider_name = "static"

        async def get_news(self, *_args: Any, **_kwargs: Any) -> NewsProviderResult:
            return NewsProviderResult(
                provider=self.provider_name,
                source=DataSource(
                    name="Static news",
                    provider=self.provider_name,
                    status="available",
                ),
                items=[
                    NewsArticle(
                        title="AAPL earnings beat expectations",
                        source="Example Markets",
                        provider=self.provider_name,
                        published_at=datetime(2024, 6, 5, tzinfo=timezone.utc),
                        url="https://example.com/aapl",
                        summary="Apple revenue rose.",
                        symbols=[EXAMPLE_SYMBOL],
                    ),
                    NewsArticle(
                        title="Duplicate",
                        source="Wire",
                        provider=self.provider_name,
                        url="https://example.com/aapl/",
                        relevance_score=0.1,
                        symbols=[EXAMPLE_SYMBOL],
                    ),
                ],
            )

    class FailingProvider:
        provider_name = "failing"

        async def get_news(self, *_args: Any, **_kwargs: Any) -> NewsProviderResult:
            raise RuntimeError("temporary failure")

    service = NewsService(  # type: ignore[list-item]
        providers=[StaticProvider(), FailingProvider()]
    )
    result = asyncio.run(service.get_news(EXAMPLE_SYMBOL, query="earnings", limit=5))

    assert result.provider == "news_service"
    assert result.status == "partial"
    assert len(result.items) == 1
    assert result.items[0].relevance_score > 0.9
    assert result.warnings == ["failing failed: temporary failure"]
