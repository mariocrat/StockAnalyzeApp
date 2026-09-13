"""Synthetic failures for child and coordinator result handling, no real app imports."""
from contextlib import contextmanager, redirect_stderr
import io
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from backend.core import env
from tests import module_isolation as isolation
from tests import run_isolated_tests as runner


class ResultHandlingTest(unittest.TestCase):
    def execute(self, action=lambda case: None, context=None, bootstrap=None):
        module = types.ModuleType("tests.synthetic_result_target")
        module.Case = type("SyntheticCase", (unittest.TestCase,), {"test_body": action})
        original_import = runner.importlib.import_module

        def imported(name, *args, **kwargs):
            return module if name == module.__name__ else original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory(prefix="stockboda-result-probe-") as temp:
            root = Path(temp) / "runtime"
            with patch.object(runner.importlib, "import_module", side_effect=imported), redirect_stderr(io.StringIO()):
                if context:
                    with patch.object(runner, "isolated_module", context):
                        report = runner.execute_child(module.__name__, root, isolation.ProtectedPaths())
                elif bootstrap:
                    with patch.object(isolation, "install_network_patches", bootstrap):
                        report = runner.execute_child(module.__name__, root, isolation.ProtectedPaths())
                else:
                    report = runner.execute_child(module.__name__, root, isolation.ProtectedPaths())
        self.assertFalse(Path(temp).exists())
        self.assertTrue(report["restored"], report)
        self.assertTrue(report["patches_restored"], report)
        return report

    def test_bootstrap_violation_is_counted(self):
        result = self.execute(bootstrap=lambda stack, blocked: blocked())
        self.assertFalse(result["passed"])
        self.assertEqual(result["tests"], 0)
        self.assertEqual(result["unexpected"], 1)
        self.assertEqual(result["error_stage"], "bootstrap")

    def test_assertion_failure_is_not_an_isolation_violation(self):
        result = self.execute(action=lambda case: case.fail("synthetic assertion"))
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["violations"], 0)

    def test_runtime_violation_cannot_be_swallowed(self):
        def swallowed(case):
            try:
                isolation.current_boundary().deny("network")
            except isolation.IsolationViolation:
                pass
        result = self.execute(action=swallowed)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["unexpected"], 1)

    def test_cleanup_exception_after_restoration_fails(self):
        original = runner.isolated_module

        @contextmanager
        def cleanup_failure(*args, **kwargs):
            with original(*args, **kwargs) as boundary:
                yield boundary
            raise RuntimeError("synthetic cleanup failure")

        result = self.execute(context=cleanup_failure)
        self.assertFalse(result["passed"])
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["error_stage"], "cleanup")
        self.assertEqual(result["error_kind"], "RuntimeError")

    def test_import_failure_is_in_child_report(self):
        result = runner.run_module("tests.synthetic_nonexistent_import_target")
        self.assertFalse(result["passed"])
        self.assertEqual(result["tests"], 0)
        self.assertEqual(result["error_stage"], "import")
        self.assertEqual(result["error_kind"], "ModuleNotFoundError")
        self.assertEqual(result["violations"], 0)
        self.assertTrue(result["cleanup"])

    def test_parent_cleanup_failure_is_in_module_result(self):
        cleanup = tempfile.TemporaryDirectory.cleanup

        def fail_after_cleanup(owned):
            cleanup(owned)  # Leave no synthetic files behind even in this negative probe.
            raise OSError("synthetic parent cleanup failure")

        with patch.object(tempfile.TemporaryDirectory, "cleanup", fail_after_cleanup):
            result = runner.run_module("tests.isolation_smoke")
        self.assertFalse(result["passed"])
        self.assertFalse(result["cleanup"])
        self.assertEqual(result["cleanup_error"], "OSError")
        self.assertFalse(Path(result["root"]).parent.exists())

    def test_registry_uses_resolver_without_reading_selected_env(self):
        synthetic = Path(tempfile.gettempdir()) / "stockboda-path-only-nonexistent"
        host = {name: str(synthetic / name) for name in env.DB_FILES}
        host.update(ALPHAMATE_ENV_FILE=str(synthetic / "selected"),
                    ALPHAMATE_CACHE_DIR=str(synthetic / "cache"),
                    GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=str(synthetic / "identity"),
                    OPENAI_API_KEY="SYNTHETIC_SECRET")
        with patch.object(env, "_settings", side_effect=AssertionError("must not load env")):
            protected = isolation.protected_paths(host)
        for environment in ("production", "development"):
            for value in env._validated_paths({"ALPHAMATE_ENV": environment}).values():
                self.assertTrue(protected.contains(value))
        for name in env.DB_FILES:
            for suffix in ("", "-wal", "-shm", "-journal"):
                self.assertTrue(protected.contains(host[name] + suffix))
        self.assertTrue(protected.contains(synthetic / "identity"))
        self.assertNotIn("SYNTHETIC_SECRET", str(protected.metadata()))
        self.assertFalse(protected.contains(Path(__file__).resolve()))

    def test_expected_scope_does_not_consume_multiple_violations(self):
        with tempfile.TemporaryDirectory(prefix="stockboda-ledger-probe-") as temp:
            boundary = isolation.Boundary(temp)
            with self.assertRaises(AssertionError):
                with boundary.expect_violation("network"):
                    for kind in ("network", "write"):
                        try:
                            boundary.deny(kind)
                        except isolation.IsolationViolation:
                            pass
            self.assertEqual(boundary.unexpected, 2)
