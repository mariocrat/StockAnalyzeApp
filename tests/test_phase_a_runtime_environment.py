"""H4-D Harness/Environment only; Application and OAuth remain deferred."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

BOUNDARY = require_storage_boundary()

import asyncio
import encodings.utf_8_sig
import importlib
import json
import os
import sqlite3
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import requests
from curl_cffi import requests as curl_requests
from backend.core import env
from tests import phase_a_isolation as phase
from tests.phase_a_isolation import isolated_runtime as _legacy_runtime

# Import real store dependencies under A1 and a disposable storage environment.
# No application/main import, reload or lifespan is needed by these 16 cases.
with storage_fixture():
    _STORES = tuple(importlib.import_module("backend.core." + name) for name in
                    ("account_store", "access_control", "journal", "review_history", "event_log"))
    for _name in ("fastapi.middleware.asyncexitstack", "starlette.middleware.errors",
                  "starlette.middleware.exceptions"):
        importlib.import_module(_name)


@contextmanager
def isolated_runtime():
    """Keep the original Phase A guards, with testcase-owned HOME/config paths."""
    with _legacy_runtime() as root:
        values = {"HOME": str(root), "USERPROFILE": str(root),
                  "APPDATA": str(root / "config"), "LOCALAPPDATA": str(root / "config")}
        with patch.dict(os.environ, values):
            assert Path.home() == root
            assert root.is_relative_to(BOUNDARY.root)
            previous_cwd = Path.cwd()
            try:
                yield root
            finally:
                # Release Windows' current-directory handle before temp removal.
                os.chdir(previous_cwd)


class _OwnedCase:
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
        modules = dict(sys.modules)
        # Restore parent-package attributes as well as module membership.
        managed = [module for module in modules.values()
                   if isinstance(module, ModuleType) and
                   ("__path__" in vars(module) or module in (*_STORES, env, phase))]
        namespaces = [(module, dict(vars(module))) for module in managed]
        own_namespace = dict(vars(sys.modules[__name__]))
        policy = asyncio.events._event_loop_policy
        guards = (phase._active_root, phase._socketpair_setup.get(),
                  socket.socketpair, sqlite3.connect, requests.sessions.Session.request,
                  curl_requests.Session.request)
        count = BOUNDARY.unexpected
        self.addCleanup(self._assert_restored, baseline, modules, namespaces,
                        own_namespace, policy, guards, count)
        stack = self.enterContext(ExitStack())
        fixture = stack.enter_context(storage_fixture())
        self._case_container = fixture.root.parent
        stack.enter_context(patch.object(sys, "path", list(sys.path)))
        stack.enter_context(patch.dict(sys.modules))
        for module, _ in namespaces:
            stack.enter_context(patch.dict(vars(module)))
        stack.enter_context(patch.object(asyncio.events, "_event_loop_policy",
                                        asyncio.DefaultEventLoopPolicy()))

    def _assert_restored(self, baseline, modules, namespaces, own_namespace,
                         policy, guards, count):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path)), baseline)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is value for name, value in modules.items()))
        for module, before in namespaces:
            after = vars(module)
            self.assertEqual(set(after), set(before), module.__name__)
            self.assertTrue(all(after[name] is value for name, value in before.items()), module.__name__)
        after = vars(sys.modules[__name__])
        self.assertEqual(set(after), set(own_namespace))
        self.assertTrue(all(after[name] is value for name, value in own_namespace.items()))
        self.assertIs(asyncio.events._event_loop_policy, policy)
        self.assertEqual((phase._active_root, phase._socketpair_setup.get(),
                          socket.socketpair, sqlite3.connect, requests.sessions.Session.request,
                          curl_requests.Session.request), guards)
        self.assertEqual(BOUNDARY.unexpected, count)
        container = self.__dict__.pop("_case_container", None)
        if container is not None:
            self.assertFalse(container.exists())

    def _check_failure_cleanup(self):
        # Exercise the same case setup/cleanup, not a substitute fixture.
        for outcome in ("success", "assertion", "setup"):
            roots = []
            connections = []

            class Probe(_OwnedCase, unittest.TestCase):
                def setUp(case):
                    super().setUp()
                    roots.append(case._case_container)
                    root = case.enterContext(isolated_runtime())
                    case.enterContext(patch.dict(env.__dict__))
                    case.enterContext(patch.dict(phase.__dict__))
                    env._phase_synthetic = outcome
                    phase._phase_synthetic = outcome
                    sys.path.append(str(root / "synthetic-import-path"))
                    sys.modules["phase_synthetic_module"] = ModuleType("phase_synthetic_module")
                    os.environ["PHASE_SYNTHETIC"] = outcome
                    os.chdir(root)
                    connection = case.enterContext(closing(sqlite3.connect(root / "synthetic.sqlite3")))
                    connections.append(connection)
                    connection.execute("CREATE TABLE owned(value INTEGER)")
                    connection.commit()
                    (root / "cache").mkdir()
                    (root / "cache" / "synthetic").write_text("synthetic", encoding="utf-8")
                    (Path.home() / "synthetic-home").write_text("synthetic", encoding="utf-8")
                    if outcome == "setup":
                        raise RuntimeError("synthetic setup failure")

                def runTest(case):
                    if outcome == "assertion":
                        case.fail("synthetic assertion failure")

            result = unittest.TestResult()
            Probe().run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), int(outcome == "assertion"), result.failures)
            self.assertEqual(len(result.errors), int(outcome == "setup"), result.errors)
            self.assertTrue(all(not root.exists() for root in roots))
            for connection in connections:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")

class PhaseAHarnessTest(_OwnedCase, unittest.TestCase):
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
                with self.subTest(event=event), BOUNDARY.expect_violation("network"), self.assertRaisesRegex(AssertionError, event):
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
                    with self.subTest(host=host, event=event), BOUNDARY.expect_violation("network"), self.assertRaises(AssertionError):
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
            with BOUNDARY.expect_violation("network"), self.assertRaisesRegex(AssertionError, "external"):
                socket.getaddrinfo("provider.invalid", 443)
            with socket.socket() as outbound:
                with BOUNDARY.expect_violation("network"), self.assertRaisesRegex(AssertionError, "external"):
                    outbound.connect(("192.0.2.1", 443))
            import requests
            from curl_cffi import requests as curl_requests
            for transport in (requests, curl_requests):
                with BOUNDARY.expect_violation("network"), self.assertRaisesRegex(AssertionError, "network blocked"):
                    transport.get("https://provider.invalid")
            with BOUNDARY.expect_violation("write"), self.assertRaisesRegex(AssertionError, "outside temporary root"):
                sqlite3.connect(root.parent / "blocked-synthetic.sqlite3")
            with BOUNDARY.expect_violation("write"), self.assertRaisesRegex(AssertionError, "outside temporary root"):
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
        self._check_failure_cleanup()


class PhaseAEnvironmentTest(_OwnedCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
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


if __name__ == "__main__":
    unittest.main()
