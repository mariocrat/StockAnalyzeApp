import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BatchWrapperTest(unittest.TestCase):
    def test_root_batch_wrappers_are_ascii_safe_for_cmd(self):
        for path in ROOT.glob("*.bat"):
            with self.subTest(batch=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.isascii(), f"{path.name} should leave Korean output to PowerShell/Python")


if __name__ == "__main__":
    unittest.main()
