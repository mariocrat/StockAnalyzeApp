"""Real concurrent SQLite seeding with worker ownership before fixture cleanup."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests import api_test_modules as api

import importlib
import os
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

with api._import_state():
    from backend.core import account_store, access_control


def _state():
    logger = logging.getLogger("uvicorn.error")
    filters = [(id(logger.filters), tuple(map(id, logger.filters)))]
    while logger is not None:
        filters.extend((id(handler), id(handler.filters), tuple(map(id, handler.filters)))
                       for handler in logger.handlers)
        if not logger.propagate:
            break
        logger = logger.parent
    return (
        dict(os.environ), list(sys.path), Path.cwd(), tempfile.tempdir,
        [{key: id(value) for key, value in module.__dict__.items()}
         for module in (*api._stores, api._main, account_store, access_control)],
        api._main._review_example_trades_lock.locked(), filters,
        logging.getLogger("yfinance").level, frozenset(threading.enumerate()),
    )


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

    @contextmanager
    def _owned_workers(self, barrier, release, futures, evidence):
        with ThreadPoolExecutor(max_workers=2) as executor:
            try:
                yield executor
            finally:
                # Covers failed submission/setup and assertions before release,
                # as well as exceptions raised by future.result().
                release.set()
                barrier.abort()
                executor.shutdown(wait=True)
                workers = tuple(executor._threads)
                self.assertTrue(workers)
                self.assertTrue(all(not worker.is_alive() for worker in workers))
                self.assertTrue(all(future.done() for future in futures))
                evidence["workers"] = workers
                evidence["released"] = release.is_set()
                evidence["barrier_broken"] = barrier.broken
                evidence["joined"] = True

    def _exercise(self, outcome, failure, evidence):
        with storage_fixture() as storage, api.api_module_state() as modules, ExitStack() as aliases:
            evidence["root"] = storage.root
            # The original helper reloads backend.core aliases; main imports
            # core.*. Restore both namespaces without changing either helper.
            for module in (account_store, access_control):
                aliases.enter_context(patch.dict(module.__dict__))
            tmpdir = storage.root
            env = self._configured_env(tmpdir)
            env["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")
            with patch.dict(os.environ, env, clear=False):
                _, _ = self._load_modules()
                import main

                main = importlib.reload(main)
                evidence["lock"] = main._review_example_trades_lock
                original_count = main.count_trades
                original_add = main._add_journal_trade
                start_barrier = threading.Barrier(2)
                first_add_started = threading.Event()
                second_count_started = threading.Event()
                release_first_add = threading.Event()
                call_lock = threading.Lock()
                entered = threading.Event()
                worker_threads = set()
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
                        if not release_first_add.wait(timeout=5):
                            raise TimeoutError("seeding release was not signalled")
                    return original_add(payload, user_id=user_id)

                def run_seed(index):
                    with call_lock:
                        worker_threads.add(threading.current_thread())
                    entered.set()
                    start_barrier.wait(timeout=5)
                    if outcome == "worker" and index == 0:
                        raise failure
                    return main._ensure_review_example_trades("review-user")

                futures = []
                def verify_patch_restore():
                    self.assertTrue(evidence.get("joined"))
                    self.assertIs(main.count_trades, original_count)
                    self.assertIs(main._add_journal_trade, original_add)
                    self.assertTrue(storage.root.is_dir())
                    self.assertEqual(str(storage.root), os.environ["ALPHAMATE_TEST_ROOT"])
                    evidence["patches_restored_before_storage"] = True

                with ExitStack() as patches:
                    patches.callback(verify_patch_restore)
                    patches.enter_context(patch.object(main, "count_trades", side_effect=gated_count))
                    patches.enter_context(patch.object(main, "_add_journal_trade", side_effect=gated_add))
                    try:
                        with self._owned_workers(start_barrier, release_first_add, futures, evidence) as executor:
                            futures.append(executor.submit(run_seed, 0))
                            if outcome == "setup":
                                self.assertTrue(entered.wait(timeout=5))
                                raise failure  # Partial setup: peer not submitted.
                            futures.append(executor.submit(run_seed, 1))
                            self.assertTrue(first_add_started.wait(timeout=5))
                            if outcome == "assertion":
                                raise failure
                            if outcome == "worker":
                                futures[0].result(timeout=5)
                                self.fail("worker exception was not propagated")
                            second_count_started.wait(timeout=0.2)
                            release_first_add.set()
                            results = [future.result(timeout=5) for future in futures]
                    finally:
                        # This checkpoint is inside both patches and the live
                        # storage/env/module contexts, after worker shutdown.
                        self.assertTrue(evidence.get("joined"))
                        self.assertIs(main.count_trades.side_effect, gated_count)
                        self.assertIs(main._add_journal_trade.side_effect, gated_add)
                        self.assertTrue(storage.root.is_dir())
                        self.assertEqual(str(storage.root), os.environ["ALPHAMATE_TEST_ROOT"])
                        self.assertFalse(main._review_example_trades_lock.locked())
                        self.assertEqual(1 if outcome == "setup" else 2, len(worker_threads))
                        self.assertEqual(worker_threads, set(evidence["workers"]))
                        errors = [future.exception() for future in futures]
                        if outcome == "worker":
                            self.assertEqual([failure, None], errors)
                        elif outcome == "setup":
                            self.assertEqual(1, len(errors))
                            self.assertIsInstance(errors[0], threading.BrokenBarrierError)
                        else:
                            self.assertEqual([None, None], errors)

                self.assertIs(main.count_trades, original_count)
                self.assertIs(main._add_journal_trade, original_add)
                self.assertEqual(2, original_count(user_id="review-user"))
                self.assertEqual(2, sum(results))

    def test_review_example_trades_are_seeded_once_when_logins_overlap(self):
        baseline = _state()
        baseline_lock = api._main._review_example_trades_lock
        for outcome in ("success", "assertion", "worker", "setup"):
            with self.subTest(outcome=outcome):
                evidence = {}
                failure = (AssertionError("synthetic assertion before release")
                           if outcome == "assertion" else RuntimeError("synthetic " + outcome))
                try:
                    if outcome == "success":
                        self._exercise(outcome, failure, evidence)
                    else:
                        with self.assertRaises(type(failure)) as caught:
                            self._exercise(outcome, failure, evidence)
                        self.assertIs(caught.exception, failure)
                finally:
                    self.assertTrue(evidence.get("joined"))
                    self.assertTrue(evidence["released"])
                    self.assertTrue(evidence["barrier_broken"])
                    self.assertTrue(evidence["patches_restored_before_storage"])
                    self.assertTrue(all(not worker.is_alive() for worker in evidence["workers"]))
                    self.assertFalse(evidence["root"].exists())
                    self.assertIsNot(baseline_lock, evidence["lock"])
                    self.assertIs(baseline_lock, api._main._review_example_trades_lock)
                    self.assertEqual(baseline, _state())


if __name__ == "__main__":
    unittest.main()
