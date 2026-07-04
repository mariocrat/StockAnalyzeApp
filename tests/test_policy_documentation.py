import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PolicyDocumentationTest(unittest.TestCase):
    def test_ai_monetization_plan_matches_ad_free_pro_policy(self):
        plan = (ROOT / "docs" / "ai_review_monetization_plan.md").read_text(encoding="utf-8")

        self.assertIn("Pro users do not see non-rewarded ads anywhere in the app.", plan)
        self.assertNotIn("Theme/ranking information screens can keep banner ads", plan)

    def test_ai_monetization_plan_mentions_current_admob_integration_status(self):
        plan = (ROOT / "docs" / "ai_review_monetization_plan.md").read_text(encoding="utf-8")

        self.assertIn("Mobile AdMob SDK integration is implemented", plan)
        self.assertNotIn("mobile AdMob SDK integration and production ad unit setup are still required", plan)

    def test_release_checklist_uses_korean_final_verification_labels(self):
        checklist = (ROOT / "docs" / "release_preparation_checklist.md").read_text(encoding="utf-8")

        self.assertIn("프론트 출시 설정 테스트", checklist)
        self.assertIn("Android 출시 AAB 빌드", checklist)
        self.assertIn("메모리 기반 요청 제한기 안전 상한", checklist)
        self.assertNotIn("frontend release-env tests", checklist)
        self.assertNotIn("Android release AAB build", checklist)
        self.assertNotIn("In-memory rate limiter safety cap", checklist)


if __name__ == "__main__":
    unittest.main()
