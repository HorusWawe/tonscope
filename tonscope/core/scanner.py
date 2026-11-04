from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from tonscope.core.evaluator import evaluate_username
from tonscope.core.generator import UsernameGenerator
from tonscope.storage.database import Database


class CandidateWorker(QThread):
    candidate_created = Signal(str, dict)
    progress = Signal(int)
    message = Signal(str)
    finished_count = Signal(int)

    def __init__(self, database: Database, length: int, mode: str, target: int = 0):
        super().__init__()
        self.database = database
        self.length = length
        self.mode = mode
        self.target = target  # 0 means run until stopped
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        generator = UsernameGenerator(self.length, self.mode)
        created = 0
        processed = 0
        self.message.emit("Generating candidates…")
        try:
            for username in generator.stream():
                if self._stop_requested:
                    break
                processed += 1
                if self.database.exists(username):
                    continue
                scores = evaluate_username(username)
                if self.database.add_candidate(username, scores):
                    created += 1
                    self.candidate_created.emit(username, scores)
                if processed % 100 == 0:
                    self.progress.emit(processed)
                if self.target and created >= self.target:
                    break
        except Exception as exc:
            self.message.emit(f"Error: {exc}")
        self.finished_count.emit(created)
        self.message.emit(f"Stopped. New candidates: {created}")
