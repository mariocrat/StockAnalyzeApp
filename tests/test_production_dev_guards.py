from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

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
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())

    def test_persistent_journal_routes_require_auth_in_production(self):
        with patched_env(ALPHAMATE_ENV="production"):
            import main

            trade = main.JournalTradeIn(
                trade_date="2026-06-21T10:30",
                ticker="005930",
                name="Samsung",
                side="buy",
                price=70000,
                quantity=1,
            )

            blocked_calls = [
                lambda: main.get_journal_trades(),
                lambda: main.create_journal_trade(trade),
                lambda: main.remove_journal_trade(1),
                lambda: main.remove_all_journal_trades(),
                lambda: main.get_journal_review(),
                lambda: main.get_journal_charts(),
            ]
            for call in blocked_calls:
                with self.assertRaises(HTTPException) as blocked:
                    call()
                self.assertEqual(401, blocked.exception.status_code)

            self.enterContext(patch.object(main, "build_journal_charts", lambda trades: {"charts": [{"trade_count": len(trades)}]}))
            once_review = main.get_journal_review_once(main.JournalBatchIn(trades=[trade]))
            once_charts = main.get_journal_charts_once(main.JournalBatchIn(trades=[trade]))
            self.assertIn("summary", once_review)
            self.assertEqual(1, once_charts["charts"][0]["trade_count"])

    def test_dev_login_is_disabled_in_production(self):
        with patched_env(ALPHAMATE_ENV="production"):
            from core import account_store


            with self.assertRaises(HTTPException) as raised:
                account_store.login_dev_provider(
                    provider="kakao",
                    provider_user_id="prod-dev-login",
                    display_name="운영 차단",
                )

            self.assertEqual(403, raised.exception.status_code)

    def test_dev_token_and_dev_purchase_are_disabled_in_production(self):
        with patched_env(ALPHAMATE_ENV="production"):
            from core import access_control, account_store


            with patched_env(ALPHAMATE_ENV="development", ALPHAMATE_ALLOW_DEV_ACCESS="true"):
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
                    product_id="advanced_review_10",
                )
            self.assertEqual(403, dev_purchase_error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
