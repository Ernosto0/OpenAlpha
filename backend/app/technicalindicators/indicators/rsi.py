from __future__ import annotations

from collections.abc import Sequence

from backend.app.technicalindicators.indicators.common import (
    Number,
    clean_values,
    validate_period,
)


def rsi(values: Sequence[Number], period: int = 14) -> float | None:
    validate_period(period)
    clean = clean_values(values)
    if len(clean) <= period:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(clean, clean[1:], strict=False):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:], strict=False):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period

    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0

    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))
