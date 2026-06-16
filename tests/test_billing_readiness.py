import importlib
import os
import tempfile
import unittest
from contextlib import contextmanager

from fastapi import HTTPException


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
    def test_product_catalog_exposes_public_ids_and_readiness_only(self):
        with patched_env(
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON="secret-json",
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
        ):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            catalog = access_control.get_product_catalog()

            self.assertEqual("alphamate.basic.30", catalog["consumables"]["basic_review_30"]["google_play_product_id"])
            self.assertTrue(catalog["google_play"]["ready"])
            self.assertTrue(catalog["google_play"]["service_account_configured"])
            self.assertNotIn("secret-json", str(catalog))

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

    def test_google_play_purchase_does_not_grant_before_verification_is_implemented(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON="secret-json",
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

            self.assertEqual(501, raised.exception.status_code)
            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            self.assertEqual(0, entitlements["basic"]["purchased_remaining"])


if __name__ == "__main__":
    unittest.main()
