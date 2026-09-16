"""Purchase, credential-refresh failure and refund transport isolation."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state

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


with _import_state():
    from backend.core import access_control as _access_control


class BillingPurchaseTransportTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        # Body-local reloads and function replacements restore even on failure.
        self.enterContext(patch.dict(_access_control.__dict__))
        importlib.reload(_access_control)

    def test_google_play_purchase_does_not_grant_when_verification_cannot_run(self):
        from google.auth.exceptions import TransportError
        from google.auth.transport.requests import Request
        from urllib.parse import parse_qs

        # Preserve real credential creation/refresh; fail before HTTP dispatch.
        transport_failure = TransportError("synthetic token refresh failure")
        token_request = self.enterContext(patch.object(
            Request, "__call__", autospec=True, side_effect=transport_failure))

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
            self.assertIs(transport_failure, raised.exception.__cause__)
            token_request.assert_called_once()
            self.assertEqual("https://oauth2.googleapis.com/token", token_request.call_args.kwargs["url"])
            self.assertEqual("POST", token_request.call_args.kwargs["method"])
            self.assertEqual("application/x-www-form-urlencoded", token_request.call_args.kwargs["headers"]["Content-Type"])
            token_body = parse_qs(token_request.call_args.kwargs["body"].decode("utf-8"))
            self.assertEqual(["urn:ietf:params:oauth:grant-type:jwt-bearer"], token_body["grant_type"])
            self.assertTrue(token_body["assertion"][0])
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
