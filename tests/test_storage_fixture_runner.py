"""Coordinator checks; never import the storage target modules here."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.module_isolation import sanitized_environment
from tests.run_isolated_tests import REPOSITORY, run_module


STORAGE_MODULES = (
    "tests.test_account_store",
    "tests.test_access_control_persistence",
    "tests.test_user_journal_storage",
    "tests.test_review_history",
    "tests.test_event_log",
    "tests.test_me_data_routes",
    "tests.test_admin_event_routes",
    "tests.test_billing_rate_limits",
)


class StorageFixtureRunnerTest(unittest.TestCase):
    def test_direct_import_fails_before_storage_dependencies_or_files(self):
        # Forged test env alone must not substitute for the actual A1 boundary.
        with tempfile.TemporaryDirectory(prefix="storage-direct-probe-") as directory:
            container = Path(directory).resolve()
            root = container / "runtime"
            env = sanitized_environment(os.environ, root)
            for module in STORAGE_MODULES:
                with self.subTest(module=module):
                    code = f'''
import importlib, sys
sys.path.insert(0, {str(REPOSITORY)!r})
try:
    importlib.import_module({module!r})
except RuntimeError as error:
    assert str(error) == "isolation is not installed"
else:
    raise AssertionError("unguarded module import succeeded")
assert not any(name in sys.modules for name in (
    "backend.core.account_store", "backend.core.access_control",
    "backend.core.journal", "backend.core.review_history", "backend.core.event_log",
    "main", "backend.main"))
'''
                    result = subprocess.run([sys.executable, "-I", "-B", "-c", code],
                                            cwd=container, env=env, capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual([], list(container.iterdir()))
        self.assertFalse(container.exists())

    def test_focused_fixture_regression_in_sanitized_child(self):
        host = dict(os.environ)
        host["STORAGE_HOST_SENTINEL"] = "synthetic"
        report = run_module("tests.test_storage_fixture", host=host)
        self.assertTrue(report["passed"], report)
        self.assertEqual(4, report["tests"])
        self.assertEqual(0, report["unexpected"])
        self.assertTrue(report["restored"])
        self.assertTrue(report["patches_restored"])
        self.assertTrue(report["cleanup"])
        self.assertFalse(Path(report["root"]).parent.exists())
