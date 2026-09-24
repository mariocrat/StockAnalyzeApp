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


def node_regression_suite(executable):
    """Explicit Stage 2 synthetic cohort, invoked by --node-regressions only.

    These nested coordinator checks are not new Python primary inventory IDs or
    Node package cases. The approved 450+14 Python cohort remains unchanged.
    """
    executable = runner.node_executable(executable)

    class NodeCoordinatorRegression(unittest.TestCase):
        def setUp(self):
            self.owned = tempfile.TemporaryDirectory(prefix="h4-node-fixture-")
            self.addCleanup(self.owned.cleanup)
            self.frontend = Path(self.owned.name) / "frontend"
            (self.frontend / "scripts").mkdir(parents=True)

        def fixture(self, body, names=("synthetic",)):
            file = "scripts/synthetic.test.js"
            (self.frontend / "package.json").write_text(json.dumps({"type": "module", "scripts": {
                "test:synthetic": "node --test " + file}}), encoding="utf-8")
            source = "import test from 'node:test';\nimport assert from 'node:assert/strict';\n" + body
            (self.frontend / file).write_text(source, encoding="utf-8")
            return {"name": "test:synthetic", "file": file, "command": "node --test " + file,
                    "profile": "standard", "cases": list(names), "sha256": inventory.node_source_hash(source),
                    "reads": ["package.json", file], "release_eval_sha256": []}

        def launch(self, spec, **kwargs):
            result = runner.run_node_entry(spec, executable, frontend=self.frontend, **kwargs)
            self.assertTrue(result["cleanup"], result)
            self.assertFalse(Path(result["root"]).exists())
            return result

        def test_inventory_package_source_manifest_exact_and_fail_closed(self):
            live = inventory.load_node_inventory()
            self.assertEqual(len(live), 18)
            self.assertEqual(sum(len(item["cases"]) for item in live.values()), 149)
            self.assertIn("test:broker-import", live)
            self.assertIn("test:mobile-bundle", live)
            spec = self.fixture("test('synthetic', () => {});\n")
            manifest = {"version": 1, "entries": [spec]}
            self.assertEqual(len(inventory.validate_node_inventory(self.frontend, manifest)), 1)
            for fault in ("missing", "duplicate", "extra", "hash", "case", "shell"):
                broken = copy.deepcopy(manifest)
                if fault == "missing": broken["entries"] = []
                elif fault == "duplicate": broken["entries"] *= 2
                elif fault == "extra": broken["entries"][0]["name"] = "test:extra"
                elif fault == "hash": broken["entries"][0]["sha256"] = "0" * 64
                elif fault == "case": broken["entries"][0]["cases"] = ["absent"]
                else:
                    package = {"type": "module", "scripts": {spec["name"]: spec["command"] + " && npm run build"}}
                    (self.frontend / "package.json").write_text(json.dumps(package), encoding="utf-8")
                with self.subTest(fault=fault), self.assertRaises(inventory.InventoryError):
                    inventory.validate_node_inventory(self.frontend, broken)
            for private in (".env", "release-private/secret.js", "../private.js", "src/credential.json"):
                with self.assertRaises(inventory.InventoryError):
                    inventory.node_source_path(self.frontend, private)
            with self.assertRaises(ValueError):
                runner.node_executable("node")

        def test_reporter_nested_coverage_environment_and_restoration(self):
            body = """
import fs from 'node:fs';
import path from 'node:path';
test('outer', async t => {
  for (const key of ['PATH','NODE_OPTIONS','GOOGLE_APPLICATION_CREDENTIALS','OPENAI_API_KEY','ALPHAMATE_ANDROID_KEYSTORE_FILE']) assert.equal(process.env[key], undefined);
  assert.equal(process.env.HOME, path.join(process.cwd(), 'home'));
  fs.writeFileSync(path.join(process.env.TEMP, 'owned'), 'synthetic');
  assert.equal(fs.readFileSync(path.join(process.env.TEMP, 'owned'), 'utf8'), 'synthetic');
  await t.test('nested', () => {});
});
test('restoration', () => {
  process.chdir(process.env.TEMP);
  process.env.SYNTHETIC_MUTATION = 'owned';
  fs.existsSync = () => false;
});
"""
            spec = self.fixture(body, ("outer", "restoration"))
            hostile = {key: "synthetic-host-value" for key in ("PATH", "NODE_OPTIONS", "GOOGLE_APPLICATION_CREDENTIALS", "OPENAI_API_KEY", "ALPHAMATE_ANDROID_KEYSTORE_FILE")}
            hostile.update({key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE"}})
            result = self.launch(spec, host=hostile)
            self.assertTrue(result["passed"], result)
            self.assertEqual(len(result["cases"]), 2)
            self.assertEqual(len(result["nested"]), 1)
            self.assertTrue(result["restored"] and result["patches_restored"])
            aggregate = runner.coordinate_node({spec["name"]: spec}, executable, launch=lambda *args: result)
            self.assertTrue(aggregate["passed"], aggregate)
            self.assertEqual(aggregate["coverage"]["observed"], 2)
            for fault in ("duplicate", "missing", "extra"):
                malformed = copy.deepcopy(result)
                if fault == "duplicate": malformed["cases"] *= 2
                elif fault == "missing": malformed["cases"].pop()
                else: malformed["cases"][0]["id"] = "extra"
                self.assertTrue(runner.check_node_report(spec, malformed))

        def test_guard_blocks_synthetic_private_network_dns_and_tools_before_access(self):
            body = """
import fs from 'node:fs';
import path from 'node:path';
import dns from 'node:dns';
import net from 'node:net';
import childProcess from 'node:child_process';
test('synthetic', () => {
  const outside = path.join(process.cwd(), '..', 'synthetic-never-opened');
  for (const name of ['frontend/.env', 'home/credentials.json', 'release-private/upload.jks']) {
    assert.throws(() => fs.readFileSync(path.join(outside, name)), /isolation blocked/);
  }
  assert.throws(() => fs.writeFileSync(path.join(outside, 'write'), 'blocked'), /isolation blocked/);
  assert.throws(() => dns.lookup('synthetic.invalid'), /isolation blocked/);
  assert.throws(() => net.connect(9, '192.0.2.1'), /isolation blocked/);
  assert.throws(() => fetch('https://synthetic.invalid'), /isolation blocked/);
  assert.throws(() => childProcess.spawnSync('synthetic-never-launched'), /isolation blocked/);
});
"""
            result = self.launch(self.fixture(body))
            self.assertFalse(result["passed"])
            self.assertEqual(result["unexpected"], 8)
            self.assertEqual(result["cases"][0]["status"], "PASS")
            self.assertTrue(result["restored"] and result["patches_restored"])

        def test_fail_skip_setup_crash_and_timeout_propagate(self):
            for name, body in (
                ("assertion", "test('synthetic', () => assert.fail('synthetic'));"),
                ("skip", "test('synthetic', {skip:'synthetic'}, () => {});"),
                ("setup", "throw new Error('synthetic setup');\ntest('synthetic', () => {});"),
                ("crash", "process.exit(7);\ntest('synthetic', () => {});"),
                ("timeout", "test('synthetic', () => new Promise(() => { setInterval(() => {}, 1000); }));"),
            ):
                with self.subTest(name=name):
                    result = self.launch(self.fixture(body), timeout=1 if name == "timeout" else 30)
                    self.assertFalse(result["passed"], result)
                    if name == "assertion": self.assertEqual(result["cases"][0]["status"], "FAIL")
                    if name == "skip": self.assertEqual(result["cases"][0]["status"], "SKIP")
                    if name == "timeout": self.assertEqual(result["coordinator_error"], "TimeoutExpired")

        def test_malformed_missing_duplicate_protocol_and_cleanup_failure(self):
            spec = self.fixture("test('synthetic', () => {});")
            for value in ("", runner.NODE_REPORT_PREFIX + "{", runner.NODE_REPORT_PREFIX + "{}\n" * 2):
                with self.assertRaises(ValueError):
                    runner.parse_node_report(value, spec)
            with self.assertRaises(ValueError):
                runner.parse_node_report((runner.NODE_REPORT_PREFIX + json.dumps({"name": spec["name"], "file": spec["file"]}) + "\n") * 2, spec)
            with self.assertRaises(ValueError):
                runner.parse_node_report(runner.NODE_REPORT_PREFIX + '{"name":"test:synthetic","name":"test:synthetic"}', spec)
            native_cleanup = tempfile.TemporaryDirectory.cleanup

            def cleanup_failure(owned):
                native_cleanup(owned)
                raise OSError("synthetic cleanup failure after removal")

            with patch.object(tempfile.TemporaryDirectory, "cleanup", cleanup_failure):
                result = runner.run_node_entry(spec, executable, frontend=self.frontend)
            self.assertFalse(result["passed"])
            self.assertFalse(result["cleanup"])
            self.assertEqual(result["cleanup_error"], "OSError")
            self.assertFalse(Path(result["root"]).exists())

        def test_missing_dependency_fails_before_node_launch(self):
            spec = self.fixture("test('synthetic', () => {});")
            spec["reads"].append("scripts/missing-source.js")
            with patch.object(runner.subprocess, "run", side_effect=AssertionError("must fail before execution")):
                result = self.launch(spec)
            self.assertFalse(result["passed"])
            self.assertEqual(result["coordinator_error"], "FileNotFoundError")

        def billing_snapshot(self):
            spec = copy.deepcopy(inventory.load_node_inventory()["test:android-billing"])
            for relative in (*spec["reads"], "package-lock.json", spec["fixture"]["source"]):
                target = self.frontend / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((inventory.REPOSITORY / "frontend" / relative).read_bytes())
            self.assertFalse((self.frontend / "node_modules").exists())
            return spec

        def test_billing_fixture_provenance_fails_closed_before_launch(self):
            for fault in ("missing", "sha", "version", "integrity", "resolved", "destination", "metadata"):
                with self.subTest(fault=fault):
                    spec = self.billing_snapshot()
                    fixture = self.frontend / spec["fixture"]["source"]
                    if fault == "missing":
                        fixture.unlink()
                    elif fault == "sha":
                        content = fixture.read_bytes()
                        fixture.write_bytes(bytes([content[0] ^ 1]) + content[1:])
                    elif fault in ("version", "integrity", "resolved"):
                        lock_path = self.frontend / "package-lock.json"
                        lock = json.loads(lock_path.read_bytes())
                        lock["packages"]["node_modules/capacitor-plugin-cdv-purchase"][fault] = "synthetic-mismatch"
                        lock_path.write_bytes(json.dumps(lock).encode("utf-8"))
                    elif fault == "destination":
                        spec["fixture"]["destination"] = "../synthetic-escape/build.gradle"
                    else:
                        del spec["fixture"]
                    with self.assertRaises((inventory.InventoryError, FileNotFoundError)):
                        inventory.validated_node_fixture(self.frontend, spec)
                    with patch.object(runner.subprocess, "run", side_effect=AssertionError("no process on invalid fixture")) as launch:
                        result = self.launch(spec)
                        launch.assert_not_called()
                    self.assertFalse(result["passed"], result)
                    self.assertEqual(result["coordinator_error"], "FileNotFoundError" if fault == "missing" else "InventoryError")

        def test_billing_fixture_runs_original_assertions_offline(self):
            import socket

            spec = self.billing_snapshot()
            destination, content = inventory.validated_node_fixture(self.frontend, spec)
            self.assertEqual(destination, inventory.NODE_PLUGIN_SOURCE)
            self.assertEqual(len(content), 1345)
            self.assertEqual(inventory.hashlib.sha256(content).hexdigest(), spec["fixture"]["sha256"])
            native_run = runner.subprocess.run
            commands = []

            def node_only(command, **options):
                self.assertEqual(command[0], str(executable))
                commands.append(command)
                if command[1:] != ["--version"]:
                    self.assertIn("--permission", command)
                    self.assertNotIn("--allow-child-process", command)
                    self.assertEqual(command[-1], spec["file"])
                    copied = Path(options["cwd"]) / destination
                    self.assertEqual(copied.read_bytes(), content)
                return native_run(command, **options)

            with patch.object(socket, "getaddrinfo", side_effect=AssertionError("offline DNS")), \
                    patch.object(socket.socket, "connect", side_effect=AssertionError("offline network")), \
                    patch.object(runner.subprocess, "run", side_effect=node_only):
                result = self.launch(spec)
            self.assertEqual(len(commands), 2)  # Node version + one test; no npm/tool/install.
            self.assertTrue(result["passed"], result)
            self.assertEqual([case["id"] for case in result["cases"]], [spec["file"] + "::" + spec["cases"][0]])
            self.assertEqual(result["cases"][0]["status"], "PASS")
            self.assertEqual(result["unexpected"], 0)
            self.assertTrue(result["restored"] and result["patches_restored"])
            self.assertFalse((self.frontend / "node_modules").exists())

        def test_existing_release_and_bundle_contracts_under_outer_guard(self):
            entries = inventory.load_node_inventory()
            for name in ("test:release-env", "test:mobile-bundle"):
                with self.subTest(name=name):
                    result = runner.run_node_entry(entries[name], executable)
                    self.assertTrue(result["passed"], result)
                    self.assertEqual(len(result["cases"]), len(entries[name]["cases"]))
                    self.assertTrue(result["restored"] and result["patches_restored"] and result["cleanup"])
                    self.assertFalse(Path(result["root"]).exists())

    return unittest.defaultTestLoader.loadTestsFromTestCase(NodeCoordinatorRegression)


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
        self.assertEqual(result["probe_expected_negative_raw_violations"], 1)
        self.assertEqual(result["probe_contract_mismatch"], 0)
        self.assertNotIn("probe_unexpected", result)

        # Use the reviewed 4+1+1 manifest contracts without executing a full suite.
        negatives = [copy.deepcopy(spec) for spec in inventory.load_inventory().values()
                     if spec["execution_role"] == "probe" and not spec["expected"]["passed"]]
        self.assertEqual(sorted(spec["expected"]["unexpected"] for spec in negatives), [1, 1, 4])
        parent = report(owner)
        parent["nested_reports"] = []
        for spec in negatives:
            spec["owner"] = owner["module"] + ".Case.test_body"
            child = report(spec)
            child.update(spec["expected"])
            child.update(tests=len(spec["cases"]), violations=len(child["violation_kinds"]),
                         cases=[{"id": spec["module"] + "." + case, "status": "PASS", "finished": True}
                                for case in spec["cases"]])
            parent["nested_reports"].append({"owner": spec["owner"], "report": child})
        result = runner.coordinate({spec["module"]: spec for spec in [owner, *negatives]},
                                   coordinator=lambda module: parent,
                                   guarded=lambda module: self.fail("unexpected direct probe launch"))
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["probe_expected_negative_raw_violations"], 6)
        self.assertEqual(result["probe_contract_mismatch"], 0)
        self.assertEqual(result["unexpected"], 0)
        self.assertTrue(all(result[key] for key in ("restored", "patches_restored", "cleanup")))

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
            self.assertEqual(result["probe_contract_mismatch"], 1)
            self.assertEqual(result["probe_expected_negative_raw_violations"], 0)

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
                self.assertEqual(args[0][1:5], ["-I", "-X", "utf8", "-B"])
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

        # Run a real failing synthetic child through the same launcher/decoder.
        # -I ignores PYTHONUTF8, so the command-line flag must carry this contract.
        native_run = subprocess.run
        korean = "합성 실패: 한국어 stderr 보존"
        body = "import unittest\nclass Case(unittest.TestCase):\n def test_body(self):\n  self.fail(" + repr(korean) + ")\n"
        code = (
            "import sys, json, types\nfrom pathlib import Path\n"
            "assert sys.flags.isolated == 1 and sys.flags.utf8_mode == 1\n"
            f"sys.path.insert(0, {str(runner.REPOSITORY)!r})\n"
            "from tests import run_isolated_tests as runner\n"
            "module = types.ModuleType('tests.synthetic_target')\n"
            f"exec({body!r}, module.__dict__)\n"
            "sys.modules[module.__name__] = module\n"
            "raise SystemExit(runner.child(module.__name__, Path(sys.argv[1]), "
            "runner.ProtectedPaths(**json.loads(sys.stdin.read()))))\n"
        )

        def launch_korean(command, **options):
            self.assertEqual(command[1:5], ["-I", "-X", "utf8", "-B"])
            self.assertEqual(options["encoding"], "utf-8")
            self.assertNotIn("errors", options)
            options["env"].pop("PYTHONUTF8", None)
            roots.append(Path(options["cwd"]))
            return native_run([*command[:5], "-c", code, command[-1]], **options)

        with patch.object(runner.subprocess, "run", side_effect=launch_korean):
            result = runner.run_module("tests.synthetic_target")
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["cases"][0]["status"], "FAIL")
        self.assertIn(korean, result["stderr"])
        self.assertNotIn("UnicodeDecodeError", result["stderr"])
        self.assertNotIn("coordinator_error", result)
        self.assertEqual(result["unexpected"], 0)
        self.assertTrue(all(result[key] for key in ("restored", "patches_restored", "cleanup")))
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
        # Stage 3 static wrapper contract; synthetic process checks are in the
        # explicit PS regression, not another primary Python inventory cohort.
        wrapper = (runner.REPOSITORY / "scripts/verify_project.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$Mode -cnotin @('TestOnly', 'BuildChecks')", wrapper)
        self.assertIn("$start.EnvironmentVariables.Clear()", wrapper)
        self.assertIn("Resolve-Executable $PythonPath 'python.exe'", wrapper)
        self.assertIn("Resolve-Executable $NodePath 'node.exe'", wrapper)
        branch = wrapper.split("if ($Mode -ceq 'TestOnly') {", 1)[1].split("\n    else {", 1)[0]
        self.assertEqual(branch.count("Require-Success (Invoke-IsolatedTool"), 2)
        self.assertEqual(branch.count("@('-I', '-X', 'utf8', '-B', $coordinator"), 2)
        self.assertIn("'--all'", branch)
        self.assertIn("'--node-all'", branch)
        for prohibited in ("npm", "compileall", "build", "Gradle", "keytool", "discover"):
            self.assertNotIn(prohibited, branch)
        self.assertNotIn("unittest discover", wrapper)
        manifest = json.loads((runner.REPOSITORY / "tests/test_inventory.json").read_text(encoding="utf-8"))
        for field, value in (("execution_role", "coordinator"), ("h4_classification", "migrated")):
            changed = copy.deepcopy(manifest)
            target = next(item for item in changed["modules"] if item["module"] == "tests.test_rate_limit")
            target[field] = value
            with patch.object(inventory.json, "loads", return_value=changed):
                with self.assertRaises(inventory.InventoryError):
                    inventory.load_inventory()
