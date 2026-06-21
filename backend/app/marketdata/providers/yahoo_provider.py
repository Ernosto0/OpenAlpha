from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from urllib.parse import urlencode

from backend.app.marketdata.base import (
    MarketDataProvider,
    MarketDataProviderError,
    PriceHistoryResult,
    PriceInterval,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import DataSource, PriceBar


class YahooProvider(MarketDataProvider):
    provider_name = "yahoo"
    capabilities = ("historical_ohlcv", "chart_data")
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        normalized_symbol = normalize_symbol(symbol)
        url = self._history_url(
            normalized_symbol,
            start=start,
            end=end,
            interval=interval,
        )
        text = await self._fetch_text(url)
        bars = self._parse_chart_response(text)
        status = "available" if bars else "missing"
        warnings = ["Yahoo Finance is an unofficial optional fallback."]
        if not bars:
            warnings.append(f"No Yahoo price history returned for {normalized_symbol}.")

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
                notes=["Unofficial fallback; not guaranteed."],
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
        start_dt = datetime.combine(
            start or date(1970, 1, 1),
            time.min,
            tzinfo=timezone.utc,
        )
        end_dt = datetime.combine(end or date.today(), time.max, tzinfo=timezone.utc)
        params = {
            "period1": int(start_dt.timestamp()),
            "period2": int(end_dt.timestamp()),
            "interval": interval,
            "events": "history",
        }
        return f"{self.base_url}/{symbol}?{urlencode(params)}"

    def _parse_chart_response(self, text: str) -> list[PriceBar]:
        try:
            payload = json.loads(text)
            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result["indicators"]["quote"][0]
            adjusted = (
                result.get("indicators", {})
                .get("adjclose", [{}])[0]
                .get("adjclose", [])
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise MarketDataProviderError(
                "Could not parse Yahoo chart response",
                retryable=True,
            ) from exc

        bars: list[PriceBar] = []
        for index, timestamp in enumerate(timestamps):
            close = self._value_at(quote.get("close"), index)
            if close is None:
                continue
            bars.append(
                PriceBar(
                    timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    open=self._value_at(quote.get("open"), index),
                    high=self._value_at(quote.get("high"), index),
                    low=self._value_at(quote.get("low"), index),
                    close=close,
                    adjusted_close=self._value_at(adjusted, index),
                    volume=self._int_value_at(quote.get("volume"), index),
                )
            )
        return bars

    def _value_at(self, values: list[float | None] | None, index: int) -> float | None:
        if values is None or index >= len(values) or values[index] is None:
            return None
        return float(values[index])

    def _int_value_at(self, values: list[int | None] | None, index: int) -> int | None:
        value = self._value_at(values, index)
        return int(value) if value is not None else None
