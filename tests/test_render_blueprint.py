import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "render.yaml"


class RenderBlueprintTest(unittest.TestCase):
    def test_render_blueprint_defines_starter_web_service(self):
        text = RENDER.read_text(encoding="utf-8")

        self.assertIn("name: alphamate-api", text)
        self.assertIn("type: web", text)
        self.assertIn("runtime: python", text)
        self.assertIn("plan: starter", text)
        self.assertIn("region: singapore", text)
        self.assertIn("buildCommand: pip install -r requirements.txt", text)
        self.assertIn("startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT", text)
        self.assertIn("healthCheckPath: /healthz", text)
        self.assertRegex(text, r"key: ALPHAMATE_WARM_CACHE_ON_STARTUP\n\s+value: false")
        self.assertIn("key: ALPHAMATE_CACHE_DIR", text)
        self.assertIn("value: /var/data/alphamate/cache", text)
        self.assertRegex(text, r"key: ALPHAMATE_THEME_FETCH_WORKERS\n\s+value: 8")

    def test_render_blueprint_mounts_one_persistent_disk_for_sqlite(self):
        text = RENDER.read_text(encoding="utf-8")

        self.assertIn("name: alphamate-data", text)
        self.assertIn("mountPath: /var/data/alphamate", text)
        self.assertRegex(text, r"sizeGB:\s*[1-9]")
        for db_name in (
            "accounts.sqlite3",
            "access.sqlite3",
            "trades.sqlite3",
            "review_history.sqlite3",
            "event_log.sqlite3",
        ):
            with self.subTest(db_name=db_name):
                self.assertIn(f"value: /var/data/alphamate/{db_name}", text)

    def test_render_blueprint_keeps_secrets_out_of_git(self):
        text = RENDER.read_text(encoding="utf-8")

        for key in (
            "OPENAI_API_KEY",
            "KAKAO_CLIENT_SECRET",
            "NAVER_CLIENT_SECRET",
            "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
        ):
            with self.subTest(key=key):
                self.assertRegex(text, rf"key: {key}\n\s+sync: false")
                self.assertNotRegex(text, rf"key: {key}\n\s+value: .+")

        for key in ("ALPHAMATE_ADMIN_TOKEN", "GOOGLE_PLAY_RTDN_SHARED_TOKEN"):
            with self.subTest(key=key):
                self.assertRegex(text, rf"key: {key}\n\s+generateValue: true")

        self.assertNotIn("sk-", text)
        self.assertNotIn("BEGIN PRIVATE KEY", text)
        self.assertNotIn("KAKAO_CLIENT_SECRET=", text)

    def test_render_blueprint_uses_confirmed_production_urls(self):
        text = RENDER.read_text(encoding="utf-8")

        expected_values = (
            "https://api.alphamate.co.kr",
            "https://alphamate.co.kr",
            "https://api.alphamate.co.kr/privacy",
            "https://api.alphamate.co.kr/api/auth/kakao/callback",
            "https://api.alphamate.co.kr/api/auth/naver/callback",
            "https://api.alphamate.co.kr/api/journal/google-play-rtdn",
            "com.mariocrat.stockanalyze",
        )
        for value in expected_values:
            with self.subTest(value=value):
                self.assertIn(value, text)

    def test_render_blueprint_publishes_confirmed_privacy_contact(self):
        text = RENDER.read_text(encoding="utf-8")

        self.assertRegex(text, r"key: ALPHAMATE_PRIVACY_OPERATOR_NAME\n\s+value: 김건희")
        self.assertRegex(
            text,
            r"key: ALPHAMATE_PRIVACY_CONTACT_EMAIL\n\s+value: support@alphamate\.co\.kr",
        )

    def test_env_example_mentions_render_blueprint_without_real_secrets(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("Render Blueprint", text)
        self.assertIn("/var/data/alphamate/accounts.sqlite3", text)
        self.assertIn("ALPHAMATE_WARM_CACHE_ON_STARTUP=false", text)
        self.assertIn("https://api.alphamate.co.kr", text)
        self.assertNotIn("actual_openai_key", text)

    def test_render_setup_guide_is_written_for_non_developers(self):
        text = (ROOT / "docs" / "render_deployment_guide.md").read_text(encoding="utf-8")

        for phrase in (
            "Blueprint",
            "New Blueprint Instance",
            "비밀값",
            "OPENAI_API_KEY",
            "Deploy",
            "Postgres 전환 검토 기준",
            "database is locked",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
