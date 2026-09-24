from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

# Load the real BOM codec under A1 before per-case module snapshots.
import encodings.utf_8_sig
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OwnerFacingMessagesTest(unittest.TestCase):
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

    def test_release_owner_scripts_do_not_contain_mojibake_or_replacement_characters(self):
        paths = [
            ROOT / "backend" / "core" / "release_check.py",
            ROOT / "backend" / "scripts" / "validate_release_alignment.py",
            ROOT / "frontend" / "scripts" / "validate-release-env.js",
            ROOT / "scripts" / "verify_project.ps1",
            ROOT / "scripts" / "verify_android_debug.ps1",
            ROOT / "scripts" / "verify_android_release.ps1",
        ]

        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8-sig")
                self.assertNotIn("�", text)
                self.assertNotIn("占", text)
                self.assertFalse(
                    any(0x4E00 <= ord(char) <= 0x9FFF for char in text),
                    f"{path.relative_to(ROOT)} has CJK mojibake-like text",
                )


if __name__ == "__main__":
    unittest.main()
