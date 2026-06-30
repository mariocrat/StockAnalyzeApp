import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "prepare_private_release_setup.bat"


class PrivateReleaseSetupTest(unittest.TestCase):
    def test_double_click_batch_runs_private_release_setup_steps_in_order(self):
        batch = BATCH.read_text(encoding="utf-8")

        expected_order = [
            "scripts\\create_release_env_files.py",
            "scripts\\generate_release_secrets.py --fill-empty",
            "scripts\\generate_android_upload_key.py --create-key",
            "backend\\scripts\\owner_release_report.py",
            "npm.cmd run --silent release:report",
        ]
        cursor = -1
        for item in expected_order:
            next_index = batch.find(item)
            self.assertGreater(next_index, cursor, f"{item} should be called after the previous setup step")
            cursor = next_index

        self.assertNotIn("call \"%~dp0prepare_release_env_files.bat\"", batch.lower())
        self.assertNotIn("call \"%~dp0generate_release_secrets.bat\"", batch.lower())
        self.assertNotIn("call \"%~dp0generate_android_upload_key.bat\"", batch.lower())
        self.assertNotIn("call \"%~dp0release_readiness_report.bat\"", batch.lower())
        self.assertIn("pause", batch.lower())
        self.assertIn("exit /b %SETUP_EXIT%", batch)
        self.assertNotIn("OPENAI_API_KEY=", batch)
        self.assertNotIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=", batch)


if __name__ == "__main__":
    unittest.main()
