import importlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing


class AccountStoreTest(unittest.TestCase):
    def test_provider_login_reuses_user_and_authenticates_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")

            from backend.core import account_store

            account_store = importlib.reload(account_store)
            first = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="kakao-user-1",
                display_name="테스트 사용자",
            )
            second = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="kakao-user-1",
                display_name="테스트 사용자",
            )
            naver = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="kakao-user-1",
                display_name="테스트 사용자",
            )

            self.assertEqual(first["user"]["id"], second["user"]["id"])
            self.assertNotEqual(first["session_token"], second["session_token"])
            self.assertNotEqual(first["user"]["id"], naver["user"]["id"])

            current = account_store.authenticate_session(f"Bearer {first['session_token']}")
            self.assertEqual(first["user"]["id"], current["id"])
            self.assertEqual("kakao", current["identities"][0]["provider"])

    def test_access_wallets_are_separated_by_login_session_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            from backend.core import access_control, account_store

            account_store = importlib.reload(account_store)
            access_control = importlib.reload(access_control)

            kakao = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="user-a",
                display_name="A",
            )
            naver = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="user-b",
                display_name="B",
            )

            access_control.apply_dev_purchase(
                authorization=f"Bearer {kakao['session_token']}",
                entitlement_token="",
                product_id="advanced_review_5",
            )

            kakao_entitlements = access_control.get_user_entitlements(
                authorization=f"Bearer {kakao['session_token']}",
                entitlement_token="",
            )
            naver_entitlements = access_control.get_user_entitlements(
                authorization=f"Bearer {naver['session_token']}",
                entitlement_token="",
            )

            self.assertEqual(5, kakao_entitlements["advanced"]["purchased_remaining"])
            self.assertEqual(0, naver_entitlements["advanced"]["purchased_remaining"])

    def test_journal_storage_setting_can_be_changed_for_session_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")

            from backend.core import account_store

            account_store = importlib.reload(account_store)
            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="storage-user",
                display_name="저장 테스트",
            )
            updated = account_store.update_journal_storage_setting(
                authorization=f"Bearer {session['session_token']}",
                enabled=True,
            )

            self.assertTrue(updated["journal_storage_enabled"])

            current = account_store.authenticate_session(f"Bearer {session['session_token']}")
            self.assertTrue(current["journal_storage_enabled"])

    def test_delete_user_account_data_removes_server_side_user_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            account_db = os.path.join(tmpdir, "accounts.sqlite3")
            access_db = os.path.join(tmpdir, "access.sqlite3")
            journal_db = os.path.join(tmpdir, "trades.sqlite3")
            review_history_db = os.path.join(tmpdir, "review_history.sqlite3")
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = account_db
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = access_db
            os.environ["ALPHAMATE_JOURNAL_DB_PATH"] = journal_db
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = review_history_db
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            from backend.core import access_control, account_store, journal, review_history

            account_store = importlib.reload(account_store)
            access_control = importlib.reload(access_control)
            journal = importlib.reload(journal)
            review_history = importlib.reload(review_history)

            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="delete-user",
                display_name="삭제 테스트",
            )
            token = f"Bearer {session['session_token']}"
            user_id = session["user"]["id"]
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            journal.add_trade(
                {
                    "trade_date": "2026-06-19T09:01",
                    "ticker": "005930",
                    "name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 1,
                },
                user_id=user_id,
            )
            access_control.apply_dev_purchase(
                authorization=token,
                entitlement_token="",
                product_id="advanced_review_5",
            )
            access_control._verify_admob_ssv_signature = lambda raw_query: {
                "transaction_id": "delete-ad-1",
                "user_id": user_id,
                "ad_unit": "",
                "reward_amount": "1",
                "reward_item": "AI_REVIEW",
                "custom_data": "basic",
            }
            access_control.record_admob_ssv_reward("transaction_id=delete-ad-1")
            review_history.add_review_history(
                user_id=user_id,
                review_type="basic",
                ticker="005930",
                name="삼성전자",
                ai_review={"summary": "deleted review"},
            )

            result = account_store.delete_user_account_data(token)

            self.assertEqual(user_id, result["deleted_user_id"])
            self.assertEqual(1, result["deleted_trades"])
            self.assertEqual(1, result["deleted_wallets"])
            self.assertEqual(1, result["deleted_admob_rewards"])
            self.assertEqual(1, result["deleted_review_history"])
            with self.assertRaises(Exception):
                account_store.authenticate_session(token)

            with closing(sqlite3.connect(account_db)) as conn:
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,)).fetchone()[0])
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM user_identities WHERE user_id = ?", (user_id,)).fetchone()[0])
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM user_sessions WHERE user_id = ?", (user_id,)).fetchone()[0])
            with closing(sqlite3.connect(access_db)) as conn:
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM access_wallets WHERE user_id = ?", (user_id,)).fetchone()[0])
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM admob_reward_events WHERE user_id = ?", (user_id,)).fetchone()[0])
            self.assertEqual(0, journal.count_trades(user_id=user_id))
            self.assertEqual([], review_history.list_review_history(user_id=user_id))


if __name__ == "__main__":
    unittest.main()
