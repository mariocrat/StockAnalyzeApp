import importlib
import os
import tempfile
import unittest

from fastapi import HTTPException


class OAuthLoginTest(unittest.TestCase):
    def test_oauth_request_timeout_setting_is_capped(self):
        previous = os.environ.get("ALPHAMATE_OAUTH_TIMEOUT_SECONDS")
        try:
            os.environ["ALPHAMATE_OAUTH_TIMEOUT_SECONDS"] = "999"

            from backend.core import oauth_login

            oauth_login = importlib.reload(oauth_login)
            captured = {}

            class FakeResponse:
                status_code = 200

                def json(self):
                    return {"ok": True}

            def fake_post(url, *, data, headers, timeout):
                captured["post_timeout"] = timeout
                return FakeResponse()

            def fake_get(url, *, headers, timeout):
                captured["get_timeout"] = timeout
                return FakeResponse()

            oauth_login.requests.post = fake_post
            oauth_login.requests.get = fake_get

            self.assertEqual({"ok": True}, oauth_login._exchange_json("https://example.com/token", {"code": "x"}))
            self.assertEqual({"ok": True}, oauth_login._request_json("https://example.com/me", "token"))
            self.assertEqual(20, captured["post_timeout"])
            self.assertEqual(20, captured["get_timeout"])
        finally:
            if previous is None:
                os.environ.pop("ALPHAMATE_OAUTH_TIMEOUT_SECONDS", None)
            else:
                os.environ["ALPHAMATE_OAUTH_TIMEOUT_SECONDS"] = previous

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

    def test_kakao_authorization_code_is_exchanged_before_login(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["KAKAO_CLIENT_ID"] = "kakao-client-id"
            os.environ["KAKAO_CLIENT_SECRET"] = "kakao-client-secret"

            from backend.core import account_store, oauth_login

            account_store = importlib.reload(account_store)
            oauth_login = importlib.reload(oauth_login)

            def fake_exchange(url, payload, headers=None):
                self.assertEqual("https://kauth.kakao.com/oauth/token", url)
                self.assertEqual("authorization_code", payload["grant_type"])
                self.assertEqual("kakao-client-id", payload["client_id"])
                self.assertEqual("kakao-client-secret", payload["client_secret"])
                self.assertEqual("https://alphamate.example/auth/kakao", payload["redirect_uri"])
                self.assertEqual("kakao-code", payload["code"])
                return {"access_token": "exchanged-kakao-token"}

            def fake_request_json(url, token):
                self.assertEqual("https://kapi.kakao.com/v2/user/me", url)
                self.assertEqual("exchanged-kakao-token", token)
                return {
                    "id": 987654321,
                    "kakao_account": {"profile": {"nickname": "교환 카카오"}},
                }

            oauth_login._exchange_json = fake_exchange
            oauth_login._request_json = fake_request_json

            session = oauth_login.login_oauth_code(
                provider="kakao",
                code="kakao-code",
                redirect_uri="https://alphamate.example/auth/kakao",
            )

            self.assertEqual("교환 카카오", session["user"]["display_name"])
            self.assertEqual("987654321", session["user"]["identities"][0]["provider_user_id"])

    def test_naver_authorization_code_is_exchanged_before_login(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["NAVER_CLIENT_ID"] = "naver-client-id"
            os.environ["NAVER_CLIENT_SECRET"] = "naver-client-secret"

            from backend.core import account_store, oauth_login

            account_store = importlib.reload(account_store)
            oauth_login = importlib.reload(oauth_login)

            def fake_exchange(url, payload, headers=None):
                self.assertEqual("https://nid.naver.com/oauth2.0/token", url)
                self.assertEqual("authorization_code", payload["grant_type"])
                self.assertEqual("naver-client-id", payload["client_id"])
                self.assertEqual("naver-client-secret", payload["client_secret"])
                self.assertEqual("https://alphamate.example/auth/naver", payload["redirect_uri"])
                self.assertEqual("naver-code", payload["code"])
                self.assertEqual("naver-state", payload["state"])
                return {"access_token": "exchanged-naver-token"}

            def fake_request_json(url, token):
                self.assertEqual("https://openapi.naver.com/v1/nid/me", url)
                self.assertEqual("exchanged-naver-token", token)
                return {
                    "response": {
                        "id": "naver-exchanged-user",
                        "nickname": "교환 네이버",
                    },
                }

            oauth_login._exchange_json = fake_exchange
            oauth_login._request_json = fake_request_json

            session = oauth_login.login_oauth_code(
                provider="naver",
                code="naver-code",
                redirect_uri="https://alphamate.example/auth/naver",
                state="naver-state",
            )

            self.assertEqual("교환 네이버", session["user"]["display_name"])
            self.assertEqual("naver-exchanged-user", session["user"]["identities"][0]["provider_user_id"])

    def test_oauth_code_login_requires_provider_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ.pop("KAKAO_CLIENT_ID", None)

            from backend.core import oauth_login

            oauth_login = importlib.reload(oauth_login)

            with self.assertRaises(HTTPException) as raised:
                oauth_login.login_oauth_code(
                    provider="kakao",
                    code="code",
                    redirect_uri="https://alphamate.example/auth/kakao",
                )

            self.assertEqual(503, raised.exception.status_code)

    def test_oauth_config_status_reports_missing_server_settings(self):
        for key in ("KAKAO_CLIENT_ID", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
            os.environ.pop(key, None)

        from backend.core import oauth_login

        oauth_login = importlib.reload(oauth_login)
        status = oauth_login.get_oauth_config_status()

        self.assertFalse(status["providers"]["kakao"]["server_ready"])
        self.assertEqual(["KAKAO_CLIENT_ID"], status["providers"]["kakao"]["missing_server_settings"])
        self.assertFalse(status["providers"]["naver"]["server_ready"])
        self.assertEqual(
            ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"],
            status["providers"]["naver"]["missing_server_settings"],
        )

    def test_oauth_config_status_reports_ready_server_settings(self):
        os.environ["KAKAO_CLIENT_ID"] = "kakao-client-id"
        os.environ["NAVER_CLIENT_ID"] = "naver-client-id"
        os.environ["NAVER_CLIENT_SECRET"] = "naver-client-secret"

        from backend.core import oauth_login

        oauth_login = importlib.reload(oauth_login)
        status = oauth_login.get_oauth_config_status()

        self.assertTrue(status["providers"]["kakao"]["server_ready"])
        self.assertEqual([], status["providers"]["kakao"]["missing_server_settings"])
        self.assertTrue(status["providers"]["naver"]["server_ready"])
        self.assertEqual([], status["providers"]["naver"]["missing_server_settings"])


if __name__ == "__main__":
    unittest.main()
