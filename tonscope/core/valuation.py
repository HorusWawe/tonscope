from __future__ import annotations

from statistics import median


def comparable_range(prices_ton: list[float], minimum_samples: int = 3) -> tuple[float, float] | None:
    """Range from observed active Fragment asks, never a fabricated appraisal."""
    clean = sorted(value for value in prices_ton if value > 0)
    if len(clean) < minimum_samples:
        return None
    if len(clean) < 4:
        return round(clean[0], 3), round(clean[-1], 3)
    low = clean[max(0, int((len(clean) - 1) * 0.25))]
    high = clean[min(len(clean) - 1, int((len(clean) - 1) * 0.75))]
    return round(low, 3), round(high, 3)
