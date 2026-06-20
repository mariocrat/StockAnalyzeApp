import importlib
import json
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
                    "privacy_consent_version": "",
                    "privacy_consented_at": "",
                },
                summary,
            )

    def test_delete_me_account_data_is_exposed_as_current_user_only_route(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            backend_dir = os.path.join(os.getcwd(), "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            account_store = importlib.reload(importlib.import_module("core.account_store"))
            journal = importlib.reload(importlib.import_module("core.journal"))
            main = importlib.reload(importlib.import_module("main"))

            session = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="delete-route-user",
                display_name="삭제 라우트",
            )
            token = f"Bearer {session['session_token']}"
            user_id = session["user"]["id"]
            journal.add_trade(
                {
                    "trade_date": "2026-06-19T10:00",
                    "ticker": "005930",
                    "name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 1,
                },
                user_id=user_id,
            )

            paths = set(main.app.openapi()["paths"].keys())
            result = main.delete_me_account_data(authorization=token)

            self.assertIn("/api/me/account-data", paths)
            self.assertTrue(result["ok"])
            self.assertEqual(user_id, result["deleted_user_id"])
            self.assertEqual(1, result["deleted_trades"])

    def test_export_me_data_includes_current_user_trades_and_entitlements_without_session_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            backend_dir = os.path.join(os.getcwd(), "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            account_store = importlib.reload(importlib.import_module("core.account_store"))
            access_control = importlib.reload(importlib.import_module("core.access_control"))
            journal = importlib.reload(importlib.import_module("core.journal"))
            review_history = importlib.reload(importlib.import_module("core.review_history"))
            main = importlib.reload(importlib.import_module("main"))

            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="export-user",
                display_name="내보내기 사용자",
            )
            token = f"Bearer {session['session_token']}"
            user_id = session["user"]["id"]
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            journal.add_trade(
                {
                    "trade_date": "2026-06-19T10:30",
                    "ticker": "005930",
                    "name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 2,
                },
                user_id=user_id,
            )
            access_control.apply_dev_purchase(
                authorization=token,
                entitlement_token="",
                product_id="basic_review_30",
            )
            account_store.record_privacy_consent(authorization=token, version="ai-review-privacy-export")
            review_history.add_review_history(
                user_id=user_id,
                review_type="advanced",
                ticker="005930",
                name="삼성전자",
                ai_review={"summary": "stored advanced review"},
            )

            paths = set(main.app.openapi()["paths"].keys())
            exported = main.export_me_data(authorization=token)
            serialized = json.dumps(exported, ensure_ascii=False)

            self.assertIn("/api/me/export-data", paths)
            self.assertEqual("alphamate_user_data_export", exported["type"])
            self.assertEqual(user_id, exported["user"]["id"])
            self.assertEqual(1, len(exported["saved_trades"]))
            self.assertEqual("005930", exported["saved_trades"][0]["ticker"])
            self.assertEqual(30, exported["entitlements"]["basic"]["purchased_remaining"])
            self.assertEqual(1, len(exported["review_history"]))
            self.assertEqual("stored advanced review", exported["review_history"][0]["ai_review"]["summary"])
            self.assertTrue(exported["server_keeps_ai_review_history"])
            self.assertEqual("ai-review-privacy-export", exported["user"]["privacy_consent_version"])
            self.assertNotIn(session["session_token"], serialized)


if __name__ == "__main__":
    unittest.main()
