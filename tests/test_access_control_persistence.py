import importlib
import os
import tempfile
import unittest


class AccessControlPersistenceTest(unittest.TestCase):
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
