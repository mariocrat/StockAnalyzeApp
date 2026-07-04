import importlib
import os
import sys
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
    def test_persistent_journal_routes_require_auth_in_production(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="production",
            ALPHAMATE_ACCOUNT_DB_PATH=os.path.join(tmpdir, "accounts.sqlite3"),
            ALPHAMATE_JOURNAL_DB_PATH=os.path.join(tmpdir, "journal.sqlite3"),
        ):
            backend_dir = os.path.join(os.getcwd(), "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            import main

            main = importlib.reload(main)
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

            main.build_journal_charts = lambda trades: {"charts": [{"trade_count": len(trades)}]}
            once_review = main.get_journal_review_once(main.JournalBatchIn(trades=[trade]))
            once_charts = main.get_journal_charts_once(main.JournalBatchIn(trades=[trade]))
            self.assertIn("summary", once_review)
            self.assertEqual(1, once_charts["charts"][0]["trade_count"])

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
