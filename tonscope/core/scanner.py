from __future__ import annotations

import time
from PySide6.QtCore import QThread, Signal

from tonscope.core.evaluator import evaluate_username
from tonscope.core.generator import UsernameGenerator
from tonscope.core.rates import CurrencyRates
from tonscope.integrations.public_checker import PublicUsernameChecker
from tonscope.storage.database import Database


class ScanWorker(QThread):
    candidate_checked = Signal(str, str, dict)
    progress = Signal(int, int, int)
    message = Signal(str)
    finished_summary = Signal(dict)

    def __init__(self, database: Database, length: int, mode: str, target_free: int,
                 min_score: int, requests_per_minute: int, api_url: str):
        super().__init__()
        self.database = database
        self.length = length
        self.mode = mode
        self.target_free = target_free
        self.min_score = min_score
        self.requests_per_minute = max(1, min(24, requests_per_minute))
        self.api_url = api_url
        self._stop_requested = False
        self.mixed_lengths = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        checker = PublicUsernameChecker(self.api_url, timeout=12)
        lengths = (5, 6, 7) if self.mixed_lengths else (self.length,)
        iterators = {n: UsernameGenerator(n, self.mode).stream() for n in lengths}
        batch = []
        checked = available = processed = generated = 0
        last_request = 0.0
        duplicate_streak = 0
        pool_exhausted = False
        self.message.emit("Generating candidates and preparing live checks…")

        def flush():
            nonlocal checked, available, last_request
            if not batch:
                return True
            wait = max(0.0, 60.0 / self.requests_per_minute - (time.monotonic() - last_request))
            until = time.monotonic() + wait
            while not self._stop_requested and time.monotonic() < until:
                time.sleep(min(0.2, max(0.0, until - time.monotonic())))
            if self._stop_requested:
                return False
            names = list(batch)
            batch.clear()
            try:
                results = checker.check_many(names)
                last_request = time.monotonic()
                for result in results:
                    self.database.record_check(
                        result.username, result.status, fragment_status=result.fragment_status,
                        fragment_url=result.fragment_url, fragment_price_ton=result.fragment_price_ton,
                        detail=result.detail,
                    )
                    checked += 1
                    available += int(result.status == "available")
                    row = next((x for x in self.database.list_usernames("all", 10000) if x["username"] == result.username), {"username": result.username})
                    self.candidate_checked.emit(result.username, result.status, row)
                self.progress.emit(checked, available, processed)
                self.message.emit(f"Checked {checked} · free {available} · generated {generated}")
            except Exception as exc:
                last_request = time.monotonic()
                for name in names:
                    self.database.record_check(name, "check_error", detail=str(exc))
                    checked += 1
                    self.candidate_checked.emit(name, "check_error", {"username": name, "check_detail": str(exc)})
                self.message.emit(f"API error; results saved for manual recheck: {exc}")
                self.progress.emit(checked, available, processed)
            return True

        try:
            while not self._stop_requested:
                progressed = False
                for length in lengths:
                    if self._stop_requested:
                        break
                    username = next(iterators[length])
                    processed += 1
                    progressed = True
                    existing = self.database.get_username(username)
                    if existing and existing["status"] not in ("candidate", "check_error"):
                        duplicate_streak += 1
                        if duplicate_streak >= 500:
                            pool_exhausted = True
                            self.message.emit("No unseen candidates in this generation pool. Change style or length to continue.")
                            break
                        continue
                    duplicate_streak = 0
                    scores = evaluate_username(username)
                    if scores["overall"] < self.min_score:
                        continue
                    if not existing:
                        self.database.add_candidate(username, scores)
                    generated += 1
                    batch.append(username)
                    if len(batch) >= 15:
                        if not flush():
                            break
                        if self.target_free and available >= self.target_free:
                            break
                if pool_exhausted or (self.target_free and available >= self.target_free):
                    break
                if not progressed:
                    break
        except Exception as exc:
            self.message.emit(f"Scan error: {exc}")
        if not self._stop_requested and batch and (not self.target_free or available < self.target_free):
            flush()
        self.finished_summary.emit({
            "checked": checked, "available": available, "generated": generated,
            "processed": processed, "stopped": self._stop_requested,
        })
        self.message.emit(f"Finished · checked {checked} · free {available}. Results saved in profile.")


class RecheckWorker(QThread):
    candidate_checked = Signal(str, str, dict)
    message = Signal(str)
    finished_summary = Signal(dict)

    def __init__(self, database: Database, usernames: list[str], requests_per_minute: int, api_url: str):
        super().__init__()
        self.database = database
        self.usernames = list(dict.fromkeys(usernames))
        self.requests_per_minute = max(1, min(24, requests_per_minute))
        self.api_url = api_url
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        checker = PublicUsernameChecker(self.api_url, timeout=12)
        checked = available = 0
        last_request = 0.0
        for start in range(0, len(self.usernames), 15):
            if self._stop_requested:
                break
            batch = self.usernames[start:start + 15]
            wait = max(0.0, 60.0 / self.requests_per_minute - (time.monotonic() - last_request))
            until = time.monotonic() + wait
            while not self._stop_requested and time.monotonic() < until:
                time.sleep(min(0.2, max(0.0, until - time.monotonic())))
            if self._stop_requested:
                break
            try:
                results = checker.check_many(batch)
                last_request = time.monotonic()
                for result in results:
                    self.database.record_check(
                        result.username, result.status, fragment_status=result.fragment_status,
                        fragment_url=result.fragment_url, fragment_price_ton=result.fragment_price_ton,
                        detail=result.detail,
                    )
                    checked += 1
                    available += int(result.status == "available")
                    self.candidate_checked.emit(result.username, result.status, {"username": result.username})
                self.message.emit(f"Rechecked {checked}/{len(self.usernames)} · free {available}")
            except Exception as exc:
                last_request = time.monotonic()
                for name in batch:
                    self.database.record_check(name, "check_error", detail=str(exc))
                    checked += 1
                self.message.emit(f"Recheck error: {exc}")
        self.finished_summary.emit({"checked": checked, "available": available, "generated": 0, "stopped": self._stop_requested})


class RatesWorker(QThread):
    updated = Signal(object, object)

    def run(self):
        ton_usd, usd_rub = CurrencyRates().refresh()
        self.updated.emit(ton_usd, usd_rub)
