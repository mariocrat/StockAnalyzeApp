import importlib
import os
import sys
import unittest

from fastapi import HTTPException


def _load_main():
    backend_dir = os.path.join(os.getcwd(), "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    importlib.reload(importlib.import_module("core.account_store"))
    importlib.reload(importlib.import_module("core.access_control"))
    return importlib.reload(importlib.import_module("main"))


def _trade(main, index: int):
    return main.JournalTradeIn(
        trade_date="2026-06-21T10:30",
        ticker="005930",
        name="삼성전자",
        side="buy",
        price=70000 + index,
        quantity=1,
    )


class JournalBatchLimitTest(unittest.TestCase):
    ENV_KEYS = [
        "ALPHAMATE_JOURNAL_ONCE_MAX_TRADES",
        "ALPHAMATE_AI_REVIEW_MAX_TRADES",
        "ALPHAMATE_ALLOW_DEV_ACCESS",
        "ALPHAMATE_ENV",
        "ALPHAMATE_ACCOUNT_DB_PATH",
        "ALPHAMATE_ACCESS_DB_PATH",
    ]

    def setUp(self):
        self._previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_review_once_rejects_batches_above_configured_limit(self):
        os.environ["ALPHAMATE_JOURNAL_ONCE_MAX_TRADES"] = "2"
        main = _load_main()
        batch = main.JournalBatchIn(trades=[_trade(main, 1), _trade(main, 2), _trade(main, 3)])

        with self.assertRaises(HTTPException) as blocked:
            main.get_journal_review_once(batch)

        self.assertEqual(413, blocked.exception.status_code)
        self.assertIn("최대 2건", blocked.exception.detail)

    def test_ai_review_once_rejects_batches_above_ai_limit_before_charging(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_AI_REVIEW_MAX_TRADES"] = "1"
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"
            os.environ["ALPHAMATE_ENV"] = "development"
            main = _load_main()
            account_store = importlib.import_module("core.account_store")
            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="batch-limit-user",
                display_name="Batch Limit",
            )
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="basic",
                trades=[_trade(main, 1), _trade(main, 2)],
            )

            with self.assertRaises(HTTPException) as blocked:
                main.get_journal_ai_review_once(batch, authorization=f"Bearer {session['session_token']}")

            self.assertEqual(413, blocked.exception.status_code)
            self.assertIn("AI 복기는 한 번에 최대 1건", blocked.exception.detail)


if __name__ == "__main__":
    unittest.main()
