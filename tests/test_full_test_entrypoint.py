"""Stage 1 coordinator regressions: synthetic inventories, reports and owned files.

No recursive full-suite execution. Existing H4 baseline classifications are not
changed by this supplemental cohort.
"""

import copy
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tests import isolation_inventory as inventory
from tests import run_isolated_tests as runner
from tests.module_isolation import sanitized_environment


def entry(module="tests.synthetic_target", role="guarded"):
    return {"module": module, "h4_classification": "OUT", "execution_role": role,
            "cohort": "baseline", "cases": ["Case.test_body"], "skips": {}}


def report(spec):
    return {"module": spec["module"], "tests": 1, "failures": 0, "errors": 0, "skipped": 0,
            "cases": [{"id": spec["module"] + ".Case.test_body", "status": "PASS", "finished": True}],
            "events": [], "passed": True, "returncode": 0, "violations": 0, "unexpected": 0, "violation_kinds": [],
            "restored": True, "patches_restored": True, "cleanup": True}


def probe_fixture():
    owner = entry("tests.synthetic_coordinator", "coordinator")
    target = entry("tests.synthetic_probe", "probe")
    target.update(h4_classification=None, cohort="probe", owner=owner["module"] + ".Case.test_body",
                  expected={"passed": False, "returncode": 1, "unexpected": 1, "violation_kinds": ["network"]})
    negative = report(target)
    negative.update(passed=False, returncode=1, unexpected=1, violations=1, violation_kinds=["network"])
    parent = report(owner)
    parent["nested_reports"] = [{"owner": target["owner"], "report": negative}]
    return owner, target, parent


