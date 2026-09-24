"""Synthetic child target. Import itself proves bootstrap ordering."""

import os
from contextlib import closing
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import unittest

from backend.core.env import DB_FILES, REPOSITORY_ROOT, validate_configuration
from tests.module_isolation import current_boundary

BOUNDARY = current_boundary()  # This must fail if a coordinator imports this module.
ROOT = BOUNDARY.root
assert os.environ["ALPHAMATE_ENV"] == "test"
assert Path.cwd() == ROOT
(ROOT / "import-proof").write_text("synthetic", encoding="utf-8")


class IsolationProbes(unittest.TestCase):
    def test_host_environment_is_removed_before_import(self):
        forbidden = {"OPENAI_API_KEY", "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS", "KAKAO_CLIENT_SECRET",
                     "ALPHAMATE_ENV_FILE", "ALPHAMATE_FRONTEND_ENV_FILE", "VITE_API_BASE_URL",
                     "RENDER_SERVICE_ID", "HTTPS_PROXY", "PYTHONPATH", "ARBITRARY_PROVIDER_SECRET"}
        self.assertFalse(forbidden & os.environ.keys())
        self.assertNotIn("SYNTHETIC_HOST_SECRET", os.environ.values())

    def test_all_db_cache_and_temp_paths_are_owned(self):
        paths = validate_configuration()
        self.assertEqual(len(DB_FILES), 5)
        self.assertEqual(len(paths), 6)
        self.assertTrue(all(path.is_relative_to(ROOT) for path in paths.values()))
        with closing(sqlite3.connect(paths["ALPHAMATE_ACCOUNT_DB_PATH"])) as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(Path(directory).is_relative_to(ROOT))
        self.assertEqual((ROOT / "import-proof").read_text(), "synthetic")

    def test_write_is_blocked_before_file_creation(self):
        outside = ROOT.parent / "synthetic-outside-write"
        with BOUNDARY.expect_violation("write"):
            outside.write_text("must never be written", encoding="utf-8")
        self.assertFalse(outside.exists())
        with BOUNDARY.expect_violation("write"):
            outside.unlink()
        with BOUNDARY.expect_violation("write"):
            outside.mkdir()
        inside = ROOT / "rename-source"
        inside.write_text("synthetic", encoding="utf-8")
        with BOUNDARY.expect_violation("write"):
            inside.rename(outside)
        self.assertTrue(inside.exists())
        self.assertFalse(outside.exists())

    def test_sensitive_reads_precede_open(self):
        # No real persistent file is touched: all paths are in the owned container,
        # outside its runtime root, and do not exist. An OS read would raise ENOENT.
        base = ROOT.parent / "synthetic-protected"
        for directory in (base / "production", base / "development", base / "cache"):
            BOUNDARY.protected.add_root(directory)
        private = base / "private-config"
        credential = base / "opaque-identity"
        BOUNDARY.protected.add_file(private)
        BOUNDARY.protected.add_file(credential)
        database = base / "configured-db"
        BOUNDARY.protected.add_database(database)
        targets = [base / "production" / "opaque", base / "development" / "opaque",
                   base / "cache" / "opaque", private, credential,
                   database, Path(str(database) + "-wal"), Path(str(database) + "-shm"),
                   Path(str(database) + "-journal"), base / "cache" / ".." / "private-config"]
        if os.name == "nt":
            targets.append(Path(str(private).upper().replace("\\", "/")))
        targets.append(Path("..") / "synthetic-protected" / "opaque-identity")
        for path in targets:
            with self.subTest(name=path.name), BOUNDARY.expect_violation("sensitive-read"):
                path.read_bytes()
        # Exact files must not become protected directories; adjacent prefixes are independent.
        self.assertFalse(BOUNDARY.protected.contains(Path(str(private) + "-neighbor")))
        self.assertFalse(BOUNDARY.protected.contains(private / "child"))
        self.assertFalse(BOUNDARY.protected.contains(base / "cache-neighbor" / "opaque"))
        # Unregistered names outside runtime are also ordinary reads (these do not exist).
        for name in (".env", "credential.json", "example.sqlite3", ".cache/opaque"):
            with self.assertRaises(FileNotFoundError):
                (ROOT.parent / "synthetic-unregistered" / name).read_bytes()

    def test_owned_sensitive_looking_files_are_allowed(self):
        # Owned root wins even over a registered ancestor.
        BOUNDARY.protected.add_root(ROOT.parent)
        try:
            for name in (".env", "accounts.sqlite3", "access.sqlite3", "credential.json",
                         ".cache/opaque", "service-account.json"):
                path = ROOT / "fixtures" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic", encoding="utf-8")
                self.assertEqual(path.read_text(), "synthetic")
        finally:
            BOUNDARY.protected.roots.remove(ROOT.parent)
        self.assertIn("class InMemoryRateLimiter", (REPOSITORY_ROOT / "backend/core/rate_limit.py").read_text())
        import contextlib
        self.assertTrue(Path(contextlib.__file__).read_bytes())

    def test_parent_path_metadata_without_application_env(self):
        # Coordinator supplies these nonexistent path-only fixtures via its host mapping.
        for name in ("ALPHAMATE_ENV_FILE", "ALPHAMATE_FRONTEND_ENV_FILE", "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE"):
            path = REPOSITORY_ROOT / "synthetic-never-opened" / name
            self.assertNotIn(name, os.environ)
            self.assertTrue(BOUNDARY.protected.contains(path))
            with BOUNDARY.expect_violation("sensitive-read"):
                path.read_bytes()

    def test_network_calls_never_reach_transport(self):
        import requests
        import urllib.request
        from curl_cffi import requests as curl_requests
        with socket.socket() as sock:
            for host in ("192.0.2.1", "127.0.0.1"):
                with BOUNDARY.expect_violation("network"):
                    sock.connect((host, 9))
        with BOUNDARY.expect_violation("network"):
            socket.getaddrinfo("synthetic.invalid", 9)
        with socket.socket(type=socket.SOCK_DGRAM) as sock:
            with BOUNDARY.expect_violation("network"):
                sock.sendto(b"synthetic", ("192.0.2.1", 9))
        for call in (requests.get, urllib.request.urlopen, curl_requests.get):
            with BOUNDARY.expect_violation("network"):
                call("https://synthetic.invalid/")
        with BOUNDARY.expect_violation("network"):
            sys.audit("socket.sendmsg", None, ("192.0.2.1", 9))

    def test_socketpair_owned_resources_are_closed(self):
        left, right = socket.socketpair()
        with left, right:
            left.sendall(b"synthetic")
            self.assertEqual(right.recv(9), b"synthetic")
        self.assertEqual(left.fileno(), -1)
        self.assertEqual(right.fileno(), -1)

    def test_unmatched_expectation_does_not_hide_violation(self):
        # An isolated ledger tests expectation semantics without acknowledging the active ledger.
        from tests.module_isolation import Boundary
        ledger = Boundary(ROOT)
        with self.assertRaises(AssertionError):
            with ledger.expect_violation("network"):
                ledger.deny("write")
        self.assertEqual(ledger.unexpected, 1)
        with self.assertRaises(AssertionError):
            with ledger.expect_violation("network"):
                pass
