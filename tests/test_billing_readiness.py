import base64
import importlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

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
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_ADS_PER_ADVANCED_TICKET="3",
            ALPHAMATE_FORCE_REWARDED_AD_CHAIN="false",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertEqual("alphamate.basic.30", catalog["consumables"]["basic_review_30"]["google_play_product_id"])
            self.assertTrue(catalog["google_play"]["ready"])
            self.assertTrue(catalog["google_play"]["service_account_configured"])
            self.assertTrue(catalog["admob"]["ready"])
            self.assertTrue(catalog["admob"]["rewarded_ad_unit_configured"])
            self.assertEqual("/api/journal/admob-ssv", catalog["admob"]["ssv_callback_path"])
            self.assertEqual(1, catalog["settings"]["ad_policy"]["basic_reviews_per_rewarded_ad"])
            self.assertEqual(3, catalog["settings"]["ad_policy"]["ads_per_advanced_ticket"])
            self.assertFalse(catalog["settings"]["ad_policy"]["force_rewarded_ad_chain"])
            self.assertNotIn("fake-private-key", str(catalog))

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
            GOOGLE_PLAY_BASIC_REVIEW_30_ID=None,
            GOOGLE_PLAY_BASIC_REVIEW_100_ID=None,
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID=None,
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID=None,
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID=None,
            GOOGLE_PLAY_PRO_MONTHLY_ID=None,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertFalse(catalog["google_play"]["ready"])
            self.assertIn(
                "GOOGLE_PLAY_BASIC_REVIEW_30_ID",
                catalog["google_play"]["missing_server_settings"],
            )
            self.assertIn(
                "GOOGLE_PLAY_PRO_MONTHLY_ID",
                catalog["google_play"]["missing_server_settings"],
            )
            self.assertIn("product_id_mappings", catalog["google_play"])
            self.assertFalse(catalog["google_play"]["product_id_mappings"]["all_configured"])

    def test_production_readiness_rejects_duplicate_google_play_product_ids(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.duplicate",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.duplicate",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
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
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.basic.100",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
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
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.basic.100",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
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

    def test_ad_reward_advanced_threshold_is_configurable(self):
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
            self.assertEqual(1, second.quota["advanced"]["weekly_reward_remaining"])
            self.assertEqual(0, second.quota["advanced"]["weekly_ad_views_needed"])

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
                    product_id="basic_review_30",
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
                    product_id="basic_review_30",
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
                    "acknowledgement_state": "acknowledged",
                }

            consumed = []
            access_control._verify_google_play_purchase = fake_verify
            access_control._consume_google_play_product = lambda **kwargs: consumed.append(kwargs) or True

            first = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_30",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )
            second = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_30",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual(30, first["basic"]["purchased_remaining"])
            self.assertEqual(30, second["basic"]["purchased_remaining"])
            self.assertEqual("applied", first["purchase"]["status"])
            self.assertEqual("already_applied", second["purchase"]["status"])
            self.assertEqual(1, len(consumed))

    def test_google_play_purchase_stored_fields_are_length_limited(self):
        long_product_id = "alphamate.basic." + ("p" * 500)
        long_order_id = "GPA." + ("o" * 500)
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_30_ID=long_product_id,
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control._verify_google_play_purchase = lambda **kwargs: {
                "package_name": "com.alphamate.app",
                "product_id": kwargs["google_product_id"],
                "purchase_state": "purchased",
                "order_id": long_order_id,
                "acknowledgement_state": "acknowledged",
            }
            access_control._consume_google_play_product = lambda **kwargs: True

            access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_30",
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
                product_id="basic_review_30",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )
            second = access_control.apply_google_play_purchase(
                authorization="Bearer dev-token",
                product_id="basic_review_30",
                purchase_token="purchase-token",
                package_name="com.alphamate.app",
            )

            self.assertEqual(30, first["basic"]["purchased_remaining"])
            self.assertEqual(30, second["basic"]["purchased_remaining"])
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
                    product_id="basic_review_30",
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
            self.assertEqual(150, entitlements["basic"]["pro_monthly_remaining"])
            self.assertEqual(5, entitlements["advanced"]["pro_monthly_remaining"])

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
            self.assertEqual(4, access.quota["advanced"]["pro_monthly_remaining"])

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
                "custom_data": "basic",
            }

            first = access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")
            second = access_control.record_admob_ssv_reward("transaction_id=ad-tx-1")

            self.assertEqual("recorded", first["status"])
            self.assertEqual("already_recorded", second["status"])

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
                "custom_data": "basic",
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
            self.assertEqual(3, access.quota["basic"]["free_daily_max_remaining"])

    def test_admob_ssv_signature_requires_required_fields(self):
        with patched_env(ADMOB_REWARDED_AD_UNIT_ID=""):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control._verify_admob_ssv_signature("transaction_id=ad-tx-1")

            self.assertEqual(400, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
