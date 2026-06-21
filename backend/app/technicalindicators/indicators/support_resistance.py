from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from backend.app.technicalindicators.indicators.common import (
    PriceBarInput,
    high,
    low,
    normalize_bars,
    to_float,
    validate_period,
)


def support_resistance(
    bars: Sequence[PriceBarInput],
    *,
    window: int = 2,
    max_levels: int = 3,
    tolerance_pct: float = 0.015,
) -> tuple[list[float], list[float]]:
    validate_period(window)
    validate_period(max_levels)
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct must be greater than or equal to 0")

    normalized = normalize_bars(bars)
    if len(normalized) < (window * 2) + 1:
        return [], []

    support_candidates: list[float] = []
    resistance_candidates: list[float] = []
    for index in range(window, len(normalized) - window):
        surrounding = normalized[index - window : index] + normalized[
            index + 1 : index + window + 1
        ]
        low_value = low(normalized[index])
        high_value = high(normalized[index])

        if all(low_value <= low(bar) for bar in surrounding):
            support_candidates.append(low_value)
        if all(high_value >= high(bar) for bar in surrounding):
            resistance_candidates.append(high_value)

    last_close = to_float(normalized[-1].close)
    support_levels = _select_levels(
        support_candidates,
        max_levels=max_levels,
        tolerance_pct=tolerance_pct,
        last_close=last_close,
        side="support",
    )
    resistance_levels = _select_levels(
        resistance_candidates,
        max_levels=max_levels,
        tolerance_pct=tolerance_pct,
        last_close=last_close,
        side="resistance",
    )
    return support_levels, resistance_levels


def _select_levels(
    candidates: Sequence[float],
    *,
    max_levels: int,
    tolerance_pct: float,
    last_close: float,
    side: Literal["support", "resistance"],
) -> list[float]:
    filtered = [
        candidate
        for candidate in candidates
        if (candidate < last_close if side == "support" else candidate > last_close)
    ]
    if not filtered:
        return []

    clusters: list[list[float]] = []
    for candidate in sorted(filtered):
        for cluster in clusters:
            cluster_level = sum(cluster) / len(cluster)
            tolerance = abs(cluster_level) * tolerance_pct
            if abs(candidate - cluster_level) <= tolerance:
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])

    ranked = sorted(
        clusters,
        key=lambda cluster: (
            -len(cluster),
            abs((sum(cluster) / len(cluster)) - last_close),
        ),
    )
    levels = [round(sum(cluster) / len(cluster), 4) for cluster in ranked[:max_levels]]
    return sorted(levels, reverse=side == "support")
