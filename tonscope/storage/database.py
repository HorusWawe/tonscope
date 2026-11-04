from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS usernames (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    source TEXT NOT NULL DEFAULT 'generated',
                    readability INTEGER NOT NULL DEFAULT 0,
                    pronounceability INTEGER NOT NULL DEFAULT 0,
                    uniqueness INTEGER NOT NULL DEFAULT 0,
                    brandability INTEGER NOT NULL DEFAULT 0,
                    overall INTEGER NOT NULL DEFAULT 0,
                    telegram_checked_at TEXT,
                    fragment_checked_at TEXT,
                    estimated_ton REAL,
                    estimated_usd REAL,
                    estimated_rub REAL,
                    is_saved INTEGER NOT NULL DEFAULT 0,
                    is_seen INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_usernames_status ON usernames(status);
                CREATE INDEX IF NOT EXISTS idx_usernames_saved ON usernames(is_saved);
                CREATE INDEX IF NOT EXISTS idx_usernames_score ON usernames(overall);
            """)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def add_candidate(self, username: str, scores: dict[str, int]) -> bool:
        now = self.now()
        with self.connect() as db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO usernames (
                    username, status, readability, pronounceability,
                    uniqueness, brandability, overall, created_at, updated_at
                ) VALUES (?, 'candidate', ?, ?, ?, ?, ?, ?, ?)
            """, (
                username, scores["readability"], scores["pronounceability"],
                scores["uniqueness"], scores["brandability"], scores["overall"],
                now, now,
            ))
            return cursor.rowcount > 0

    def exists(self, username: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM usernames WHERE username = ?", (username,)).fetchone() is not None

    def set_status(self, username: str, status: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET status=?, updated_at=? WHERE username=?", (status, self.now(), username))

    def mark_seen(self, username: str, seen: bool = True) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET is_seen=?, updated_at=? WHERE username=?", (int(seen), self.now(), username))

    def toggle_saved(self, username: str, saved: bool) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET is_saved=?, updated_at=? WHERE username=?", (int(saved), self.now(), username))

    def list_usernames(self, view: str = "all", limit: int = 500) -> list[dict]:
        clauses = []
        if view == "new":
            clauses.append("is_seen = 0 AND status = 'available'")
        elif view == "saved":
            clauses.append("is_saved = 1")
        elif view == "checked":
            clauses.append("status IN ('available','occupied','auction','check_error')")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM usernames" + where + " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        with self.connect() as db:
            row = db.execute("""
                SELECT COUNT(*) AS total,
                    SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available,
                    SUM(CASE WHEN is_saved=1 THEN 1 ELSE 0 END) AS saved,
                    SUM(CASE WHEN status='candidate' THEN 1 ELSE 0 END) AS candidates
                FROM usernames
            """).fetchone()
        return {key: int(row[key] or 0) for key in ("total", "available", "saved", "candidates")}
