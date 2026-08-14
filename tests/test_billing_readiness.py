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


class BillingReadinessTest(unittest.TestCase):
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

    def test_google_play_purchase_code_does_not_claim_subscription_verification_is_missing(self):
        code = (ROOT / "backend" / "core" / "access_control.py").read_text(encoding="utf-8")

        self.assertIn("def _verify_google_play_subscription", code)
        self.assertNotIn("Google Play subscription verification is not implemented yet", code)

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
