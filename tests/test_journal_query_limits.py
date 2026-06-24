import importlib
import os
import sys
import unittest


def _load_main():
    backend_dir = os.path.join(os.getcwd(), "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    return importlib.reload(importlib.import_module("main"))


class JournalQueryLimitTest(unittest.TestCase):
    ENV_KEYS = [
        "ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT",
        "ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES",
    ]

    def setUp(self):
        self._previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_journal_trades_query_limit_is_capped(self):
        os.environ["ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT"] = "20"
        main = _load_main()
        captured = {}

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        main.list_trades = fake_list_trades

        result = main.get_journal_trades(limit=999999)

        self.assertEqual([], result)
        self.assertEqual(20, captured["limit"])

    def test_review_history_query_limit_is_capped(self):
        os.environ["ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT"] = "20"
        main = _load_main()
        captured = {}
        main.authenticate_session = lambda authorization: {
            "id": "user-a",
            "journal_storage_enabled": True,
        }

        def fake_list_review_history(*, user_id, limit=100):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        main.list_review_history = fake_list_review_history

        result = main.get_journal_review_history(limit=999999, authorization="Bearer session")

        self.assertEqual([], result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(20, captured["limit"])

    def test_saved_journal_review_uses_analysis_limit(self):
        os.environ["ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES"] = "30"
        main = _load_main()
        captured = {}
        main._optional_session_user = lambda authorization: {
            "id": "user-a",
            "journal_storage_enabled": True,
        }
        main.build_review = lambda trades: {"count": len(trades)}

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        main.list_trades = fake_list_trades

        result = main.get_journal_review(authorization="Bearer session")

        self.assertEqual({"count": 0}, result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(30, captured["limit"])

    def test_saved_journal_chart_uses_analysis_limit(self):
        os.environ["ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES"] = "30"
        main = _load_main()
        captured = {}
        main._optional_session_user = lambda authorization: {
            "id": "user-a",
            "journal_storage_enabled": True,
        }
        main.build_journal_charts = lambda trades: {"charts": []}

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        main.list_trades = fake_list_trades

        result = main.get_journal_charts(authorization="Bearer session")

        self.assertEqual({"charts": []}, result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(30, captured["limit"])


if __name__ == "__main__":
    unittest.main()
