from __future__ import annotations

import math
from collections.abc import Sequence

from backend.app.orchestrator.schemas import BollingerBands
from backend.app.technicalindicators.indicators.common import (
    Number,
    clean_values,
    validate_period,
)


def bollinger_bands(
    values: Sequence[Number],
    *,
    period: int = 20,
    standard_deviations: float = 2,
) -> BollingerBands | None:
    validate_period(period)
    if standard_deviations <= 0:
        raise ValueError("standard_deviations must be greater than 0")

    clean = clean_values(values)
    if len(clean) < period:
        return None

    window = clean[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    standard_deviation = math.sqrt(variance)

    return BollingerBands(
        upper=middle + (standard_deviations * standard_deviation),
        middle=middle,
        lower=middle - (standard_deviations * standard_deviation),
    )
