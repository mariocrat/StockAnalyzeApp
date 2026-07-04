import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecretScanOutputTest(unittest.TestCase):
    def test_secret_scan_uses_korean_owner_messages(self):
        script = (ROOT / "scripts" / "check_no_tracked_secrets.py").read_text(encoding="utf-8")

        self.assertIn("Git 추적 파일에서 비밀값 패턴을 찾지 못했습니다.", script)
        self.assertIn("Git 추적 파일에서 비밀값으로 보이는 패턴을 찾았습니다:", script)
        self.assertNotIn("No tracked secret patterns found.", script)
        self.assertNotIn("Potential tracked secrets found:", script)


if __name__ == "__main__":
    unittest.main()
