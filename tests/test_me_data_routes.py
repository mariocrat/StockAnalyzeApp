import importlib
import os
import sys
import tempfile
import unittest


class MeDataRoutesTest(unittest.TestCase):
    def test_data_summary_counts_only_the_session_users_saved_trades(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")

            backend_dir = os.path.join(os.getcwd(), "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            account_store = importlib.reload(importlib.import_module("core.account_store"))
            journal = importlib.reload(importlib.import_module("core.journal"))
            main = importlib.reload(importlib.import_module("main"))

            kakao = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="summary-kakao",
                display_name="카카오 요약",
            )
            naver = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="summary-naver",
                display_name="네이버 요약",
            )

            trade = {
                "trade_date": "2026-06-15T09:00",
                "ticker": "005930",
                "name": "삼성전자",
                "side": "buy",
                "price": 70000,
                "quantity": 1,
            }
            journal.add_trade(trade, user_id=kakao["user"]["id"])
            journal.add_trade({**trade, "ticker": "000660", "name": "SK하이닉스"}, user_id=naver["user"]["id"])

            paths = set(main.app.openapi()["paths"].keys())
            summary = main.get_me_data_summary(
                authorization=f"Bearer {kakao['session_token']}",
            )

            self.assertIn("/api/me/data-summary", paths)
            self.assertEqual(
                {
                    "journal_storage_enabled": False,
                    "saved_trade_count": 1,
                    "connected_providers": ["kakao"],
                    "delete_scope": "current_user_only",
                    "server_keeps_ai_review_history": False,
                },
                summary,
            )


if __name__ == "__main__":
    unittest.main()
