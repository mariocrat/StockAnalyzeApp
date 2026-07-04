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
