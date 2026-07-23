import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException


class AccessControlPersistenceTest(unittest.TestCase):
    def test_first_oauth_login_advanced_ticket_is_granted_only_once(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {
            "ALPHAMATE_ACCESS_DB_PATH": os.path.join(tmpdir, "access.sqlite3"),
            "ALPHAMATE_ALLOW_DEV_ACCESS": "true",
        }):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            self.assertTrue(access_control.grant_first_login_advanced_review("dev-user"))
            self.assertFalse(access_control.grant_first_login_advanced_review("dev-user"))

            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            self.assertEqual(1, entitlements["advanced"]["signup_remaining"])

            access = access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )
            self.assertEqual("signup_advanced", access.source)
            self.assertEqual(0, access.quota["advanced"]["signup_remaining"])

    def test_advanced_review_without_ticket_returns_korean_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = db_path
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            from backend.core import access_control

            access_control = importlib.reload(access_control)
            with self.assertRaises(HTTPException) as raised:
                access_control.verify_ai_review_access(
                    authorization="Bearer dev-token",
                    ad_reward_token="",
                    entitlement_token="",
                    privacy_consent=True,
                    review_type="advanced",
                )

            self.assertEqual(402, raised.exception.status_code)
            self.assertIn("심화 복기 이용권이 필요합니다", raised.exception.detail)

    def test_rewarded_ads_can_be_claimed_toward_advanced_ticket(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {
            "ALPHAMATE_ACCESS_DB_PATH": os.path.join(tmpdir, "access.sqlite3"),
            "ALPHAMATE_ALLOW_DEV_ACCESS": "true",
            "ALPHAMATE_ADS_PER_ADVANCED_TICKET": "2",
        }):
            from backend.core import access_control

            access_control = importlib.reload(access_control)
            first = access_control.claim_rewarded_ad_progress(
                authorization="Bearer dev-token",
                entitlement_token="",
                ad_reward_token="dev-ad-reward",
            )
            second = access_control.claim_rewarded_ad_progress(
                authorization="Bearer dev-token",
                entitlement_token="",
                ad_reward_token="dev-ad-reward",
            )
            blocked = access_control.claim_rewarded_ad_progress(
                authorization="Bearer dev-token",
                entitlement_token="",
                ad_reward_token="dev-ad-reward",
            )

            self.assertTrue(first["ad_reward"]["claimed"])
            self.assertFalse(first["ad_reward"]["advanced_ticket_granted"])
            self.assertEqual(1, first["advanced"]["weekly_ad_views"])
            self.assertTrue(second["ad_reward"]["advanced_ticket_granted"])
            self.assertEqual(1, second["advanced"]["weekly_reward_remaining"])
            self.assertFalse(blocked["ad_reward"]["claimed"])
            self.assertEqual("ticket_already_held", blocked["ad_reward"]["blocked_reason"])
            self.assertEqual(second["advanced"]["weekly_ad_views"], blocked["advanced"]["weekly_ad_views"])

    def test_purchased_advanced_credits_survive_module_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "access.sqlite3")
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = db_path
            os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

            from backend.core import access_control

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_5",
            )
            access_control.verify_ai_review_access(
                authorization="Bearer dev-token",
                ad_reward_token="",
                entitlement_token="",
                privacy_consent=True,
                review_type="advanced",
            )

            access_control = importlib.reload(access_control)
            entitlements = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )

            self.assertEqual(4, entitlements["advanced"]["purchased_remaining"])


if __name__ == "__main__":
    unittest.main()
