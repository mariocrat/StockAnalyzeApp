import importlib
import os
import sys
import tempfile
import unittest


class ReviewHistoryStoreTest(unittest.TestCase):
    def test_review_history_is_isolated_by_user_and_returns_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            from backend.core import review_history

            review_history = importlib.reload(review_history)

            first = review_history.add_review_history(
                user_id="user-a",
                review_type="advanced",
                ticker="005930",
                name="삼성전자",
                trade_date="2026-06-19T10:30",
                target_trade_id=7,
                trade_snapshot={"id": 7, "ticker": "005930", "name": "삼성전자"},
                recent_trades_snapshot=[{"id": 7}],
                chart_snapshot={"charts": [{"ticker": "005930"}]},
                ai_review={"summary": "심층 복기 요약"},
                access_snapshot={"source": "purchased_advanced"},
                model="gpt-5.5",
                source="openai",
            )
            review_history.add_review_history(
                user_id="user-b",
                review_type="basic",
                ticker="000660",
                name="SK하이닉스",
                trade_date="2026-06-18T10:30",
                target_trade_id=8,
                trade_snapshot={"id": 8},
                recent_trades_snapshot=[],
                chart_snapshot={},
                ai_review={"summary": "다른 사용자 복기"},
                access_snapshot={},
                model="gpt-5.4-mini",
                source="openai",
            )

            rows = review_history.list_review_history(user_id="user-a")
            detail = review_history.get_review_history(first["id"], user_id="user-a")

            self.assertEqual(1, len(rows))
            self.assertEqual(first["id"], rows[0]["id"])
            self.assertEqual("advanced", rows[0]["review_type"])
            self.assertEqual("삼성전자", detail["name"])
            self.assertEqual("심층 복기 요약", detail["ai_review"]["summary"])
            self.assertEqual({"charts": [{"ticker": "005930"}]}, detail["chart_snapshot"])
            self.assertIsNone(review_history.get_review_history(first["id"], user_id="user-b"))

    def test_clear_review_history_removes_only_requested_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            from backend.core import review_history

            review_history = importlib.reload(review_history)

            review_history.add_review_history(user_id="user-a", review_type="basic", ticker="005930", name="삼성전자")
            review_history.add_review_history(user_id="user-b", review_type="basic", ticker="000660", name="SK하이닉스")

            deleted = review_history.clear_review_history(user_id="user-a")

            self.assertEqual(1, deleted)
            self.assertEqual([], review_history.list_review_history(user_id="user-a"))
            self.assertEqual(1, len(review_history.list_review_history(user_id="user-b")))

    def test_ai_review_once_saves_history_for_authenticated_storage_user(self):
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
            access_control = importlib.reload(importlib.import_module("core.access_control"))
            review_history = importlib.reload(importlib.import_module("core.review_history"))
            main = importlib.reload(importlib.import_module("main"))
            main.build_advanced_ai_review = lambda trades, target_trade_id=None: {
                "status": "ready",
                "source": "openai",
                "review_type": "advanced",
                "model": "gpt-5.5",
                "summary": "saved advanced review",
                "chart_contexts": [{"ticker": "005930"}],
            }
            main.build_journal_charts = lambda trades: {
                "charts": [{
                    "ticker": "005930",
                    "name": "삼성전자",
                    "candles": [{"time": "2026-06-19", "open": 70000, "high": 71000, "low": 69000, "close": 70500}],
                    "markers": [{"time": "2026-06-19", "text": "B"}],
                }],
            }

            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="review-save-user",
                display_name="복기 저장",
            )
            token = f"Bearer {session['session_token']}"
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            access_control.apply_dev_purchase(
                authorization=token,
                entitlement_token="",
                product_id="advanced_review_5",
            )
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="advanced",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-19T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            result = main.get_journal_ai_review_once(batch, authorization=token)
            rows = review_history.list_review_history(user_id=session["user"]["id"])
            detail = review_history.get_review_history(rows[0]["id"], user_id=session["user"]["id"])

            self.assertIn("review_history_id", result)
            self.assertEqual(1, len(rows))
            self.assertEqual("advanced", rows[0]["review_type"])
            self.assertEqual("saved advanced review", detail["ai_review"]["summary"])
            self.assertEqual([{"ticker": "005930"}], detail["chart_snapshot"]["chart_contexts"])
            self.assertEqual("005930", detail["chart_snapshot"]["charts"][0]["ticker"])

    def test_ai_review_once_does_not_save_history_when_storage_is_off(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            backend_dir = os.path.join(os.getcwd(), "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            account_store = importlib.reload(importlib.import_module("core.account_store"))
            review_history = importlib.reload(importlib.import_module("core.review_history"))
            main = importlib.reload(importlib.import_module("main"))
            main.build_basic_ai_review = lambda trades, target_trade_id=None: {
                "status": "ready",
                "source": "openai",
                "review_type": "basic",
                "model": "gpt-5.4-mini",
                "summary": "transient basic review",
            }

            session = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="review-nosave-user",
                display_name="복기 미저장",
            )
            token = f"Bearer {session['session_token']}"
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="basic",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-19T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            result = main.get_journal_ai_review_once(batch, authorization=token)

            self.assertNotIn("review_history_id", result)
            self.assertEqual([], review_history.list_review_history(user_id=session["user"]["id"]))


if __name__ == "__main__":
    unittest.main()
