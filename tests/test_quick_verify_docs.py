from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

# Load the real BOM codec under A1 before per-case module snapshots.
import encodings.utf_8_sig
import os
import sys
import tempfile
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuickVerifyDocsTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
        modules = dict(sys.modules)
        namespace = dict(vars(sys.modules[__name__]))
        self.addCleanup(self._assert_restored, baseline, modules, namespace)
        fixture = self.enterContext(storage_fixture())
        self._case_container = fixture.root.parent

    def _assert_restored(self, baseline, modules, namespace):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path)), baseline)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is module for name, module in modules.items()))
        current = vars(sys.modules[__name__])
        self.assertEqual(set(current), set(namespace))
        self.assertTrue(all(current[name] is value for name, value in namespace.items()))
        container = self.__dict__.pop("_case_container", None)
        if container is not None:
            self.assertFalse(container.exists())

    def test_double_click_verify_batch_is_ascii_safe_wrapper(self):
        batch = (ROOT / "verify_project.bat").read_text(encoding="utf-8")

        self.assertIn('"%SystemRoot%\\System32\\chcp.com" 65001 >nul', batch)
        self.assertIn("scripts\\verify_project.ps1", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Project verification passed.", batch)
        self.assertIn("Project verification failed.", batch)
        self.assertIn('"%~dp0scripts\\verify_project.ps1" %*', batch)
        self.assertIn('set "verify_exit=%errorlevel%"', batch)
        self.assertIn('exit /b %verify_exit%', batch)
        self.assertNotIn('cd /d', batch)
        self.assertNotIn('pause', batch.lower())

    def test_verify_project_script_forces_utf8_console_output(self):
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("[Console]::OutputEncoding", script)
        self.assertIn("$OutputEncoding", script)
        self.assertIn("$env:PYTHONUTF8 = \"1\"", script)
        branch = script.split("if ($Mode -ceq 'TestOnly') {", 1)[1].split("\n    else {", 1)[0]
        self.assertEqual(branch.count("@('-I', '-X', 'utf8', '-B', $coordinator"), 2)

    def test_quick_verify_docs_show_powershell_batch_invocation(self):
        docs = (ROOT / "docs" / "quick_verify.md").read_text(encoding="utf-8")

        self.assertIn("```powershell", docs)
        self.assertIn(".\\verify_project.bat", docs)
        self.assertIn(".\\verify_android_debug.bat", docs)
        self.assertIn("PowerShell에서는 앞에 `.\\`를 붙여야 합니다", docs)
        self.assertIn("ALPHAMATE_NO_PAUSE", docs)
        self.assertIn("release_readiness_report.bat", docs)
        self.assertIn("verify_android_release.bat", docs)

    def test_owner_docs_avoid_stale_workspace_paths(self):
        docs = [
            ROOT / "docs" / "manual_test_guide.md",
            ROOT / "docs" / "quick_verify.md",
            ROOT / "docs" / "project_owner_dashboard.md",
            ROOT / "docs" / "release_preparation_checklist.md",
        ]
        forbidden = ["D:\\작업", "D:/작업", "windsurf", "cd D:\\Project\\Vibe\\StockAnalyze"]

        for path in docs:
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                with self.subTest(path=path.name, value=value):
                    self.assertNotIn(value, text)

        manual = (ROOT / "docs" / "manual_test_guide.md").read_text(encoding="utf-8")
        self.assertIn("$projectRoot='D:\\Project\\Vibe\\StockAnalyze'", manual)
        self.assertIn("다른 PC에서는 `$projectRoot` 값", manual)

    def test_verify_project_powershell_script_keeps_utf8_bom_for_windows_powershell(self):
        script = (ROOT / "scripts" / "verify_project.ps1").read_bytes()
        self.assertTrue(script.startswith(b"\xef\xbb\xbf"))

    def test_verify_project_runs_every_frontend_safety_test_script(self):
        from tests.isolation_inventory import load_node_inventory, node_inventory_summary

        live = node_inventory_summary(load_node_inventory())
        self.assertEqual((live["entrypoints"], live["direct"]), (18, 149))
        current_node_contract = f"Node **{live['entrypoints']} entrypoint / {live['direct']} direct testcase**"
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("tests\\run_isolated_tests.py", script)
        self.assertIn("'--node-all', '--node-executable', $node", script)
        self.assertNotIn("npm.cmd run test:", script)
        self.assertNotIn("unittest discover", script)
        for name in ("TESTING.md", "quick_verify.md"):
            docs = (ROOT / "docs" / name).read_text(encoding="utf-8")
            for value in ("-Mode TestOnly", "-Mode BuildChecks", "-PythonPath", "-NodePath",
                          "464", "18", current_node_contract, "test:broker-import",
                          "historical baseline", "35 / 393 / 22", "14",
                          "run_phase_a_tests.py", "exit 2", "diagnose_phase_a_probe.py",
                          "raw", "network", "install", "signing"):
                self.assertIn(value, docs)

    def test_quick_verify_docs_list_every_project_verification_step(self):
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "quick_verify.md").read_text(encoding="utf-8")

        step_names = re.findall(r'Run-Step "([^"]+)"', script)

        self.assertGreater(len(step_names), 0)
        for step_name in step_names:
            with self.subTest(step=step_name):
                self.assertIn(step_name, docs)


if __name__ == "__main__":
    unittest.main()
