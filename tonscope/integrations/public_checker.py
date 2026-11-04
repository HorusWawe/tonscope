from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_API = "https://tg-username-api.vercel.app/api/v1"


@dataclass(frozen=True)
class UsernameResult:
    username: str
    status: str
    fragment_status: str | None = None
    fragment_url: str | None = None
    fragment_price_ton: float | None = None
    detail: str | None = None


class PublicUsernameChecker:
    """Public Telegram + Fragment checker using the documented TG Username API.

    The upstream performs conservative checks against public Telegram pages and
    Fragment. It has a documented 25-request/minute limit and bulk size of 15.
    """

    def __init__(self, base_url: str = DEFAULT_API, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def check_many(self, usernames: list[str]) -> list[UsernameResult]:
        if not usernames:
            return []
        if len(usernames) > 15:
            raise ValueError("Bulk check accepts at most 15 usernames")
        payload = json.dumps({"usernames": usernames}).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/check/bulk",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "TONSCOPE/0.2"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After", "")
            raise RuntimeError(f"Checker HTTP {exc.code}; Retry-After={retry_after}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Checker network/response error: {exc}") from exc

        if not data.get("success") or not isinstance(data.get("results"), list):
            raise RuntimeError("Checker returned an invalid response")

        results: list[UsernameResult] = []
        for item in data["results"]:
            username = (item.get("username") or "").lower()
            summary = item.get("result") or {}
            verdict = summary.get("status", "unknown")
            fragment: dict[str, Any] = item.get("fragment") or {}
            frag_status = fragment.get("status")
            price = fragment.get("price") or {}
            auction = fragment.get("auction") or {}
            if not price:
                price = auction.get("minimum_bid") or auction.get("highest_bid") or {}
            amount = price.get("amount") if isinstance(price, dict) else None
            currency = (price.get("currency") or "TON").upper() if isinstance(price, dict) else "TON"
            price_ton = None
            if amount is not None and currency == "TON":
                try:
                    price_ton = float(amount)
                except (TypeError, ValueError):
                    price_ton = None

            if verdict == "available":
                status = "available"
            elif verdict == "taken":
                status = "occupied"
            elif verdict == "fragment_collectible":
                status = "auction" if frag_status == "on_auction" else "fragment_collectible"
            elif verdict == "invalid":
                status = "invalid"
            else:
                status = "check_error"

            detail = summary.get("explanation")
            error = (item.get("telegram") or {}).get("error") or fragment.get("error")
            if error:
                detail = f"{detail or ''} {error.get('code', '')}: {error.get('message', '')}".strip()
            results.append(UsernameResult(
                username=username,
                status=status,
                fragment_status=frag_status,
                fragment_url=fragment.get("url"),
                fragment_price_ton=price_ton,
                detail=detail,
            ))
        return results
