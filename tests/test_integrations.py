import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

from tonscope.integrations.public_checker import PublicUsernameChecker, UsernameResult
from tonscope.core.valuation import comparable_range


class CheckerTests(unittest.TestCase):
    def test_bulk_response_maps_fragment_auction_and_available(self):
        payload = {
            "success": True,
            "results": [
                {
                    "username": "suaqa",
                    "result": {"status": "available", "explanation": "No public listing"},
                    "fragment": {"checked": True, "found": False}
                },
                {
                    "username": "durov",
                    "result": {"status": "fragment_collectible", "explanation": "Listed"},
                    "fragment": {
                        "checked": True, "found": True, "status": "on_auction",
                        "url": "https://fragment.com/username/durov",
                        "price": {"amount": 123.5, "currency": "TON"}
                    }
                }
            ]
        }

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(payload).encode()

        with patch("urllib.request.urlopen", return_value=Response()):
            results = PublicUsernameChecker().check_many(["suaqa", "durov"])

        self.assertEqual(results[0].status, "available")
        self.assertEqual(results[1].status, "auction")
        self.assertEqual(results[1].fragment_price_ton, 123.5)
        self.assertEqual(results[1].fragment_url, "https://fragment.com/username/durov")

    def test_rejects_batches_larger_than_fifteen(self):
        with self.assertRaises(ValueError):
            PublicUsernameChecker().check_many(["x"] * 16)


class ValuationTests(unittest.TestCase):
    def test_requires_three_observed_comparables(self):
        self.assertIsNone(comparable_range([1.0, 2.0]))
        self.assertIsNotNone(comparable_range([1.0, 2.0, 3.0]))


if __name__ == "__main__":
    unittest.main()
