from __future__ import annotations

import json
import time
import urllib.request


class CurrencyRates:
    """Small in-memory TON/USD and USD/RUB rate cache."""

    def __init__(self, ttl: int = 900):
        self.ttl = ttl
        self._updated = 0.0
        self._ton_usd: float | None = None
        self._usd_rub: float | None = None

    def refresh(self) -> tuple[float | None, float | None]:
        if time.monotonic() - self._updated < self.ttl:
            return self._ton_usd, self._usd_rub
        try:
            req = urllib.request.Request(
                "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd",
                headers={"User-Agent": "TONSCOPE/0.2"},
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                self._ton_usd = float(json.loads(response.read().decode())["the-open-network"]["usd"])
        except Exception:
            pass
        try:
            req = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={"User-Agent": "TONSCOPE/0.2"})
            with urllib.request.urlopen(req, timeout=12) as response:
                self._usd_rub = float(json.loads(response.read().decode())["rates"]["RUB"])
        except Exception:
            pass
        self._updated = time.monotonic()
        return self._ton_usd, self._usd_rub

    def convert(self, ton: float | None) -> tuple[float | None, float | None]:
        if ton is None:
            return None, None
        usd_rate, rub_rate = self.refresh()
        usd = ton * usd_rate if usd_rate is not None else None
        rub = usd * rub_rate if usd is not None and rub_rate is not None else None
        return usd, rub
