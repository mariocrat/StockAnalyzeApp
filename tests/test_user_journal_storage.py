from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import importlib
import unittest


class UserJournalStorageTest(unittest.TestCase):
    def test_saved_trades_are_visible_only_to_their_owner(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"):

            from backend.core import account_store, journal

            account_store = importlib.reload(account_store)
            journal = importlib.reload(journal)

            kakao = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="journal-a",
                display_name="A",
            )
            naver = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="journal-b",
                display_name="B",
            )
            kakao_user_id = kakao["user"]["id"]
            naver_user_id = naver["user"]["id"]

            journal.add_trade(
                {
                    "trade_date": "2026-06-14T09:00",
                    "ticker": "005930",
                    "name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 1,
                },
                user_id=kakao_user_id,
            )

            self.assertEqual(1, len(journal.list_trades(user_id=kakao_user_id)))
            self.assertEqual([], journal.list_trades(user_id=naver_user_id))

    def test_clear_trades_removes_only_the_requested_user_records(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"):

            from backend.core import account_store, journal

            account_store = importlib.reload(account_store)
            journal = importlib.reload(journal)

            kakao = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="clear-a",
                display_name="A",
            )
            naver = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="clear-b",
                display_name="B",
            )
            kakao_user_id = kakao["user"]["id"]
            naver_user_id = naver["user"]["id"]
            trade = {
                "trade_date": "2026-06-14T09:00",
                "ticker": "005930",
                "name": "삼성전자",
                "side": "buy",
                "price": 70000,
                "quantity": 1,
            }

            journal.add_trade(trade, user_id=kakao_user_id)
            journal.add_trade({**trade, "ticker": "000660", "name": "SK하이닉스"}, user_id=naver_user_id)

            deleted_count = journal.clear_trades(user_id=kakao_user_id)

            self.assertEqual(1, deleted_count)
            self.assertEqual([], journal.list_trades(user_id=kakao_user_id))
            self.assertEqual(1, len(journal.list_trades(user_id=naver_user_id)))


if __name__ == "__main__":
    unittest.main()
