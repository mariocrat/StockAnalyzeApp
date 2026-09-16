"""H4-B1 deferred Google Play, AdMob and OIDC provider/verification tests."""

import base64
import datetime
import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]


def fake_service_account_json() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return json.dumps({
        "type": "service_account",
        "client_email": "play-api@example.iam.gserviceaccount.com",
        "private_key": private_key,
        "token_uri": "https://oauth2.googleapis.com/token",
    })


@contextmanager
def patched_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class BillingProviderVerificationTest(unittest.TestCase):


    def test_verified_google_play_subscription_enables_pro_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            future = "2099-01-01T00:00:00Z"
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "alphamate.pro.monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": future,
                "latest_order_id": "GPA.pro.1234",
                "auto_renewing": True,
            }

            result = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )
            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )

            self.assertEqual("pro", result["plan"])
            self.assertEqual("active", result["purchase"]["status"])
            self.assertEqual("pro", entitlements["plan"])
            self.assertEqual(35, entitlements["basic"]["pro_monthly_remaining"])
            self.assertEqual(25, entitlements["advanced"]["pro_monthly_remaining"])

    def test_google_play_subscription_stored_fields_are_length_limited(self):
        long_product_id = "alphamate.pro." + ("p" * 500)
        long_order_id = "GPA.pro." + ("o" * 500)
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_PRO_MONTHLY_ID=long_product_id,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": kwargs["google_product_id"],
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": long_order_id,
                "auto_renewing": True,
            }

            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )

            conn = access_control._connect_access_db()
            try:
                row = conn.execute("SELECT * FROM google_play_subscriptions LIMIT 1").fetchone()
            finally:
                conn.close()

            self.assertLessEqual(len(row["google_play_product_id"]), 120)
            self.assertLessEqual(len(row["latest_order_id"]), 120)

    def test_unacknowledged_google_play_subscription_is_acknowledged_before_pro_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "alphamate.pro.monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.unacknowledged",
                "auto_renewing": True,
                "acknowledgement_state": "ACKNOWLEDGEMENT_STATE_PENDING",
            }
            acknowledgements = []
            access_control._acknowledge_google_play_subscription = lambda **kwargs: acknowledgements.append(kwargs) or True

            result = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual("pro", result["plan"])
            self.assertTrue(result["purchase"]["acknowledged"])
            self.assertEqual(1, len(acknowledgements))
            self.assertEqual("alphamate.pro.monthly", acknowledgements[0]["google_product_id"])

    def test_failed_subscription_acknowledgement_does_not_enable_pro_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "pro_monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.unacknowledged",
                "auto_renewing": True,
                "acknowledgement_state": "ACKNOWLEDGEMENT_STATE_PENDING",
            }
            access_control._acknowledge_google_play_subscription = lambda **kwargs: False

            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="pro_monthly",
                    purchase_token="subscription-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(503, raised.exception.status_code)
            self.assertEqual("free", access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )["plan"])

    def test_google_play_subscription_token_cannot_be_reused_by_another_user(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCOUNT_DB_PATH=os.path.join(tmpdir, "accounts.sqlite3"),
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
        ):
            from backend.core import access_control, account_store

            access_control = importlib.reload(access_control)
            account_store = importlib.reload(account_store)
            buyer = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="buyer",
                display_name="Buyer",
            )
            other = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="other",
                display_name="Other",
            )
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "alphamate.pro.monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.shared",
                "auto_renewing": True,
            }

            access_control.apply_google_play_purchase(
                authorization=f"Bearer {buyer['session_token']}",
                product_id="pro_monthly",
                purchase_token="shared-subscription-token",
                package_name="com.alphamate.app",
            )

            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization=f"Bearer {other['session_token']}",
                    product_id="pro_monthly",
                    purchase_token="shared-subscription-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(409, raised.exception.status_code)
            self.assertEqual("pro", access_control.get_user_entitlements(
                authorization=f"Bearer {buyer['session_token']}",
                entitlement_token="",
            )["plan"])
            self.assertEqual("free", access_control.get_user_entitlements(
                authorization=f"Bearer {other['session_token']}",
                entitlement_token="",
            )["plan"])

    def test_expired_google_play_subscription_does_not_enable_pro(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "pro_monthly",
                "subscription_state": "SUBSCRIPTION_STATE_EXPIRED",
                "expiry_time": "2020-01-01T00:00:00Z",
                "latest_order_id": "GPA.expired",
                "auto_renewing": False,
            }

            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="pro_monthly",
                    purchase_token="expired-subscription-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(402, raised.exception.status_code)
            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            self.assertEqual("free", entitlements["plan"])

    def test_active_google_play_subscription_uses_pro_review_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "pro_monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.usage",
                "auto_renewing": True,
            }
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )

            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )

            self.assertEqual("pro", access.plan)
            self.assertEqual("pro_monthly_advanced", access.source)
            self.assertEqual(24, access.quota["advanced"]["pro_monthly_remaining"])

    def test_pro_advanced_quota_is_consumed_before_purchased_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_10",
            )
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "pro_monthly",
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.priority",
                "auto_renewing": True,
            }
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-priority-token",
                package_name="com.alphamate.app",
            )

            for _ in range(25):
                access = access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="advanced",
                )
                self.assertEqual("pro_monthly_advanced", access.source)

            before_purchased_use = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            self.assertEqual(0, before_purchased_use["advanced"]["pro_monthly_remaining"])
            self.assertEqual(10, before_purchased_use["advanced"]["purchased_remaining"])

            purchased_access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )
            self.assertEqual("purchased_advanced", purchased_access.source)
            self.assertEqual(9, purchased_access.quota["advanced"]["purchased_remaining"])

    def test_pro_billing_cycle_renewal_preserves_purchased_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_10",
            )
            subscription = {
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.cycle.1",
                "auto_renewing": True,
            }

            def fake_verify(**kwargs):
                return {
                    "package_name": "com.alphamate.app",
                    "product_id": "pro_monthly",
                    **subscription,
                }

            access_control._verify_google_play_subscription = fake_verify
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-renewal-token",
                package_name="com.alphamate.app",
            )
            access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )

            subscription.update({
                "expiry_time": "2099-02-01T00:00:00Z",
                "latest_order_id": "GPA.pro.cycle.2",
            })
            renewed = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-renewal-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual(25, renewed["advanced"]["pro_monthly_remaining"])
            self.assertEqual(10, renewed["advanced"]["purchased_remaining"])
            self.assertIsNone(renewed["validity"]["purchased_pass_expires_at"])

    def test_canceled_pro_remains_active_until_play_expiry_without_resetting_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            subscription = {
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.cancel-cycle",
                "auto_renewing": True,
            }

            def fake_verify(**kwargs):
                return {
                    "package_name": "com.alphamate.app",
                    "product_id": "pro_monthly",
                    **subscription,
                }

            access_control._verify_google_play_subscription = fake_verify
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-cancel-token",
                package_name="com.alphamate.app",
            )
            access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )

            subscription.update({
                "subscription_state": "SUBSCRIPTION_STATE_CANCELED",
                "auto_renewing": False,
            })
            canceled = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-cancel-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual("pro", canceled["plan"])
            self.assertEqual(24, canceled["advanced"]["pro_monthly_remaining"])
            self.assertEqual("2099-01-01T00:00:00Z", canceled["validity"]["pro_allowance_resets_at"])

            subscription.update({
                "expiry_time": "2020-01-01T00:00:00Z",
            })
            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="pro_monthly",
                    purchase_token="subscription-cancel-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(402, raised.exception.status_code)
            self.assertEqual(
                "free",
                access_control.get_user_entitlements(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                )["plan"],
            )

    def test_grace_period_keeps_pro_until_play_expiry(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)

            def fake_verify(**kwargs):
                return {
                    "package_name": "com.alphamate.app",
                    "product_id": "pro_monthly",
                    "subscription_state": "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
                    "expiry_time": "2099-01-01T00:00:00Z",
                    "latest_order_id": "GPA.pro.grace-cycle",
                    "auto_renewing": True,
                }

            access_control._verify_google_play_subscription = fake_verify
            entitlements = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-grace-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual("pro", entitlements["plan"])
            self.assertEqual(35, entitlements["basic"]["pro_monthly_remaining"])
            self.assertEqual(25, entitlements["advanced"]["pro_monthly_remaining"])

    def test_payment_hold_disables_pro_even_before_previous_expiry(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            subscription = {
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.hold-cycle",
                "auto_renewing": True,
            }

            def fake_verify(**kwargs):
                return {
                    "package_name": "com.alphamate.app",
                    "product_id": "pro_monthly",
                    **subscription,
                }

            access_control._verify_google_play_subscription = fake_verify
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-hold-token",
                package_name="com.alphamate.app",
            )

            subscription.update({
                "subscription_state": "SUBSCRIPTION_STATE_ON_HOLD",
                "auto_renewing": False,
            })
            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="pro_monthly",
                    purchase_token="subscription-hold-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(402, raised.exception.status_code)
            self.assertEqual(
                "free",
                access_control.get_user_entitlements(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                )["plan"],
            )

    def test_inactive_subscription_refresh_disables_previous_pro_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)

            subscription_state = {
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.active",
                "auto_renewing": True,
            }

            def fake_verify(**kwargs):
                return {
                    "package_name": "com.alphamate.app",
                    "product_id": "pro_monthly",
                    **subscription_state,
                }

            access_control._verify_google_play_subscription = fake_verify
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )
            self.assertEqual(
                "pro",
                access_control.get_user_entitlements(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                )["plan"],
            )

            subscription_state.update({
                "subscription_state": "SUBSCRIPTION_STATE_EXPIRED",
                "expiry_time": "2020-01-01T00:00:00Z",
                "latest_order_id": "GPA.pro.expired",
                "auto_renewing": False,
            })
            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="pro_monthly",
                    purchase_token="subscription-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(402, raised.exception.status_code)
            self.assertEqual(
                "free",
                access_control.get_user_entitlements(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                )["plan"],
            )

    def test_rtdn_subscription_notification_refreshes_stored_subscription(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-secret",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            subscription_state = {
                "subscription_state": "SUBSCRIPTION_STATE_ACTIVE",
                "expiry_time": "2099-01-01T00:00:00Z",
                "latest_order_id": "GPA.rtdn.active",
                "auto_renewing": True,
            }
            access_control._verify_google_play_subscription = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "pro_monthly",
                **subscription_state,
            }
            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="pro_monthly",
                purchase_token="subscription-token",
                package_name="com.alphamate.app",
            )

            subscription_state.update({
                "subscription_state": "SUBSCRIPTION_STATE_EXPIRED",
                "expiry_time": "2020-01-01T00:00:00Z",
                "latest_order_id": "GPA.rtdn.expired",
                "auto_renewing": False,
            })
            notification = {
                "version": "1.0",
                "packageName": "com.alphamate.app",
                "eventTimeMillis": "1710000000000",
                "subscriptionNotification": {
                    "version": "1.0",
                    "notificationType": 13,
                    "purchaseToken": "subscription-token",
                    "subscriptionId": "pro_monthly",
                },
            }
            payload = {
                "message": {
                    "messageId": "msg-1",
                    "data": base64.b64encode(json.dumps(notification).encode("utf-8")).decode("ascii"),
                },
                "subscription": "projects/test/subscriptions/google-play",
            }

            result = access_control.handle_google_play_rtdn(
                pubsub_payload=payload,
                shared_token="rtdn-secret",
            )

            self.assertEqual("inactive", result["status"])
            self.assertEqual("free", access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )["plan"])

    def test_rtdn_accepts_valid_oidc_claims(self):
        with patched_env(
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-secret",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE="https://example.com/rtdn",
            GOOGLE_PLAY_RTDN_OIDC_EMAIL="pubsub-push@example.iam.gserviceaccount.com",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_rtdn_oidc_token = lambda authorization: {
                "aud": "https://example.com/rtdn",
                "email": "pubsub-push@example.iam.gserviceaccount.com",
                "email_verified": True,
            }
            notification = {"version": "1.0", "packageName": "com.alphamate.app", "testNotification": {}}
            payload = {
                "message": {
                    "messageId": "msg-oidc",
                    "data": base64.b64encode(json.dumps(notification).encode("utf-8")).decode("ascii"),
                },
            }

            result = access_control.handle_google_play_rtdn(
                pubsub_payload=payload,
                shared_token="rtdn-secret",
                authorization="Bearer test-jwt",
            )

            self.assertEqual("test", result["status"])
            self.assertTrue(result["oidc_verified"])

    def test_admob_ssv_records_reward_once(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-tx-1",
                "user_id": "dev-user",
                "ad_unit": "rewarded-unit-1",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "basic_review",
            }

            first = access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")
            second = access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")

            self.assertEqual("recorded", first["status"])
            self.assertEqual("already_recorded", second["status"])

    def test_admob_reward_status_can_be_polled_without_consuming_reward(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-status-1",
                "user_id": "dev-user",
                "ad_unit": "rewarded-unit-1",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "basic_review",
            }
            access_control.record_admob_ssv_reward("transaction_id=ad-status-1")

            first = access_control.get_rewarded_ad_status(
                authorization="Bearer dev-token",
                entitlement_token="",
                purpose="basic_review",
            )
            second = access_control.get_rewarded_ad_status(
                authorization="Bearer dev-token",
                entitlement_token="",
                purpose="basic_review",
            )

            self.assertTrue(first["ready"])
            self.assertTrue(second["ready"])
            conn = access_control._connect_access_db()
            try:
                row = conn.execute(
                    "SELECT status FROM admob_reward_events WHERE transaction_id = ?",
                    ("ad-status-1",),
                ).fetchone()
                self.assertEqual("pending", row["status"])
            finally:
                conn.close()

    def test_admob_ssv_stored_fields_are_length_limited(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "tx-" + ("x" * 500),
                "user_id": "user-" + ("u" * 500),
                "ad_unit": "rewarded-unit-1",
                "reward_amount": "1",
                "reward_item": "item-" + ("i" * 500),
                "custom_data": "custom-" + ("c" * 500),
            }

            access_control.record_admob_ssv_reward("transaction_id=oversized")

            conn = access_control._connect_access_db()
            try:
                row = conn.execute("SELECT * FROM admob_reward_events LIMIT 1").fetchone()
            finally:
                conn.close()

            self.assertLessEqual(len(row["transaction_id"]), 120)
            self.assertLessEqual(len(row["user_id"]), 120)
            self.assertLessEqual(len(row["ad_unit"]), 120)
            self.assertLessEqual(len(row["reward_item"]), 120)
            self.assertLessEqual(len(row["custom_data"]), 500)

    def test_admob_ssv_rejects_wrong_ad_unit(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-tx-1",
                "user_id": "dev-user",
                "ad_unit": "other-unit",
            }

            with self.assertRaises(HTTPException) as raised:
                access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")

            self.assertEqual(403, raised.exception.status_code)

    def test_admob_ssv_accepts_signed_numeric_ad_unit_identifier(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ADMOB_REWARDED_AD_UNIT_ID="ca-app-pub-1234567890123456/9876543210",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-tx-numeric-unit",
                "user_id": "dev-user",
                "ad_unit": "9876543210",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "advanced_ticket_progress",
            }

            result = access_control.record_admob_ssv_reward("transaction_id=ad-tx-numeric-unit")

            self.assertEqual("recorded", result["status"])

    def test_admob_ssv_accepts_console_verification_probe_without_recording_reward(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ADMOB_REWARDED_AD_UNIT_ID="ca-app-pub-1234567890123456/9876543210",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "123456789",
                "user_id": "admob-setup-test",
                "ad_unit": "1234567890",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "advanced_ticket_progress",
            }

            result = access_control.record_admob_ssv_reward("transaction_id=123456789")

            self.assertEqual({"ok": True, "status": "verification_probe"}, result)
            conn = access_control._connect_access_db()
            try:
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM admob_reward_events").fetchone()[0])
            finally:
                conn.close()

    def test_pending_admob_reward_is_consumed_for_basic_review(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-tx-1",
                "user_id": "dev-user",
                "ad_unit": "rewarded-unit-1",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "basic_review",
            }

            for _ in range(6):
                access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )

            access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")
            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )

            self.assertEqual("rewarded_ad_basic", access.source)
            self.assertEqual(1, access.quota["basic"]["free_daily_max_remaining"])

    def test_pending_admob_reward_waits_until_immediate_free_credits_are_exhausted(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "ad-tx-wait",
                "user_id": "dev-user",
                "ad_unit": "rewarded-unit-1",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "basic_review",
            }

            access_control.record_admob_ssv_reward("transaction_id=ad-tx-wait")
            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )

            self.assertEqual("signup_basic", access.source)
            conn = access_control._connect_access_db()
            try:
                row = conn.execute(
                    "SELECT status FROM admob_reward_events WHERE transaction_id = ?",
                    ("ad-tx-wait",),
                ).fetchone()
                self.assertEqual("pending", row["status"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
