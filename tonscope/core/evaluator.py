from __future__ import annotations

import re

VOWELS = set("aeiouy")


def evaluate_username(username: str) -> dict[str, int]:
    """Return 1-10 linguistic/brand heuristics, not a guaranteed sale prediction."""
    value = username.lower()
    if not re.fullmatch(r"[a-z]{5,7}", value):
        raise ValueError("Username must contain 5-7 lowercase Latin letters")

    length = len(value)
    vowel_count = sum(ch in VOWELS for ch in value)
    vowel_ratio = vowel_count / length
    alternating = sum(
        (value[i] in VOWELS) != (value[i - 1] in VOWELS)
        for i in range(1, length)
    ) / max(1, length - 1)
    repeated_penalty = sum(value[i] == value[i - 1] for i in range(1, length))
    rare_penalty = sum(ch in "qwx" for ch in value)

    pronounceability = round(max(1, min(10, 3 + alternating * 5 - rare_penalty * 0.7)))
    readability = round(max(1, min(10, 2 + min(vowel_ratio, 0.5) * 9 + alternating * 2 - repeated_penalty)))
    uniqueness = max(1, min(10, 5 + rare_penalty - repeated_penalty))
    brandability = max(1, min(10, round((readability + pronounceability + uniqueness) / 3)))

    # Short, easy-to-pronounce names are generally easier to remember.
    length_bonus = {5: 2, 6: 1, 7: 0}[length]
    liquidity = max(1, min(10, round(readability * 0.4 + pronounceability * 0.35 + brandability * 0.25 + length_bonus)))
    overall = round(readability * 0.30 + pronounceability * 0.25 + brandability * 0.20 + liquidity * 0.25)
    return {
        "readability": readability,
        "pronounceability": pronounceability,
        "uniqueness": uniqueness,
        "brandability": brandability,
        "liquidity": liquidity,
        "overall": overall,
    }
