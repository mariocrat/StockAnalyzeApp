"""Finalization refunds and cleanup inside the H4-A1 boundary."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state
from unittest.mock import patch

import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException


def _load_main_with_temp_state(tmpdir):
    os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
    os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
    os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
    os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"
    os.environ["ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["ALPHAMATE_AI_REVIEW_MAX_CONCURRENT"] = "1"

    backend_dir = os.path.join(os.getcwd(), "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    account_store = importlib.reload(importlib.import_module("core.account_store"))
    access_control = importlib.reload(importlib.import_module("core.access_control"))
    main = importlib.reload(importlib.import_module("main"))
    session = account_store.login_dev_provider(
        provider="kakao",
        provider_user_id="ai-review-safety-user",
        display_name="AI Safety",
    )
    return main, access_control, f"Bearer {session['session_token']}"


def _basic_batch(main):
    return main.JournalAiReviewIn(
        privacy_consent=True,
        review_type="basic",
        trades=[main.JournalTradeIn(
            trade_date="2026-06-21T10:30",
            ticker="005930",
            name="Samsung",
            side="buy",
            price=70000,
            quantity=1,
        )],
    )


def _load_review_main_with_temp_state(tmpdir):
    backend_dir = os.path.join(os.getcwd(), "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    account_store = importlib.import_module("core.account_store")
    os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
    os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
    os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
    os.environ["ALPHAMATE_REVIEW_ACCESS_ENABLED"] = "true"
    os.environ["ALPHAMATE_REVIEW_ACCESS_ID"] = "play-review-id"
    os.environ["ALPHAMATE_REVIEW_ACCESS_PASSWORD_HASH"] = account_store.hash_review_password(
        "play-review-password",
        iterations=100_000,
    )
    os.environ["ALPHAMATE_REVIEW_ACCESS_EXPIRES_AT"] = (
        datetime.now(timezone.utc) + timedelta(days=7)
    ).isoformat()
    os.environ["ALPHAMATE_REVIEW_BASIC_QUOTA"] = "100"
    os.environ["ALPHAMATE_REVIEW_ADVANCED_QUOTA"] = "100"
    os.environ["ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE"] = "10"

    account_store = importlib.reload(account_store)
    access_control = importlib.reload(importlib.import_module("core.access_control"))
    review_history = importlib.reload(importlib.import_module("core.review_history"))
    main = importlib.reload(importlib.import_module("main"))
    session = account_store.login_review_access(
        review_id="play-review-id",
        password="play-review-password",
    )
    access_control.initialize_review_entitlement(session["user"]["id"])
    return main, access_control, review_history, session


class AiReviewSafetyFinalizationTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())
        # Original helpers reload main, so patch its import source first.
        # Persistence/refunds stay real; no chart provider is needed to save history.
        charts = importlib.import_module("core.journal_chart")
        self.enterContext(patch.object(
            charts, "build_journal_charts", return_value={"charts": []}))

    def test_finalization_failure_refunds_general_access_and_cleans_history_and_pending_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            account_store = importlib.import_module("core.account_store")
            review_history = importlib.reload(importlib.import_module("core.review_history"))
            user = account_store.authenticate_session(token)
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            os.environ["ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE"] = "10"
            calls = {"review": 0, "finish": 0, "refund": 0}

            def fake_basic_review(trades, target_trade_id=None, analysis_focus="balanced"):
                calls["review"] += 1
                return {
                    "status": "ready",
                    "source": "openai",
                    "review_type": "basic",
                    "model": "gpt-5.6-luna",
                    "summary": f"review-{calls['review']}",
                }

            original_finish = main._finish_ai_review_idempotency
            original_refund = main.refund_ai_review_access

            def fail_finish_once(cache_key, result):
                calls["finish"] += 1
                if calls["finish"] == 1:
                    raise RuntimeError("forced finalization failure")
                return original_finish(cache_key, result)

            def count_refund(access):
                calls["refund"] += 1
                return original_refund(access)

            main.build_basic_ai_review = fake_basic_review
            main._finish_ai_review_idempotency = fail_finish_once
            main.refund_ai_review_access = count_refund
            batch = _basic_batch(main)
            cache_key = main._ai_review_idempotency_cache_key(token, "finalize-failure-1")
            before = access_control.get_user_entitlements(authorization=token, entitlement_token="")
            try:
                with self.assertRaisesRegex(RuntimeError, "forced finalization failure"):
                    main.get_journal_ai_review_once(
                        batch,
                        authorization=token,
                        x_idempotency_key="finalize-failure-1",
                    )

                after_failure = access_control.get_user_entitlements(authorization=token, entitlement_token="")
                self.assertEqual(
                    before["basic"]["signup_remaining"],
                    after_failure["basic"]["signup_remaining"],
                )
                self.assertEqual([], review_history.list_review_history(user_id=user["id"]))
                self.assertNotIn(cache_key, main._ai_review_idempotency_cache)
                self.assertEqual(1, calls["refund"])

                retry = main.get_journal_ai_review_once(
                    batch,
                    authorization=token,
                    x_idempotency_key="finalize-failure-1",
                )
                replay = main.get_journal_ai_review_once(
                    batch,
                    authorization=token,
                    x_idempotency_key="finalize-failure-1",
                )
                after_success = access_control.get_user_entitlements(authorization=token, entitlement_token="")

                self.assertEqual("ready", retry["status"])
                self.assertTrue(replay["access"]["idempotent_replay"])
                self.assertEqual(2, calls["review"])
                self.assertEqual(1, calls["refund"])
                self.assertEqual(1, len(review_history.list_review_history(user_id=user["id"])))
                self.assertEqual(
                    before["basic"]["signup_remaining"] - 1,
                    after_success["basic"]["signup_remaining"],
                )
            finally:
                main._finish_ai_review_idempotency = original_finish
                main.refund_ai_review_access = original_refund

    def test_finalization_failure_refunds_review_quota_exactly_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, review_history, session = _load_review_main_with_temp_state(tmpdir)
            token = f"Bearer {session['session_token']}"
            user_id = session["user"]["id"]
            main.build_advanced_ai_review = lambda trades, target_trade_id=None: {
                "status": "ready",
                "source": "openai",
                "review_type": "advanced",
                "model": "gpt-5.6-luna",
                "summary": "advanced review",
            }
            original_finish = main._finish_ai_review_idempotency
            main._finish_ai_review_idempotency = lambda cache_key, result: (_ for _ in ()).throw(
                RuntimeError("forced review finalization failure")
            )
            batch = _basic_batch(main)
            batch.review_type = "advanced"
            cache_key = main._ai_review_idempotency_cache_key(token, "review-finalize-failure-1")
            try:
                with self.assertRaisesRegex(RuntimeError, "forced review finalization failure"):
                    main.get_journal_ai_review_once(
                        batch,
                        authorization=token,
                        x_idempotency_key="review-finalize-failure-1",
                    )
            finally:
                main._finish_ai_review_idempotency = original_finish

            entitlements = access_control.get_user_entitlements(authorization=token, entitlement_token="")
            self.assertEqual(100, entitlements["advanced"]["pro_monthly_remaining"])
            self.assertEqual([], review_history.list_review_history(user_id=user_id))
            self.assertNotIn(cache_key, main._ai_review_idempotency_cache)
            with closing(sqlite3.connect(os.environ["ALPHAMATE_ACCESS_DB_PATH"])) as conn:
                statuses = conn.execute(
                    "SELECT status FROM review_entitlement_usage WHERE user_id = ? AND review_type = 'advanced'",
                    (user_id,),
                ).fetchall()
            self.assertEqual([("reversed",)], statuses)


if __name__ == "__main__":
    unittest.main()