class FullTestEntrypointTest(unittest.TestCase):
    def test_live_inventory_preserves_baseline_and_counts_source_probes(self):
        entries = inventory.load_inventory()
        summary = inventory.inventory_summary(entries)
        self.assertEqual(summary["baseline_direct"], 450)
        self.assertEqual(summary["baseline_classification"], inventory.BASELINE)
        source = inventory.source_inventory(runner.REPOSITORY)
        probes = {name: cases for name, cases in source.items() if entries[name]["execution_role"] == "probe"}
        self.assertEqual(sum(map(len, probes.values())), 18)
        self.assertEqual(summary["child_probes"], 18)
        self.assertEqual(len(probes), 6)
        self.assertEqual(summary["direct"], 450 + len(entries[inventory.STAGE1]["cases"]))
        self.assertNotIn("tests.diagnose_phase_a_probe", entries)

    def test_manifest_rejects_missing_duplicate_zero_and_invalid_skip(self):
        spec = entry()
        source = {spec["module"]: spec["cases"]}
        self.assertEqual(set(inventory.validate_manifest(source, {"version": 1, "modules": [spec]})), set(source))
        mutations = [[], [spec, spec]]
        for key, value in (("cases", []), ("cases", spec["cases"] * 2),
                           ("execution_role", "raw"), ("skips", {"missing": {"when": "always", "reason": "x"}})):
            invalid = copy.deepcopy(spec)
            invalid[key] = value
            mutations.append([invalid])
        for modules in mutations:
            with self.subTest(modules=modules), self.assertRaises(inventory.InventoryError):
                inventory.validate_manifest(source, {"version": 1, "modules": modules})
        with self.assertRaises(inventory.InventoryError):
            json.loads('{"version":1,"version":1}', object_pairs_hook=inventory._unique_object)

    def test_source_inventory_is_static_and_excludes_diagnostic_before_read(self):
        with tempfile.TemporaryDirectory(prefix="h4-inventory-source-") as temp:
            root = Path(temp)
            (root / "tests").mkdir()
            target = root / "tests/test_synthetic.py"
            target.write_text("raise AssertionError('must not import')\nclass Case:\n    def test_one(self): pass\n", encoding="utf-8")
            # A disposable namesake, never the excluded workspace diagnostic.
            (root / "tests/diagnose_phase_a_probe.py").write_text("not valid Python", encoding="utf-8")
            native = Path.read_text

            def read(path, *args, **kwargs):
                self.assertNotEqual(path.name, "diagnose_phase_a_probe.py")
                return native(path, *args, **kwargs)

            with patch.object(Path, "read_text", read):
                self.assertEqual(inventory.source_inventory(root), {"tests.test_synthetic": ["Case.test_one"]})
            target.write_text("class Empty: pass\n", encoding="utf-8")
            with self.assertRaises(inventory.InventoryError):
                inventory.source_inventory(root)
        self.assertFalse(root.exists())

    def test_runtime_identity_count_skip_and_lifecycle_fail_closed(self):
        spec = entry()
        valid = report(spec)
        self.assertEqual(runner.check_report(spec, valid), [])
        changes = [("tests", 0), ("cases", []), ("cases", valid["cases"] * 2),
                   ("skipped", 1), ("restored", False), ("patches_restored", False),
                   ("cleanup", False), ("returncode", 1), ("unexpected", 1),
                   ("events", [{"status": "ERROR"}]), ("cases", [{"id": {}}])]
        for key, value in changes:
            invalid = copy.deepcopy(valid)
            invalid[key] = value
            with self.subTest(field=key):
                self.assertTrue(runner.check_report(spec, invalid))
                aggregate = runner.coordinate({spec["module"]: spec}, guarded=lambda module: invalid)
                self.assertFalse(aggregate["passed"])
        for invalid in (None, {"cases": ["not a record"]}, {"cases": [{"id": "case", "status": {}}]}):
            aggregate = runner.coordinate({spec["module"]: spec}, guarded=lambda module: invalid)
            self.assertFalse(aggregate["passed"])

    def test_expected_skip_requires_exact_id_reason_and_condition(self):
        spec = entry()
        skipped = report(spec)
        skipped["cases"][0].update(status="SKIP", reason="synthetic skip")
        skipped["skipped"] = 1
        self.assertTrue(runner.check_report(spec, skipped))
        spec["skips"] = {"Case.test_body": {"when": "always", "reason": "synthetic skip"}}
        self.assertEqual(runner.check_report(spec, skipped), [])
        self.assertTrue(runner.check_report(spec, report(spec)))
        spec["skips"]["Case.test_body"]["when"] = "non_windows"
        self.assertEqual(inventory.expected_skips(spec, "nt"), {})
        self.assertEqual(len(inventory.expected_skips(spec, "posix")), 1)

    def test_result_records_subtests_and_class_setup_errors(self):
        module = types.ModuleType("tests.synthetic_result_records")

        class SubtestCase(unittest.TestCase):
            def test_body(self):
                with self.subTest():
                    self.fail("synthetic")

        class SetupCase(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("synthetic setup")

            def test_body(self):
                pass

        module.SubtestCase, module.SetupCase = SubtestCase, SetupCase
        with redirect_stderr(io.StringIO()):
            result = runner.run_suite(module)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.cases[0]["status"], "FAIL")
        self.assertEqual({event["status"] for event in result.events}, {"FAIL", "ERROR"})

    def test_coordinator_separates_primary_coverage_and_expected_negative_probe(self):
        owner, target, parent = probe_fixture()
        # Repeated ancillary evidence is not a second primary direct testcase.
        parent["nested_reports"].extend([{"owner": "ancillary", "report": report(owner)}] * 2)
        result = runner.coordinate({owner["module"]: owner, target["module"]: target},
                                   coordinator=lambda module: parent,
                                   guarded=lambda module: self.fail("unexpected direct probe launch"))
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["counts"], {"PASS": 1, "FAIL": 0, "ERROR": 0, "SKIP": 0})
        self.assertEqual(result["probe_counts"], result["counts"])
        self.assertEqual(result["coverage"]["duplicates"], [])
        self.assertEqual(result["probe_coverage"]["missing"], [])
        self.assertEqual(result["unexpected"], 0)
        self.assertEqual(result["probe_unexpected"], 1)

    def test_missing_duplicate_or_wrong_negative_probe_fails(self):
        for fault in ("missing", "duplicate", "wrong-outcome", "wrong-owner"):
            owner, target, parent = probe_fixture()
            records = parent["nested_reports"]
            if fault == "missing":
                records.clear()
            elif fault == "duplicate":
                records *= 2
            elif fault == "wrong-owner":
                records[0]["owner"] = "unknown"
            else:
                records[0]["report"]["unexpected"] = 0
            result = runner.coordinate({owner["module"]: owner, target["module"]: target}, coordinator=lambda module: parent)
            self.assertFalse(result["passed"], fault)
            self.assertIn(target["module"], result["issues"])

    def test_role_dispatch_cannot_select_general_unguarded_target(self):
        with patch.object(runner, "launch_module", side_effect=AssertionError("must reject before launch")):
            with self.assertRaises(ValueError):
                runner.run_coordinator_module("tests.test_rate_limit")
        with self.assertRaises(ValueError):
            runner.run_module("tests.diagnose_phase_a_probe")
        with self.assertRaises(ValueError):
            runner.coordinator_child("tests.test_rate_limit")

    def test_real_a1_child_has_import_boundary_and_cleanup(self):
        result = runner.run_module("tests.isolation_smoke")
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["unexpected"], 0)
        self.assertTrue(all(result[key] for key in ("restored", "patches_restored", "cleanup")))
        self.assertFalse(Path(result["root"]).parent.exists())

    def test_real_coordinator_child_collects_owned_probe_evidence(self):
        result = runner.run_coordinator_module("tests.test_isolation_runner")
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["tests"], 3)
        records = result["nested_reports"]
        self.assertEqual(len(records), 4)
        self.assertEqual(sum(record["report"]["module"] == "tests.isolation_probes" for record in records), 1)
        self.assertTrue(all(record["owner"].startswith("tests.test_isolation_runner.") for record in records))
        self.assertTrue(all(result[key] for key in ("restored", "patches_restored", "cleanup")))
        self.assertFalse(Path(result["root"]).parent.exists())

    def test_child_protocol_errors_and_timeout_still_cleanup(self):
        roots = []
        for fault in ("missing", "duplicate", "malformed", "forged-root", "timeout"):
            def launch(*args, **kwargs):
                roots.append(Path(kwargs["cwd"]))
                self.assertEqual(kwargs["env"]["HOME"], str(roots[-1] / "runtime"))
                self.assertNotIn("ARBITRARY_PROVIDER_SECRET", kwargs["env"])
                if fault == "timeout":
                    raise subprocess.TimeoutExpired(args[0], 1)
                payload = {"module": "tests.synthetic_target", "passed": True}
                if fault == "forged-root":
                    payload["root"] = "not-owned"
                line = runner.REPORT_PREFIX + json.dumps(payload) + "\n"
                output = {"missing": "", "duplicate": line * 2, "malformed": runner.REPORT_PREFIX + "{",
                          "forged-root": line}[fault]
                return types.SimpleNamespace(stdout=output, stderr="", returncode=0)

            with patch.object(runner.subprocess, "run", side_effect=launch):
                result = runner.run_module("tests.synthetic_target", host={"ARBITRARY_PROVIDER_SECRET": "synthetic"})
            self.assertFalse(result["passed"], fault)
            self.assertTrue(result["cleanup"], result)
        self.assertTrue(all(not root.exists() for root in roots))

    def test_legacy_exit_two_before_any_target_or_application_import(self):
        legacy = runner.REPOSITORY / "tests/run_phase_a_tests.py"
        code = (
            "import runpy, sys\n"
            "class RejectTargets:\n"
            " def find_spec(self, fullname, path=None, target=None):\n"
            "  if fullname == 'main' or fullname.startswith(('tests', 'backend')): raise AssertionError('target import')\n"
            "sys.meta_path.insert(0, RejectTargets())\n"
            f"runpy.run_path({str(legacy)!r}, run_name='__main__')\n"
        )
        with tempfile.TemporaryDirectory(prefix="h4-legacy-") as temp:
            root = Path(temp)
            result = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=root,
                                    env=sanitized_environment(os.environ, root / "runtime"),
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Deprecated", result.stderr)
            self.assertIn("run_isolated_tests.py --all", result.stderr)
            self.assertEqual(list(root.iterdir()), [])
        self.assertFalse(root.exists())

    def test_live_role_or_classification_tampering_fails_closed(self):
        manifest = json.loads((runner.REPOSITORY / "tests/test_inventory.json").read_text(encoding="utf-8"))
        for field, value in (("execution_role", "coordinator"), ("h4_classification", "migrated")):
            changed = copy.deepcopy(manifest)
            target = next(item for item in changed["modules"] if item["module"] == "tests.test_rate_limit")
            target[field] = value
            with patch.object(inventory.json, "loads", return_value=changed):
                with self.assertRaises(inventory.InventoryError):
                    inventory.load_inventory()
