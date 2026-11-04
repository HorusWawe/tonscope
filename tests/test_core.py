import tempfile
import unittest
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
        self.assertEqual(set(scores), {"readability", "pronounceability", "uniqueness", "brandability", "overall"})
        self.assertTrue(all(1 <= score <= 10 for score in scores.values()))

    def test_rejects_invalid_username(self):
        with self.assertRaises(ValueError):
            evaluate_username("wq-12")


class DatabaseTests(unittest.TestCase):
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
