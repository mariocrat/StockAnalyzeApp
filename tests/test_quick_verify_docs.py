import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuickVerifyDocsTest(unittest.TestCase):
    def test_double_click_verify_batch_uses_korean_owner_messages(self):
        batch = (ROOT / "verify_project.bat").read_text(encoding="utf-8")

        self.assertIn("프로젝트 전체 검증을 통과했습니다", batch)
        self.assertIn("프로젝트 전체 검증에 실패했습니다", batch)
        self.assertNotIn("Project verification passed", batch)
        self.assertNotIn("Project verification failed", batch)

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
