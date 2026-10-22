from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from core.review_display_contract import SCHEMA_VERSION

from tests.api_test_modules import api_module_state
from tests.review_source_fixtures import approved_route_fixture, compact_chart_fixture
from tests.test_review_finalizer_compatibility import model_output

import importlib
import json
import os
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException


class ReviewAccessTest(unittest.TestCase):
    def test_debug_tester_requires_real_session_marker_allowlist_and_consent(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state():
            account_store, access_control = self._load_modules()
            session = account_store.login_dev_provider(
                provider="kakao", provider_user_id="synthetic-owner", display_name="Synthetic owner")
            token = f"Bearer {session['session_token']}"
            user_id = session["user"]["id"]
            with patch.dict(os.environ, {
                "ALPHAMATE_ENV": "production", "ALPHAMATE_ALLOW_DEV_ACCESS": "false",
                "ALPHAMATE_DEBUG_REVIEW_TESTER_USER_IDS": f"other-user, {user_id}",
            }):
                before = access_control.get_user_entitlements(authorization=token, entitlement_token="")
                self.assertFalse(before["debug_review_tester"])
                self.assertTrue(access_control.get_user_entitlements(
                    authorization=token, entitlement_token="", client_marker="debug")["debug_review_tester"])
                with patch.object(access_control, "_consume_basic", side_effect=AssertionError("quota consumed")), \
                     patch.object(access_control, "_consume_advanced", side_effect=AssertionError("quota consumed")), \
                     patch.object(access_control, "_consume_ad_reward", side_effect=AssertionError("ad consumed")), \
                     patch.object(access_control, "_save_wallet", side_effect=AssertionError("wallet write")):
                    for review_type in ("basic", "advanced"):
                        for _ in range(3):
                            access = access_control.verify_ai_review_access(
                                authorization=token, ad_reward_token="", entitlement_token="",
                                privacy_consent=True, review_type=review_type, client_marker="debug")
                            self.assertEqual(f"debug_tester_{review_type}", access.source)
                            self.assertEqual("session", access.auth_mode)
                            self.assertEqual(before["basic"], access.product_balances["basic"])
                            self.assertEqual(before["advanced"], access.product_balances["advanced"])
                            self.assertEqual(access.product_balances, access_control.refund_ai_review_access(access))
                for consent, authorization, expected in ((False, token, 400), (True, None, 401),
                                                          (True, "Bearer dev-token", 401)):
                    with self.assertRaises(HTTPException) as raised:
                        access_control.verify_ai_review_access(
                            authorization=authorization, ad_reward_token="", entitlement_token="",
                            privacy_consent=consent, review_type="advanced", client_marker="debug")
                    self.assertEqual(expected, raised.exception.status_code)

    def test_non_allowlisted_debug_and_release_keep_ordinary_quota(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state():
            account_store, access_control = self._load_modules()
            session = account_store.login_dev_provider(
                provider="naver", provider_user_id="synthetic-normal", display_name="Synthetic normal")
            token, user_id = f"Bearer {session['session_token']}", session["user"]["id"]
            for allowlist, marker in (("other-user", "debug"), ("", "debug"),
                                      (user_id, None), (user_id, "release"), (user_id, "DEBUG")):
                with self.subTest(allowlisted=allowlist == user_id, marker=marker), patch.dict(os.environ, {
                    "ALPHAMATE_ENV": "production", "ALPHAMATE_ALLOW_DEV_ACCESS": "false",
                    "ALPHAMATE_DEBUG_REVIEW_TESTER_USER_IDS": allowlist,
                }):
                    before = access_control.get_user_entitlements(authorization=token, entitlement_token="")
                    access = access_control.verify_ai_review_access(
                        authorization=token, ad_reward_token="", entitlement_token="",
                        privacy_consent=True, review_type="basic", client_marker=marker)
                    self.assertEqual("signup_basic", access.source)
                    self.assertEqual(before["basic"]["signup_remaining"] - 1,
                                     access.product_balances["basic"]["signup_remaining"])
                    access_control.refund_ai_review_access(access)
                    with self.assertRaises(HTTPException) as raised:
                        access_control.verify_ai_review_access(
                            authorization=token, ad_reward_token="", entitlement_token="",
                            privacy_consent=True, review_type="advanced", client_marker=marker)
                    self.assertEqual(402, raised.exception.status_code)

    def test_debug_tester_route_and_execution_cache_preserve_no_charge_identity(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state():
            account_store, access_control = self._load_modules()
            session = account_store.login_dev_provider(
                provider="kakao", provider_user_id="synthetic-route-owner", display_name="Synthetic route")
            token, user_id = f"Bearer {session['session_token']}", session["user"]["id"]
            main = importlib.import_module("main")
            ai = importlib.import_module("core.ai_review_v2")
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            with patch.dict(os.environ, {
                "ALPHAMATE_ENV": "production", "ALPHAMATE_ALLOW_DEV_ACCESS": "false",
                "ALPHAMATE_DEBUG_REVIEW_TESTER_USER_IDS": user_id,
            }), patch.object(main, "build_journal_charts", return_value={"charts": []}), \
                 patch.object(ai, "_compact_chart_snapshot", return_value=compact_chart_fixture()), \
                 patch.object(ai, "_contexts_for_trades", return_value=[]), \
                 patch.object(access_control, "_save_wallet", side_effect=AssertionError("wallet write")):
                batch = main.JournalAiReviewIn(
                    trades=[main.JournalReviewTradeIn(trade_date="2026-09-02T09:00", ticker="005930",
                                                     name="Synthetic", side="buy", price=70000, quantity=1, fee=0, tax=0)],
                    privacy_consent=True)
                for review_type in ("basic", "advanced"):
                    with patch.object(ai, "_call_openai_review", return_value=json.dumps(model_output(review_type), ensure_ascii=False)) as generated:
                        args = dict(authorization=token, x_idempotency_key=f"tester-{review_type}",
                                    x_review_display_contract=[SCHEMA_VERSION], x_stockboda_client="debug")
                        typed_batch = batch.model_copy(update={"review_type": review_type})
                        first = main.get_journal_ai_review_once(typed_batch, **args)
                        replay = main.get_journal_ai_review_once(typed_batch, **args)
                        self.assertEqual("ready", first["status"], (review_type, first.get("internal_status"), first.get("source")))
                        self.assertEqual(f"debug_tester_{review_type}", first["access"]["source"])
                        self.assertTrue(replay["access"]["idempotent_replay"])
                        self.assertEqual(first["display_snapshot"], replay["display_snapshot"])
                        self.assertEqual(1, generated.call_count)
                        detail = main.get_journal_review_history_detail(
                            first["review_history_id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
                        self.assertEqual(first["display_snapshot"], detail["ai_review"]["display_snapshot"])
                        self.assertEqual(f"debug_tester_{review_type}", detail["access_snapshot"]["source"])

    def _configured_env(self, tmpdir, *, enabled="true", expires_at=None):
        from core import account_store

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
        from core import access_control, account_store

        account_store = importlib.reload(account_store)
        access_control = importlib.reload(access_control)
        return account_store, access_control

    def test_review_access_is_off_or_expired_by_default(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true") as storage, api_module_state() as modules:
            tmpdir = storage.root
            from core import account_store

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
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true") as storage, api_module_state() as modules:
            tmpdir = storage.root
            from core import account_store

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
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true") as storage, api_module_state() as modules:
            tmpdir = storage.root
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
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true") as storage, api_module_state() as modules:
            tmpdir = storage.root
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
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true") as storage, api_module_state() as modules:
            tmpdir = storage.root
            env = self._configured_env(tmpdir)
            env.update({
                "ALPHAMATE_JOURNAL_DB_PATH": os.path.join(tmpdir, "trades.sqlite3"),
                "ALPHAMATE_REVIEW_HISTORY_DB_PATH": os.path.join(tmpdir, "review-history.sqlite3"),
                "ALPHAMATE_EVENT_LOG_DB_PATH": os.path.join(tmpdir, "events.sqlite3"),
            })
            with patch.dict(os.environ, env, clear=False):
                account_store, access_control = self._load_modules()
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
                    main.build_basic_ai_review = lambda trades, target_trade_id=None, analysis_focus="balanced", **kwargs: approved_route_fixture(
                        "basic review", approval_state=kwargs["approval_state"], chart_contexts=[], chart_reviews=[])
                    main.build_advanced_ai_review = lambda trades, target_trade_id=None, **kwargs: approved_route_fixture(
                        "advanced review", approval_state=kwargs["approval_state"], review_type="advanced", chart_contexts=[], chart_reviews=[])
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
                    basic_result = main.get_journal_ai_review_once(basic_batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
                    advanced_result = main.get_journal_ai_review_once(advanced_batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
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



if __name__ == "__main__":
    unittest.main()
