from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import sys
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
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
        modules = dict(sys.modules)
        namespace = dict(vars(sys.modules[__name__]))
        self.addCleanup(self._assert_restored, baseline, modules, namespace)
        fixture = self.enterContext(storage_fixture())
        self._case_container = fixture.root.parent

    def _assert_restored(self, baseline, modules, namespace):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path)), baseline)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is module for name, module in modules.items()))
        current = vars(sys.modules[__name__])
        self.assertEqual(set(current), set(namespace))
        self.assertTrue(all(current[name] is value for name, value in namespace.items()))
        container = self.__dict__.pop("_case_container", None)
        if container is not None:
            self.assertFalse(container.exists())

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
