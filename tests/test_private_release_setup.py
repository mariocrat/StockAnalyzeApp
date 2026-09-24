from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "prepare_private_release_setup.bat"


class PrivateReleaseSetupTest(unittest.TestCase):
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

    def test_double_click_batch_runs_private_release_setup_steps_in_order(self):
        batch = BATCH.read_text(encoding="utf-8")

        expected_order = [
            "scripts\\create_release_env_files.py",
            "scripts\\generate_release_secrets.py --fill-empty",
            "scripts\\generate_android_upload_key.py --create-key",
            "backend\\scripts\\owner_release_report.py",
            "npm.cmd run --silent release:report",
            "backend\\scripts\\validate_release_alignment.py",
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
        self.assertNotIn('if "%BACKEND_REPORT_EXIT%"=="1" set SETUP_EXIT=1', batch)
        self.assertNotIn('if "%FRONTEND_REPORT_EXIT%"=="1" set SETUP_EXIT=1', batch)
        self.assertIn("exit /b 0", batch)
        self.assertIn("pause", batch.lower())
        self.assertIn("exit /b %SETUP_EXIT%", batch)
        self.assertNotIn("OPENAI_API_KEY=", batch)
        self.assertNotIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=", batch)

    def test_private_release_setup_reports_server_app_alignment_without_failing_setup(self):
        batch = BATCH.read_text(encoding="utf-8")

        self.assertTrue(batch.isascii())
        self.assertIn("Server/app release setting alignment", batch)
        self.assertIn("ALIGNMENT_REPORT_EXIT", batch)
        self.assertIn("backend\\scripts\\validate_release_alignment.py", batch)
        self.assertNotIn('if "%ALIGNMENT_REPORT_EXIT%"=="1" set SETUP_EXIT=1', batch)

    def test_private_release_setup_batch_is_ascii_safe_wrapper(self):
        batch = BATCH.read_text(encoding="utf-8")

        self.assertTrue(batch.isascii())
        self.assertIn("Preparing private release setup files", batch)
        self.assertIn("Korean details will be printed by the Python and npm scripts.", batch)
        self.assertIn("Private release setup finished, but some external values still need setup.", batch)


if __name__ == "__main__":
    unittest.main()
