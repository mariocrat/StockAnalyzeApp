import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_release_env_files.py"


def load_module():
    spec = importlib.util.spec_from_file_location("create_release_env_files", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseEnvFileSetupTest(unittest.TestCase):
    def test_creates_private_release_env_files_from_templates(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / ".env.release.example").write_text("ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / "frontend" / ".env.release.example").write_text("VITE_ALPHAMATE_ENV=production\n", encoding="utf-8")

            result = module.create_release_env_files(root)

            self.assertEqual(2, result["created"])
            self.assertEqual(0, result["skipped"])
            self.assertEqual(0, result["updated"])
            self.assertEqual("ALPHAMATE_ENV=production\n", (root / ".env.release").read_text(encoding="utf-8"))
            self.assertEqual(
                "VITE_ALPHAMATE_ENV=production\n",
                (root / "frontend" / ".env.release").read_text(encoding="utf-8"),
            )

    def test_does_not_overwrite_existing_private_values_but_appends_new_template_keys(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / ".env.release.example").write_text(
                "ALPHAMATE_ENV=production\nOPENAI_API_KEY=\n",
                encoding="utf-8",
            )
            (root / "frontend" / ".env.release.example").write_text(
                "VITE_ALPHAMATE_ENV=production\nVITE_ADMOB_ANDROID_APP_ID=ca-app-pub-0000000000000000~0000000000\n",
                encoding="utf-8",
            )
            (root / ".env.release").write_text("ALPHAMATE_ENV=production\nKEEP_BACKEND_SECRET=1\n", encoding="utf-8")
            (root / "frontend" / ".env.release").write_text(
                "VITE_ALPHAMATE_ENV=production\nKEEP_FRONTEND_SECRET=1\n",
                encoding="utf-8",
            )

            result = module.create_release_env_files(root)

            backend_text = (root / ".env.release").read_text(encoding="utf-8")
            frontend_text = (root / "frontend" / ".env.release").read_text(encoding="utf-8")

            self.assertEqual(0, result["created"])
            self.assertEqual(0, result["skipped"])
            self.assertEqual(2, result["updated"])
            self.assertIn("KEEP_BACKEND_SECRET=1", backend_text)
            self.assertIn("OPENAI_API_KEY=", backend_text)
            self.assertIn("KEEP_FRONTEND_SECRET=1", frontend_text)
            self.assertIn("VITE_ADMOB_ANDROID_APP_ID=ca-app-pub-0000000000000000~0000000000", frontend_text)
            self.assertEqual(["OPENAI_API_KEY"], result["missing_keys_by_file"][".env.release"])
            self.assertEqual(
                ["VITE_ADMOB_ANDROID_APP_ID"],
                result["missing_keys_by_file"]["frontend\\.env.release"],
            )

    def test_keeps_existing_private_release_env_files_when_template_keys_are_current(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / ".env.release.example").write_text("ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / "frontend" / ".env.release.example").write_text("VITE_ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / ".env.release").write_text("ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / "frontend" / ".env.release").write_text("VITE_ALPHAMATE_ENV=production\n", encoding="utf-8")

            result = module.create_release_env_files(root)

            self.assertEqual(0, result["created"])
            self.assertEqual(2, result["skipped"])
            self.assertEqual(0, result["updated"])

    def test_double_click_batch_runs_release_env_setup_script(self):
        batch = (ROOT / "prepare_release_env_files.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\create_release_env_files.py", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("pause", batch.lower())

    def test_release_env_setup_script_uses_korean_owner_messages(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("다음: .env.release 파일을 열고 실제 운영용 값을 채우세요.", script)
        self.assertIn("GitHub에 올리지 마세요.", script)
        self.assertIn("추가함:", script)
        self.assertNotIn("Next: open", script)
        self.assertNotIn("Do not commit", script)


if __name__ == "__main__":
    unittest.main()
