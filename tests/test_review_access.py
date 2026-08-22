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


class ReviewAccessTest(unittest.TestCase):
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

    def test_review_access_is_off_or_expired_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from backend.core import account_store

            with patch.dict(os.environ, self._configured_env(tmpdir, enabled="false"), clear=False):
                account_store = importlib.reload(account_store)
                self.assertFalse(account_store.get_review_access_status()["enabled"])
                with self.assertRaises(HTTPException) as raised:
                    account_store.login_review_access(review_id="play-review-id", password="play-review-password")
                self.assertEqual(401, raised.exception.status_code)

            expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            with patch.dict(os.environ, self._configured_env(tmpdir, expires_at=expired), clear=False):
                account_store = importlib.reload(account_store)
                self.assertFalse(account_store.get_review_access_status()["enabled"])
                with self.assertRaises(HTTPException) as raised:
                    account_store.login_review_access(review_id="play-review-id", password="play-review-password")
                self.assertEqual(401, raised.exception.status_code)

    def test_review_login_uses_normal_session_and_isolated_pro_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from backend.core import account_store

            env = self._configured_env(tmpdir)
            with patch.dict(os.environ, env, clear=False):
                account_store, access_control = self._load_modules()
                session = account_store.login_review_access(
                    review_id="play-review-id",
                    password="play-review-password",
                )
                access_control.initialize_review_entitlement(session["user"]["id"])

                entitlements = access_control.get_user_entitlements(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                )
                self.assertEqual("pro", entitlements["plan"])
                self.assertEqual("review", entitlements["user"]["auth_mode"])
                self.assertEqual(100, entitlements["basic"]["pro_monthly_remaining"])
                self.assertEqual(100, entitlements["advanced"]["pro_monthly_remaining"])
                self.assertTrue(session["user"]["journal_storage_enabled"])

                ad_status = access_control.get_rewarded_ad_status(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                    purpose="basic_review",
                )
                self.assertFalse(ad_status["ready"])
                self.assertEqual("pro", ad_status["wallet"]["plan"])
                ad_claim = access_control.claim_rewarded_ad_progress(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                    ad_reward_token="unexpected-token",
                )
                self.assertEqual("pro_no_ads", ad_claim["ad_reward"]["blocked_reason"])

                basic = access_control.verify_ai_review_access(
                    authorization=f"Bearer {session['session_token']}",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )
                advanced = access_control.verify_ai_review_access(
                    authorization=f"Bearer {session['session_token']}",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="advanced",
                )
                self.assertEqual("review_basic", basic.source)
                self.assertEqual("review_advanced", advanced.source)

                after_use = access_control.get_user_entitlements(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                )
                self.assertEqual(99, after_use["basic"]["pro_monthly_remaining"])
                self.assertEqual(99, after_use["advanced"]["pro_monthly_remaining"])

                access_control.refund_ai_review_access(basic)
                access_control.refund_ai_review_access(advanced)
                restored = access_control.get_user_entitlements(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                )
                self.assertEqual(100, restored["basic"]["pro_monthly_remaining"])
                self.assertEqual(100, restored["advanced"]["pro_monthly_remaining"])

                with closing(sqlite3.connect(env["ALPHAMATE_ACCESS_DB_PATH"])) as conn:
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM google_play_purchases").fetchone()[0])
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM google_play_subscriptions").fetchone()[0])
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM purchase_credit_orders").fetchone()[0])
                    self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM review_entitlement_usage WHERE status = 'reversed'").fetchone()[0])

    def test_review_credentials_are_generic_and_normal_user_has_no_review_entitlement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._configured_env(tmpdir)
            with patch.dict(os.environ, env, clear=False):
                account_store, access_control = self._load_modules()
                with self.assertRaises(HTTPException) as raised:
                    account_store.login_review_access(review_id="play-review-id", password="wrong")
                self.assertEqual(401, raised.exception.status_code)
                self.assertIn("credentials", raised.exception.detail)
                with self.assertRaises(HTTPException) as raised:
                    account_store.login_dev_provider(
                        provider="review",
                        provider_user_id="google-play-reviewer",
                        display_name="심사 계정",
                    )
                self.assertEqual(400, raised.exception.status_code)

                normal = account_store.login_dev_provider(
                    provider="kakao",
                    provider_user_id="normal-user",
                    display_name="일반 사용자",
                )
                normal_entitlements = access_control.get_user_entitlements(
                    authorization=f"Bearer {normal['session_token']}",
                    entitlement_token="",
                )
                self.assertEqual("free", normal_entitlements["plan"])
                self.assertNotEqual("review", normal_entitlements["user"]["auth_mode"])

    def test_review_session_loses_access_when_disabled_or_entitlement_expires(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._configured_env(tmpdir)
            with patch.dict(os.environ, env, clear=False):
                account_store, access_control = self._load_modules()
                session = account_store.login_review_access(
                    review_id="play-review-id",
                    password="play-review-password",
                )
                access_control.initialize_review_entitlement(session["user"]["id"])
                token = f"Bearer {session['session_token']}"

                os.environ["ALPHAMATE_REVIEW_ACCESS_ENABLED"] = "false"
                with self.assertRaises(HTTPException) as raised:
                    account_store.authenticate_session(token)
                self.assertEqual(401, raised.exception.status_code)

                os.environ["ALPHAMATE_REVIEW_ACCESS_ENABLED"] = "true"
                os.environ["ALPHAMATE_REVIEW_ACCESS_USER_KEY"] = "rotated-review-user"
                account_store = importlib.reload(account_store)
                with self.assertRaises(HTTPException) as raised:
                    account_store.authenticate_session(token)
                self.assertEqual(401, raised.exception.status_code)
                os.environ["ALPHAMATE_REVIEW_ACCESS_USER_KEY"] = "google-play-reviewer"
                with closing(sqlite3.connect(env["ALPHAMATE_ACCESS_DB_PATH"])) as conn:
                    conn.execute(
                        "UPDATE review_entitlements SET expires_at = ? WHERE user_id = ?",
                        ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), session["user"]["id"]),
                    )
                    conn.commit()
                entitlements = access_control.get_user_entitlements(authorization=token, entitlement_token="")
                self.assertEqual("free", entitlements["plan"])
                self.assertEqual(0, entitlements["basic"]["pro_monthly_remaining"])

    def test_review_login_route_seeds_examples_and_runs_both_ai_review_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._configured_env(tmpdir)
            env.update({
                "ALPHAMATE_JOURNAL_DB_PATH": os.path.join(tmpdir, "trades.sqlite3"),
                "ALPHAMATE_REVIEW_HISTORY_DB_PATH": os.path.join(tmpdir, "review-history.sqlite3"),
                "ALPHAMATE_EVENT_LOG_DB_PATH": os.path.join(tmpdir, "events.sqlite3"),
            })
            with patch.dict(os.environ, env, clear=False):
                account_store, access_control = self._load_modules()
                backend_dir = os.path.join(os.getcwd(), "backend")
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                import main

                main = importlib.reload(main)
                request = SimpleNamespace(headers={}, client=SimpleNamespace(host="review-test"))
                session = main.post_auth_review_login(
                    main.AuthReviewLoginIn(review_id="play-review-id", password="play-review-password"),
                    request,
                )
                token = f"Bearer {session['session_token']}"
                self.assertEqual(2, len(main.get_journal_trades(authorization=token)))
                self.assertEqual("pro", main.get_journal_entitlements(authorization=token, entitlement_token=None)["plan"])

                original_basic = main.build_basic_ai_review
                original_advanced = main.build_advanced_ai_review
                original_charts = main.build_journal_charts
                try:
                    main.build_journal_charts = lambda trades: {"charts": []}
                    main.build_basic_ai_review = lambda trades, target_trade_id=None, analysis_focus="balanced": {
                        "status": "ready",
                        "source": "test",
                        "review_type": "basic",
                        "summary": "basic review",
                        "chart_contexts": [],
                        "chart_reviews": [],
                    }
                    main.build_advanced_ai_review = lambda trades, target_trade_id=None: {
                        "status": "ready",
                        "source": "test",
                        "review_type": "advanced",
                        "summary": "advanced review",
                        "chart_contexts": [],
                        "chart_reviews": [],
                    }
                    basic_batch = main.JournalAiReviewIn(
                        trades=[main.JournalTradeIn(
                            trade_date="2026-08-20T10:00",
                            ticker="005930",
                            name="삼성전자 (예시)",
                            side="buy",
                            price=70000,
                            quantity=1,
                        )],
                        privacy_consent=True,
                        review_type="basic",
                    )
                    advanced_batch = basic_batch.model_copy(update={"review_type": "advanced"})
                    basic_result = main.get_journal_ai_review_once(basic_batch, authorization=token)
                    advanced_result = main.get_journal_ai_review_once(advanced_batch, authorization=token)
                    self.assertEqual("review_basic", basic_result["access"]["source"])
                    self.assertEqual("review_advanced", advanced_result["access"]["source"])
                finally:
                    main.build_basic_ai_review = original_basic
                    main.build_advanced_ai_review = original_advanced
                    main.build_journal_charts = original_charts

                with closing(sqlite3.connect(env["ALPHAMATE_ACCESS_DB_PATH"])) as conn:
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM google_play_purchases").fetchone()[0])
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM google_play_subscriptions").fetchone()[0])
                    self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM purchase_credit_orders").fetchone()[0])

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
