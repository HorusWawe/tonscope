import tempfile
import unittest
import sqlite3
from pathlib import Path

from tonscope.core.evaluator import evaluate_username
from tonscope.core.generator import UsernameGenerator
from tonscope.storage.database import Database


class GeneratorTests(unittest.TestCase):
    def test_output_is_lowercase_latin_and_requested_length(self):
        for length in (5, 6, 7):
            generator = UsernameGenerator(length, "readable", seed=123)
            for _ in range(100):
                value = generator.generate()
                self.assertEqual(len(value), length)
                self.assertRegex(value, r"^[a-z]+$")

    def test_modes_are_valid(self):
        for mode in ("readable", "words", "brand", "random"):
            self.assertRegex(UsernameGenerator(6, mode, seed=7).generate(), r"^[a-z]{6}$")


class EvaluatorTests(unittest.TestCase):
    def test_scores_are_in_range(self):
        scores = evaluate_username("suaqa")
        self.assertEqual(set(scores), {"readability", "pronounceability", "uniqueness", "brandability", "liquidity", "overall"})
        self.assertTrue(all(1 <= score <= 10 for score in scores.values()))

    def test_rejects_invalid_username(self):
        with self.assertRaises(ValueError):
            evaluate_username("wq-12")


class DatabaseTests(unittest.TestCase):

    def test_v01_database_is_migrated(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.db"
            with sqlite3.connect(path) as connection:
                connection.execute("""
                    CREATE TABLE usernames (
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
                    )
                """)
            db = Database(path)
            with db.connect() as connection:
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(usernames)")}
            self.assertIn("liquidity", columns)
            self.assertIn("fragment_status", columns)
            self.assertIn("fragment_price_ton", columns)

    def test_candidate_persists_and_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "profile.db")
            scores = evaluate_username("suaqa")
            self.assertTrue(db.add_candidate("suaqa", scores))
            self.assertFalse(db.add_candidate("suaqa", scores))
            self.assertEqual(db.stats()["total"], 1)
            db.toggle_saved("suaqa", True)
            self.assertEqual(len(db.list_usernames("saved")), 1)


if __name__ == "__main__":
    unittest.main()
