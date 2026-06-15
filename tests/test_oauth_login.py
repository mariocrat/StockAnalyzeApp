import importlib
import os
import tempfile
import unittest

from fastapi import HTTPException


class OAuthLoginTest(unittest.TestCase):
    def test_kakao_access_token_profile_creates_alphamate_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")

            from backend.core import account_store, oauth_login

            account_store = importlib.reload(account_store)
            oauth_login = importlib.reload(oauth_login)

            def fake_request_json(url, token):
                self.assertEqual("https://kapi.kakao.com/v2/user/me", url)
                self.assertEqual("kakao-access-token", token)
                return {
                    "id": 123456789,
                    "kakao_account": {
                        "email": "user@example.com",
                        "profile": {"nickname": "카카오 사용자"},
                    },
                }

            oauth_login._request_json = fake_request_json

            session = oauth_login.login_oauth_provider(
                provider="kakao",
                access_token="kakao-access-token",
            )

            self.assertEqual("bearer", session["token_type"])
            self.assertEqual("카카오 사용자", session["user"]["display_name"])
            self.assertEqual("kakao", session["user"]["identities"][0]["provider"])
            self.assertEqual("123456789", session["user"]["identities"][0]["provider_user_id"])

    def test_naver_access_token_profile_creates_alphamate_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")

            from backend.core import account_store, oauth_login

            account_store = importlib.reload(account_store)
            oauth_login = importlib.reload(oauth_login)

            def fake_request_json(url, token):
                self.assertEqual("https://openapi.naver.com/v1/nid/me", url)
                self.assertEqual("naver-access-token", token)
                return {
                    "resultcode": "00",
                    "response": {
                        "id": "naver-user-id",
                        "email": "naver@example.com",
                        "nickname": "네이버 사용자",
                    },
                }

            oauth_login._request_json = fake_request_json

            session = oauth_login.login_oauth_provider(
                provider="naver",
                access_token="naver-access-token",
            )

            self.assertEqual("네이버 사용자", session["user"]["display_name"])
            self.assertEqual("naver", session["user"]["identities"][0]["provider"])
            self.assertEqual("naver-user-id", session["user"]["identities"][0]["provider_user_id"])

    def test_oauth_login_requires_access_token(self):
        from backend.core import oauth_login

        with self.assertRaises(HTTPException) as raised:
            oauth_login.login_oauth_provider(provider="kakao", access_token="")

        self.assertEqual(400, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
