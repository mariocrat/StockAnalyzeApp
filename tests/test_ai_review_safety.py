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


class AiReviewSafetyTest(unittest.TestCase):
    ENV_KEYS = [
        "ALPHAMATE_ACCOUNT_DB_PATH",
        "ALPHAMATE_ACCESS_DB_PATH",
        "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
        "ALPHAMATE_ALLOW_DEV_ACCESS",
        "ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE",
        "ALPHAMATE_AI_REVIEW_MAX_CONCURRENT",
        "ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS",
        "ALPHAMATE_REVIEW_ACCESS_ENABLED",
        "ALPHAMATE_REVIEW_ACCESS_ID",
        "ALPHAMATE_REVIEW_ACCESS_PASSWORD_HASH",
        "ALPHAMATE_REVIEW_ACCESS_EXPIRES_AT",
        "ALPHAMATE_REVIEW_BASIC_QUOTA",
        "ALPHAMATE_REVIEW_ADVANCED_QUOTA",
    ]

    def setUp(self):
        self._previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_legacy_ai_review_module_does_not_keep_direct_openai_client(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        ai_review = importlib.reload(importlib.import_module("core.ai_review"))

        self.assertFalse(hasattr(ai_review, "build_ai_review"))
        self.assertFalse(hasattr(ai_review, "_call_openai"))
        self.assertFalse(hasattr(ai_review, "_rule_notes"))

    def test_legacy_ai_review_get_endpoint_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            calls = {"count": 0}

            def forbidden_build_ai_review(trades):
                calls["count"] += 1
                return {"status": "ready", "summary": "bypassed"}

            main.build_ai_review = forbidden_build_ai_review
            with self.assertRaises(HTTPException) as blocked:
                main.get_journal_ai_review(authorization=token)

            self.assertEqual(410, blocked.exception.status_code)
            self.assertEqual(0, calls["count"])

    def test_ai_review_rate_limit_rejects_repeated_user_requests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            main.build_basic_ai_review = lambda trades, target_trade_id=None, analysis_focus="balanced": {
                "status": "ready",
                "source": "openai",
                "review_type": "basic",
                "summary": "ok",
            }

            batch = _basic_batch(main)
            first = main.get_journal_ai_review_once(batch, authorization=token)

            self.assertEqual("ready", first["status"])
            with self.assertRaises(HTTPException) as blocked:
                main.get_journal_ai_review_once(batch, authorization=token)

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)

    def test_ai_review_rate_limit_has_upper_bound(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, _ = _load_main_with_temp_state(tmpdir)
            os.environ["ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE"] = "999999"

            self.assertEqual(60, main._ai_review_rate_limit())

    def test_ai_review_max_concurrent_has_upper_bound(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, _ = _load_main_with_temp_state(tmpdir)
            os.environ["ALPHAMATE_AI_REVIEW_MAX_CONCURRENT"] = "999999"

            self.assertEqual(20, main._ai_review_max_concurrent())

    def test_ai_review_concurrency_guard_rejects_when_server_is_busy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, _ = _load_main_with_temp_state(tmpdir)
            self.assertTrue(main._ai_review_concurrency_guard.acquire(blocking=False))
            try:
                with self.assertRaises(HTTPException) as blocked:
                    main._acquire_ai_review_capacity()
            finally:
                main._ai_review_concurrency_guard.release()

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)

    def test_ai_review_error_refunds_consumed_basic_credit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            main.build_basic_ai_review = lambda trades, target_trade_id=None, analysis_focus="balanced": {
                "status": "error",
                "source": "chart-rules",
                "review_type": "basic",
                "summary": "AI request failed",
            }

            result = main.get_journal_ai_review_once(_basic_batch(main), authorization=token)
            entitlements = access_control.get_user_entitlements(
                authorization=token,
                entitlement_token="",
            )

            self.assertEqual("error", result["status"])
            self.assertTrue(result["access"]["refunded"])
            self.assertEqual(5, result["access"]["quota"]["basic"]["signup_remaining"])
            self.assertEqual(5, entitlements["basic"]["signup_remaining"])

    def test_ai_review_rejects_unknown_review_type_without_charging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            batch = _basic_batch(main)
            batch.review_type = "premium"

            with self.assertRaises(HTTPException) as blocked:
                main.get_journal_ai_review_once(batch, authorization=token)
            entitlements = access_control.get_user_entitlements(
                authorization=token,
                entitlement_token="",
            )

            self.assertEqual(400, blocked.exception.status_code)
            self.assertIn("review_type", blocked.exception.detail)
            self.assertEqual(5, entitlements["basic"]["signup_remaining"])

    def test_ai_review_idempotency_key_prevents_duplicate_charge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            calls = {"count": 0}

            def fake_basic_review(trades, target_trade_id=None, analysis_focus="balanced"):
                calls["count"] += 1
                return {
                    "status": "ready",
                    "source": "openai",
                    "review_type": "basic",
                    "summary": f"ok-{calls['count']}",
                }

            main.build_basic_ai_review = fake_basic_review
            batch = _basic_batch(main)

            first = main.get_journal_ai_review_once(batch, authorization=token, x_idempotency_key="same-request-1")
            second = main.get_journal_ai_review_once(batch, authorization=token, x_idempotency_key="same-request-1")
            entitlements = access_control.get_user_entitlements(
                authorization=token,
                entitlement_token="",
            )

            self.assertEqual("ok-1", first["summary"])
            self.assertEqual("ok-1", second["summary"])
            self.assertTrue(second["access"]["idempotent_replay"])
            self.assertEqual(1, calls["count"])
            self.assertEqual(4, entitlements["basic"]["signup_remaining"])

    def test_openai_text_is_plain_string_and_idempotency_replay_is_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            ai_review_v2 = importlib.import_module("core.ai_review_v2")
            calls = {"count": 0}

            def fake_basic_review(trades, target_trade_id=None, analysis_focus="balanced"):
                calls["count"] += 1
                return {
                    "status": "ready",
                    "source": "openai",
                    "review_type": "basic",
                    "model": "gpt-5.6-luna",
                    "summary": ai_review_v2._OpenAiReviewText(
                        "visible OpenAI review",
                        response_status="completed",
                    ),
                }

            main.build_basic_ai_review = fake_basic_review
            batch = _basic_batch(main)

            first = main.get_journal_ai_review_once(
                batch,
                authorization=token,
                x_idempotency_key="openai-text-request-1",
            )
            second = main.get_journal_ai_review_once(
                batch,
                authorization=token,
                x_idempotency_key="openai-text-request-1",
            )
            entitlements = access_control.get_user_entitlements(authorization=token, entitlement_token="")

            self.assertIs(str, type(first["summary"]))
            self.assertIs(str, type(second["summary"]))
            self.assertEqual("visible OpenAI review", first["summary"])
            self.assertEqual(first["summary"], second["summary"])
            self.assertFalse(first["access"]["idempotent_replay"])
            self.assertTrue(second["access"]["idempotent_replay"])
            self.assertEqual(1, calls["count"])
            self.assertEqual(4, entitlements["basic"]["signup_remaining"])

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

    def test_idempotency_abort_does_not_remove_completed_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            cache_key = main._ai_review_idempotency_cache_key(token, "completed-request-1")
            main._ai_review_idempotency_cache[cache_key] = {
                "status": "done",
                "result": {"summary": "completed"},
                "payload_fingerprint": "fingerprint",
                "expires_at": main.datetime.datetime.now(main.datetime.timezone.utc)
                + main.datetime.timedelta(minutes=5),
            }

            main._abort_ai_review_idempotency(cache_key)

            self.assertIn(cache_key, main._ai_review_idempotency_cache)

    def test_two_intentional_basic_reviews_consume_two_available_free_credits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            os.environ["ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE"] = "10"
            calls = {"count": 0}

            def fake_basic_review(trades, target_trade_id=None, analysis_focus="balanced"):
                calls["count"] += 1
                return {
                    "status": "ready",
                    "source": "openai",
                    "review_type": "basic",
                    "summary": f"ok-{calls['count']}",
                }

            main.build_basic_ai_review = fake_basic_review
            batch = _basic_batch(main)

            first = main.get_journal_ai_review_once(batch, authorization=token, x_idempotency_key="request-1")
            second = main.get_journal_ai_review_once(batch, authorization=token, x_idempotency_key="request-2")
            entitlements = access_control.get_user_entitlements(authorization=token, entitlement_token="")

            self.assertEqual("ok-1", first["summary"])
            self.assertEqual("ok-2", second["summary"])
            self.assertEqual(2, calls["count"])
            self.assertEqual(3, entitlements["basic"]["signup_remaining"])
            self.assertEqual(4, entitlements["basic"]["free_available_now"])
            self.assertEqual(2, entitlements["basic"]["rewarded_ad_available"])

    def test_daily_free_balance_does_not_include_ad_only_capacity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, access_control, token = _load_main_with_temp_state(tmpdir)

            for _ in range(6):
                access_control.verify_ai_review_access(
                    authorization=token,
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )

            entitlements = access_control.get_user_entitlements(authorization=token, entitlement_token="")

            self.assertEqual(0, entitlements["basic"]["free_available_now"])
            self.assertEqual(2, entitlements["basic"]["rewarded_ad_available"])
            with self.assertRaises(HTTPException) as blocked:
                access_control.verify_ai_review_access(
                    authorization=token,
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )
            self.assertEqual(402, blocked.exception.status_code)
            self.assertIn("광고", blocked.exception.detail)

    def test_ai_review_idempotency_key_rejects_different_payload_without_charging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            calls = {"count": 0}

            def fake_basic_review(trades, target_trade_id=None, analysis_focus="balanced"):
                calls["count"] += 1
                return {
                    "status": "ready",
                    "source": "openai",
                    "review_type": "basic",
                    "summary": f"ok-{calls['count']}",
                }

            main.build_basic_ai_review = fake_basic_review
            first_batch = _basic_batch(main)
            second_batch = _basic_batch(main)
            second_batch.trades[0].price = 71000

            first = main.get_journal_ai_review_once(first_batch, authorization=token, x_idempotency_key="same-request-1")
            with self.assertRaises(HTTPException) as blocked:
                main.get_journal_ai_review_once(second_batch, authorization=token, x_idempotency_key="same-request-1")
            entitlements = access_control.get_user_entitlements(
                authorization=token,
                entitlement_token="",
            )

            self.assertEqual("ok-1", first["summary"])
            self.assertEqual(409, blocked.exception.status_code)
            self.assertIn("Idempotency key", blocked.exception.detail)
            self.assertEqual(1, calls["count"])
            self.assertEqual(4, entitlements["basic"]["signup_remaining"])

    def test_ai_review_idempotency_cache_key_does_not_expose_request_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            idempotency_key = "same-request-1"

            cache_key = main._ai_review_idempotency_cache_key(token, idempotency_key)

            self.assertNotIn(token, cache_key)
            self.assertNotIn(idempotency_key, cache_key)

    def test_ai_review_idempotency_ttl_has_upper_bound(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS"] = "999999"
            main, _, _ = _load_main_with_temp_state(tmpdir)

            self.assertEqual(3600, main._ai_review_idempotency_ttl_seconds())

    def test_ai_review_idempotency_cache_has_maximum_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            previous_max_size = main.AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE
            try:
                main.AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE = 3
                now = main.datetime.datetime.now(main.datetime.timezone.utc)
                main._ai_review_idempotency_cache = {
                    f"old-{index}": {
                        "status": "done",
                        "result": {"summary": f"old-{index}"},
                        "payload_fingerprint": f"old-{index}",
                        "expires_at": now + main.datetime.timedelta(seconds=300 + index),
                    }
                    for index in range(3)
                }

                cache_key, replay = main._begin_ai_review_idempotency(
                    token,
                    "new-request-1",
                    "new-payload",
                )

                self.assertIsNone(replay)
                self.assertIn(cache_key, main._ai_review_idempotency_cache)
                self.assertLessEqual(len(main._ai_review_idempotency_cache), 3)
            finally:
                main.AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE = previous_max_size


if __name__ == "__main__":
    unittest.main()
