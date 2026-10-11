"""F3 Step 1 observations of real producers; no new write validator.

All identities, subscriptions, entitlements and records are synthetic and live
inside H4. Model/market boundaries are mocked; access/auth/history stay real.
Assertions describe current output, including exceptions that Step 2 must reject.
"""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import copy
import datetime
import importlib
import json
import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi import HTTPException

from tests.api_test_modules import api_module_state
from tests.review_source_fixtures import compact_chart_fixture
from tests.test_review_finalizer_compatibility import model_output
from backend.core.review_display_contract import SCHEMA_VERSION
from backend.core.review_legacy_compatibility import admit_legacy_body


# Independent declarations: do not derive expected keys/types from admission.
BASIC = dict.fromkeys((
    "signup_remaining", "free_daily_remaining", "free_daily_max_remaining", "free_available_now",
    "rewarded_ad_available", "rewarded_ad_daily_remaining", "free_monthly_remaining",
    "free_monthly_limit", "pro_monthly_remaining", "purchased_remaining",
), int)
ADVANCED = dict.fromkeys((
    "signup_remaining", "pro_monthly_remaining", "weekly_reward_remaining", "weekly_advanced_granted",
    "weekly_ad_views", "weekly_ad_views_needed", "purchased_remaining", "max_hold",
), int)
PRODUCT_VALUES = {
    "basic_review_15": {"kind": "basic", "quantity": 15, "price_krw": 2900},
    "basic_review_25": {"kind": "basic", "quantity": 25, "price_krw": 4500},
    "advanced_review_10": {"kind": "advanced", "quantity": 10, "price_krw": 3900},
    "advanced_review_20": {"kind": "advanced", "quantity": 20, "price_krw": 6900},
}
RESETS = ("daily_reset_at", "weekly_reset_at", "monthly_reset_at", "weekly_reward_expires_at")
VALIDITY = {
    "timezone": str, **dict.fromkeys(RESETS, (str, type(None))),
    "signup_pass_expires_at": type(None), "purchased_pass_expires_at": type(None),
    "pro_allowance_resets_at": (str, type(None)),
}
WALLET = {
    "plan": str, "basic": BASIC, "advanced": ADVANCED,
    "products": {key: {"kind": str, "quantity": int, "price_krw": int} for key in PRODUCT_VALUES},
    "settings": {
        "allow_advanced_ticket_for_basic": bool,
        "ad_policy": {
            "basic_reviews_per_rewarded_ad": int, "rewarded_basic_daily_max": int,
            "ads_per_advanced_ticket": int, "force_rewarded_ad_chain": bool,
            "preferred_rewarded_ad_sequence": str,
        },
        "free_policy": {
            "daily_basic": int, "rewarded_basic_daily_max": int,
            "monthly_basic_max": int, "weekly_advanced_max": int,
        },
    },
    "validity": VALIDITY,
}
ACCESS = {
    "auth_mode": str, "plan": str, "review_type": str, "source": str,
    "quota": {"basic": BASIC, "advanced": ADVANCED}, "wallet": WALLET,
    "refunded": bool, "idempotent_replay": bool,
}
EXPIRY = "2099-11-02T12:34:56Z"


