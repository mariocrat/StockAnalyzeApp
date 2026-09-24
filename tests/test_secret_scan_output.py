from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecretScanOutputTest(unittest.TestCase):
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

    def test_secret_scan_uses_korean_owner_messages(self):
        script = (ROOT / "scripts" / "check_no_tracked_secrets.py").read_text(encoding="utf-8")

        self.assertIn("Git 추적 파일에서 비밀값 패턴을 찾지 못했습니다.", script)
        self.assertIn("Git 추적 파일에서 비밀값으로 보이는 패턴을 찾았습니다:", script)
        self.assertNotIn("No tracked secret patterns found.", script)
        self.assertNotIn("Potential tracked secrets found:", script)


    def test_secret_scan_covers_release_credential_patterns(self):
        script = (ROOT / "scripts" / "check_no_tracked_secrets.py").read_text(encoding="utf-8")

        self.assertIn("OpenAI API key", script)
        self.assertIn("Google/Gemini API key", script)
        self.assertIn("AIza", script)
        self.assertIn("Google private key block", script)
        self.assertIn("Google service account JSON", script)
        self.assertIn("hard-coded password assignment", script)
        self.assertIn("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", script)
        self.assertIn("PRIVATE KEY", script)

if __name__ == "__main__":
    unittest.main()
