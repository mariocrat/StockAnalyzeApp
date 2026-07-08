import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OwnerFacingMessagesTest(unittest.TestCase):
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