import importlib
import os
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


if __name__ == "__main__":
    unittest.main()
