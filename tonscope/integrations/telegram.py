from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TelegramStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    ERROR = "check_error"


@dataclass(frozen=True)
class TelegramCheckResult:
    username: str
    status: TelegramStatus
    detail: str = ""


class TelegramUsernameChecker:
    """Checks basic usernames using an already-authorized Telethon client.

    The caller owns the client/session lifecycle. A successful CheckUsername
    response means the name can currently be assigned as a basic username.
    Collectible usernames and Fragment auction state are checked separately.
    """

    def __init__(self, client: Any):
        self.client = client

    async def check(self, username: str) -> TelegramCheckResult:
        clean = username.removeprefix("@").lower()
        if not clean.isascii() or not clean.isalpha() or len(clean) not in (5, 6, 7):
            return TelegramCheckResult(clean, TelegramStatus.INVALID, "Expected 5-7 lowercase Latin letters")

        try:
            from telethon import functions, errors

            available = await self.client(functions.account.CheckUsernameRequest(username=clean))
            status = TelegramStatus.AVAILABLE if available else TelegramStatus.OCCUPIED
            return TelegramCheckResult(clean, status)
        except Exception as exc:
            try:
                from telethon import errors
                if isinstance(exc, errors.UsernameOccupiedError):
                    return TelegramCheckResult(clean, TelegramStatus.OCCUPIED, str(exc))
                if isinstance(exc, errors.UsernameInvalidError):
                    return TelegramCheckResult(clean, TelegramStatus.INVALID, str(exc))
                if isinstance(exc, errors.FloodWaitError):
                    return TelegramCheckResult(clean, TelegramStatus.RATE_LIMITED, f"Retry after {exc.seconds}s")
            except ImportError:
                pass
            return TelegramCheckResult(clean, TelegramStatus.ERROR, str(exc))
