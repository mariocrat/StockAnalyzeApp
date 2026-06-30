import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidReleaseVerificationTest(unittest.TestCase):
    def test_double_click_batch_runs_android_release_verification_script(self):
        batch = (ROOT / "verify_android_release.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\verify_android_release.ps1", batch)
        self.assertIn("ExecutionPolicy Bypass", batch)
        self.assertIn("Android release verification passed", batch)
        self.assertIn("pause", batch.lower())

    def test_release_verification_script_loads_frontend_release_env_and_builds_aab(self):
        script = (ROOT / "scripts" / "verify_android_release.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $frontend ".env.release"', script)
        self.assertIn("Load-EnvFile", script)
        self.assertIn("ALPHAMATE_FRONTEND_ENV_FILE", script)
        self.assertIn("npm.cmd run mobile:release:aab", script)
        self.assertIn("bundle\\release\\app-release.aab", script)
        self.assertIn("JAVA_HOME", script)
        self.assertIn("ANDROID_HOME", script)
        self.assertNotIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD)", script)


if __name__ == "__main__":
    unittest.main()
