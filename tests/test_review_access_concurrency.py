"""H4-B2 deferred concurrent review seeding test; excluded from A2 execution."""

import importlib
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException


class ReviewAccessConcurrencyTest(unittest.TestCase):
    def _configured_env(self, tmpdir, *, enabled="true", expires_at=None):
        from backend.core import account_store

        return {
            "ALPHAMATE_ACCOUNT_DB_PATH": os.path.join(tmpdir, "accounts.sqlite3"),
            "ALPHAMATE_ACCESS_DB_PATH": os.path.join(tmpdir, "access.sqlite3"),
            "ALPHAMATE_REVIEW_ACCESS_ENABLED": enabled,
            "ALPHAMATE_REVIEW_ACCESS_ID": "play-review-id",
            "ALPHAMATE_REVIEW_ACCESS_PASSWORD_HASH": account_store.hash_review_password("play-review-password", iterations=100_000),
            "ALPHAMATE_REVIEW_ACCESS_EXPIRES_AT": expires_at or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "ALPHAMATE_REVIEW_BASIC_QUOTA": "100",
            "ALPHAMATE_REVIEW_ADVANCED_QUOTA": "100",
        }

    def _load_modules(self):
        from backend.core import access_control, account_store

        account_store = importlib.reload(account_store)
        access_control = importlib.reload(access_control)
        return account_store, access_control

    def test_review_example_trades_are_seeded_once_when_logins_overlap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._configured_env(tmpdir)
            env["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")
            with patch.dict(os.environ, env, clear=False):
                _, _ = self._load_modules()
                backend_dir = os.path.join(os.getcwd(), "backend")
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                import main

                main = importlib.reload(main)
                original_count = main.count_trades
                original_add = main._add_journal_trade
                start_barrier = threading.Barrier(2)
                first_add_started = threading.Event()
                second_count_started = threading.Event()
                release_first_add = threading.Event()
                call_lock = threading.Lock()
                count_calls = {"value": 0}
                add_calls = {"value": 0}

                def gated_count(*, user_id):
                    with call_lock:
                        count_calls["value"] += 1
                        call_number = count_calls["value"]
                    result = original_count(user_id=user_id)
                    if call_number == 2:
                        second_count_started.set()
                    return result

                def gated_add(payload, *, user_id=""):
                    with call_lock:
                        add_calls["value"] += 1
                        call_number = add_calls["value"]
                    if call_number == 1:
                        first_add_started.set()
                        release_first_add.wait(timeout=1)
                    return original_add(payload, user_id=user_id)

                def run_seed():
                    start_barrier.wait(timeout=1)
                    return main._ensure_review_example_trades("review-user")

                with patch.object(main, "count_trades", side_effect=gated_count), patch.object(
                    main, "_add_journal_trade", side_effect=gated_add
                ):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [executor.submit(run_seed) for _ in range(2)]
                        self.assertTrue(first_add_started.wait(timeout=1))
                        second_count_started.wait(timeout=0.2)
                        release_first_add.set()
                        results = [future.result(timeout=2) for future in futures]

                self.assertEqual(2, original_count(user_id="review-user"))
                self.assertEqual(2, sum(results))


if __name__ == "__main__":
    unittest.main()
