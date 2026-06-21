from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from backend.app.marketdata.base import (
    CompanyFactsResult,
    MarketDataConfigurationError,
    MarketDataProvider,
    PriceHistoryResult,
    PriceInterval,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import DataSource, PriceBar


class UserApiProvider(MarketDataProvider):
    provider_name = "user_api"
    capabilities = (
        "historical_ohlcv",
        "chart_data",
        "company_profile",
        "financials",
        "filings",
        "company_facts",
    )

    def __init__(
        self,
        *,
        callbacks: Mapping[str, Callable[..., Any]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.callbacks = dict(callbacks)

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        callback = self.callbacks.get("get_price_history")
        normalized = normalize_symbol(symbol)
        if callback is None:
            raise MarketDataConfigurationError(
                "UserApiProvider requires a get_price_history callback.",
                retryable=False,
            )

        raw_bars = callback(
            normalized,
            start=start,
            end=end,
            interval=interval,
        )
        if asyncio.iscoroutine(raw_bars):
            raw_bars = await raw_bars

        if isinstance(raw_bars, PriceHistoryResult):
            return raw_bars

        bars = [
            bar if isinstance(bar, PriceBar) else PriceBar.model_validate(bar)
            for bar in raw_bars
        ]
        status = "available" if bars else "missing"
        return PriceHistoryResult(
            symbol=normalized,
            provider=self.provider_name,
            status=status,
            bars=bars,
            source=DataSource(
                name="User API historical OHLCV",
                provider=self.provider_name,
                status=status,
                notes=["User-supplied provider callback."],
            ),
        )

    async def get_company_facts(self, symbol: str) -> CompanyFactsResult:
        callback = self.callbacks.get("get_company_facts")
        normalized = normalize_symbol(symbol)
        if callback is None:
            return await super().get_company_facts(normalized)

        result = callback(normalized)
        if asyncio.iscoroutine(result):
            result = await result
        if isinstance(result, CompanyFactsResult):
            return result
        return CompanyFactsResult.model_validate(result)
