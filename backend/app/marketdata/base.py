from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.orchestrator.schemas import (
    CompanyProfile,
    DataSource,
    FinancialSnapshot,
    PriceBar,
    normalize_symbol_value,
)


MarketDataStatus = Literal["available", "partial", "missing"]
PriceInterval = Literal["1d", "1wk", "1mo"]
ProviderCapability = Literal[
    "historical_ohlcv",
    "chart_data",
    "technical_indicators",
    "backtesting",
    "company_profile",
    "financials",
    "filings",
    "company_facts",
]
TextTransport = Callable[[str, Mapping[str, str] | None, float], str]
AsyncTextTransport = Callable[[str, Mapping[str, str] | None, float], Awaitable[str]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDataProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class MarketDataConfigurationError(MarketDataProviderError):
    pass


class MarketDataResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    status: MarketDataStatus = "available"
    source: DataSource
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=utc_now)


class PriceHistoryResult(MarketDataResult):
    symbol: str = Field(min_length=1, max_length=32)
    bars: list[PriceBar] = Field(default_factory=list)

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> Any:
        return normalize_symbol_value(value)


class CompanyFactsResult(MarketDataResult):
    symbol: str = Field(min_length=1, max_length=32)
    profile: CompanyProfile | None = None
    financials: FinancialSnapshot | None = None
    filings: list[dict[str, Any]] = Field(default_factory=list)
    company_facts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> Any:
        return normalize_symbol_value(value)


class MarketDataProvider(ABC):
    provider_name: str
    capabilities: tuple[ProviderCapability, ...] = ()

    def __init__(
        self,
        *,
        timeout_seconds: float = 20,
        transport: TextTransport | AsyncTextTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @abstractmethod
    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        raise NotImplementedError

    async def get_chart_data(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        return await self.get_price_history(
            symbol,
            start=start,
            end=end,
            interval=interval,
        )

    async def get_company_facts(self, symbol: str) -> CompanyFactsResult:
        normalized = normalize_symbol_value(symbol)
        source = DataSource(
            name="Company facts",
            provider=self.provider_name,
            status="missing",
            notes=["Provider does not implement company facts."],
        )
        return CompanyFactsResult(
            symbol=normalized,
            provider=self.provider_name,
            status="missing",
            source=source,
            warnings=["Provider does not implement company facts."],
        )

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    async def _fetch_text(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        if self.transport is None:
            return await asyncio.to_thread(
                default_text_transport,
                url,
                headers,
                self.timeout_seconds,
            )

        result = self.transport(url, headers, self.timeout_seconds)
        if asyncio.iscoroutine(result):
            return await result
        return result


def default_text_transport(
    url: str,
    headers: Mapping[str, str] | None,
    timeout_seconds: float,
) -> str:
    from urllib.request import Request, urlopen

    request = Request(url, headers=dict(headers or {}))
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def normalize_symbol(symbol: str) -> str:
    return normalize_symbol_value(symbol)


def get_default_market_data_provider() -> MarketDataProvider:
    from backend.app.marketdata.providers.stooq_provider import StooqProvider

    return StooqProvider()


def get_market_data_provider(
    provider_name: str = "stooq",
    *,
    user_callbacks: Mapping[str, Callable[..., Any]] | None = None,
) -> MarketDataProvider:
    normalized = provider_name.strip().lower().replace("-", "_")

    if normalized == "stooq":
        from backend.app.marketdata.providers.stooq_provider import StooqProvider

        return StooqProvider()
    if normalized == "yahoo":
        from backend.app.marketdata.providers.yahoo_provider import YahooProvider

        return YahooProvider()
    if normalized in {"yfinance", "yahoo_finance"}:
        from backend.app.marketdata.providers.yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    if normalized in {"sec", "sec_edgar", "edgar"}:
        from backend.app.marketdata.providers.sec_provider import SECProvider

        return SECProvider()
    if normalized in {"user", "user_api", "custom"}:
        from backend.app.marketdata.providers.user_api_provider import UserApiProvider

        return UserApiProvider(callbacks=user_callbacks or {})

    raise MarketDataConfigurationError(f"Unknown market data provider: {provider_name}")


async def get_price_history(
    symbol: str,
    *,
    provider_name: str = "stooq",
    start: date | None = None,
    end: date | None = None,
    interval: PriceInterval = "1d",
) -> PriceHistoryResult:
    provider = get_market_data_provider(provider_name)
    return await provider.get_price_history(
        symbol,
        start=start,
        end=end,
        interval=interval,
    )


__all__ = [
    "CompanyFactsResult",
    "MarketDataConfigurationError",
    "MarketDataProvider",
    "MarketDataProviderError",
    "MarketDataResult",
    "MarketDataStatus",
    "PriceHistoryResult",
    "PriceInterval",
    "ProviderCapability",
    "TextTransport",
    "get_default_market_data_provider",
    "get_market_data_provider",
    "get_price_history",
    "normalize_symbol",
]
