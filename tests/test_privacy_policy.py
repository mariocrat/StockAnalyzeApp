import os
import unittest
from unittest.mock import patch

from backend.core.privacy_policy import account_deletion_html, privacy_policy_html


class PrivacyPolicyTest(unittest.TestCase):
    def test_policy_identifies_service_operator_and_privacy_officer(self):
        env = {
            "ALPHAMATE_PRIVACY_OPERATOR_NAME": "김건희",
            "ALPHAMATE_PRIVACY_CONTACT_EMAIL": "support@stockboda.co.kr",
        }

        with patch.dict(os.environ, env, clear=False):
            page = privacy_policy_html()

        self.assertIn("서비스명: 스톡보다(StockBoda)", page)
        self.assertIn("개인정보처리자 및 운영자: Orvetriq Labs", page)
        self.assertIn("Orvetriq Labs(이하", page)
        self.assertIn("개인정보 보호책임자", page)
        self.assertIn("성명: 김건희", page)
        self.assertIn("support@stockboda.co.kr", page)
        self.assertNotIn("support@alphamate.co.kr", page)
        self.assertNotIn("mariocrat", page)

    def test_account_deletion_page_uses_public_operator_brand(self):
        with patch.dict(
            os.environ,
            {"ALPHAMATE_PRIVACY_OPERATOR_NAME": "김건희"},
            clear=False,
        ):
            page = account_deletion_html()

        self.assertIn("운영자: Orvetriq Labs", page)
        self.assertNotIn("김건희", page)
        self.assertNotIn("mariocrat", page)


if __name__ == "__main__":
    unittest.main()
