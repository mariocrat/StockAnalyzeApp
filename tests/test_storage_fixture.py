from tests.storage_fixture import require_storage_boundary, storage_fixture

BOUNDARY = require_storage_boundary()

import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.core.env import DB_FILES


class StorageFixtureTest(unittest.TestCase):
    def test_consecutive_testcases_after_success_and_failures(self):
        baseline = dict(os.environ)
        cwd, temp = Path.cwd(), tempfile.tempdir
        target = SimpleNamespace(value="original")
        roots = []
        for outcome in ("success", "assertion", "exception", "setup"):
            with self.subTest(outcome=outcome):
                connections = []

                class Writer(unittest.TestCase):
                    def setUp(case):
                        storage = case.enterContext(storage_fixture())
                        roots.append(storage.root)
                        case.assertEqual("test", os.environ["ALPHAMATE_ENV"])
                        for key in DB_FILES:
                            conn = storage.connect(key)
                            connections.append(conn)
                            conn.execute("CREATE TABLE previous_case (value TEXT)")
                            conn.execute("INSERT INTO previous_case VALUES ('synthetic')")
                            conn.commit()
                        (storage.cache / "previous-cache").write_text("synthetic")
                        Path("previous-data").write_text("synthetic")
                        Path(tempfile.gettempdir(), "previous-temp").write_text("synthetic")
                        for key in ("TEMP", "TMP", "TMPDIR"):
                            env_temp = Path(os.environ[key])
                            case.assertEqual(storage.root.parent, env_temp)
                            (env_temp / ("previous-" + key)).write_text("synthetic")
                        os.environ["STORAGE_CASE_LEAK"] = "synthetic"
                        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"
                        os.environ.pop("HOME")
                        storage.patch_object(target, "value", "patched")
                        if outcome == "setup":
                            raise RuntimeError("synthetic setUp failure")

                    def runTest(case):
                        if outcome == "assertion":
                            case.fail("synthetic assertion failure")
                        if outcome == "exception":
                            raise RuntimeError("synthetic test exception")

                writer_result = unittest.TestResult()
                Writer().run(writer_result)
                self.assertEqual(1, writer_result.testsRun)
                self.assertEqual(int(outcome == "assertion"), len(writer_result.failures))
                self.assertEqual(int(outcome in ("setup", "exception")), len(writer_result.errors))

                class Reader(unittest.TestCase):
                    def setUp(case):
                        case.assertEqual(baseline, dict(os.environ))
                        case.assertEqual((cwd, temp), (Path.cwd(), tempfile.tempdir))
                        case.assertEqual("original", target.value)
                        case.assertTrue(all(not root.parent.exists() for root in roots))
                        for conn in connections:
                            with case.assertRaises(sqlite3.ProgrammingError):
                                conn.execute("SELECT 1")
                        case.storage = case.enterContext(storage_fixture())
                        case.assertNotIn(case.storage.root, roots)
                        roots.append(case.storage.root)

                    def runTest(case):
                        storage = case.storage
                        case.assertNotIn("STORAGE_CASE_LEAK", os.environ)
                        case.assertEqual("false", os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"])
                        case.assertEqual([], list(storage.cache.iterdir()))
                        case.assertEqual([], list(Path(tempfile.gettempdir()).iterdir()))
                        case.assertFalse(Path("previous-data").exists())
                        for key in ("TEMP", "TMP", "TMPDIR"):
                            env_temp = Path(os.environ[key])
                            case.assertEqual(storage.root.parent, env_temp)
                            case.assertFalse((env_temp / ("previous-" + key)).exists())
                        for key in DB_FILES:
                            path = storage.paths[key]
                            case.assertTrue(path.is_relative_to(storage.root))
                            case.assertFalse(path.exists())
                            conn = storage.connect(key)
                            case.assertEqual([], conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table'"
                            ).fetchall())

                reader_result = unittest.TestResult()
                Reader().run(reader_result)
                self.assertTrue(reader_result.wasSuccessful(), reader_result.errors + reader_result.failures)
                self.assertTrue(all(not root.parent.exists() for root in roots))
                self.assertEqual(baseline, dict(os.environ))

    def test_context_exception_restores_and_sanitizes_module_environment(self):
        # The runner's host sanitizer is separately exercised by the coordinator.
        self.assertNotIn("STORAGE_HOST_SENTINEL", os.environ)
        with patch.dict(os.environ, {"STORAGE_CASE_LEAK": "synthetic-module-setting"}):
            baseline = dict(os.environ)
            cwd, temp = Path.cwd(), tempfile.tempdir
            with self.assertRaisesRegex(RuntimeError, "synthetic body failure"):
                with storage_fixture() as storage:
                    root = storage.root
                    self.assertNotIn("STORAGE_CASE_LEAK", os.environ)
                    conn = storage.connect("ALPHAMATE_ACCOUNT_DB_PATH")
                    conn.execute("CREATE TABLE synthetic (id INTEGER)")
                    os.environ.clear()
                    raise RuntimeError("synthetic body failure")
            self.assertFalse(root.parent.exists())
            self.assertEqual(baseline, dict(os.environ))
            self.assertEqual((cwd, temp), (Path.cwd(), tempfile.tempdir))
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def test_rejects_isolation_overrides_before_allocating_storage(self):
        before = set((BOUNDARY.root / "temp").iterdir())
        for key in (*DB_FILES, "ALPHAMATE_ENV", "ALPHAMATE_TEST_ROOT",
                    "ALPHAMATE_CACHE_DIR", "ALPHAMATE_ENV_FILE", "TMPDIR", "HOME"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                with storage_fixture(**{key: "synthetic-invalid"}):
                    self.fail("invalid fixture entered")
        self.assertEqual(before, set((BOUNDARY.root / "temp").iterdir()))

    def test_rejects_invalid_active_environment_before_storage_creation(self):
        before = set((BOUNDARY.root / "temp").iterdir())
        # All negative paths are synthetic; the env-file gate runs before reading.
        cases = (
            {"ALPHAMATE_ENV": "development"},
            {"ALPHAMATE_ENV_FILE": str(BOUNDARY.root / "absent-config")},
            {"ALPHAMATE_TEST_ROOT": str(BOUNDARY.root.parent / "absent-root")},
            {"ALPHAMATE_ACCOUNT_DB_PATH": str(BOUNDARY.root.parent / "absent.sqlite3")},
        )
        for values in cases:
            with self.subTest(keys=list(values)), patch.dict(os.environ, values):
                with self.assertRaises((RuntimeError, ValueError)):
                    with storage_fixture():
                        self.fail("invalid fixture entered")
        self.assertEqual(before, set((BOUNDARY.root / "temp").iterdir()))
