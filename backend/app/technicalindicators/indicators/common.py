from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from backend.app.orchestrator.schemas import PriceBar


Number = float | int
PriceBarInput = PriceBar | Mapping[str, Any]


def to_float(value: Number) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("indicator inputs must be finite numbers")
    return result


def clean_values(values: Sequence[Number]) -> list[float]:
    if not values:
        return []
    return [to_float(value) for value in values]


def validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be greater than 0")


def normalize_bars(bars: Sequence[PriceBarInput]) -> list[PriceBar]:
    normalized = [
        bar if isinstance(bar, PriceBar) else PriceBar.model_validate(bar)
        for bar in bars
    ]
    return sorted(normalized, key=lambda bar: bar.timestamp)


def high(bar: PriceBar) -> float:
    return to_float(bar.high if bar.high is not None else bar.close)


def low(bar: PriceBar) -> float:
    return to_float(bar.low if bar.low is not None else bar.close)
