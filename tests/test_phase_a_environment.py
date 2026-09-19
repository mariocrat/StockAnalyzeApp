import asyncio
import importlib
import json
import os
import sqlite3
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from backend.core import env
from tests.phase_a_isolation import isolated_runtime




class PhaseAOAuthCleanupTest(unittest.TestCase):
    def test_oauth_mocks_restore_in_both_orders(self):
        from tests.test_oauth_login import OAuthLoginTest
        names = (
            "test_oauth_request_timeout_setting_is_capped",
            "test_oauth_app_redirect_uses_one_time_app_ticket_without_session_token",
            "test_kakao_access_token_profile_creates_alphamate_session",
            "test_naver_access_token_profile_creates_alphamate_session",
            "test_kakao_authorization_code_is_exchanged_before_login",
            "test_naver_authorization_code_is_exchanged_before_login",
        )
        for order in (names, tuple(reversed(names))):
            with isolated_runtime():
                from backend.core import oauth_login
                targets = ((oauth_login.requests, "get"), (oauth_login.requests, "post"), (oauth_login, "_request_json"), (oauth_login, "_exchange_json"), (oauth_login, "login_oauth_code"))
                originals = [getattr(target, name) for target, name in targets]
                environment = dict(os.environ)
                temporary = tempfile.tempdir
                for name in order:
                    with self.subTest(test=name, reversed=order != names):
                        result = unittest.TestResult()
                        OAuthLoginTest(name).run(result)
                        self.assertEqual(result.testsRun, 1)
                        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
                        for (target, attribute), original in zip(targets, originals):
                            self.assertIs(getattr(target, attribute), original)
                        self.assertEqual(dict(os.environ), environment)
                        self.assertEqual(tempfile.tempdir, temporary)

    def test_oauth_cleanup_runs_after_an_assertion_failure(self):
        from tests.test_oauth_login import OAuthLoginTest
        with isolated_runtime():
            import requests
            original = requests.get
            environment = dict(os.environ)
            class FailingProbe(OAuthLoginTest):
                def runTest(self):
                    self._replace(requests, "get", lambda *args: None)
                    os.environ["SYNTHETIC_FAILURE"] = "temporary"
                    self.fail("expected synthetic failure to exercise addCleanup")
            result = unittest.TestResult()
            FailingProbe().run(result)
            self.assertEqual(len(result.failures), 1)
            self.assertEqual(result.errors, [])
            self.assertIs(requests.get, original)
            self.assertEqual(dict(os.environ), environment)




class PhaseAApplicationTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = self.stack.enter_context(isolated_runtime())
        self.stack.enter_context(patch.object(sys, "path", [str(env.BACKEND_ROOT), *sys.path]))
        self.main = importlib.import_module("main")

    def test_invalid_import_precedes_application_imports_and_persistent_effects(self):
        import threading
        source = (env.BACKEND_ROOT / "main.py").read_text(encoding="utf-8")
        for values in (
            {"ALPHAMATE_ENV": "invalid"}, {"ALPHAMATE_ENV": ""}, {"ALPHAMATE_ENV": None},
            {"ALPHAMATE_ENV": "production", "ALPHAMATE_ALLOW_DEV_ACCESS": "true"},
            {"ALPHAMATE_JOURNAL_DB_PATH": str(self.root / ".." / "outside.sqlite3")},
            {"ALPHAMATE_CACHE_DIR": os.environ["ALPHAMATE_JOURNAL_DB_PATH"]},
            {"ALPHAMATE_ENV_FILE": str(self.root / "missing.env")},
        ):
            values = dict(values)
            missing_environment = values.get("ALPHAMATE_ENV", "present") is None
            if missing_environment:
                values.pop("ALPHAMATE_ENV")
            with patch.dict(os.environ, values), patch.object(sqlite3, "connect") as connect, patch.object(Path, "mkdir") as mkdir, patch.object(threading.Thread, "start") as start:
                if missing_environment:
                    os.environ.pop("ALPHAMATE_ENV")
                with self.assertRaises(ValueError) as caught:
                    exec(compile(source, str(env.BACKEND_ROOT / "main.py"), "exec"), {"__name__": "phase_a_import_probe"})
                self.assertTrue(str(caught.exception))
                connect.assert_not_called()
                mkdir.assert_not_called()
                start.assert_not_called()

    def test_lifespan_validates_before_cache_and_background(self):
        import threading
        async def run():
            async with self.main.lifespan(self.main.app):
                self.fail("invalid lifespan entered")
        with patch.dict(os.environ, ALPHAMATE_ENV="invalid"), patch.object(self.main, "initialize_yfinance_cache") as cache, patch.object(threading.Thread, "start") as start, patch.object(sqlite3, "connect") as connect:
            with self.assertRaises(ValueError):
                asyncio.run(run())
            cache.assert_not_called()
            start.assert_not_called()
            connect.assert_not_called()

    def test_cache_import_is_pure_and_initialization_uses_test_root(self):
        from core import journal_chart, data_fetcher
        with patch.object(Path, "mkdir") as mkdir, patch.object(journal_chart.yf, "set_tz_cache_location") as location:
            importlib.reload(journal_chart)
            mkdir.assert_not_called()
            location.assert_not_called()
        with patch.object(journal_chart.yf, "set_tz_cache_location") as location:
            journal_chart.initialize_yfinance_cache()
            location.assert_called_once_with(str(self.root / "cache" / "yfinance"))
        self.assertEqual(data_fetcher._cache_dir(), self.root / "cache")

    def test_dev_login_and_default_token_require_opt_in(self):
        from core import account_store, access_control
        from fastapi import HTTPException
        for environment in ("development", "test", "production"):
            with patch.dict(os.environ, ALPHAMATE_ENV=environment):
                with self.assertRaises(HTTPException):
                    account_store.login_dev_provider(provider="kakao", provider_user_id="synthetic")
                with self.assertRaises(HTTPException):
                    access_control._authenticate("Bearer dev-token")
        for environment in ("development", "test"):
            with patch.dict(os.environ, ALPHAMATE_ENV=environment, ALPHAMATE_ALLOW_DEV_ACCESS="true"):
                session = account_store.login_dev_provider(provider="kakao", provider_user_id="synthetic")
                self.assertTrue(session["user"]["id"])
                self.assertEqual(access_control._authenticate("Bearer dev-token"), ("dev-user", "dev"))

    async def _request(self, method, path, payload=None, token=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        headers = [(b"content-type", b"application/json")]
        if token:
            headers.append((b"authorization", f"Bearer {token}".encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "", "headers": headers, "client": ("127.0.0.1", 1234), "server": ("test", 80)}
        messages = []
        consumed = False
        finished = asyncio.Event()
        async def receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": body, "more_body": False}
            await finished.wait()
            return {"type": "http.disconnect"}
        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                finished.set()
        await self.main.app(scope, receive, send)
        status = next(message["status"] for message in messages if message["type"] == "http.response.start")
        raw = b"".join(message.get("body", b"") for message in messages)
        return status, json.loads(raw) if raw else None

    def request(self, *args, **kwargs):
        return asyncio.run(self._request(*args, **kwargs))

    def test_asgi_auth_failure_never_reaches_stored_journal(self):
        from core import account_store
        expired = account_store.login_provider_identity(provider="kakao", provider_user_id="expired")
        with closing(account_store._connect()) as conn:
            with conn:
                conn.execute("UPDATE user_sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
        payload = {"trade_date": "2026-01-01", "name": "Synthetic", "side": "buy", "price": 10, "quantity": 1}
        for environment in ("development", "test", "production"):
            with patch.dict(os.environ, ALPHAMATE_ENV=environment), patch("core.journal._connect", side_effect=AssertionError("journal must not open")):
                for token in (None, "invalid-synthetic-token", expired["session_token"]):
                    for method, path, body in (("GET", "/api/journal/trades", None), ("POST", "/api/journal/trades", payload), ("DELETE", "/api/journal/trades/1", None), ("DELETE", "/api/journal/trades", None), ("GET", "/api/journal/review", None), ("GET", "/api/journal/charts", None)):
                        with self.subTest(environment=environment, method=method, path=path, token=bool(token)):
                            status, _ = self.request(method, path, body, token)
                            self.assertEqual(status, 401)

    def test_asgi_ownership_and_storage_opt_in(self):
        from core import account_store
        sessions = [account_store.login_provider_identity(provider="kakao", provider_user_id=identity) for identity in ("synthetic-A", "synthetic-B")]
        tokens = [session["session_token"] for session in sessions]
        payload = {"trade_date": "2026-01-01", "name": "Synthetic", "side": "buy", "price": 10, "quantity": 1}
        self.assertEqual(self.request("POST", "/api/journal/trades", payload, tokens[0])[0], 403)
        self.assertEqual(self.request("GET", "/api/journal/trades", token=tokens[0]), (200, []))
        for token in tokens:
            account_store.update_journal_storage_setting(authorization=f"Bearer {token}", enabled=True)
        rows = []
        for token in tokens:
            status, row = self.request("POST", "/api/journal/trades", payload, token)
            self.assertEqual(status, 200)
            rows.append(row)
        for index, token in enumerate(tokens):
            status, listed = self.request("GET", "/api/journal/trades", token=token)
            self.assertEqual(status, 200)
            self.assertEqual([row["id"] for row in listed], [rows[index]["id"]])
            status, review = self.request("GET", "/api/journal/review", token=token)
            self.assertEqual(status, 200)
            self.assertEqual(review["summary"]["trade_count"], 1)
            with patch.object(self.main, "build_journal_charts", return_value={"synthetic": True}) as charts:
                self.assertEqual(self.request("GET", "/api/journal/charts", token=token)[0], 200)
                self.assertEqual([row["id"] for row in charts.call_args.args[0]], [rows[index]["id"]])
        account_store.update_journal_storage_setting(authorization=f"Bearer {tokens[0]}", enabled=False)
        self.assertEqual(self.request("GET", "/api/journal/review", token=tokens[0])[1]["summary"]["trade_count"], 0)
        with patch.object(self.main, "build_journal_charts", return_value={}) as charts:
            self.assertEqual(self.request("GET", "/api/journal/charts", token=tokens[0])[0], 200)
            charts.assert_called_once_with([])
        self.assertEqual(self.request("DELETE", f'/api/journal/trades/{rows[1]["id"]}', token=tokens[0])[1]["deleted_count"], 0)
        self.assertEqual(self.request("DELETE", "/api/journal/trades", token=tokens[0])[1]["deleted_count"], 1)
        self.assertEqual(len(self.request("GET", "/api/journal/trades", token=tokens[1])[1]), 1)

    def test_once_analysis_does_not_access_stored_journal(self):
        with patch("core.journal._connect", side_effect=AssertionError("journal must not open")):
            self.assertEqual(self.request("POST", "/api/journal/review-once", {"trades": []})[0], 200)
            self.assertEqual(self.request("POST", "/api/journal/charts-once", {"trades": []})[0], 200)
        self.assertEqual(self.request("GET", "/healthz")[0], 200)
        self.assertEqual(self.request("GET", "/api/healthz")[0], 200)

    def test_debug_callback_scheme_preserves_code_state_and_ticket_contract(self):
        from urllib.parse import parse_qs, urlparse
        from core import oauth_login
        session = {"session_token": "SYNTHETIC_SESSION", "user": {"id": "synthetic"}}
        configured = "com.mariocrat.stockanalyze"
        for environment in ("development", "test", "production"):
            with patch.dict(os.environ, ALPHAMATE_ENV=environment):
                for suffix, scheme in (("", configured), (f"|stockboda-app-scheme={configured}.debug", configured + ".debug"), ("|stockboda-app-scheme=unapproved", configured)):
                    state = "SYNTHETIC_STATE" + suffix
                    for provider in ("kakao", "naver"):
                        with patch.object(oauth_login, "login_oauth_code", return_value=session) as login:
                            url = oauth_login.create_oauth_app_redirect(provider=provider, code="SYNTHETIC_CODE", state=state)
                        login.assert_called_once_with(provider=provider, code="SYNTHETIC_CODE", redirect_uri="", state=state)
                        parsed = urlparse(url)
                        self.assertEqual(parsed.scheme, scheme)
                        query = parse_qs(parsed.query)
                        self.assertEqual(query["state"], [state])
                        self.assertNotIn("SYNTHETIC_SESSION", url)
                        self.assertEqual(oauth_login.consume_oauth_app_ticket(query["ticket"][0]), session)
                        error = oauth_login.create_oauth_app_error_redirect(provider=provider, state=state)
                        self.assertEqual(urlparse(error).scheme, scheme)

    def test_missing_oauth_configuration_does_not_create_stored_identity(self):
        from core import oauth_login
        from fastapi import HTTPException
        for environment in ("development", "test", "production"):
            with patch.dict(os.environ, ALPHAMATE_ENV=environment), patch.object(oauth_login, "login_provider_identity") as login, patch.object(sqlite3, "connect") as connect:
                with self.assertRaises(HTTPException) as caught:
                    oauth_login.login_oauth_code(provider="kakao", code="synthetic", redirect_uri="https://synthetic.invalid/callback")
                self.assertEqual(caught.exception.status_code, 503)
                login.assert_not_called()
                connect.assert_not_called()
