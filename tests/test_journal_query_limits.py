from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import os
import unittest
import datetime
import hashlib
from contextlib import closing
from unittest.mock import patch


class JournalQueryLimitTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.modules = self.enterContext(api_module_state())
        # Real account/session rows retain the original synthetic identity and
        # token while exercising the production authentication and opt-in checks.
        now = datetime.datetime.now(datetime.timezone.utc)
        with closing(self.modules.account_store._connect()) as conn:
            conn.execute(
                "INSERT INTO users (id, journal_storage_enabled, created_at, last_login_at) "
                "VALUES (?, ?, ?, ?)",
                ("user-a", 1, now.isoformat(), now.isoformat()),
            )
            conn.execute(
                "INSERT INTO user_sessions (id, user_id, session_token_hash, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("query-session", "user-a", hashlib.sha256(b"session").hexdigest(),
                 now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()),
            )
            conn.commit()

    def test_journal_trades_query_limit_is_capped(self):
        os.environ["ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT"] = "20"
        main = self.modules.main
        captured = {}

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        self.enterContext(patch.object(main, "list_trades", fake_list_trades))

        result = main.get_journal_trades(limit=999999, authorization="Bearer session")

        self.assertEqual([], result)
        self.assertEqual(20, captured["limit"])

    def test_journal_query_settings_have_upper_bounds(self):
        os.environ["ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT"] = "999999"
        os.environ["ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES"] = "999999"
        main = self.modules.main

        self.assertEqual(1000, main._journal_query_max_limit())
        self.assertEqual(1000, main._saved_journal_analysis_max_trades())

    def test_review_history_query_limit_is_capped(self):
        os.environ["ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT"] = "20"
        main = self.modules.main
        captured = {}

        def fake_list_review_history(*, user_id, limit=100):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        self.enterContext(patch.object(main, "list_review_history", fake_list_review_history))

        result = main.get_journal_review_history(limit=999999, authorization="Bearer session")

        self.assertEqual([], result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(20, captured["limit"])

    def test_saved_journal_review_uses_analysis_limit(self):
        os.environ["ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES"] = "30"
        main = self.modules.main
        captured = {}
        self.enterContext(patch.object(main, "build_review", lambda trades: {"count": len(trades)}))

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        self.enterContext(patch.object(main, "list_trades", fake_list_trades))

        result = main.get_journal_review(authorization="Bearer session")

        self.assertEqual({"count": 0}, result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(30, captured["limit"])

    def test_saved_journal_chart_uses_analysis_limit(self):
        os.environ["ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES"] = "30"
        main = self.modules.main
        captured = {}
        self.enterContext(patch.object(main, "build_journal_charts", lambda trades: {"charts": []}))

        def fake_list_trades(*, limit=500, user_id=None):
            captured["limit"] = limit
            captured["user_id"] = user_id
            return []

        self.enterContext(patch.object(main, "list_trades", fake_list_trades))

        result = main.get_journal_charts(authorization="Bearer session")

        self.assertEqual({"charts": []}, result)
        self.assertEqual("user-a", captured["user_id"])
        self.assertEqual(30, captured["limit"])


if __name__ == "__main__":
    unittest.main()
