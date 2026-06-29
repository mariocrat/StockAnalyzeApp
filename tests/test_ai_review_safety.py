import importlib
import os
import sys
import tempfile
import unittest
from fastapi import HTTPException


def _load_main_with_temp_state(tmpdir):
    os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
    os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
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


class AiReviewSafetyTest(unittest.TestCase):
    ENV_KEYS = [
        "ALPHAMATE_ACCOUNT_DB_PATH",
        "ALPHAMATE_ACCESS_DB_PATH",
        "ALPHAMATE_ALLOW_DEV_ACCESS",
        "ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE",
        "ALPHAMATE_AI_REVIEW_MAX_CONCURRENT",
        "ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS",
    ]

    def setUp(self):
        self._previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_ai_review_rate_limit_rejects_repeated_user_requests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, _, token = _load_main_with_temp_state(tmpdir)
            main.build_basic_ai_review = lambda trades, target_trade_id=None: {
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
            main.build_basic_ai_review = lambda trades, target_trade_id=None: {
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

            def fake_basic_review(trades, target_trade_id=None):
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

    def test_ai_review_idempotency_key_rejects_different_payload_without_charging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, access_control, token = _load_main_with_temp_state(tmpdir)
            calls = {"count": 0}

            def fake_basic_review(trades, target_trade_id=None):
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
