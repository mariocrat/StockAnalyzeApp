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
