import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_android_upload_key.py"
BATCH = ROOT / "generate_android_upload_key.bat"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_android_upload_key", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AndroidUploadKeyGenerationTest(unittest.TestCase):
    def test_double_click_batch_runs_android_upload_key_script_as_ascii_safe_wrapper(self):
        batch = BATCH.read_text(encoding="utf-8")

        self.assertIn("chcp 65001 >nul", batch)
        self.assertIn("scripts\\generate_android_upload_key.py", batch)
        self.assertIn("--create-key", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Preparing private Android upload signing key", batch)
        self.assertIn("Python virtual environment was not found", batch)
        self.assertIn("pause", batch.lower())


if __name__ == "__main__":
    unittest.main()
