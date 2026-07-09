import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuickVerifyDocsTest(unittest.TestCase):
    def test_double_click_verify_batch_is_ascii_safe_wrapper(self):
        batch = (ROOT / "verify_project.bat").read_text(encoding="utf-8")

        self.assertIn("chcp 65001 >nul", batch)
        self.assertIn("scripts\\verify_project.ps1", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Project verification passed.", batch)
        self.assertIn("Project verification failed.", batch)

    def test_verify_project_script_forces_utf8_console_output(self):
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("[Console]::OutputEncoding", script)
        self.assertIn("$OutputEncoding", script)
        self.assertIn("$env:PYTHONUTF8 = \"1\"", script)

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
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8-sig")

        for npm_script in (
            "test:release-env",
            "test:android-branding",
            "test:android-billing",
            "test:mobile-billing",
            "test:mobile-admob",
            "test:client-events",
            "test:api-errors",
            "test:oauth-app-return",
            "test:ai-idempotency",
            "test:splash-loading",
        ):
            with self.subTest(npm_script=npm_script):
                self.assertIn(f"npm.cmd run {npm_script}", script)

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
