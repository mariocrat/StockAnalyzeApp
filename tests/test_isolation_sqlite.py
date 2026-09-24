"""Coordinator-owned outer fixtures contain damage even if an SQLite guard regresses."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from sqlite3 import connect as pre_bootstrap_connect
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.module_isolation import isolated_module
from tests import run_isolated_tests as runner


class SQLiteIsolationTest(unittest.TestCase):
    def run_checked(self, module):
        original_run = runner.subprocess.run
        checked = []

        def launch(*args, **kwargs):
            outer = Path(kwargs["cwd"]).resolve()
            decoy = outer / "existing-decoy.sqlite3"
            with closing(sqlite3.connect(decoy)) as connection:
                connection.execute("CREATE TABLE decoy(value INTEGER)")
                connection.execute("INSERT INTO decoy VALUES (42)")
                connection.commit()
            before = decoy.read_bytes()
            metadata = json.loads(kwargs["input"])
            metadata["files"].append(str(decoy))
            kwargs["input"] = json.dumps(metadata)
            process = original_run(*args, **kwargs)
            self.assertEqual(decoy.read_bytes(), before)
            for filename in ("attach-output.sqlite3", "vacuum-output.sqlite3", "backup-output.sqlite3", "factory-output.sqlite3"):
                self.assertFalse((outer / filename).exists(), filename)
            checked.append(True)
            return process

        with patch.object(runner.subprocess, "run", side_effect=launch):
            result = runner.run_module(module)
        self.assertEqual(checked, [True])
        self.assertTrue(result["restored"], result)
        self.assertTrue(result["patches_restored"], result)
        self.assertTrue(result["cleanup"], result)
        self.assertFalse(Path(result["root"]).parent.exists())
        self.assertNotIn(module, sys.modules)
        print("SQLite probe:", {key: result[key] for key in ("module", "tests", "passed", "violations", "unexpected", "cleanup")})
        return result

    def test_sqlite_boundaries_and_normal_operations(self):
        result = self.run_checked("tests.isolation_sqlite_probes")
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["tests"], 5)
        self.assertEqual(result["violations"], 19)
        self.assertEqual(result["unexpected"], 0)

    def test_swallowed_attach_fails_child_without_creating_target(self):
        result = self.run_checked("tests.isolation_sqlite_swallowed_probe")
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["violations"], 1)
        self.assertEqual(result["unexpected"], 1)
        self.assertEqual(result["violation_kinds"], ["sqlite-attach"])

    def test_pre_bootstrap_connect_alias_is_fail_closed_and_restored(self):
        original = sqlite3.connect
        with tempfile.TemporaryDirectory(prefix="stockboda-sqlite-alias-") as temp:
            with isolated_module(Path(temp) / "runtime") as boundary:
                path = boundary.root / "pre-bootstrap.sqlite3"
                with boundary.expect_violation("sqlite-connect"):
                    pre_bootstrap_connect(path)
                self.assertFalse(path.exists())
        self.assertIs(sqlite3.connect, original)
        self.assertFalse(Path(temp).exists())
