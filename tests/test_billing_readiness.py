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
    from backend.core import access_control as _access_control, readiness as _readiness


class BillingReadinessTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        for module in (_access_control, _readiness):
            # Snapshot before body-local reloads and function/global replacements.
            self.enterContext(patch.dict(module.__dict__))
            importlib.reload(module)

    def test_purchase_credit_ledger_schema_tracks_order_balances_and_usage_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            conn = access_control._connect_access_db()
            try:
                order_columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(purchase_credit_orders)").fetchall()
                }
                usage_columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(credit_usage_ledger)").fetchall()
                }
                event_columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(billing_event_receipts)").fetchall()
                }
            finally:
                conn.close()

            self.assertTrue({
                "order_id",
                "purchase_token_hash",
                "purchase_token_ciphertext",
                "product_id",
                "credit_kind",
                "granted_quantity",
                "used_quantity",
                "remaining_quantity",
                "order_status",
                "price_amount_micros",
                "currency_code",
                "refund_amount_micros",
                "refund_status",
                "balance_locked",
            }.issubset(order_columns))
            self.assertTrue({
                "user_id",
                "review_type",
                "source_type",
                "source_order_id",
                "quantity",
                "idempotency_key",
            }.issubset(usage_columns))
            self.assertTrue({
                "event_key",
                "order_id",
                "event_type",
                "payload_hash",
                "status",
            }.issubset(event_columns))

    def test_purchase_credit_ledger_rejects_incomplete_order_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            conn = access_control._connect_access_db()
            try:
                sql = """
                    INSERT INTO purchase_credit_orders (
                        order_id, purchase_token_hash, purchase_token_ciphertext,
                        purchase_token_key_id, user_id, product_id,
                        google_play_product_id, credit_kind, granted_quantity,
                        remaining_quantity, order_status, price_amount_micros,
                        currency_code, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                invalid_fields = {
                    "null order id": (0, None),
                    "empty order id": (0, ""),
                    "empty encrypted token": (2, b""),
                    "empty token key id": (3, ""),
                    "missing price": (11, 0),
                    "empty currency": (12, ""),
                }
                for index, (label, (field_index, invalid_value)) in enumerate(invalid_fields.items()):
                    values = [
                        f"GPA.order-{index}", f"token-hash-{index}", b"encrypted-token", "billing-key-v1",
                        "user-1", "basic_review_15", "basic_review_15", "basic",
                        15, 15, "paid", 2_900_000_000, "KRW", "now", "now",
                    ]
                    values[field_index] = invalid_value
                    with self.subTest(case=label), self.assertRaises(sqlite3.IntegrityError):
                        conn.execute(sql, tuple(values))
            finally:
                conn.close()

    def test_purchase_usage_requires_an_existing_order_for_the_same_user(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            conn = access_control._connect_access_db()
            try:
                conn.execute(
                    """
                    INSERT INTO purchase_credit_orders (
                        order_id, purchase_token_hash, purchase_token_ciphertext,
                        purchase_token_key_id, user_id, product_id,
                        google_play_product_id, credit_kind, granted_quantity,
                        remaining_quantity, order_status, price_amount_micros,
                        currency_code, created_at, updated_at
                    ) VALUES (
                        'GPA.order-1', 'token-hash-1', X'0102', 'billing-key-v1',
                        'user-1', 'basic_review_15', 'basic_review_15', 'basic',
                        15, 15, 'paid', 2900000000, 'KRW', 'now', 'now'
                    )
                    """
                )
                usage_sql = """
                    INSERT INTO credit_usage_ledger (
                        user_id, review_type, source_type, source_order_id,
                        idempotency_key, created_at
                    ) VALUES (?, 'basic', 'purchase_order', ?, ?, 'now')
                """
                invalid_cases = (
                    ("user-1", None, "usage-null-order"),
                    ("user-1", "", "usage-empty-order"),
                    ("user-1", "GPA.missing", "usage-missing-order"),
                    ("user-2", "GPA.order-1", "usage-wrong-user"),
                )
                for values in invalid_cases:
                    with self.subTest(values=values), self.assertRaises(sqlite3.IntegrityError):
                        conn.execute(usage_sql, values)

                conn.execute(usage_sql, ("user-1", "GPA.order-1", "usage-valid"))
                self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM credit_usage_ledger").fetchone()[0])
            finally:
                conn.close()

    def test_legacy_test_purchase_balances_are_reset_only_by_explicit_one_time_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            conn = access_control._connect_access_db()
            try:
                conn.execute(
                    """
                    INSERT INTO access_wallets (
                        user_id, purchased_basic, purchased_advanced, updated_at
                    ) VALUES ('legacy-user', 7, 3, '2026-01-01T00:00:00')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO google_play_purchases (
                        purchase_token_hash, user_id, local_product_id,
                        google_play_product_id, kind, order_id, status, granted_at
                    ) VALUES (
                        'legacy-token-hash', 'legacy-user', 'basic_review_15',
                        'basic_review_15', 'basic', 'legacy-order', 'applied',
                        '2026-01-01T00:00:00'
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(ValueError):
                access_control.initialize_purchase_credit_ledger()

            conn = sqlite3.connect(os.path.join(tmpdir, "access.sqlite3"))
            try:
                unchanged = conn.execute(
                    "SELECT purchased_basic, purchased_advanced FROM access_wallets WHERE user_id = 'legacy-user'"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual((7, 3), unchanged)

            self.assertTrue(access_control.initialize_purchase_credit_ledger(reset_legacy_balances=True))
            self.assertFalse(access_control.initialize_purchase_credit_ledger(reset_legacy_balances=True))

            conn = sqlite3.connect(os.path.join(tmpdir, "access.sqlite3"))
            try:
                balances = conn.execute(
                    "SELECT purchased_basic, purchased_advanced FROM access_wallets WHERE user_id = 'legacy-user'"
                ).fetchone()
                purchases = conn.execute("SELECT COUNT(*) FROM google_play_purchases").fetchone()[0]
            finally:
                conn.close()

            self.assertEqual((0, 0), balances)
            self.assertEqual(0, purchases)

    def test_app_readiness_summarizes_deployment_without_secret_values(self):
        with patched_env(
            OPENAI_API_KEY="sk-secret-openai",
            KAKAO_CLIENT_ID="kakao-client",
            KAKAO_CLIENT_SECRET="kakao-secret",
            KAKAO_REDIRECT_URI=None,
            NAVER_CLIENT_ID="naver-client",
            NAVER_CLIENT_SECRET="naver-secret",
            NAVER_REDIRECT_URI=None,
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_PRIVACY_POLICY_URL="https://alphamate.example/privacy",
            ALPHAMATE_ACCOUNT_DB_PATH="D:/prod/alphamate/accounts.sqlite3",
            ALPHAMATE_JOURNAL_DB_PATH="D:/prod/alphamate/trades.sqlite3",
            ALPHAMATE_ACCESS_DB_PATH="D:/prod/alphamate/access.sqlite3",
            ALPHAMATE_REVIEW_HISTORY_DB_PATH="D:/prod/alphamate/review-history.sqlite3",
            ALPHAMATE_EVENT_LOG_DB_PATH="D:/prod/alphamate/events.sqlite3",
            ALPHAMATE_ADMIN_TOKEN="admin-token-with-at-least-32-characters",
            ALPHAMATE_CORS_ORIGINS="https://app.alphamate.example,capacitor://localhost",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE=None,
            GOOGLE_PLAY_RTDN_OIDC_EMAIL=None,
        ):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertTrue(status["overall_ready"])
            self.assertTrue(status["sections"]["ai"]["ready"])
            self.assertTrue(status["sections"]["login"]["ready"])
            self.assertTrue(status["sections"]["google_play"]["ready"])
            self.assertTrue(status["sections"]["admob"]["ready"])
            self.assertTrue(status["sections"]["data_storage"]["ready"])
            self.assertTrue(status["sections"]["admin"]["ready"])
            self.assertTrue(status["sections"]["cors"]["ready"])
            self.assertTrue(status["sections"]["privacy_policy"]["ready"])
            self.assertEqual("https://alphamate.example/privacy", status["sections"]["privacy_policy"]["url"])
            self.assertNotIn("sk-secret-openai", str(status))
            self.assertNotIn("kakao-secret", str(status))
            self.assertNotIn("naver-secret", str(status))
            self.assertNotIn("fake-private-key", str(status))

    def test_app_readiness_rejects_short_admin_token_without_exposing_value(self):
        with patched_env(ALPHAMATE_ADMIN_TOKEN="short-token"):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertFalse(status["sections"]["admin"]["ready"])
            self.assertIn("ALPHAMATE_ADMIN_TOKEN_MIN_LENGTH_32", status["sections"]["admin"]["missing_server_settings"])
            self.assertNotIn("short-token", str(status))

    def test_app_readiness_reports_missing_settings_by_section(self):
        with patched_env(
            OPENAI_API_KEY=None,
            ALPHAMATE_OPENAI_API_KEY=None,
            KAKAO_CLIENT_ID=None,
            NAVER_CLIENT_ID=None,
            NAVER_CLIENT_SECRET=None,
            GOOGLE_PLAY_PACKAGE_NAME=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
            ADMOB_REWARDED_AD_UNIT_ID=None,
            ALPHAMATE_PRIVACY_POLICY_URL=None,
            ALPHAMATE_ACCOUNT_DB_PATH=None,
            ALPHAMATE_JOURNAL_DB_PATH=None,
            ALPHAMATE_ACCESS_DB_PATH=None,
            ALPHAMATE_REVIEW_HISTORY_DB_PATH=None,
            ALPHAMATE_EVENT_LOG_DB_PATH=None,
            ALPHAMATE_ADMIN_TOKEN=None,
            ALPHAMATE_ENV="production",
            ALPHAMATE_CORS_ORIGINS=None,
        ):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertFalse(status["overall_ready"])
            self.assertIn("OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY", status["sections"]["ai"]["missing_server_settings"])
            self.assertIn("GOOGLE_PLAY_PACKAGE_NAME", status["sections"]["google_play"]["missing_server_settings"])
            self.assertIn("ADMOB_REWARDED_AD_UNIT_ID", status["sections"]["admob"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_PRIVACY_POLICY_URL", status["sections"]["privacy_policy"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_ACCOUNT_DB_PATH", status["sections"]["data_storage"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_REVIEW_HISTORY_DB_PATH", status["sections"]["data_storage"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_EVENT_LOG_DB_PATH", status["sections"]["data_storage"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_ADMIN_TOKEN", status["sections"]["admin"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_CORS_ORIGINS", status["sections"]["cors"]["missing_server_settings"])
            self.assertIn("KAKAO_CLIENT_ID", status["sections"]["login"]["providers"]["kakao"]["missing_server_settings"])
            self.assertIn("NAVER_CLIENT_SECRET", status["sections"]["login"]["providers"]["naver"]["missing_server_settings"])

    def test_production_readiness_rejects_local_or_relative_data_paths(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            ALPHAMATE_ACCOUNT_DB_PATH="backend/data/accounts.sqlite3",
            ALPHAMATE_JOURNAL_DB_PATH="trades.sqlite3",
            ALPHAMATE_ACCESS_DB_PATH="D:/secure/alphamate/access.sqlite3",
            ALPHAMATE_REVIEW_HISTORY_DB_PATH="D:/secure/alphamate/review-history.sqlite3",
            ALPHAMATE_EVENT_LOG_DB_PATH="backend/data/event_log.sqlite3",
        ):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertFalse(status["sections"]["data_storage"]["ready"])
            self.assertIn(
                "ALPHAMATE_ACCOUNT_DB_PATH_LOCAL_DEV_PATH",
                status["sections"]["data_storage"]["missing_server_settings"],
            )
            self.assertIn(
                "ALPHAMATE_JOURNAL_DB_PATH_ABSOLUTE_PATH",
                status["sections"]["data_storage"]["missing_server_settings"],
            )
            self.assertIn(
                "ALPHAMATE_EVENT_LOG_DB_PATH_LOCAL_DEV_PATH",
                status["sections"]["data_storage"]["missing_server_settings"],
            )
            self.assertIn(
                "ALPHAMATE_ACCESS_DB_PATH_PLACEHOLDER",
                status["sections"]["data_storage"]["missing_server_settings"],
            )
            self.assertIn(
                "ALPHAMATE_REVIEW_HISTORY_DB_PATH_PLACEHOLDER",
                status["sections"]["data_storage"]["missing_server_settings"],
            )
            self.assertNotIn("backend/data/accounts.sqlite3", str(status))

    def test_app_readiness_rejects_placeholder_release_values(self):
        with patched_env(
            ADMOB_REWARDED_AD_UNIT_ID="ca-app-pub-0000000000000000/0000000000",
            ALPHAMATE_PRIVACY_POLICY_URL="https://your-domain.example/privacy",
            ALPHAMATE_ENV="production",
            ALPHAMATE_CORS_ORIGINS="https://your-app.example.com,capacitor://localhost",
        ):
            from backend.core import access_control, readiness

            access_control = importlib.reload(access_control)
            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertFalse(status["sections"]["admob"]["ready"])
            self.assertIn("ADMOB_REWARDED_AD_UNIT_ID_PLACEHOLDER", status["sections"]["admob"]["missing_server_settings"])
            self.assertFalse(status["sections"]["privacy_policy"]["ready"])
            self.assertIn("ALPHAMATE_PRIVACY_POLICY_URL_PLACEHOLDER", status["sections"]["privacy_policy"]["missing_server_settings"])
            self.assertFalse(status["sections"]["cors"]["ready"])
            self.assertIn("ALPHAMATE_CORS_ORIGINS_PLACEHOLDER", status["sections"]["cors"]["missing_server_settings"])

    def test_app_readiness_rejects_unsafe_release_cors_origins(self):
        with patched_env(
            ALPHAMATE_CORS_ORIGINS="*,http://localhost:5174,capacitor://localhost",
        ):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertFalse(status["sections"]["cors"]["ready"])
            self.assertIn("ALPHAMATE_CORS_ORIGINS_WILDCARD", status["sections"]["cors"]["missing_server_settings"])
            self.assertIn("ALPHAMATE_CORS_ORIGINS_LOCALHOST", status["sections"]["cors"]["missing_server_settings"])

    def test_app_readiness_accepts_capacitor_android_https_origin(self):
        with patched_env(
            ALPHAMATE_CORS_ORIGINS="https://alphamate.co.kr,https://localhost,capacitor://localhost",
        ):
            from backend.core import readiness

            readiness = importlib.reload(readiness)
            status = readiness.get_app_readiness()

            self.assertTrue(status["sections"]["cors"]["ready"])
            self.assertIn("https://localhost", status["sections"]["cors"]["origins"])

    def test_product_catalog_exposes_public_ids_and_readiness_only(self):
        with patched_env(
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID="alphamate.basic.15",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_ADS_PER_ADVANCED_TICKET="3",
            ALPHAMATE_FORCE_REWARDED_AD_CHAIN="false",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertEqual("alphamate.basic.15", catalog["consumables"]["basic_review_15"]["google_play_product_id"])
            self.assertTrue(catalog["google_play"]["ready"])
            self.assertTrue(catalog["google_play"]["service_account_configured"])
            self.assertTrue(catalog["admob"]["ready"])
            self.assertTrue(catalog["admob"]["rewarded_ad_unit_configured"])
            self.assertEqual("/api/journal/admob-ssv", catalog["admob"]["ssv_callback_path"])
            self.assertEqual(1, catalog["settings"]["ad_policy"]["basic_reviews_per_rewarded_ad"])
            self.assertEqual(3, catalog["settings"]["ad_policy"]["ads_per_advanced_ticket"])
            self.assertFalse(catalog["settings"]["ad_policy"]["force_rewarded_ad_chain"])
            self.assertNotIn("fake-private-key", str(catalog))

    def test_product_catalog_matches_current_review_offers(self):
        from backend.core import access_control

        access_control = importlib.reload(access_control)
        catalog = access_control.get_product_catalog()

        self.assertNotIn("basic_review_100", catalog["consumables"])
        self.assertEqual(15, catalog["consumables"]["basic_review_15"]["quantity"])
        self.assertEqual(2900, catalog["consumables"]["basic_review_15"]["price_krw"])
        self.assertEqual(25, catalog["consumables"]["basic_review_25"]["quantity"])
        self.assertEqual(4500, catalog["consumables"]["basic_review_25"]["price_krw"])
        self.assertNotIn("advanced_review_5", catalog["consumables"])
        self.assertEqual(10, catalog["consumables"]["advanced_review_10"]["quantity"])
        self.assertEqual(3900, catalog["consumables"]["advanced_review_10"]["price_krw"])
        self.assertEqual(20, catalog["consumables"]["advanced_review_20"]["quantity"])
        self.assertEqual(6900, catalog["consumables"]["advanced_review_20"]["price_krw"])

        pro = catalog["subscriptions"]["pro_monthly"]
        self.assertEqual((35, 25, 9900), (pro["monthly_basic"], pro["monthly_advanced"], pro["price_krw"]))
        self.assertEqual("monthly", pro["google_play_base_plan_id"])
        self.assertEqual("launch_7900_3m", pro["google_play_offer_id"])
        self.assertEqual(
            {
                "price_krw": 7900,
                "enrollment_window_months": 3,
                "discounted_billing_cycles": 3,
                "starts_from": "public_release",
            },
            pro["launch_offer"],
        )

    def test_ad_policy_caps_ads_per_advanced_ticket_setting(self):
        with patched_env(ALPHAMATE_ADS_PER_ADVANCED_TICKET="999999"):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertEqual(20, catalog["settings"]["ad_policy"]["ads_per_advanced_ticket"])

    def test_google_play_readiness_rejects_invalid_service_account_json(self):
        with patched_env(
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON="not-json",
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertFalse(catalog["google_play"]["service_account_configured"])
            self.assertIn(
                "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON valid service account JSON",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_google_play_readiness_rejects_malformed_service_account_key(self):
        malformed = json.dumps({
            "type": "service_account",
            "client_email": "play-api@example.iam.gserviceaccount.com",
            "private_key": "not-a-private-key",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        with patched_env(
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=malformed,
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertFalse(catalog["google_play"]["service_account_configured"])
            self.assertIn(
                "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON valid service account credentials",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_production_readiness_requires_google_play_product_ids(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID=None,
            GOOGLE_PLAY_BASIC_REVIEW_25_ID=None,
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID=None,
            GOOGLE_PLAY_ADVANCED_REVIEW_20_ID=None,
            GOOGLE_PLAY_PRO_MONTHLY_ID=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_BASIC_REVIEW_15_ID",
                catalog["google_play"]["missing_server_settings"],
            )
            self.assertIn(
                "GOOGLE_PLAY_PRO_MONTHLY_ID",
                catalog["google_play"]["missing_server_settings"],
            )
            self.assertIn("product_id_mappings", catalog["google_play"])
            self.assertFalse(catalog["google_play"]["product_id_mappings"]["all_configured"])

    def test_production_readiness_requires_purchase_token_encryption_key(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_PURCHASE_TOKEN_ENCRYPTION_KEY=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_PURCHASE_TOKEN_ENCRYPTION_KEY",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_production_readiness_rejects_duplicate_google_play_product_ids(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID="alphamate.duplicate",
            GOOGLE_PLAY_BASIC_REVIEW_25_ID="alphamate.duplicate",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_ADVANCED_REVIEW_20_ID="alphamate.advanced.20",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-token-with-at-least-32-characters",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_PRODUCT_ID_DUPLICATE: alphamate.duplicate",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_production_readiness_requires_strong_rtdn_shared_token(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID="alphamate.basic.15",
            GOOGLE_PLAY_BASIC_REVIEW_25_ID="alphamate.basic.25",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_ADVANCED_REVIEW_20_ID="alphamate.advanced.20",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="short-rtdn-token",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_RTDN_SHARED_TOKEN_MIN_LENGTH_32",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_production_readiness_rejects_placeholder_rtdn_oidc_settings(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_15_ID="alphamate.basic.15",
            GOOGLE_PLAY_BASIC_REVIEW_25_ID="alphamate.basic.25",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_ADVANCED_REVIEW_20_ID="alphamate.advanced.20",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-token-with-at-least-32-characters",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE="https://your-api.example.com/api/journal/google-play-rtdn",
            GOOGLE_PLAY_RTDN_OIDC_EMAIL="pubsub-push@your-project.iam.gserviceaccount.com",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_RTDN_OIDC_AUDIENCE_PLACEHOLDER",
                catalog["google_play"]["missing_server_settings"],
            )
            self.assertIn(
                "GOOGLE_PLAY_RTDN_OIDC_EMAIL_PLACEHOLDER",
                catalog["google_play"]["missing_server_settings"],
            )

    def test_basic_and_advanced_rewarded_ad_progress_are_separate(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ALPHAMATE_ADS_PER_ADVANCED_TICKET="2",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            for _ in range(6):
                access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )

            first = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="dev-ad-reward",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )
            second = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="dev-ad-reward",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )

            self.assertEqual("rewarded_ad_basic", first.source)
            self.assertEqual("rewarded_ad_basic", second.source)
            self.assertEqual(0, second.quota["advanced"]["weekly_reward_remaining"])
            self.assertEqual(0, second.quota["advanced"]["weekly_ad_views"])
            self.assertEqual(2, second.quota["advanced"]["weekly_ad_views_needed"])

            refunded = access_control.refund_ai_review_access(second)

            self.assertEqual(0, refunded["advanced"]["weekly_reward_remaining"])
            self.assertEqual(0, refunded["advanced"]["weekly_ad_views"])
            self.assertEqual(2, refunded["advanced"]["weekly_ad_views_needed"])

            advanced_first = access_control.claim_rewarded_ad_progress(
                authorization="Bearer dev-token",
                entitlement_token="",
                ad_reward_token="dev-ad-reward",
            )
            advanced_second = access_control.claim_rewarded_ad_progress(
                authorization="Bearer dev-token",
                entitlement_token="",
                ad_reward_token="dev-ad-reward",
            )

            self.assertEqual(1, advanced_first["advanced"]["weekly_ad_views"])
            self.assertFalse(advanced_first["ad_reward"]["advanced_ticket_granted"])
            self.assertEqual(2, advanced_second["advanced"]["weekly_ad_views"])
            self.assertTrue(advanced_second["ad_reward"]["advanced_ticket_granted"])
            self.assertEqual(1, advanced_second["advanced"]["weekly_reward_remaining"])

    def test_basic_rewarded_ad_does_not_consume_purchased_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            for _ in range(6):
                access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )

            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="basic_review_15",
            )

            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="dev-ad-reward",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )

            self.assertEqual("rewarded_ad_basic", access.source)
            self.assertEqual(15, access.quota["basic"]["purchased_remaining"])

    def test_google_play_purchase_requires_server_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.apply_google_play_purchase(
                    authorization="Bearer dev-token",
                    product_id="basic_review_15",
                    purchase_token="purchase-token",
                )

            self.assertEqual(503, raised.exception.status_code)

    def test_purchase_credits_are_consumed_fifo_and_record_order_source(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
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

            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )

            conn = access_control._connect_access_db()
            try:
                orders = conn.execute(
                    "SELECT order_id, used_quantity, remaining_quantity FROM purchase_credit_orders ORDER BY created_at, order_id"
                ).fetchall()
                usage = conn.execute("SELECT * FROM credit_usage_ledger").fetchone()
            finally:
                conn.close()

            self.assertEqual("purchased_advanced", access.source)
            self.assertEqual(29, access.quota["advanced"]["purchased_remaining"])
            self.assertEqual((1, 9), (orders[0]["used_quantity"], orders[0]["remaining_quantity"]))
            self.assertEqual((0, 20), (orders[1]["used_quantity"], orders[1]["remaining_quantity"]))
            self.assertEqual(orders[0]["order_id"], usage["source_order_id"])
            self.assertEqual("purchase_order", usage["source_type"])

    def test_basic_purchase_credit_is_consumed_after_free_credits(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="basic_review_15",
            )
            for _ in range(6):
                access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="basic",
                )
            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="basic",
            )

            self.assertEqual("purchased_basic", access.source)
            self.assertEqual(14, access.quota["basic"]["purchased_remaining"])

    def test_purchase_credit_refund_restores_the_same_order(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
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
            refunded = access_control.refund_ai_review_access(access)

            conn = access_control._connect_access_db()
            try:
                order = conn.execute("SELECT * FROM purchase_credit_orders").fetchone()
                usage = conn.execute("SELECT * FROM credit_usage_ledger").fetchone()
            finally:
                conn.close()

            self.assertEqual(10, refunded["advanced"]["purchased_remaining"])
            self.assertEqual((0, 10), (order["used_quantity"], order["remaining_quantity"]))
            self.assertEqual("reversed", usage["status"])

    def test_purchase_credit_consumption_rolls_back_when_wallet_save_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_10",
            )
            with patch.object(access_control, "_write_wallet", side_effect=RuntimeError("save failed")):
                with self.assertRaises(RuntimeError):
                    access_control.verify_ai_review_access(
                        authorization="Bearer dev-token",
                        ad_reward_token="",
                        entitlement_token="",
                        privacy_consent=True,
                        review_type="advanced",
                    )

            conn = access_control._connect_access_db()
            try:
                order = conn.execute("SELECT * FROM purchase_credit_orders").fetchone()
                usage_count = conn.execute("SELECT COUNT(*) FROM credit_usage_ledger").fetchone()[0]
            finally:
                conn.close()

            self.assertEqual((0, 10), (order["used_quantity"], order["remaining_quantity"]))
            self.assertEqual(0, usage_count)

    def test_purchase_credit_consumption_rolls_back_when_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_10",
            )
            with patch.object(access_control, "_wallet_snapshot", side_effect=RuntimeError("snapshot failed")):
                with self.assertRaises(RuntimeError):
                    access_control.verify_ai_review_access(
                        authorization="Bearer dev-token",
                        ad_reward_token="",
                        entitlement_token="",
                        privacy_consent=True,
                        review_type="advanced",
                    )

            conn = access_control._connect_access_db()
            try:
                order = conn.execute("SELECT * FROM purchase_credit_orders").fetchone()
                usage_count = conn.execute("SELECT COUNT(*) FROM credit_usage_ledger").fetchone()[0]
            finally:
                conn.close()

            self.assertEqual((0, 10), (order["used_quantity"], order["remaining_quantity"]))
            self.assertEqual(0, usage_count)

    def test_rtdn_requires_shared_token(self):
        with patched_env(GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-secret"):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.handle_google_play_rtdn(
                    pubsub_payload={"message": {"data": "e30="}},
                    shared_token="wrong",
                )

            self.assertEqual(403, raised.exception.status_code)

    def test_rtdn_shared_token_uses_constant_time_compare(self):
        with patched_env(GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-secret"):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            calls = []

            class FakeHmac:
                @staticmethod
                def compare_digest(left, right):
                    calls.append((left, right))
                    return False

            access_control.hmac = FakeHmac
            with self.assertRaises(HTTPException) as raised:
                access_control.handle_google_play_rtdn(
                    pubsub_payload={"message": {"data": "e30="}},
                    shared_token="wrong",
                )

            self.assertEqual(403, raised.exception.status_code)
            self.assertEqual([("wrong", "rtdn-secret")], calls)

    def test_rtdn_rejects_short_shared_token_in_production(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="short-rtdn-token",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.handle_google_play_rtdn(
                    pubsub_payload={"message": {"data": "e30="}},
                    shared_token="short-rtdn-token",
                )

            self.assertEqual(503, raised.exception.status_code)
            self.assertIn("RTDN shared token", raised.exception.detail)

    def test_rtdn_requires_oidc_when_configured(self):
        with patched_env(
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-secret",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE="https://example.com/rtdn",
            GOOGLE_PLAY_RTDN_OIDC_EMAIL="pubsub-push@example.iam.gserviceaccount.com",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.handle_google_play_rtdn(
                    pubsub_payload={"message": {"data": "e30="}},
                    shared_token="rtdn-secret",
                )

            self.assertEqual(403, raised.exception.status_code)

    def test_admob_ssv_signature_requires_required_fields(self):
        with patched_env(ADMOB_REWARDED_AD_UNIT_ID=""):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control._verify_admob_ssv_signature("transaction_id=ad-tx-1")

            self.assertEqual(400, raised.exception.status_code)

    def test_admob_ssv_signature_content_decodes_percent_encoded_reward_text(self):
        from backend.core import access_control

        content = access_control._admob_content_to_verify(
            "ad_unit=1234567890&reward_item=%EA%B4%91%EA%B3%A0%20%EC%8B%9C%EC%B2%AD"
            "&custom_data=a+b&signature=test&key_id=1"
        )

        self.assertEqual(
            "ad_unit=1234567890&reward_item=광고 시청&custom_data=a+b".encode("utf-8"),
            content,
        )

    def test_voided_purchase_reconciliation_defaults_to_thirty_day_window(self):
        from backend.core import access_control

        start_time_millis, end_time_millis = access_control._voided_purchase_window(
            start_time_millis=None,
            end_time_millis=None,
        )

        self.assertEqual(30 * 24 * 60 * 60 * 1000, end_time_millis - start_time_millis)


if __name__ == "__main__":
    unittest.main()
