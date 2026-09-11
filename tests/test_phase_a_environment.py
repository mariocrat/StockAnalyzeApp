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


class PhaseAHarnessTest(unittest.TestCase):
    def test_external_socket_audit_events_are_blocked(self):
        # Emit the CPython audit events directly: no DNS query or packet is sent.
        events = (
            ("socket.connect", (None, ("192.0.2.1", 443))),
            ("socket.getaddrinfo", ("provider.invalid", 443, 0, 0, 0)),
            ("socket.gethostbyname", ("provider.invalid",)),
            ("socket.gethostbyaddr", ("192.0.2.1",)),
            ("socket.getnameinfo", (("192.0.2.1", 443), 0)),
            ("socket.sendto", (None, ("192.0.2.1", 443))),
            ("socket.sendmsg", (None, ("192.0.2.1", 443))),
        )
        with isolated_runtime():
            for event, args in events:
                with self.subTest(event=event), self.assertRaisesRegex(AssertionError, event):
                    sys.audit(event, *args)

    def test_socketpair_works_but_arbitrary_loopback_is_blocked(self):
        with isolated_runtime():
            with ExitStack() as stack:
                left, right = socket.socketpair()
                stack.callback(left.close)
                stack.callback(right.close)
                left.sendall(b"internal")
                self.assertEqual(right.recv(8), b"internal")
            for host in ("127.0.0.1", "127.0.0.2", "::1"):
                for event in ("socket.connect", "socket.bind", "socket.sendto"):
                    with self.subTest(host=host, event=event), self.assertRaises(AssertionError):
                        sys.audit(event, None, (host, 12345))
    def test_event_loop_and_asgi_messages(self):
        async def exercise():
            from fastapi import FastAPI
            app = FastAPI()
            @app.get("/fixture")
            async def fixture():
                return {"isolated": True}
            messages = []
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            async def send(message):
                messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http", "path": "/fixture", "query_string": b"", "headers": [], "server": ("test", 80), "client": ("127.0.0.1", 1), "root_path": ""}, receive, send)
            self.assertEqual(messages[0]["status"], 200)
            self.assertEqual(json.loads(messages[1]["body"]), {"isolated": True})
        with isolated_runtime():
            asyncio.run(exercise())

    def test_outbound_dns_http_and_non_temp_database_are_blocked(self):
        with isolated_runtime() as root:
            with self.assertRaisesRegex(AssertionError, "external"):
                socket.getaddrinfo("provider.invalid", 443)
            with socket.socket() as outbound:
                with self.assertRaisesRegex(AssertionError, "external"):
                    outbound.connect(("192.0.2.1", 443))
            import requests
            from curl_cffi import requests as curl_requests
            for transport in (requests, curl_requests):
                with self.assertRaisesRegex(AssertionError, "network blocked"):
                    transport.get("https://provider.invalid")
            with self.assertRaisesRegex(AssertionError, "outside temporary root"):
                sqlite3.connect(root.parent / "blocked-synthetic.sqlite3")
            with self.assertRaisesRegex(AssertionError, "outside temporary root"):
                (root.parent / "blocked-synthetic.txt").write_text("blocked", encoding="utf-8")
            with closing(sqlite3.connect(root / "allowed.sqlite3")) as connection:
                self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))

    def test_environment_is_restored(self):
        previous = dict(os.environ)
        previous_tempdir = tempfile.tempdir
        previous_socketpair = socket.socketpair
        with isolated_runtime():
            os.environ["PHASE_A_SYNTHETIC"] = "temporary"
        self.assertEqual(dict(os.environ), previous)
        self.assertEqual(tempfile.tempdir, previous_tempdir)
        self.assertIs(socket.socketpair, previous_socketpair)


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


class PhaseAEnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = self.stack.enter_context(isolated_runtime())

    def test_environment_values_and_normalization(self):
        for value in ("development", "test", "production", " TEST ", "PRODUCTION"):
            with self.subTest(value=value), patch.dict(os.environ, ALPHAMATE_ENV=value):
                self.assertEqual(env.runtime_environment().value, value.strip().lower())

    def test_missing_empty_unknown_never_fall_back(self):
        for value in (None, "", " ", "dev", "prod", "produciton", "SYNTHETIC_SECRET"):
            with self.subTest(value=value), patch.dict(os.environ):
                if value is None:
                    os.environ.pop("ALPHAMATE_ENV")
                else:
                    os.environ["ALPHAMATE_ENV"] = value
                for function in (env.runtime_environment, env.dev_access_enabled, env.validate_configuration):
                    with self.assertRaises(env.ConfigurationError) as caught:
                        function()
                    self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    def test_test_dev_access_requires_complete_isolation(self):
        with patch.dict(os.environ, ALPHAMATE_ALLOW_DEV_ACCESS="true"):
            for missing in ("ALPHAMATE_TEST_ROOT", "ALPHAMATE_JOURNAL_DB_PATH", "ALPHAMATE_CACHE_DIR"):
                with self.subTest(missing=missing), patch.dict(os.environ):
                    os.environ.pop(missing)
                    with self.assertRaises(env.ConfigurationError):
                        env.dev_access_enabled()

    @unittest.skipUnless(os.name == "nt", "Windows drive-relative path contract")
    def test_drive_relative_paths_cannot_depend_on_drive_cwd(self):
        with patch.dict(os.environ, ALPHAMATE_ENV_FILE="C:synthetic.env"), patch.object(Path, "read_text") as read:
            with self.assertRaises(env.ConfigurationError):
                env.env_value("ALPHAMATE_ENV")
            read.assert_not_called()
        with patch.dict(os.environ, ALPHAMATE_ENV="development", ALPHAMATE_JOURNAL_DB_PATH="C:synthetic.sqlite3"):
            with self.assertRaises(env.ConfigurationError):
                env.validate_configuration()

    def test_dev_access_matrix(self):
        for environment in ("development", "test", "production"):
            for flag in (None, "", "false", "true", "typo"):
                with self.subTest(environment=environment, flag=flag), patch.dict(os.environ, ALPHAMATE_ENV=environment):
                    if flag is None:
                        os.environ.pop("ALPHAMATE_ALLOW_DEV_ACCESS", None)
                    else:
                        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = flag
                    if flag == "typo" or (environment == "production" and flag == "true"):
                        with self.assertRaises(env.ConfigurationError):
                            env.validate_configuration()
                        with self.assertRaises(env.ConfigurationError):
                            env.dev_access_enabled()
                    else:
                        self.assertEqual(env.dev_access_enabled(), flag == "true")

    def test_selected_file_is_exclusive_for_all_database_modules(self):
        settings = {key: value for key, value in os.environ.items() if key.startswith("ALPHAMATE_")}
        settings["ALPHAMATE_TEST_ROOT"] = str(self.root)
        selected = self.root / "selected.env"
        selected.write_text("\n".join(f'{key}="{value}"' for key, value in settings.items()), encoding="utf-8")
        with patch.dict(os.environ, ALPHAMATE_ENV_FILE=str(selected), ALPHAMATE_ENV="invalid", OPENAI_API_KEY="SYNTHETIC_PROCESS_VALUE"):
            for key in env.DB_FILES:
                os.environ[key] = str(self.root / "process-only" / env.DB_FILES[key])
            self.assertEqual(env.runtime_environment(), env.Environment.TEST)
            self.assertEqual(env.env_value("OPENAI_API_KEY"), "")
            for module, function, key in (
                ("account_store", "_account_db_path", "ALPHAMATE_ACCOUNT_DB_PATH"),
                ("access_control", "_access_db_path", "ALPHAMATE_ACCESS_DB_PATH"),
                ("journal", "_db_path", "ALPHAMATE_JOURNAL_DB_PATH"),
                ("review_history", "_db_path", "ALPHAMATE_REVIEW_HISTORY_DB_PATH"),
                ("event_log", "event_log_db_path", "ALPHAMATE_EVENT_LOG_DB_PATH"),
            ):
                loaded = importlib.import_module(f"backend.core.{module}")
                self.assertEqual(getattr(loaded, function)(), Path(settings[key]))
                connect = "_connect_access_db" if module == "access_control" else "_connect"
                with closing(getattr(loaded, connect)()):
                    pass
                self.assertTrue(Path(settings[key]).is_file())
            self.assertFalse((self.root / "process-only").exists())
            selected.write_text("ALPHAMATE_ENV=test\n", encoding="utf-8")
            with self.assertRaises(env.ConfigurationError):
                env.validate_configuration()

    def test_bad_selected_files_fail_without_values_in_exception(self):
        for name in ("", str(self.root / "SYNTHETIC_SECRET"), str(self.root)):
            with self.subTest(name=bool(name)), patch.dict(os.environ, ALPHAMATE_ENV_FILE=name):
                with self.assertRaises(env.ConfigurationError) as caught:
                    env.validate_configuration()
                self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))
        with patch.dict(os.environ, ALPHAMATE_ENV_FILE=str(self.root / "file")), patch.object(Path, "read_text", side_effect=PermissionError("SYNTHETIC_SECRET")):
            with self.assertRaises(env.ConfigurationError) as caught:
                env.env_value("ALPHAMATE_ENV")
            self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    def test_cwd_does_not_choose_env_or_storage(self):
        selected = self.root / "chosen.env"
        selected.write_text("ALPHAMATE_ENV=development\nALPHAMATE_JOURNAL_DB_PATH=relative/trades.sqlite3\n", encoding="utf-8")
        (self.root / ".env").write_text("ALPHAMATE_ENV=production\n", encoding="utf-8")
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        with patch.dict(os.environ, ALPHAMATE_ENV_FILE=str(selected)):
            expected = env.validate_configuration()
            for cwd in (env.REPOSITORY_ROOT, env.BACKEND_ROOT, self.root):
                os.chdir(cwd)
                self.assertEqual(env.validate_configuration(), expected)
                self.assertEqual(expected["ALPHAMATE_JOURNAL_DB_PATH"], env.REPOSITORY_ROOT / "relative" / "trades.sqlite3")
        # A synthetic repository root exercises a relative selection without
        # computing a relative path between Windows volumes.
        with patch.object(env, "REPOSITORY_ROOT", self.root), patch.dict(os.environ, ALPHAMATE_ENV_FILE="chosen.env"):
            expected = env.validate_configuration()
            for cwd in (env.BACKEND_ROOT, self.root):
                os.chdir(cwd)
                self.assertEqual(env.validate_configuration(), expected)
        with patch.dict(os.environ):
            os.environ.pop("ALPHAMATE_ENV", None)
            with self.assertRaises(env.ConfigurationError):
                env.runtime_environment()

    def test_environment_defaults_preserve_production_and_separate_development(self):
        for environment, suffix in (("production", ""), ("development", "development")):
            with patch.dict(os.environ, {"ALPHAMATE_ENV": environment}, clear=True):
                paths = env.validate_configuration()
                for name, filename in env.DB_FILES.items():
                    self.assertEqual(paths[name], env.BACKEND_ROOT / "data" / suffix / filename)
        self.assertFalse((self.root / "accounts.sqlite3").exists())

    def test_test_paths_require_explicit_values_and_reject_escape_collision(self):
        for name in (*env.DB_FILES, "ALPHAMATE_CACHE_DIR", "ALPHAMATE_TEST_ROOT"):
            with self.subTest(missing=name), patch.dict(os.environ):
                os.environ.pop(name)
                with self.assertRaises(env.ConfigurationError):
                    env.validate_configuration()
        for key, value in (
            ("ALPHAMATE_JOURNAL_DB_PATH", str(self.root / ".." / "outside.sqlite3")),
            ("ALPHAMATE_JOURNAL_DB_PATH", os.environ["ALPHAMATE_ACCOUNT_DB_PATH"]),
            ("ALPHAMATE_CACHE_DIR", os.environ["ALPHAMATE_ACCOUNT_DB_PATH"]),
            ("ALPHAMATE_TEST_ROOT", str(env.REPOSITORY_ROOT)),
        ):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(env.ConfigurationError):
                    env.validate_configuration()

    def test_invalid_configuration_cannot_open_any_database(self):
        with patch.dict(os.environ, ALPHAMATE_ENV="invalid"), patch.object(sqlite3, "connect") as connect, patch.object(Path, "mkdir") as mkdir:
            for module, function in (("account_store", "_connect"), ("access_control", "_connect_access_db"), ("journal", "_connect"), ("review_history", "_connect"), ("event_log", "_connect")):
                loaded = importlib.import_module(f"backend.core.{module}")
                # The repository supports both core.* and backend.core.* imports.
                # Assert the exact error class used by this module's resolver.
                configuration_error = importlib.import_module(loaded.database_path.__module__).ConfigurationError
                with self.assertRaises(configuration_error):
                    getattr(loaded, function)()
            connect.assert_not_called()
            mkdir.assert_not_called()


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
