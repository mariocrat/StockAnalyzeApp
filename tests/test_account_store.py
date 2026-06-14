import importlib
import os
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
