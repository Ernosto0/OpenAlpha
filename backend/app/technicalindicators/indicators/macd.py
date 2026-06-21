from __future__ import annotations

from collections.abc import Sequence

from backend.app.orchestrator.schemas import MacdValue
from backend.app.technicalindicators.indicators.common import (
    Number,
    clean_values,
    validate_period,
)
from backend.app.technicalindicators.indicators.ema import ema, ema_series


def macd(
    values: Sequence[Number],
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MacdValue:
    validate_period(fast_period)
    validate_period(slow_period)
    validate_period(signal_period)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")

    clean = clean_values(values)
    fast = ema_series(clean, fast_period)
    slow = ema_series(clean, slow_period)

    macd_series_values: list[float] = []
    for fast_value, slow_value in zip(fast, slow, strict=False):
        if fast_value is None or slow_value is None:
            continue
        macd_series_values.append(fast_value - slow_value)

    macd_value = macd_series_values[-1] if macd_series_values else None
    signal_value = ema(macd_series_values, signal_period)
    histogram = (
        macd_value - signal_value
        if macd_value is not None and signal_value is not None
        else None
    )

    return MacdValue(macd=macd_value, signal=signal_value, histogram=histogram)
