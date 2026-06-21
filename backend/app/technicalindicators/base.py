from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from backend.app.orchestrator.schemas import (
    Horizon,
    IndicatorBundle,
    IndicatorSignal,
    normalize_symbol_value,
)
from backend.app.technicalindicators.indicators import (
    PriceBarInput,
    atr,
    bollinger_bands,
    ema,
    ema_series,
    macd,
    normalize_bars,
    rsi,
    sma,
    sma_series,
    support_resistance,
    to_float,
    volume_trend,
)


def calculate_indicators(
    symbol: str,
    bars: Sequence[PriceBarInput],
    *,
    horizon: Horizon = "1m",
    sma_periods: Sequence[int] = (20, 50, 200),
) -> IndicatorBundle:
    normalized_symbol = normalize_symbol_value(symbol)
    normalized_bars = normalize_bars(bars)
    closes = [to_float(bar.close) for bar in normalized_bars]
    warnings: list[str] = []
    missing_volume_count = sum(1 for bar in normalized_bars if bar.volume is None)
    if missing_volume_count:
        warnings.append(
            f"{missing_volume_count} price bars are missing volume; "
            "volume trend may be incomplete."
        )

    moving_averages: dict[str, float] = {}
    for period in sma_periods:
        value = sma(closes, period)
        if value is None:
            warnings.append(f"Not enough price history for SMA {period}.")
            continue
        moving_averages[str(period)] = value

    rsi_value = rsi(closes)
    rsi_signal = None
    if rsi_value is None:
        warnings.append("Not enough price history for RSI 14.")
    else:
        rsi_signal = IndicatorSignal(
            name="RSI",
            value=rsi_value,
            signal=_rsi_signal(rsi_value),
            explanation=_rsi_explanation(rsi_value),
        )

    macd_value = macd(closes)
    if macd_value.macd is None:
        warnings.append("Not enough price history for MACD.")
    elif macd_value.signal is None:
        warnings.append("Not enough MACD history for signal line.")

    bands = bollinger_bands(closes)
    if bands is None:
        warnings.append("Not enough price history for Bollinger Bands 20.")

    atr_value = atr(normalized_bars)
    if atr_value is None:
        warnings.append("Not enough price history for ATR 14.")

    volume = volume_trend(normalized_bars)
    if volume.direction == "insufficient_data":
        warnings.append("Not enough volume history for volume trend.")

    support_levels, resistance_levels = support_resistance(normalized_bars)
    if support_levels or resistance_levels:
        warnings.append(
            "Support/resistance levels are simple estimated levels, "
            "not exact price targets."
        )
    if not support_levels:
        warnings.append("No support levels detected.")
    if not resistance_levels:
        warnings.append("No resistance levels detected.")

    signals = [signal for signal in [rsi_signal] if signal is not None]

    return IndicatorBundle(
        symbol=normalized_symbol,
        horizon=horizon,
        rsi=rsi_signal,
        macd=macd_value,
        moving_averages=moving_averages,
        bollinger_bands=bands,
        atr=atr_value,
        volume_trend=volume,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        signals=signals,
        warnings=warnings,
    )


def _rsi_signal(value: float) -> Literal[
    "bullish",
    "neutral",
    "bearish",
    "insufficient_data",
]:
    if value < 30:
        return "bullish"
    if value > 70:
        return "bearish"
    return "neutral"


def _rsi_explanation(value: float) -> str:
    if value < 30:
        return "RSI is oversold; values below 30 can indicate bullish mean-reversion risk."
    if value > 70:
        return "RSI is overbought; values above 70 can indicate bearish mean-reversion risk."
    return "RSI is neutral; values below 30 are oversold and above 70 are overbought."


__all__ = [
    "PriceBarInput",
    "atr",
    "bollinger_bands",
    "calculate_indicators",
    "ema",
    "ema_series",
    "macd",
    "rsi",
    "sma",
    "sma_series",
    "support_resistance",
    "volume_trend",
]
