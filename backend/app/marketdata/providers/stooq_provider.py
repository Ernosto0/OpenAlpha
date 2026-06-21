from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
from io import StringIO
from urllib.parse import urlencode

from backend.app.marketdata.base import (
    MarketDataProvider,
    MarketDataProviderError,
    PriceHistoryResult,
    PriceInterval,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import DataSource, PriceBar


class StooqProvider(MarketDataProvider):
    provider_name = "stooq"
    capabilities = (
        "historical_ohlcv",
        "chart_data",
        "technical_indicators",
        "backtesting",
    )
    base_url = "https://stooq.com/q/d/l/"

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        normalized_symbol = normalize_symbol(symbol)
        if interval not in {"1d", "1wk", "1mo"}:
            raise MarketDataProviderError(
                f"Stooq does not support interval {interval}",
                retryable=False,
            )

        url = self._history_url(
            normalized_symbol,
            start=start,
            end=end,
            interval=interval,
        )
        text = await self._fetch_text(url)
        bars = self._parse_csv(text)
        status = "available" if bars else "missing"
        warnings = (
            []
            if bars
            else [f"No Stooq price history returned for {normalized_symbol}."]
        )

        return PriceHistoryResult(
            symbol=normalized_symbol,
            provider=self.provider_name,
            status=status,
            bars=bars,
            source=DataSource(
                name="Historical OHLCV",
                provider=self.provider_name,
                status=status,
                url=url,
                notes=["No API key required. Stooq symbols may differ by market."],
            ),
            warnings=warnings,
        )

    def _history_url(
        self,
        symbol: str,
        *,
        start: date | None,
        end: date | None,
        interval: PriceInterval,
    ) -> str:
        params = {
            "s": self._stooq_symbol(symbol),
            "i": {"1d": "d", "1wk": "w", "1mo": "m"}[interval],
        }
        if start:
            params["d1"] = start.strftime("%Y%m%d")
        if end:
            params["d2"] = end.strftime("%Y%m%d")
        return f"{self.base_url}?{urlencode(params)}"

    def _stooq_symbol(self, symbol: str) -> str:
        lowered = symbol.lower()
        if "." in lowered:
            return lowered
        return f"{lowered}.us"

    def _parse_csv(self, text: str) -> list[PriceBar]:
        reader = csv.DictReader(StringIO(text.strip()))
        bars: list[PriceBar] = []

        for row in reader:
            if not row or row.get("Date") in {None, "No data"}:
                continue

            try:
                bar_date = datetime.combine(
                    datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                    time.min,
                    tzinfo=timezone.utc,
                )
                bars.append(
                    PriceBar(
                        timestamp=bar_date,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(float(row["Volume"])) if row.get("Volume") else None,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise MarketDataProviderError(
                    f"Could not parse Stooq OHLCV row: {row}",
                    retryable=False,
                ) from exc

        return bars
