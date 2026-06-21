from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.marketdata.providers.stooq_provider import StooqProvider
from backend.app.orchestrator.schemas import PriceBar
from backend.app.technicalindicators import (
    atr,
    bollinger_bands,
    calculate_indicators,
    ema,
    ema_series,
    macd,
    rsi,
    sma,
    sma_series,
    support_resistance,
    volume_trend,
)


def _bar(
    day: int,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: int | None = 100,
) -> PriceBar:
    return PriceBar(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=day),
        open=close,
        high=high if high is not None else close + 1,
        low=low if low is not None else close - 1,
        close=close,
        volume=volume,
    )


def _stooq_csv_from_closes(closes: list[float]) -> str:
    rows = ["Date,Open,High,Low,Close,Volume"]
    start = date(2024, 1, 2)
    for index, close in enumerate(closes):
        bar_date = start + timedelta(days=index)
        volume = 1_000_000 + (index * 25_000)
        rows.append(
            ",".join(
                [
                    bar_date.isoformat(),
                    f"{close - 0.5:.2f}",
                    f"{close + 1.25:.2f}",
                    f"{close - 1.25:.2f}",
                    f"{close:.2f}",
                    str(volume),
                ]
            )
        )
    return "\n".join(rows)


def test_sma_and_ema_use_deterministic_windows() -> None:
    values = [1, 2, 3, 4, 5]

    assert sma(values, 3) == pytest.approx(4)
    assert sma_series(values, 3) == [None, None, 2, 3, 4]
    assert ema(values, 3) == pytest.approx(4)
    assert ema_series(values, 3) == [None, None, 2, 3, 4]


def test_rsi_uses_wilder_smoothing() -> None:
    closes = [
        44.34,
        44.09,
        44.15,
        43.61,
        44.33,
        44.83,
        45.10,
        45.42,
        45.84,
        46.08,
        45.89,
        46.03,
        45.61,
        46.28,
        46.28,
    ]

    assert rsi(closes, 14) == pytest.approx(70.46, abs=0.01)
    assert rsi([1, 2, 3, 4], 14) is None


def test_macd_returns_line_signal_and_histogram() -> None:
    result = macd(list(range(1, 41)))

    assert result.macd == pytest.approx(7.0)
    assert result.signal == pytest.approx(7.0)
    assert result.histogram == pytest.approx(0.0)


def test_bollinger_bands_use_population_standard_deviation() -> None:
    result = bollinger_bands(list(range(1, 21)), period=20)

    assert result is not None
    assert result.middle == pytest.approx(10.5)
    assert result.upper == pytest.approx(22.03256, abs=0.00001)
    assert result.lower == pytest.approx(-1.03256, abs=0.00001)


def test_atr_uses_true_range_and_wilder_smoothing() -> None:
    bars = [
        _bar(0, close=9, high=10, low=8),
        _bar(1, close=10, high=11, low=8.5),
        _bar(2, close=11, high=12, low=9),
        _bar(3, close=13, high=14, low=10),
    ]

    assert atr(bars, 3) == pytest.approx(3.0)


def test_volume_trend_compares_short_and_long_average_volume() -> None:
    bars = [
        _bar(day, close=100 + day, volume=100 if day < 15 else 200)
        for day in range(20)
    ]

    result = volume_trend(bars)

    assert result.direction == "increasing"
    assert result.short_average == pytest.approx(200)
    assert result.long_average == pytest.approx(125)
    assert result.ratio == pytest.approx(1.6)


def test_support_resistance_detects_clustered_pivots() -> None:
    closes = [10, 12, 9, 13, 9.1, 14, 10, 15, 11, 14.8, 12]
    bars = [
        _bar(
            day,
            close=close,
            high=close,
            low=close,
            volume=100,
        )
        for day, close in enumerate(closes)
    ]

    support, resistance = support_resistance(
        bars,
        window=1,
        max_levels=2,
        tolerance_pct=0.02,
    )

    assert support == [11.0, 9.05]
    assert resistance == [13.0, 14.9]


