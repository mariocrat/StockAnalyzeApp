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


class ProductionDevGuardsTest(unittest.TestCase):
    def test_dev_login_is_disabled_in_production(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="production",
            ALPHAMATE_ACCOUNT_DB_PATH=os.path.join(tmpdir, "accounts.sqlite3"),
        ):
            from backend.core import account_store

            account_store = importlib.reload(account_store)

            with self.assertRaises(HTTPException) as raised:
                account_store.login_dev_provider(
                    provider="kakao",
                    provider_user_id="prod-dev-login",
                    display_name="운영 차단",
                )

            self.assertEqual(403, raised.exception.status_code)

    def test_dev_token_and_dev_purchase_are_disabled_in_production(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="production",
            ALPHAMATE_ACCOUNT_DB_PATH=os.path.join(tmpdir, "accounts.sqlite3"),
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
        ):
            from backend.core import access_control, account_store

            account_store = importlib.reload(account_store)
            access_control = importlib.reload(access_control)

            with patched_env(ALPHAMATE_ENV="development"):
                session = account_store.login_dev_provider(
                    provider="kakao",
                    provider_user_id="prod-session",
                    display_name="운영 세션",
                )

            with self.assertRaises(HTTPException) as dev_token_error:
                access_control.get_user_entitlements(
                    authorization="Bearer dev-token",
                    entitlement_token="",
                )
            self.assertEqual(401, dev_token_error.exception.status_code)

            with self.assertRaises(HTTPException) as dev_purchase_error:
                access_control.apply_dev_purchase(
                    authorization=f"Bearer {session['session_token']}",
                    entitlement_token="",
                    product_id="advanced_review_5",
                )
            self.assertEqual(403, dev_purchase_error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
