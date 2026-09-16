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


class ReleaseEnvFileSetupDocsTest(unittest.TestCase):
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
