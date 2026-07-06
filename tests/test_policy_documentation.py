import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PolicyDocumentationTest(unittest.TestCase):
    def test_ai_monetization_plan_matches_ad_free_pro_policy(self):
        plan = (ROOT / "docs" / "ai_review_monetization_plan.md").read_text(encoding="utf-8")

        self.assertIn("Pro 사용자는 앱 전체에서 보상형이 아닌 광고를 보지 않는다.", plan)
        self.assertNotIn("테마 상승률 등 정보 화면에는 배너 광고를 유지", plan)

    def test_ai_monetization_plan_mentions_current_admob_integration_status(self):
        plan = (ROOT / "docs" / "ai_review_monetization_plan.md").read_text(encoding="utf-8")

        self.assertIn("모바일 AdMob SDK는 보상형, 전면, 배너 광고가 연결되어 있다.", plan)
        self.assertNotIn("mobile AdMob SDK integration and production ad unit setup are still required", plan)

    def test_security_docs_match_current_admob_sdk_status(self):
        manual = (ROOT / "docs" / "manual_test_guide.md").read_text(encoding="utf-8")
        security = (ROOT / "docs" / "security_deployment_plan.md").read_text(encoding="utf-8")

        self.assertIn("모바일 앱에는 AdMob SDK가 연결되어 있습니다", manual)
        self.assertIn("모바일 앱에는 AdMob SDK가 연결되어 있다", security)
        self.assertNotIn("모바일 앱 SDK 연결이 필요", manual)
        self.assertNotIn("AdMob SDK, 보상형 광고 단위, SSV 콜백 URL", security)

    def test_ad_display_policy_explains_resume_interstitial_instead_of_app_open_format(self):
        policy = (ROOT / "docs" / "development_history_ad_display_policy.md").read_text(encoding="utf-8")

        self.assertIn("별도 App Open Ad 포맷이 아니라 앱 복귀 전면 광고로 운영한다", policy)
        self.assertIn("90초 이상", policy)
        self.assertIn("10분 쿨타임", policy)

    def test_ai_monetization_plan_uses_clean_korean_labels(self):
        plan = (ROOT / "docs" / "ai_review_monetization_plan.md").read_text(encoding="utf-8")

        self.assertIn("일반 복기권 30회", plan)
        self.assertIn("심층 복기권 10회", plan)
        for broken_text in (chr(0x3F) + "쇰컲", chr(0x3F) + "ъ링"):
            self.assertNotIn(broken_text, plan)
        self.assertFalse(any(0x4E00 <= ord(char) <= 0x9FFF for char in plan))

    def test_release_checklist_uses_korean_final_verification_labels(self):
        checklist = (ROOT / "docs" / "release_preparation_checklist.md").read_text(encoding="utf-8")

        self.assertIn("프론트 출시 설정 테스트", checklist)
        self.assertIn("프론트 스플래시 로딩 정책 테스트", checklist)
        self.assertIn("Android 출시 AAB 빌드", checklist)
        self.assertIn("메모리 기반 요청 제한기 안전 상한", checklist)
        self.assertNotIn("frontend release-env tests", checklist)
        self.assertNotIn("Android release AAB build", checklist)
        self.assertNotIn("In-memory rate limiter safety cap", checklist)

    def test_release_checklist_lists_every_project_verification_step(self):
        script = (ROOT / "scripts" / "verify_project.ps1").read_text(encoding="utf-8-sig")
        checklist = (ROOT / "docs" / "release_preparation_checklist.md").read_text(encoding="utf-8")

        step_names = re.findall(r'Run-Step "([^"]+)"', script)

        self.assertGreater(len(step_names), 0)
        for step_name in step_names:
            with self.subTest(step=step_name):
                self.assertIn(step_name, checklist)

    def test_recent_development_history_notes_do_not_contain_broken_korean(self):
        paths = [
            ROOT / "docs" / "development_history_ad_failure_logging.md",
            ROOT / "docs" / "development_history_private_setup_alignment.md",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("#", text)
            for broken_text in (chr(0x3F) + "댁", chr(0x3F) + "쒕", chr(0x3F) + "ㅼ"):
                self.assertNotIn(broken_text, text, f"{path.name} has broken Korean text")
            self.assertFalse(
                any(0x4E00 <= ord(char) <= 0x9FFF for char in text),
                f"{path.name} has CJK mojibake-like text",
            )


if __name__ == "__main__":
    unittest.main()
