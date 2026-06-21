from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.marketdata.base import (
    MarketDataConfigurationError,
    MarketDataProvider,
    PriceHistoryResult,
    PriceInterval,
    normalize_symbol,
)
from backend.app.orchestrator.schemas import DataSource, PriceBar


class YFinanceProvider(MarketDataProvider):
    provider_name = "yfinance"
    capabilities = ("historical_ohlcv", "chart_data")

    async def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        interval: PriceInterval = "1d",
    ) -> PriceHistoryResult:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise MarketDataConfigurationError(
                "yfinance is optional and is not installed. Install it locally "
                "to enable this adapter.",
                retryable=False,
            ) from exc

        normalized = normalize_symbol(symbol)
        ticker = yf.Ticker(normalized)
        history = ticker.history(
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
            interval=interval,
            auto_adjust=False,
        )

        bars: list[PriceBar] = []
        for timestamp, row in history.iterrows():
            bars.append(
                PriceBar(
                    timestamp=timestamp.to_pydatetime(),
                    open=self._row_value(row, "Open"),
                    high=self._row_value(row, "High"),
                    low=self._row_value(row, "Low"),
                    close=float(row["Close"]),
                    adjusted_close=self._row_value(row, "Adj Close"),
                    volume=(
                        int(row["Volume"])
                        if "Volume" in row and row["Volume"] == row["Volume"]
                        else None
                    ),
                )
            )

        status = "available" if bars else "missing"
        return PriceHistoryResult(
            symbol=normalized,
            provider=self.provider_name,
            status=status,
            bars=bars,
            source=DataSource(
                name="Historical OHLCV",
                provider=self.provider_name,
                status=status,
                notes=[
                    "Optional local yfinance adapter; not default and not guaranteed."
                ],
            ),
            warnings=["yfinance is optional, unofficial, and not guaranteed."],
        )

    def _row_value(self, row: Any, key: str) -> float | None:
        if key not in row or row[key] != row[key]:
            return None
        return float(row[key])
