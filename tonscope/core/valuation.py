from __future__ import annotations

from statistics import median


def comparable_range(prices_ton: list[float], minimum_samples: int = 3) -> tuple[float, float] | None:
    """Return a conservative interquartile range from observed active Fragment asks.

    These are comparable asking prices, not a guaranteed sale value. No estimate
    is produced when there are too few observed listings.
    """
    clean = sorted(value for value in prices_ton if value > 0)
    if len(clean) < minimum_samples:
        return None
    if len(clean) < 4:
        center = median(clean)
        return round(center * 0.75, 3), round(center * 1.25, 3)
    low = clean[max(0, int((len(clean) - 1) * 0.25))]
    high = clean[min(len(clean) - 1, int((len(clean) - 1) * 0.75))]
    return round(low, 3), round(high, 3)
