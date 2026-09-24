from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state
import importlib

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException


with _import_state():
    from backend.core import oauth_login as _oauth_login


class OAuthLoginTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.enterContext(patch.dict(_oauth_login.__dict__))
        importlib.reload(_oauth_login)

    def _replace(self, target, name, value):
        replacement = patch.object(target, name, value)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_oauth_login_requires_access_token(self):
        from backend.core import oauth_login

        with self.assertRaises(HTTPException) as raised:
            oauth_login.login_oauth_provider(provider="kakao", access_token="")

        self.assertEqual(400, raised.exception.status_code)

    def test_oauth_code_login_requires_provider_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
            os.environ.pop("KAKAO_CLIENT_ID", None)

            from backend.core import oauth_login


            with self.assertRaises(HTTPException) as raised:
                oauth_login.login_oauth_code(
                    provider="kakao",
                    code="code",
                    redirect_uri="https://alphamate.example/auth/kakao",
                )

            self.assertEqual(503, raised.exception.status_code)

    def test_production_oauth_code_requires_server_redirect_uri(self):
        keys = ("ALPHAMATE_ENV", "KAKAO_CLIENT_ID", "KAKAO_REDIRECT_URI")
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["ALPHAMATE_ENV"] = "production"
            os.environ["KAKAO_CLIENT_ID"] = "kakao-client-id"
            os.environ.pop("KAKAO_REDIRECT_URI", None)

            from backend.core import oauth_login

            with self.assertRaises(HTTPException) as raised:
                oauth_login._configured_redirect_uri("kakao", "https://app.alphamate.kr/auth/kakao")

            self.assertEqual(503, raised.exception.status_code)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_production_oauth_code_rejects_invalid_server_redirect_uri(self):
        keys = ("ALPHAMATE_ENV", "KAKAO_REDIRECT_URI", "NAVER_REDIRECT_URI")
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["ALPHAMATE_ENV"] = "production"
            os.environ["KAKAO_REDIRECT_URI"] = "not-a-url"
            os.environ["NAVER_REDIRECT_URI"] = "http://localhost:5174/oauth/naver"

            from backend.core import oauth_login

            with self.assertRaises(HTTPException) as kakao_raised:
                oauth_login._configured_redirect_uri("kakao", "")
            with self.assertRaises(HTTPException) as naver_raised:
                oauth_login._configured_redirect_uri("naver", "")

            self.assertEqual(503, kakao_raised.exception.status_code)
            self.assertEqual(503, naver_raised.exception.status_code)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_production_oauth_code_rejects_redirect_uri_mismatch(self):
        keys = ("ALPHAMATE_ENV", "KAKAO_REDIRECT_URI")
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["ALPHAMATE_ENV"] = "production"
            os.environ["KAKAO_REDIRECT_URI"] = "https://api.alphamate.kr/api/auth/kakao/callback"

            from backend.core import oauth_login

            with self.assertRaises(HTTPException) as raised:
                oauth_login._configured_redirect_uri("kakao", "https://app.alphamate.kr/auth/kakao")

            self.assertEqual(400, raised.exception.status_code)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_oauth_app_redirect_uses_one_time_app_ticket_without_session_token(self):
        from urllib.parse import parse_qs, urlparse

        from backend.core import oauth_login

        self._replace(oauth_login, "login_oauth_code", lambda **kwargs: {
            "session_token": "secret-session-token",
            "token_type": "bearer",
            "user": {"id": "user-1"},
        })

        redirect_url = oauth_login.create_oauth_app_redirect(
            provider="kakao",
            code="provider-code",
            state="state-123",
        )
        parsed = urlparse(redirect_url)
        query = parse_qs(parsed.query)

        self.assertEqual("com.mariocrat.stockanalyze", parsed.scheme)
        self.assertEqual("oauth", parsed.netloc)
        self.assertEqual("/kakao", parsed.path)
        self.assertEqual(["state-123"], query.get("state"))
        self.assertNotIn("secret-session-token", redirect_url)

        session = oauth_login.consume_oauth_app_ticket(query["ticket"][0])
        self.assertEqual("secret-session-token", session["session_token"])
        with self.assertRaises(HTTPException) as replay:
            oauth_login.consume_oauth_app_ticket(query["ticket"][0])
        self.assertEqual(401, replay.exception.status_code)

        configured = "com.mariocrat.stockanalyze"
        marker = oauth_login.OAUTH_APP_SCHEME_STATE_MARKER
        with patch.dict(os.environ, {"ALPHAMATE_OAUTH_APP_SCHEME": configured}):
            with self.subTest(case="explicit release marker with current app scheme"):
                state = "state-release|stockboda-app-scheme=com.mariocrat.stockanalyze"
                error_url = oauth_login.create_oauth_app_error_redirect(provider="kakao", state=state)
                error_redirect = urlparse(error_url)
                self.assertEqual(configured, error_redirect.scheme)
                self.assertEqual("oauth", error_redirect.netloc)
                self.assertEqual("/kakao", error_redirect.path)
                self.assertEqual([state], parse_qs(error_redirect.query)["state"])
            for rejected_scheme in ("evilapp", "https", "javascript", "attacker.custom.scheme"):
                with self.subTest(rejected_scheme=rejected_scheme):
                    state = f"state-rejected{marker}{rejected_scheme}"
                    error_url = oauth_login.create_oauth_app_error_redirect(provider="kakao", state=state)
                    error_redirect = urlparse(error_url)
                    self.assertEqual(configured, error_redirect.scheme)
                    self.assertEqual("oauth", error_redirect.netloc)
                    self.assertEqual("/kakao", error_redirect.path)
                    self.assertEqual([state], parse_qs(error_redirect.query)["state"])

    def test_oauth_config_status_reports_missing_server_settings(self):
        for key in ("KAKAO_CLIENT_ID", "KAKAO_REDIRECT_URI", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "NAVER_REDIRECT_URI"):
            os.environ.pop(key, None)

        from backend.core import oauth_login

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
        os.environ.pop("KAKAO_REDIRECT_URI", None)
        os.environ["NAVER_CLIENT_ID"] = "naver-client-id"
        os.environ["NAVER_CLIENT_SECRET"] = "naver-client-secret"
        os.environ.pop("NAVER_REDIRECT_URI", None)

        from backend.core import oauth_login

        status = oauth_login.get_oauth_config_status()

        self.assertTrue(status["providers"]["kakao"]["server_ready"])
        self.assertEqual([], status["providers"]["kakao"]["missing_server_settings"])
        self.assertTrue(status["providers"]["naver"]["server_ready"])
        self.assertEqual([], status["providers"]["naver"]["missing_server_settings"])

    def test_oauth_config_status_rejects_placeholder_redirect_uris(self):
        keys = (
            "KAKAO_CLIENT_ID",
            "KAKAO_REDIRECT_URI",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
            "NAVER_REDIRECT_URI",
        )
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["KAKAO_CLIENT_ID"] = "kakao-client-id"
            os.environ["KAKAO_REDIRECT_URI"] = "https://your-api.example.com/api/auth/kakao/callback"
            os.environ["NAVER_CLIENT_ID"] = "naver-client-id"
            os.environ["NAVER_CLIENT_SECRET"] = "naver-client-secret"
            os.environ["NAVER_REDIRECT_URI"] = "https://your-api.example.com/api/auth/naver/callback"

            from backend.core import oauth_login

            status = oauth_login.get_oauth_config_status()

            self.assertFalse(status["providers"]["kakao"]["server_ready"])
            self.assertIn(
                "KAKAO_REDIRECT_URI_PLACEHOLDER",
                status["providers"]["kakao"]["missing_server_settings"],
            )
            self.assertFalse(status["providers"]["naver"]["server_ready"])
            self.assertIn(
                "NAVER_REDIRECT_URI_PLACEHOLDER",
                status["providers"]["naver"]["missing_server_settings"],
            )
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_oauth_config_status_rejects_invalid_or_local_redirect_uris(self):
        keys = (
            "KAKAO_CLIENT_ID",
            "KAKAO_REDIRECT_URI",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
            "NAVER_REDIRECT_URI",
        )
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["KAKAO_CLIENT_ID"] = "kakao-client-id"
            os.environ["KAKAO_REDIRECT_URI"] = "not-a-url"
            os.environ["NAVER_CLIENT_ID"] = "naver-client-id"
            os.environ["NAVER_CLIENT_SECRET"] = "naver-client-secret"
            os.environ["NAVER_REDIRECT_URI"] = "http://localhost:5174/oauth/naver"

            from backend.core import oauth_login

            status = oauth_login.get_oauth_config_status()

            self.assertFalse(status["providers"]["kakao"]["server_ready"])
            self.assertIn(
                "KAKAO_REDIRECT_URI_INVALID",
                status["providers"]["kakao"]["missing_server_settings"],
            )
            self.assertFalse(status["providers"]["naver"]["server_ready"])
            self.assertIn(
                "NAVER_REDIRECT_URI_LOCALHOST",
                status["providers"]["naver"]["missing_server_settings"],
            )
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
