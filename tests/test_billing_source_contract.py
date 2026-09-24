"""OUT: legacy source-text assertion, excluded from A2 execution."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BillingSourceContractTest(unittest.TestCase):
    def test_google_play_purchase_code_does_not_claim_subscription_verification_is_missing(self):
        code = (ROOT / "backend" / "core" / "access_control.py").read_text(encoding="utf-8")

        self.assertIn("def _verify_google_play_subscription", code)
        self.assertNotIn("Google Play subscription verification is not implemented yet", code)


if __name__ == "__main__":
    unittest.main()
