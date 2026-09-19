from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import sys
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
