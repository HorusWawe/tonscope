from __future__ import annotations

import time
from PySide6.QtCore import QThread, Signal

from tonscope.core.evaluator import evaluate_username
from tonscope.core.generator import UsernameGenerator
from tonscope.integrations.public_checker import PublicUsernameChecker
from tonscope.storage.database import Database


class ScanWorker(QThread):
    candidate_checked = Signal(str, str, dict)
    progress = Signal(int, int, int)  # checked, available, processed
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

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        checker = PublicUsernameChecker(self.api_url)
        generator = UsernameGenerator(self.length, self.mode)
        batch: list[str] = []
        checked = available = processed = 0
        created = 0
        last_request = 0.0
        self.message.emit("Generating candidates and preparing live checks…")

        def flush() -> bool:
            nonlocal checked, available, last_request
            if not batch:
                return True
            delay = max(0.0, 60.0 / self.requests_per_minute - (time.monotonic() - last_request))
            deadline = time.monotonic() + delay
            while not self._stop_requested and time.monotonic() < deadline:
                time.sleep(min(0.2, deadline - time.monotonic()))
            if self._stop_requested:
                return False
            names = list(batch)
            batch.clear()
            try:
                results = checker.check_many(names)
                last_request = time.monotonic()
                for result in results:
                    self.database.record_check(
                        result.username, result.status,
                        fragment_status=result.fragment_status,
                        fragment_url=result.fragment_url,
                        fragment_price_ton=result.fragment_price_ton,
                        detail=result.detail,
                    )
                    checked += 1
                    if result.status == "available":
                        available += 1
                    row = next((x for x in self.database.list_usernames("all", 10000)
                                if x["username"] == result.username), {})
                    self.candidate_checked.emit(result.username, result.status, row)
                self.progress.emit(checked, available, processed)
                self.message.emit(f"Checked {checked} · available {available} · generated {created}")
            except Exception as exc:
                last_request = time.monotonic()
                for name in names:
                    self.database.record_check(name, "check_error", detail=str(exc))
                    checked += 1
                    self.candidate_checked.emit(name, "check_error", {"username": name, "check_detail": str(exc)})
                self.message.emit(f"API error, results saved as retryable: {exc}")
                self.progress.emit(checked, available, processed)
            return True

        try:
            for username in generator.stream():
                if self._stop_requested:
                    break
                processed += 1
                if self.database.exists(username):
                    continue
                scores = evaluate_username(username)
                if scores["overall"] < self.min_score:
                    continue
                if not self.database.add_candidate(username, scores):
                    continue
                created += 1
                batch.append(username)
                if len(batch) >= 15 and not flush():
                    break
                if self.target_free and available >= self.target_free:
                    break
        except Exception as exc:
            self.message.emit(f"Scan error: {exc}")
        if not self._stop_requested and batch and (not self.target_free or available < self.target_free):
            flush()
        summary = {"checked": checked, "available": available, "generated": created, "processed": processed,
                   "stopped": self._stop_requested}
        self.finished_summary.emit(summary)
        self.message.emit(
            f"Stopped · checked {checked} · free {available}. "
            "Progress and all results are stored in the profile."
        )
