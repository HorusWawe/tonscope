from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=20)
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
                    liquidity INTEGER NOT NULL DEFAULT 0,
                    overall INTEGER NOT NULL DEFAULT 0,
                    telegram_checked_at TEXT,
                    fragment_checked_at TEXT,
                    fragment_status TEXT,
                    fragment_url TEXT,
                    fragment_price_ton REAL,
                    estimated_low_ton REAL,
                    estimated_high_ton REAL,
                    estimated_usd REAL,
                    estimated_rub REAL,
                    check_detail TEXT,
                    is_saved INTEGER NOT NULL DEFAULT 0,
                    is_seen INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_usernames_status ON usernames(status);
                CREATE INDEX IF NOT EXISTS idx_usernames_saved ON usernames(is_saved);
                CREATE INDEX IF NOT EXISTS idx_usernames_score ON usernames(overall);
            """)
            # Lightweight migration for databases created by v0.1.
            existing = {row["name"] for row in db.execute("PRAGMA table_info(usernames)")}
            needs_score_migration = "liquidity" not in existing
            additions = {
                "liquidity": "INTEGER NOT NULL DEFAULT 0",
                "fragment_status": "TEXT",
                "fragment_url": "TEXT",
                "fragment_price_ton": "REAL",
                "estimated_low_ton": "REAL",
                "estimated_high_ton": "REAL",
                "check_detail": "TEXT",
            }
            for name, sql_type in additions.items():
                if name not in existing:
                    db.execute(f"ALTER TABLE usernames ADD COLUMN {name} {sql_type}")
            # Older versions persisted candidates, occupied names and Fragment listings.
            # Keep only names that were confirmed directly available on Telegram.
            db.execute("DELETE FROM usernames WHERE status != 'available'")
            if needs_score_migration:
                from tonscope.core.evaluator import evaluate_username
                for row in db.execute("SELECT username FROM usernames").fetchall():
                    try:
                        scores = evaluate_username(row["username"])
                    except ValueError:
                        continue
                    db.execute("""
                        UPDATE usernames SET readability=?, pronounceability=?, uniqueness=?,
                            brandability=?, liquidity=?, overall=? WHERE username=?
                    """, (
                        scores["readability"], scores["pronounceability"], scores["uniqueness"],
                        scores["brandability"], scores["liquidity"], scores["overall"], row["username"],
                    ))

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def exists(self, username: str) -> bool:
        return self.get_username(username) is not None

    def get_username(self, username: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM usernames WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None

    def record_available(self, username: str, scores: dict[str, int], *,
                         fragment_status: str | None = None, fragment_url: str | None = None,
                         fragment_price_ton: float | None = None, detail: str | None = None) -> None:
        """Persist only usernames confirmed as directly available on Telegram."""
        now = self.now()
        with self.connect() as db:
            db.execute("""
                INSERT INTO usernames (
                    username, status, readability, pronounceability, uniqueness,
                    brandability, liquidity, overall, telegram_checked_at, fragment_checked_at,
                    fragment_status, fragment_url, fragment_price_ton, check_detail,
                    created_at, updated_at
                ) VALUES (?, 'available', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    status='available', readability=excluded.readability,
                    pronounceability=excluded.pronounceability, uniqueness=excluded.uniqueness,
                    brandability=excluded.brandability, liquidity=excluded.liquidity,
                    overall=excluded.overall, telegram_checked_at=excluded.telegram_checked_at,
                    fragment_checked_at=excluded.fragment_checked_at,
                    fragment_status=excluded.fragment_status, fragment_url=excluded.fragment_url,
                    fragment_price_ton=excluded.fragment_price_ton, check_detail=excluded.check_detail,
                    updated_at=excluded.updated_at
            """, (
                username, scores["readability"], scores["pronounceability"], scores["uniqueness"],
                scores["brandability"], scores["liquidity"], scores["overall"], now, now,
                fragment_status, fragment_url, fragment_price_ton, detail, now, now,
            ))

    def remove_username(self, username: str) -> None:
        """Remove a username when Telegram confirms it is not directly available."""
        with self.connect() as db:
            db.execute("DELETE FROM usernames WHERE username=?", (username,))

    def set_status(self, username: str, status: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET status=?, updated_at=? WHERE username=?", (status, self.now(), username))

    def mark_seen(self, username: str, seen: bool = True) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET is_seen=?, updated_at=? WHERE username=?", (int(seen), self.now(), username))

    def toggle_saved(self, username: str, saved: bool) -> None:
        with self.connect() as db:
            db.execute("UPDATE usernames SET is_saved=?, updated_at=? WHERE username=?", (int(saved), self.now(), username))

    def list_usernames(self, view: str = "all", limit: int = 500, min_score: int = 0) -> list[dict]:
        clauses = ["overall >= ?"]
        params: list[object] = [min_score]
        if view == "new":
            clauses.append("status='available' AND is_seen=0")
        elif view == "saved":
            clauses.append("status='available' AND is_saved=1")
        elif view == "checked":
            clauses.append("status='available'")
        where = " WHERE " + " AND ".join(clauses)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM usernames" + where + " ORDER BY overall DESC, created_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_candidate_batch(self, limit: int = 1000) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM usernames WHERE status='candidate' ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def comparable_prices(self, length: int, score: int | None = None) -> list[float]:
        score_clause = " AND overall BETWEEN ? AND ?" if score is not None else ""
        params = (length, score - 2, score + 2) if score is not None else (length,)
        with self.connect() as db:
            rows = db.execute(f"""
                SELECT fragment_price_ton FROM usernames
                WHERE length(username)=? AND fragment_status IN ('on_auction','for_sale')
                  AND fragment_price_ton > 0{score_clause}
                ORDER BY updated_at DESC LIMIT 200
            """, params).fetchall()
        return [float(row[0]) for row in rows if row[0] is not None]

    def stats(self) -> dict[str, int]:
        with self.connect() as db:
            row = db.execute("""
                SELECT COUNT(*) total,
                    SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) available,
                    SUM(CASE WHEN status='available' AND is_saved=1 THEN 1 ELSE 0 END) saved,
                    0 candidates, 0 occupied, 0 fragment
                FROM usernames
            """).fetchone()
        return {key: int(row[key] or 0) for key in ("total", "available", "saved", "candidates", "occupied", "fragment")}

    def export_rows(self, view: str = "all") -> list[dict]:
        return self.list_usernames(view, limit=1_000_000)

    def export(self, path: str | Path, fmt: str, view: str = "all") -> int:
        rows = self.export_rows(view)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "txt":
            target.write_text("\n".join("@" + row["username"] for row in rows), encoding="utf-8")
        else:
            if rows:
                with target.open("w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                target.write_text("", encoding="utf-8-sig")
        return len(rows)
