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
            self.assertEqual("ALPHAMATE_ENV=production\n", (root / ".env.release").read_text(encoding="utf-8"))
            self.assertEqual(
                "VITE_ALPHAMATE_ENV=production\n",
                (root / "frontend" / ".env.release").read_text(encoding="utf-8"),
            )

    def test_does_not_overwrite_existing_private_release_env_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / ".env.release.example").write_text("ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / "frontend" / ".env.release.example").write_text("VITE_ALPHAMATE_ENV=production\n", encoding="utf-8")
            (root / ".env.release").write_text("KEEP_BACKEND_SECRET=1\n", encoding="utf-8")
            (root / "frontend" / ".env.release").write_text("KEEP_FRONTEND_SECRET=1\n", encoding="utf-8")

            result = module.create_release_env_files(root)

            self.assertEqual(0, result["created"])
            self.assertEqual(2, result["skipped"])
            self.assertEqual("KEEP_BACKEND_SECRET=1\n", (root / ".env.release").read_text(encoding="utf-8"))
            self.assertEqual(
                "KEEP_FRONTEND_SECRET=1\n",
                (root / "frontend" / ".env.release").read_text(encoding="utf-8"),
            )

    def test_double_click_batch_runs_release_env_setup_script(self):
        batch = (ROOT / "prepare_release_env_files.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\create_release_env_files.py", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertIn("pause", batch.lower())


if __name__ == "__main__":
    unittest.main()
