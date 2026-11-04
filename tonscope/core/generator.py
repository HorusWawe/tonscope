from __future__ import annotations

import random
import re
from collections.abc import Iterator

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwxz"

# Short pronounceable patterns. They intentionally avoid punctuation and digits.
PATTERNS = (
    "CVCVC", "CVCCV", "CVCVCV", "VCVCV", "CVCVCC",
    "CVVCV", "CCVCV", "CVCV", "VCVCVC", "CVCCVC",
)

SYLLABLES = (
    "su", "sa", "se", "so", "la", "le", "li", "lo", "ra", "re",
    "ri", "ro", "va", "ve", "vi", "vo", "na", "ne", "ni", "no",
    "ka", "ke", "ki", "ko", "ta", "te", "ti", "to", "ma", "me",
    "mi", "mo", "da", "de", "di", "do", "za", "ze", "zi", "zo",
    "lu", "nu", "ru", "saq", "qua", "ari", "ora", "iva", "ena",
)

SEED_WORDS = (
    "durov", "satoshi", "vanta", "nexus", "lumen", "sonar",
    "velar", "aeris", "novus", "sable", "atlas", "orion",
)


class UsernameGenerator:
    def __init__(self, length: int = 6, mode: str = "readable", seed: int | None = None):
        if length not in (5, 6, 7):
            raise ValueError("Length must be 5, 6 or 7")
        if mode not in {"readable", "words", "brand", "random"}:
            raise ValueError("Unknown generation mode")
        self.length = length
        self.mode = mode
        self.random = random.Random(seed)

    def _pattern_word(self) -> str:
        pattern = self.random.choice(PATTERNS)
        chars = []
        for kind in pattern:
            chars.append(self.random.choice(VOWELS if kind == "V" else CONSONANTS))
        word = "".join(chars)
        if len(word) > self.length:
            word = word[:self.length]
        while len(word) < self.length:
            word += self.random.choice(VOWELS if len(word) % 2 else CONSONANTS)
        return word

    def _syllable_word(self) -> str:
        result = ""
        while len(result) < self.length:
            result += self.random.choice(SYLLABLES)
        return result[:self.length]

    def _word_variant(self) -> str:
        words = [w for w in SEED_WORDS if len(w) == self.length]
        if words and self.random.random() < 0.35:
            return self.random.choice(words)
        return self._syllable_word()

    def generate(self) -> str:
        if self.mode == "random":
            return "".join(self.random.choice(ALPHABET) for _ in range(self.length))
        if self.mode == "words":
            return self._word_variant()
        if self.mode == "brand":
            return self._syllable_word()
        return self._pattern_word()

    def stream(self) -> Iterator[str]:
        # Uniqueness is enforced by SQLite so STOP remains responsive even if a
        # small word/syllable pool starts producing duplicates repeatedly.
        while True:
            candidate = self.generate()
            if re.fullmatch(r"[a-z]{%d}" % self.length, candidate):
                yield candidate