class HistoryProducerTest(unittest.TestCase):
    def setUp(self):
        self.fixture = self.enterContext(storage_fixture(
            ALPHAMATE_ALLOW_DEV_ACCESS="true", ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE="60"))
        modules = self.enterContext(api_module_state())
        self.main, self.accounts, self.access, self.history = (
            modules.main, modules.account_store, modules.access_control, modules.review_history)
        self.ai = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai.__dict__))
        importlib.reload(self.ai)
        original_datetime = datetime.datetime
        self.clock = [original_datetime(2026, 10, 9, 3, 30, tzinfo=datetime.timezone.utc)]

        class ProducerDateTime(original_datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(self.clock[0].timestamp(), tz)

        self.enterContext(patch.object(datetime, "datetime", ProducerDateTime))
        self.enterContext(patch.dict(os.environ, {
            "OPENAI_API_KEY": "", "ALPHAMATE_OPENAI_API_KEY": "",
            "ALPHAMATE_REVIEW_ACCESS_ENABLED": "true",
            "ALPHAMATE_REVIEW_ACCESS_ID": "synthetic-producer-review",
            "ALPHAMATE_REVIEW_ACCESS_PASSWORD_HASH": self.accounts.hash_review_password(
                "synthetic-producer-password", iterations=100_000),
            "ALPHAMATE_REVIEW_ACCESS_EXPIRES_AT": EXPIRY,
        }))
        self.enterContext(patch.object(self.ai, "_compact_chart_snapshot", return_value=compact_chart_fixture()))
        self.enterContext(patch.object(self.ai, "_contexts_for_trades", return_value=[]))
        self.enterContext(patch.object(self.ai, "get_review_stock_ohlcv", side_effect=AssertionError("market boundary")))
        self.enterContext(patch.object(self.main, "build_journal_charts", return_value={"charts": []}))
        self.trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "005930", "name": "합성 종목",
             "side": "buy", "price": 70000, "quantity": 1, "fee": 0, "tax": 0, "memo": "", "source": "manual"},
            {"id": 2, "trade_date": "2026-07-10T10:00", "ticker": "005930", "name": "합성 종목",
             "side": "sell", "price": 70900, "quantity": 1, "fee": 0, "tax": 0, "memo": "", "source": "manual"},
        ]
        self.sequence = 0

    def shape(self, value, schema):
        if type(schema) is dict:
            self.assertIs(type(value), dict)
            self.assertEqual(set(value), set(schema))
            for key, child in schema.items():
                self.shape(value[key], child)
        else:
            self.assertIn(type(value), schema if type(schema) is tuple else (schema,))
            if type(value) is int:
                self.assertGreaterEqual(value, 0)

    def subscription(self, user_id, expiry=EXPIRY):
        self.access._save_google_subscription(
            user_id=user_id, token_hash="synthetic-subscription-" + user_id,
            local_product_id="pro_monthly", google_product_id="pro_monthly",
            status="SUBSCRIPTION_STATE_ACTIVE", expiry_time=expiry,
            auto_renewing=True, latest_order_id="synthetic-order-" + user_id)

    def identity(self, variant, *, expiry=EXPIRY):
        self.sequence += 1
        if variant == "review":
            session = self.accounts.login_review_access(
                review_id="synthetic-producer-review", password="synthetic-producer-password")
            self.access.initialize_review_entitlement(session["user"]["id"], expires_at=expiry)
        else:
            login = self.accounts.login_dev_provider if variant.startswith("dev-session") else self.accounts.login_provider_identity
            session = login(provider="kakao", provider_user_id=f"producer-{self.sequence}", display_name="합성 사용자")
            self.access.grant_first_login_advanced_review(session["user"]["id"])
            if variant == "session-pro":
                self.subscription(session["user"]["id"], expiry)
        token = "Bearer " + session["session_token"]
        self.accounts.update_journal_storage_setting(authorization=token, enabled=True)
        return session["user"]["id"], token

    def route(self, variant, review_type, status, *, token=None, target=2, trades=None, save=True, keyed=True):
        if token is None:
            _, token = self.identity(variant)
        batch = self.main.JournalAiReviewIn(
            privacy_consent=True, review_type=review_type, target_trade_id=target,
            entitlement_token="dev-pro-entitlement" if variant == "dev-session-pro" else "",
            trades=[self.main.JournalTradeIn(**trade) for trade in (self.trades if trades is None else trades)])
        with ExitStack() as stack:
            if status == "ready":
                stack.enter_context(patch.object(self.ai, "_call_openai_review",
                                                  return_value=json.dumps(model_output(review_type), ensure_ascii=False)))
            else:
                # Exercise the actual no-key path, before urllib/provider access.
                stack.enter_context(patch.object(self.ai.urllib.request, "urlopen", side_effect=AssertionError("missing-key network")))
            snapshots = []
            original_save = self.main._save_ai_review_history_if_enabled

            def capture(**kwargs):
                snapshots.append((copy.deepcopy(kwargs["result"]), kwargs["history_state"]))
                return original_save(**kwargs) if save else None

            stack.enter_context(patch.object(self.main, "_save_ai_review_history_if_enabled", side_effect=capture))
            self.sequence += 1
            result = self.main.get_journal_ai_review_once(
                batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION],
                x_idempotency_key=f"producer-{self.sequence}" if keyed else None)
        self.assertEqual(status, result["status"])
        return result, snapshots[0]

    def test_storage_variant_matrix_uses_real_auth_access_builders_and_writer(self):
        for variant in ("session-free", "session-pro", "review", "dev-session-free", "dev-session-pro"):
            for review_type in ("basic", "advanced"):
                for status in ("ready", "missing_key"):
                    with self.subTest(variant=variant, review_type=review_type, status=status), patch.dict(
                            os.environ, {"ALPHAMATE_ALLOW_DEV_ACCESS": str(variant.startswith("dev-session")).lower()}):
                        user_id, token = self.identity(variant)
                        result, (candidate, state) = self.route(variant, review_type, status, token=token)
                        self.shape(candidate["access"], ACCESS)
                        access, wallet = candidate["access"], candidate["access"]["wallet"]
                        plan = "pro" if variant in ("session-pro", "review", "dev-session-pro") else "free"
                        self.assertEqual(("review" if variant == "review" else "session", plan, plan, review_type),
                                         (access["auth_mode"], access["plan"], wallet["plan"], access["review_type"]))
                        expected_source = (f"review_{review_type}" if variant == "review" else
                                           f"pro_monthly_{review_type}" if plan == "pro" else f"signup_{review_type}")
                        self.assertEqual(expected_source, access["source"])
                        self.assertEqual({key: wallet[key] for key in ("basic", "advanced")}, access["quota"])
                        self.assertEqual(PRODUCT_VALUES, wallet["products"])
                        self.assertIs(access["refunded"], False)
                        self.assertIs(access["idempotent_replay"], False)
                        expected_keys = {"status", "source", "review_type", "model", "summary", "display_snapshot",
                                         "structured_review", "chart_display_snapshot", "chart_contexts", "chart_reviews", "access",
                                         "chart_snapshot" if review_type == "basic" else "chart_snapshots"}
                        self.assertEqual(expected_keys, set(candidate))
                        self.assertEqual("openai" if status == "ready" else "chart-rules", candidate["source"])
                        self.assertIs(type(candidate["model"]), str if status == "ready" else type(None))
                        self.assertEqual({} if review_type == "basic" else [],
                                         candidate["chart_snapshot" if review_type == "basic" else "chart_snapshots"])
                        self.assertEqual(([], []), (candidate["chart_contexts"], candidate["chart_reviews"]))
                        sealed = json.loads(state["approved"]["snapshot"].json_text)
                        self.assertEqual(sealed["body"], candidate["display_snapshot"])
                        self.assertEqual(admit_legacy_body(sealed["body"]).summary, candidate["summary"])
                        self.assertEqual({key: sealed[key] for key in ("charts", "chart_cards")}, candidate["chart_display_snapshot"])
                        for key in RESETS:
                            self.assertIs(type(wallet["validity"][key]), type(None) if variant == "review" else str)
                        deadline = wallet["validity"]["pro_allowance_resets_at"]
                        self.assertEqual(None if plan == "free" else "2026-11-01T00:00+09:00" if variant == "dev-session-pro" else EXPIRY,
                                         deadline)
                        stored = self.history.get_review_history(result["review_history_id"], user_id=user_id)
                        self.assertEqual(candidate, stored["ai_review"])
                        self.assertEqual(access, stored["access_snapshot"])
                        self.assertEqual(candidate["model"] or "", stored["model"])

    def test_regular_wallet_relations_do_not_imply_spendable_free_balance(self):
        for plan in ("free", "pro"):
            user_id, _ = self.identity("session-" + plan)
            wallet = self.access._wallet_for(user_id, plan)
            wallet.usage.free_basic_monthly_used = 30
            snapshot = self.access._wallet_snapshot(wallet, plan, user_id)
            self.shape(snapshot, WALLET)
            basic, advanced, validity = snapshot["basic"], snapshot["advanced"], snapshot["validity"]
            self.assertEqual((1, 3, 6, 0, 30), tuple(basic[key] for key in (
                "free_daily_remaining", "free_daily_max_remaining", "free_available_now", "free_monthly_remaining", "free_monthly_limit")))
            self.assertEqual(2 if plan == "free" else 0, basic["rewarded_ad_daily_remaining"])
            self.assertEqual(basic["rewarded_ad_available"], basic["rewarded_ad_daily_remaining"])
            self.assertEqual(5, advanced["weekly_ad_views_needed"])
            self.assertEqual("2026-10-10T00:00+09:00", validity["daily_reset_at"])
            self.assertEqual("2026-10-12T00:00+09:00", validity["weekly_reset_at"])
            self.assertEqual(validity["weekly_reset_at"], validity["weekly_reward_expires_at"])
            self.assertEqual("2026-11-01T00:00+09:00", validity["monthly_reset_at"])
        for date_text, expected in (("2026-12-31", ("2027-01-01", "2027-01-04", "2027-01-01")),
                                    ("2028-02-28", ("2028-02-29", "2028-03-06", "2028-03-01"))):
            self.clock[0] = datetime.datetime.fromisoformat(date_text + "T03:30:00+00:00")
            deadlines = self.access._reset_deadlines()
            self.assertEqual(tuple(item + "T00:00+09:00" for item in expected),
                             tuple(deadlines[key] for key in ("daily", "weekly", "monthly")))

    def test_access_sources_follow_actual_consumption_branches(self):
        cases = (
            ("free", "basic", "signup_basic", "", {}),
            ("free", "basic", "free_daily_basic", "", {"basic_signup_remaining": 0}),
            ("free", "basic", "rewarded_ad_basic", "", {"basic_signup_remaining": 0, "free_basic_daily_used": 1}),
            ("free", "basic", "purchased_basic", "basic_review_15", {"basic_signup_remaining": 0, "free_basic_daily_used": 1}),
            ("free", "basic", "purchased_advanced_as_basic", "advanced_review_10", {"basic_signup_remaining": 0, "free_basic_daily_used": 1}),
            ("pro", "basic", "pro_monthly_basic", "", {}),
            ("pro", "basic", "purchased_basic", "basic_review_15", {"pro_basic_monthly_used": 35}),
            ("free", "advanced", "signup_advanced", "", {}),
            ("free", "advanced", "weekly_ad_advanced", "", {"signup_advanced_remaining": 0, "weekly_advanced": 1}),
            ("free", "advanced", "purchased_advanced", "advanced_review_10", {"signup_advanced_remaining": 0}),
            ("pro", "advanced", "pro_monthly_advanced", "", {}),
            ("pro", "advanced", "purchased_advanced", "advanced_review_10", {"pro_advanced_monthly_used": 25}),
            ("pro", "advanced", "signup_advanced", "", {"pro_advanced_monthly_used": 25}),
            ("pro", "advanced", "weekly_ad_advanced", "", {"pro_advanced_monthly_used": 25, "signup_advanced_remaining": 0, "weekly_advanced": 1}),
        )
        for plan, review_type, source, product, changes in cases:
            with self.subTest(plan=plan, review_type=review_type, source=source):
                user_id, token = self.identity("session-" + plan)
                if product:
                    self.access.apply_dev_purchase(authorization=token, entitlement_token="", product_id=product)
                wallet = self.access._wallet_for(user_id, plan)
                for key, value in changes.items():
                    setattr(wallet if hasattr(wallet, key) else wallet.usage, key, value)
                self.access._save_wallet(user_id, wallet)
                with patch.dict(os.environ, {"ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC": "true"}):
                    context = self.access.verify_ai_review_access(
                        authorization=token, entitlement_token="", privacy_consent=True, review_type=review_type,
                        ad_reward_token="dev-ad-reward" if source == "rewarded_ad_basic" else "")
                self.assertEqual(("session", plan, review_type, source),
                                 (context.auth_mode, context.plan, context.review_type, context.source))
                self.shape(context.product_balances, WALLET)
                self.assertEqual(bool(product), bool(context.source_order_id))

    def test_review_wallet_can_expire_after_consumption_and_exceed_regular_pro_limits(self):
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                self.clock[0] = datetime.datetime.fromisoformat("2026-10-09T03:30:00+00:00")
                user_id, token = self.identity("review", expiry="2026-10-09T03:31:00Z")
                before = self.access._review_entitlement_snapshot(user_id)
                self.assertGreater(before[review_type]["pro_monthly_remaining"], 35 if review_type == "basic" else 25)
                original_consume = self.access._consume_review_quota

                def expire_after_consume(*args):
                    event = original_consume(*args)
                    self.clock[0] += datetime.timedelta(minutes=2)
                    return event

                with patch.object(self.access, "_consume_review_quota", side_effect=expire_after_consume), patch.dict(
                        os.environ, {"ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC": "true"}):
                    result, (candidate, _) = self.route("review", review_type, status, token=token)
                access, wallet = candidate["access"], candidate["access"]["wallet"]
                self.assertEqual(("pro", "free", "review_" + review_type), (access["plan"], wallet["plan"], access["source"]))
                self.assertEqual({**dict.fromkeys(BASIC, 0), "free_monthly_limit": 30}, wallet["basic"])
                self.assertEqual({**dict.fromkeys(ADVANCED, 0), "max_hold": 1}, wallet["advanced"])
                self.assertFalse(wallet["settings"]["allow_advanced_ticket_for_basic"])
                self.assertEqual("2026-10-09T03:31:00Z", wallet["validity"]["pro_allowance_resets_at"])
                self.main._validate_ai_review_cached_access(access, review_type=review_type, status=status)
                self.assertIsNotNone(self.history.get_review_history(result["review_history_id"], user_id=user_id))

    def test_date_parsers_preserve_offset_variants_and_accept_replay_incompatible_values(self):
        for variant in ("session-pro", "review"):
            for expiry in (EXPIRY, "2099-11-02T21:34:56+09:00", "2099-11-02T12:34:56", "2099-11-02"):
                with self.subTest(variant=variant, expiry=expiry):
                    _, token = self.identity(variant, expiry=expiry)
                    _, (candidate, _) = self.route(variant, "basic", "missing_key", token=token, save=False, keyed=False)
                    self.assertEqual(expiry, candidate["access"]["wallet"]["validity"]["pro_allowance_resets_at"])
                    if datetime.datetime.fromisoformat(expiry).tzinfo is None:
                        with self.assertRaisesRegex(ValueError, "validity timezone"):
                            self.main._validate_ai_review_cached_access(candidate["access"], review_type="basic", status="missing_key")
                    else:
                        self.main._validate_ai_review_cached_access(candidate["access"], review_type="basic", status="missing_key")
        # ACTIVE/GRACE accepts unparseable subscription expiry; the raw value
        # still reaches the wallet. Step 2 must reject it before history writes.
        for expiry in ("", "not-a-date", "2099-02-30T00:00:00Z"):
            with self.subTest(expiry=expiry):
                self.assertTrue(self.access._subscription_is_active(status="SUBSCRIPTION_STATE_ACTIVE", expiry_time=expiry))
                _, token = self.identity("session-pro", expiry=expiry)
                _, (candidate, _) = self.route("session-pro", "basic", "missing_key", token=token, save=False, keyed=False)
                self.assertEqual(expiry, candidate["access"]["wallet"]["validity"]["pro_allowance_resets_at"])
                with self.assertRaisesRegex(ValueError, "validity timestamp"):
                    self.main._validate_ai_review_cached_access(candidate["access"], review_type="basic", status="missing_key")

    def test_dev_bearer_and_storage_off_do_not_create_history_state(self):
        for review_type in ("basic", "advanced"):
            for entitlement in ("", "dev-pro-entitlement"):
                batch = self.main.JournalAiReviewIn(privacy_consent=True, review_type=review_type, entitlement_token=entitlement,
                                                    trades=[self.main.JournalTradeIn(**trade) for trade in self.trades])
                self.assertEqual(("dev-user", "dev"), self.access._authenticate("Bearer dev-token"))
                with self.assertRaises(HTTPException) as raised:
                    self.accounts.authenticate_session("Bearer dev-token")
                self.assertEqual(401, raised.exception.status_code)
                self.assertIsNone(self.main._prepare_ai_review_history_state(
                    authorization="Bearer dev-token", batch=batch, trades=self.main._journal_batch_payload(batch)))
        _, token = self.identity("dev-session-free")
        self.accounts.update_journal_storage_setting(authorization=token, enabled=False)
        for status in ("ready", "missing_key"):
            for review_type in ("basic", "advanced"):
                # Fresh sessions keep both statuses supplied with a real quota.
                user_id, token = self.identity("dev-session-free")
                self.accounts.update_journal_storage_setting(authorization=token, enabled=False)
                result, (_, state) = self.route("dev-session-free", review_type, status, token=token)
                self.assertIsNone(state)
                self.assertNotIn("review_history_id", result)
                self.assertEqual([], self.history.list_review_history(user_id=user_id))
        with patch.dict(os.environ, {"ALPHAMATE_ALLOW_DEV_ACCESS": "false"}):
            self.assertEqual("free", self.access._plan_for(user_id, "dev-pro-entitlement"))
            with self.assertRaises(HTTPException):
                self.accounts.login_dev_provider(provider="kakao", provider_user_id="disabled-dev")

    def test_history_metadata_supports_unsaved_ids_and_unmatched_target_fallback(self):
        for review_type in ("basic", "advanced"):
            for target, identified in ((None, False), (999, True)):
                with self.subTest(review_type=review_type, target=target):
                    trades = copy.deepcopy(self.trades)
                    if not identified:
                        for trade in trades:
                            trade.pop("id")
                    _, (_, state) = self.route("session-free", review_type, "missing_key", target=target, trades=trades)
                    metadata = json.loads(state["approved"]["metadata_json"])
                    self.assertEqual(target, metadata["target_trade_id"])
                    self.assertEqual({"ticker", "name", "trade_date", "target_trade_id", "trade_snapshot",
                                      "recent_trades_snapshot", "chart_snapshot"}, set(metadata))
                    self.assertEqual(identified, "id" in metadata["trade_snapshot"])
                    self.assertEqual("2026-07-10T10:00", metadata["trade_date"])
                    self.assertIs(type(metadata["trade_snapshot"]["price"]), float)
                    self.assertEqual({"charts": []}, metadata["chart_snapshot"])

    def test_review_quota_configuration_and_invalid_dates_follow_source(self):
        for configured, expected in (("0", 1), ("1001", 1000), ("not-an-int", 100)):
            with self.subTest(configured=configured), patch.dict(os.environ, {
                    "ALPHAMATE_REVIEW_BASIC_QUOTA": configured, "ALPHAMATE_REVIEW_ADVANCED_QUOTA": configured}):
                # Use a new review identity so ON CONFLICT does not retain quotas.
                os.environ["ALPHAMATE_REVIEW_ACCESS_USER_KEY"] = "synthetic-quota-" + configured
                user_id, _ = self.identity("review")
                snapshot = self.access._review_entitlement_snapshot(user_id)
                self.assertEqual((expected, expected), tuple(snapshot[key]["pro_monthly_remaining"] for key in ("basic", "advanced")))
                with self.assertRaises(HTTPException) as raised:
                    self.access.initialize_review_entitlement(user_id, expires_at="2099-02-30T00:00:00Z")
                self.assertEqual(503, raised.exception.status_code)
