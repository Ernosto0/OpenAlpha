from __future__ import annotations

from collections.abc import Sequence

from backend.app.technicalindicators.indicators.common import (
    Number,
    clean_values,
    validate_period,
)


def sma(values: Sequence[Number], period: int) -> float | None:
    validate_period(period)
    clean = clean_values(values)
    if len(clean) < period:
        return None
    return sum(clean[-period:]) / period


def sma_series(values: Sequence[Number], period: int) -> list[float | None]:
    validate_period(period)
    clean = clean_values(values)
    series: list[float | None] = []
    for index in range(len(clean)):
        if index + 1 < period:
            series.append(None)
            continue
        window = clean[index + 1 - period : index + 1]
        series.append(sum(window) / period)
    return series
