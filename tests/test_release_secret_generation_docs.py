import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_release_secrets.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_release_secrets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseSecretGenerationDocsTest(unittest.TestCase):
    def test_double_click_batch_runs_secret_generation_script(self):
        batch = (ROOT / "generate_release_secrets.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\generate_release_secrets.py", batch)
        self.assertIn("--fill-empty", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertIn("pause", batch.lower())

    def test_owner_docs_mention_secret_generation_helper(self):
        checklist = (ROOT / "docs" / "release_preparation_checklist.md").read_text(encoding="utf-8")
        dashboard = (ROOT / "docs" / "project_owner_dashboard.md").read_text(encoding="utf-8")

        self.assertIn("generate_release_secrets.bat", checklist)
        self.assertIn("GOOGLE_PLAY_RTDN_SHARED_TOKEN", checklist)
        self.assertIn("generate_release_secrets.bat", dashboard)



if __name__ == "__main__":
    unittest.main()
