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
    def test_google_play_purchase_does_not_grant_when_verification_cannot_run(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="basic_review_15",
                    purchase_token="purchase-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(503, raised.exception.status_code)
            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            self.assertEqual(0, entitlements["basic"]["purchased_remaining"])

    def test_verified_google_play_consumable_grants_credits_once(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)

            def fake_verify(*, package_name, google_product_id, purchase_token):
                return {
                    "package_name": package_name,
                    "product_id": google_product_id,
                    "purchase_state": "purchased",
                    "order_id": "GPA.1234",
                    "order_status": "PROCESSED",
                    "price_amount_micros": 2_900_000_000,
                    "currency_code": "KRW",
                    "acknowledgement_state": "acknowledged",
                }

            consumed = []
            access_control._verify_google_play_purchase = fake_verify
            access_control._consume_google_play_product = lambda **kwargs: consumed.append(kwargs) or True

            first = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_15",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )
            second = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_15",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual(15, first["basic"]["purchased_remaining"])
            self.assertEqual(15, second["basic"]["purchased_remaining"])
            self.assertEqual("applied", first["purchase"]["status"])
            self.assertEqual("already_applied", second["purchase"]["status"])
            self.assertEqual(1, len(consumed))

            conn = access_control._connect_access_db()
            try:
                order = conn.execute("SELECT * FROM purchase_credit_orders").fetchone()
            finally:
                conn.close()

            self.assertEqual("GPA.1234", order["order_id"])
            self.assertEqual(15, order["granted_quantity"])
            self.assertEqual(15, order["remaining_quantity"])
            self.assertEqual(2_900_000_000, order["price_amount_micros"])
            self.assertEqual("KRW", order["currency_code"])
            self.assertNotEqual(b"purchase-token", order["purchase_token_ciphertext"])
            self.assertEqual(
                b"purchase-token",
                access_control._purchase_token_cipher()[0].decrypt(order["purchase_token_ciphertext"]),
            )

    def test_google_play_consumable_rejects_non_processed_order(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            for order_status in ("CANCELED", "PENDING_REFUND", "PARTIALLY_REFUNDED", "REFUNDED"):
                access_control._verify_google_play_purchase = lambda **kwargs: {
                    "package_name": kwargs["package_name"],
                    "product_id": kwargs["google_product_id"],
                    "purchase_state": "purchased",
                    "order_id": f"GPA.{order_status.lower()}",
                    "order_status": order_status,
                    "price_amount_micros": 2_900_000_000,
                    "currency_code": "KRW",
                }
                with self.subTest(order_status=order_status), self.assertRaises(HTTPException) as raised:
                    access_control.apply_google_play_purchase(
                        authorization="Bearer dev-token",
                        product_id="basic_review_15",
                        purchase_token=f"token-{order_status.lower()}",
                        package_name="com.alphamate.app",
                    )
                self.assertEqual(402, raised.exception.status_code)

            conn = access_control._connect_access_db()
            try:
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM purchase_credit_orders").fetchone()[0])
            finally:
                conn.close()

    def test_google_play_purchase_verification_loads_actual_order_amount(self):
        from backend.core import access_control

        access_control = importlib.reload(access_control)

        class FakeResponse:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload

            def json(self):
                return self._payload

        responses = [
            FakeResponse({
                "purchaseState": 0,
                "orderId": "GPA.order.amount",
                "acknowledgementState": 1,
            }),
            FakeResponse({
                "orderId": "GPA.order.amount",
                "purchaseToken": "purchase-token",
                "state": "PROCESSED",
                "createTime": "2026-08-14T00:00:00Z",
                "lineItems": [{
                    "productId": "basic_review_15",
                    "total": {"currencyCode": "KRW", "units": "2900", "nanos": 0},
                }],
            }),
        ]
        with patch.object(access_control, "_google_play_headers", return_value={"Authorization": "Bearer test"}), \
             patch.object(access_control.requests, "get", side_effect=lambda *args, **kwargs: responses.pop(0)):
            verified = access_control._verify_google_play_purchase(
                package_name="com.alphamate.app",
                google_product_id="basic_review_15",
                purchase_token="purchase-token",
            )

        self.assertEqual("GPA.order.amount", verified["order_id"])
        self.assertEqual("PROCESSED", verified["order_status"])
        self.assertEqual(2_900_000_000, verified["price_amount_micros"])
        self.assertEqual("KRW", verified["currency_code"])

    def test_google_play_full_refund_revokes_only_the_matching_order_once(self):
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
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_20",
            )
            conn = access_control._connect_access_db()
            try:
                orders = conn.execute(
                    "SELECT order_id, remaining_quantity FROM purchase_credit_orders ORDER BY created_at, order_id"
                ).fetchall()
            finally:
                conn.close()

            access_control._verify_google_play_order = lambda **kwargs: {
                "order_status": "REFUNDED",
                "refund_amount_micros": 4_900_000_000,
                "refund_currency_code": "KRW",
            }
            first = access_control.sync_google_play_purchase_order_status(
                order_id=orders[0]["order_id"],
                event_key="refund-event-1",
            )
            repeated = access_control.sync_google_play_purchase_order_status(
                order_id=orders[0]["order_id"],
                event_key="refund-event-1",
            )

            conn = access_control._connect_access_db()
            try:
                updated_orders = conn.execute(
                    "SELECT order_id, order_status, remaining_quantity, balance_locked, refund_status, refund_amount_micros "
                    "FROM purchase_credit_orders ORDER BY created_at, order_id"
                ).fetchall()
                receipt_count = conn.execute("SELECT COUNT(*) FROM billing_event_receipts").fetchone()[0]
            finally:
                conn.close()

            self.assertEqual("revoked", first["status"])
            self.assertEqual(10, first["revoked_quantity"])
            self.assertEqual("already_processed", repeated["status"])
            self.assertEqual(1, receipt_count)
            self.assertEqual(("REFUNDED", 0, 1, "refunded", 4_900_000_000), tuple(updated_orders[0][1:]))
            self.assertEqual(("development_grant", 20, 0, "none", 0), tuple(updated_orders[1][1:]))

    def test_google_play_canceled_order_revokes_remaining_credit_without_refund_amount(self):
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
                product_id="basic_review_15",
            )
            conn = access_control._connect_access_db()
            try:
                order_id = conn.execute("SELECT order_id FROM purchase_credit_orders").fetchone()[0]
            finally:
                conn.close()

            access_control._verify_google_play_order = lambda **kwargs: {
                "order_status": "CANCELED",
                "refund_amount_micros": 0,
                "refund_currency_code": "",
            }
            result = access_control.sync_google_play_purchase_order_status(
                order_id=order_id,
                event_key="cancellation-event-1",
            )

            conn = access_control._connect_access_db()
            try:
                order = conn.execute(
                    "SELECT order_status, remaining_quantity, balance_locked, refund_status, refund_amount_micros "
                    "FROM purchase_credit_orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual({"status": "revoked", "revoked_quantity": 15}, {
                "status": result["status"],
                "revoked_quantity": result["revoked_quantity"],
            })
            self.assertEqual(("CANCELED", 0, 1, "canceled", 0), tuple(order))

    def test_failed_review_refund_does_not_restore_credit_to_refunded_order(self):
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
            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )
            access_control._verify_google_play_order = lambda **kwargs: {
                "order_status": "REFUNDED",
                "refund_amount_micros": 4_900_000_000,
                "refund_currency_code": "KRW",
            }
            access_control.sync_google_play_purchase_order_status(
                order_id=access.source_order_id,
                event_key="refund-after-consumption",
            )
            refunded_wallet = access_control.refund_ai_review_access(access)

            conn = access_control._connect_access_db()
            try:
                order = conn.execute(
                    "SELECT used_quantity, remaining_quantity, order_status, refund_status "
                    "FROM purchase_credit_orders WHERE order_id = ?",
                    (access.source_order_id,),
                ).fetchone()
                usage_status = conn.execute(
                    "SELECT status FROM credit_usage_ledger WHERE idempotency_key = ?",
                    (access.usage_event_key,),
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertEqual("purchased_advanced", access.source)
            self.assertEqual((0, 0, "REFUNDED", "refunded"), tuple(order))
            self.assertEqual("reversed", usage_status)
            self.assertEqual(0, refunded_wallet["advanced"]["purchased_remaining"])

    def test_google_play_order_verification_reads_full_refund_details(self):
        from backend.core import access_control

        access_control = importlib.reload(access_control)

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "orderId": "GPA.refunded.order",
                    "purchaseToken": "purchase-token",
                    "state": "REFUNDED",
                    "lineItems": [{
                        "productId": "basic_review_15",
                        "total": {"currencyCode": "KRW", "units": "2900", "nanos": 0},
                    }],
                    "orderHistory": {
                        "refundEvent": {
                            "refundDetails": {
                                "total": {"currencyCode": "KRW", "units": "2900", "nanos": 0},
                            },
                        },
                    },
                }

        with patch.object(access_control, "_google_play_headers", return_value={"Authorization": "Bearer test"}), \
             patch.object(access_control.requests, "get", return_value=FakeResponse()):
            verified = access_control._verify_google_play_order(
                package_name="com.alphamate.app",
                google_product_id="basic_review_15",
                purchase_token="purchase-token",
                order_id="GPA.refunded.order",
            )

        self.assertEqual("REFUNDED", verified["order_status"])
        self.assertEqual(2_900_000_000, verified["refund_amount_micros"])
        self.assertEqual("KRW", verified["refund_currency_code"])

    def test_google_play_purchase_stored_fields_are_length_limited(self):
        long_product_id = "alphamate.basic." + ("p" * 500)
        long_order_id = "GPA." + ("o" * 500)
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID=long_product_id,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_purchase = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": kwargs["google_product_id"],
                "purchase_state": "purchased",
                "order_id": long_order_id,
                "order_status": "PROCESSED",
                "price_amount_micros": 2_900_000_000,
                "currency_code": "KRW",
                "acknowledgement_state": "acknowledged",
            }
            access_control._consume_google_play_product = lambda **kwargs: True

            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_15",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )

            conn = access_control._connect_access_db()
            try:
                row = conn.execute("SELECT * FROM google_play_purchases LIMIT 1").fetchone()
            finally:
                conn.close()

            self.assertLessEqual(len(row["google_play_product_id"]), 120)
            self.assertLessEqual(len(row["order_id"]), 120)

    def test_google_play_consumable_consume_failure_can_be_retried_without_duplicate_credits(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)

            def fake_verify(*, package_name, google_product_id, purchase_token):
                return {
                    "package_name": package_name,
                    "product_id": google_product_id,
                    "purchase_state": "purchased",
                    "order_id": "GPA.consume.retry",
                    "order_status": "PROCESSED",
                    "price_amount_micros": 2_900_000_000,
                    "currency_code": "KRW",
                    "acknowledgement_state": "acknowledged",
                }

            consume_results = [False, True]
            consumed = []

            def fake_consume(**kwargs):
                consumed.append(kwargs)
                return consume_results.pop(0)

            access_control._verify_google_play_purchase = fake_verify
            access_control._consume_google_play_product = fake_consume

            first = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_15",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )
            second = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_15",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual(15, first["basic"]["purchased_remaining"])
            self.assertEqual(15, second["basic"]["purchased_remaining"])
            self.assertEqual("consume_pending", first["purchase"]["status"])
            self.assertEqual("consume_completed", second["purchase"]["status"])
            self.assertEqual(2, len(consumed))

    def test_google_play_purchase_rejects_wrong_product(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_purchase = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": "other_product",
                "purchase_state": "purchased",
            }

            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="basic_review_15",
                    purchase_token="purchase-token",
                    package_name="com.alphamate.app",
                )

            self.assertEqual(400, raised.exception.status_code)

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

    def test_voided_purchase_reconciliation_handles_chargebacks_partial_refunds_and_item_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            for product_id in ("basic_review_15", "basic_review_25", "advanced_review_10"):
                access_control.apply_dev_purchase(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                    product_id=product_id,
                )
            conn = access_control._connect_access_db()
            try:
                orders = conn.execute(
                    "SELECT * FROM purchase_credit_orders ORDER BY created_at, order_id"
                ).fetchall()
            finally:
                conn.close()
            cipher, _ = access_control._purchase_token_cipher()
            purchase_tokens = {
                order["order_id"]: cipher.decrypt(order["purchase_token_ciphertext"]).decode("utf-8")
                for order in orders
            }
            failed_order, chargeback_order, partial_order = orders

            class FakeResponse:
                status_code = 200

                @staticmethod
                def json():
                    return {
                        "voidedPurchases": [
                            {"orderId": failed_order["order_id"], "purchaseToken": "mismatched-token", "voidedTimeMillis": "1720000000000", "voidedReason": 1, "voidedSource": 0},
                            {"orderId": chargeback_order["order_id"], "purchaseToken": purchase_tokens[chargeback_order["order_id"]], "voidedTimeMillis": "1720000000001", "voidedReason": 3, "voidedSource": 1},
                            {"orderId": partial_order["order_id"], "purchaseToken": purchase_tokens[partial_order["order_id"]], "voidedTimeMillis": "1720000000002", "voidedReason": 1, "voidedSource": 0, "voidedQuantity": 1},
                            {"orderId": "GPA.untracked-order", "purchaseToken": "untracked-token", "voidedTimeMillis": "1720000000003", "voidedReason": 3, "voidedSource": 1},
                        ],
                    }

            end_time_millis = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
            start_time_millis = end_time_millis - 1000
            with patch.object(access_control, "_google_play_status", return_value={"ready": True}), \
                 patch.object(access_control, "_google_play_headers", return_value={"Authorization": "Bearer test"}), \
                 patch.object(access_control.requests, "get", return_value=FakeResponse()) as request, \
                 patch.object(access_control, "_verify_google_play_order") as verify_order:
                result = access_control.reconcile_google_play_voided_purchase_orders(
                    start_time_millis=start_time_millis,
                    end_time_millis=end_time_millis,
                )

            verify_order.assert_not_called()

            conn = access_control._connect_access_db()
            try:
                updated_orders = {
                    row["order_id"]: row
                    for row in conn.execute("SELECT * FROM purchase_credit_orders").fetchall()
                }
            finally:
                conn.close()

            self.assertEqual(1, result["pages"])
            self.assertEqual(4, result["voided_purchase_count"])
            self.assertEqual(3, result["matched_order_count"])
            self.assertEqual(2, result["processed_count"])
            self.assertEqual(1, result["revoked_count"])
            self.assertEqual(1, result["locked_for_review_count"])
            self.assertEqual(1, result["failed_count"])
            self.assertEqual(1, result["unmatched_count"])
            self.assertEqual({
                "startTime": str(start_time_millis),
                "endTime": str(end_time_millis),
                "type": 0,
                "includeQuantityBasedPartialRefund": "true",
                "pageSelection.maxResults": 100,
            }, request.call_args.kwargs["params"])
            self.assertEqual(15, updated_orders[failed_order["order_id"]]["remaining_quantity"])
            self.assertEqual(0, updated_orders[failed_order["order_id"]]["balance_locked"])
            self.assertEqual(0, updated_orders[chargeback_order["order_id"]]["remaining_quantity"])
            self.assertEqual(1, updated_orders[chargeback_order["order_id"]]["balance_locked"])
            self.assertEqual("VOIDED", updated_orders[chargeback_order["order_id"]]["order_status"])
            self.assertEqual(10, updated_orders[partial_order["order_id"]]["remaining_quantity"])
            self.assertEqual(1, updated_orders[partial_order["order_id"]]["balance_locked"])
            self.assertEqual("PARTIALLY_REFUNDED", updated_orders[partial_order["order_id"]]["order_status"])


if __name__ == "__main__":
    unittest.main()
