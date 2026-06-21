from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from backend.app.orchestrator.schemas import VolumeTrendValue
from backend.app.technicalindicators.indicators.common import (
    PriceBarInput,
    normalize_bars,
    validate_period,
)


VolumeTrendDirection = Literal[
    "increasing",
    "decreasing",
    "flat",
    "insufficient_data",
]


def volume_trend(
    bars: Sequence[PriceBarInput],
    *,
    short_period: int = 5,
    long_period: int = 20,
    threshold: float = 0.05,
) -> VolumeTrendValue:
    validate_period(short_period)
    validate_period(long_period)
    if short_period >= long_period:
        raise ValueError("short_period must be less than long_period")
    if threshold < 0:
        raise ValueError("threshold must be greater than or equal to 0")

    normalized = normalize_bars(bars)
    volumes = [float(bar.volume) for bar in normalized if bar.volume is not None]
    if len(volumes) < long_period:
        return VolumeTrendValue(direction="insufficient_data")

    short_average = sum(volumes[-short_period:]) / short_period
    long_average = sum(volumes[-long_period:]) / long_period
    if long_average == 0:
        direction: VolumeTrendDirection = "flat"
        ratio = 1.0
    else:
        ratio = short_average / long_average
        if ratio > 1 + threshold:
            direction = "increasing"
        elif ratio < 1 - threshold:
            direction = "decreasing"
        else:
            direction = "flat"

    return VolumeTrendValue(
        direction=direction,
        short_average=short_average,
        long_average=long_average,
        ratio=ratio,
    )