def test_calculate_indicators_returns_typed_bundle_with_warnings() -> None:
    bars = [
        _bar(day, close=100 + day, high=101 + day, low=99 + day, volume=100 + day)
        for day in range(60)
    ]

    bundle = calculate_indicators(" aapl ", bars, horizon="3m")

    assert bundle.symbol == "AAPL"
    assert bundle.horizon == "3m"
    assert bundle.rsi is not None
    assert bundle.rsi.signal == "bearish"
    assert bundle.rsi.explanation is not None
    assert "overbought" in bundle.rsi.explanation
    assert bundle.macd is not None
    assert bundle.moving_averages["20"] == pytest.approx(149.5)
    assert bundle.moving_averages["50"] == pytest.approx(134.5)
    assert "200" not in bundle.moving_averages
    assert bundle.bollinger_bands is not None
    assert bundle.atr == pytest.approx(2.0)
    assert bundle.volume_trend is not None
    assert bundle.volume_trend.direction == "increasing"
    assert "Not enough price history for SMA 200." in bundle.warnings


def test_calculate_indicators_warns_without_short_history_confidence() -> None:
    bars = [_bar(day, close=100 + day) for day in range(14)]

    bundle = calculate_indicators("MSFT", bars)

    assert bundle.rsi is None
    assert bundle.signals == []
    assert bundle.moving_averages == {}
    assert bundle.bollinger_bands is None
    assert bundle.macd.macd is None
    assert "Not enough price history for RSI 14." in bundle.warnings
    assert "Not enough price history for SMA 20." in bundle.warnings
    assert "Not enough volume history for volume trend." in bundle.warnings


def test_calculate_indicators_warns_when_volume_is_missing() -> None:
    bars = [_bar(day, close=100 + day, volume=None) for day in range(25)]

    bundle = calculate_indicators("MSFT", bars)

    assert bundle.volume_trend is not None
    assert bundle.volume_trend.direction == "insufficient_data"
    assert (
        "25 price bars are missing volume; volume trend may be incomplete."
        in bundle.warnings
    )
    assert "Not enough volume history for volume trend." in bundle.warnings


def test_calculate_indicators_accepts_marketdata_price_history_for_aapl() -> None:
    pattern = [0, 8, -6, 9, -7, 2]
    closes = [150 + (day * 0.6) + pattern[day % len(pattern)] for day in range(60)]
    calls: list[str] = []

    def transport(url: str, _headers: object, _timeout: float) -> str:
        calls.append(url)
        return _stooq_csv_from_closes(closes)

    provider = StooqProvider(transport=transport)
    price_history = asyncio.run(
        provider.get_price_history(
            "aapl",
            start=date(2024, 1, 2),
            end=date(2024, 3, 1),
        )
    )

    bundle = calculate_indicators(
        price_history.symbol,
        price_history.bars,
        horizon="1m",
    )

    assert provider.supports("technical_indicators")
    assert "s=aapl.us" in calls[0]
    assert price_history.provider == "stooq"
    assert price_history.symbol == "AAPL"
    assert price_history.status == "available"
    assert len(price_history.bars) == 60

    assert bundle.symbol == "AAPL"
    assert bundle.horizon == "1m"
    assert set(bundle.moving_averages) == {"20", "50"}
    assert bundle.moving_averages["20"] == pytest.approx(180.35)
    assert bundle.moving_averages["50"] == pytest.approx(171.56)
    assert bundle.rsi is not None
    assert bundle.rsi.signal in {"neutral", "bearish"}
    assert bundle.macd is not None
    assert bundle.macd.macd is not None
    assert bundle.macd.signal is not None
    assert bundle.macd.histogram is not None
    assert bundle.bollinger_bands is not None
    assert bundle.atr is not None
    assert bundle.volume_trend is not None
    assert bundle.volume_trend.direction == "increasing"
    assert bundle.support_levels
    assert bundle.resistance_levels
    assert bundle.signals == [bundle.rsi]
    assert "Not enough price history for SMA 200." in bundle.warnings
    assert (
        "Support/resistance levels are simple estimated levels, "
        "not exact price targets."
    ) in bundle.warnings
