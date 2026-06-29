import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_release_secrets.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_release_secrets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseSecretGenerationTest(unittest.TestCase):
    def test_generates_long_distinct_release_secret_values(self):
        module = load_module()

        first = module.generate_release_secrets()
        second = module.generate_release_secrets()

        self.assertIn("ALPHAMATE_ADMIN_TOKEN", first)
        self.assertIn("GOOGLE_PLAY_RTDN_SHARED_TOKEN", first)
        self.assertGreaterEqual(len(first["ALPHAMATE_ADMIN_TOKEN"]), 43)
        self.assertGreaterEqual(len(first["GOOGLE_PLAY_RTDN_SHARED_TOKEN"]), 43)
        self.assertNotEqual(first["ALPHAMATE_ADMIN_TOKEN"], first["GOOGLE_PLAY_RTDN_SHARED_TOKEN"])
        self.assertNotEqual(first["ALPHAMATE_ADMIN_TOKEN"], second["ALPHAMATE_ADMIN_TOKEN"])

    def test_formats_output_without_writing_secret_files(self):
        module = load_module()

        output = module.format_release_secrets({
            "ALPHAMATE_ADMIN_TOKEN": "admin-token-value",
            "GOOGLE_PLAY_RTDN_SHARED_TOKEN": "rtdn-token-value",
        })

        self.assertIn("ALPHAMATE_ADMIN_TOKEN=admin-token-value", output)
        self.assertIn("GOOGLE_PLAY_RTDN_SHARED_TOKEN=rtdn-token-value", output)
        self.assertIn("Do not commit", output)
        self.assertIn(".env.release", output)

    def test_double_click_batch_runs_secret_generation_script(self):
        batch = (ROOT / "generate_release_secrets.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\generate_release_secrets.py", batch)
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
