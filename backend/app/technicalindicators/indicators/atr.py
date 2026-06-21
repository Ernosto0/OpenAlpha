from __future__ import annotations

from collections.abc import Sequence

from backend.app.technicalindicators.indicators.common import (
    PriceBarInput,
    high,
    low,
    normalize_bars,
    to_float,
    validate_period,
)


def atr(bars: Sequence[PriceBarInput], period: int = 14) -> float | None:
    validate_period(period)
    normalized = normalize_bars(bars)
    if len(normalized) < period:
        return None

    true_ranges: list[float] = []
    previous_close: float | None = None
    for bar in normalized:
        high_value = high(bar)
        low_value = low(bar)
        if previous_close is None:
            true_range = high_value - low_value
        else:
            true_range = max(
                high_value - low_value,
                abs(high_value - previous_close),
                abs(low_value - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = to_float(bar.close)

    average_true_range = sum(true_ranges[:period]) / period
    for true_range in true_ranges[period:]:
        average_true_range = ((average_true_range * (period - 1)) + true_range) / period
    return average_true_range
