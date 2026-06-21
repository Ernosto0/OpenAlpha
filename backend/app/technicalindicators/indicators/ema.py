from __future__ import annotations

from collections.abc import Sequence

from backend.app.technicalindicators.indicators.common import (
    Number,
    clean_values,
    validate_period,
)


def ema(values: Sequence[Number], period: int) -> float | None:
    series = ema_series(values, period)
    for value in reversed(series):
        if value is not None:
            return value
    return None


def ema_series(values: Sequence[Number], period: int) -> list[float | None]:
    validate_period(period)
    clean = clean_values(values)
    if len(clean) < period:
        return [None for _ in clean]

    multiplier = 2 / (period + 1)
    series: list[float | None] = [None for _ in range(period - 1)]
    previous_ema = sum(clean[:period]) / period
    series.append(previous_ema)

    for value in clean[period:]:
        previous_ema = (value - previous_ema) * multiplier + previous_ema
        series.append(previous_ema)

    return series
