from __future__ import annotations

import asyncio
import builtins
import json
from datetime import date, datetime, timezone
from typing import Any

from backend.app.marketdata import get_default_market_data_provider
from backend.app.marketdata.base import (
    MarketDataConfigurationError,
    get_market_data_provider,
)
from backend.app.marketdata.providers.sec_provider import SECProvider
from backend.app.marketdata.providers.stooq_provider import StooqProvider
from backend.app.marketdata.providers.yahoo_provider import YahooProvider
from backend.app.marketdata.providers.yfinance_provider import YFinanceProvider


def test_default_market_data_provider_is_stooq() -> None:
    provider = get_default_market_data_provider()

    assert isinstance(provider, StooqProvider)
    assert provider.supports("historical_ohlcv")


def test_stooq_provider_parses_historical_ohlcv() -> None:
    calls: list[str] = []

    def transport(url: str, _headers: Any, _timeout: float) -> str:
        calls.append(url)
        return (
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100.0,110.0,95.0,108.5,123456\n"
        )

    provider = StooqProvider(transport=transport)
    result = asyncio.run(
        provider.get_price_history(
            "aapl",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )
    )

    assert result.provider == "stooq"
    assert result.symbol == "AAPL"
    assert result.status == "available"
    assert result.bars[0].close == 108.5
    assert result.bars[0].volume == 123456
    assert "s=aapl.us" in calls[0]
    assert "d1=20240101" in calls[0]


def test_yahoo_provider_normalizes_chart_response() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0],
                                "high": [105.0],
                                "low": [99.0],
                                "close": [104.0],
                                "volume": [500],
                            }
                        ],
                        "adjclose": [{"adjclose": [103.5]}],
                    },
                }
            ],
            "error": None,
        }
    }

    provider = YahooProvider(transport=lambda *_args: json.dumps(payload))
    result = asyncio.run(provider.get_price_history("msft"))

    assert result.provider == "yahoo"
    assert result.symbol == "MSFT"
    assert result.bars[0].adjusted_close == 103.5
    assert "unofficial" in result.warnings[0].lower()


def test_yfinance_provider_reports_missing_optional_dependency() -> None:
    original_import = builtins.__import__

    def missing_yfinance_import(
        name: str,
        globals_: Any = None,
        locals_: Any = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "yfinance":
            raise ImportError("No module named yfinance")
        return original_import(name, globals_, locals_, fromlist, level)

    builtins.__import__ = missing_yfinance_import
    try:
        try:
            asyncio.run(YFinanceProvider().get_price_history("aapl"))
        except MarketDataConfigurationError as exc:
            assert "yfinance is optional" in str(exc)
            assert exc.retryable is False
        else:
            raise AssertionError("YFinanceProvider should require yfinance")
    finally:
        builtins.__import__ = original_import


def test_sec_provider_returns_facts_financials_and_filings() -> None:
    def transport(url: str, _headers: Any, _timeout: float) -> str:
        if url.endswith("company_tickers.json"):
            return json.dumps(
                {
                    "0": {
                        "cik_str": 320193,
                        "ticker": "AAPL",
                        "title": "Apple Inc.",
                    }
                }
            )
        if "companyfacts" in url:
            return json.dumps(
                {
                    "cik": 320193,
                    "entityName": "Apple Inc.",
                    "facts": {
                        "us-gaap": {
                            "Revenues": {
                                "units": {
                                    "USD": [
                                        {
                                            "val": 1000,
                                            "form": "10-K",
                                            "end": "2024-09-28",
                                        }
                                    ]
                                }
                            },
                            "NetIncomeLoss": {
                                "units": {
                                    "USD": [
                                        {
                                            "val": 200,
                                            "form": "10-K",
                                            "end": "2024-09-28",
                                        }
                                    ]
                                }
                            },
                            "GrossProfit": {
                                "units": {
                                    "USD": [
                                        {
                                            "val": 450,
                                            "form": "10-K",
                                            "end": "2024-09-28",
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            )
        return json.dumps(
            {
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000320193-24-000123"],
                        "form": ["10-K"],
                        "filingDate": ["2024-11-01"],
                        "primaryDocument": ["aapl-20240928.htm"],
                    }
                }
            }
        )

    provider = SECProvider(transport=transport)
    result = asyncio.run(provider.get_company_facts("aapl"))

    assert result.provider == "sec_edgar"
    assert result.profile is not None
    assert result.profile.name == "Apple Inc."
    assert result.financials is not None
    assert result.financials.revenue == 1000
    assert result.financials.gross_margin == 0.45
    assert result.filings[0]["form"] == "10-K"


def test_user_api_provider_callbacks_are_callable_from_base_factory() -> None:
    timestamp = datetime(2024, 1, 2, tzinfo=timezone.utc)

    provider = get_market_data_provider(
        "user_api",
        user_callbacks={
            "get_price_history": lambda *_args, **_kwargs: [
                {"timestamp": timestamp, "close": 10.0}
            ]
        },
    )
    result = asyncio.run(provider.get_price_history("tsla"))

    assert result.provider == "user_api"
    assert result.symbol == "TSLA"
    assert result.bars[0].close == 10.0
