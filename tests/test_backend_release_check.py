import json
import os
import tempfile
import unittest
from contextlib import contextmanager

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def fake_service_account_json() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return json.dumps({
        "type": "service_account",
        "client_email": "play-api@example.iam.gserviceaccount.com",
        "private_key": private_key,
        "token_uri": "https://oauth2.googleapis.com/token",
    })


@contextmanager
def patched_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class BackendReleaseCheckTest(unittest.TestCase):
    def test_backend_env_example_documents_release_check_settings(self):
        with open(".env.example", encoding="utf-8") as env_file:
            example = env_file.read()

        required_names = [
            "ALPHAMATE_ENV",
            "OPENAI_API_KEY",
            "KAKAO_CLIENT_ID",
            "KAKAO_CLIENT_SECRET",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
            "GOOGLE_PLAY_PACKAGE_NAME",
            "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
            "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE",
            "GOOGLE_PLAY_BASIC_REVIEW_30_ID",
            "GOOGLE_PLAY_BASIC_REVIEW_100_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_5_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_10_ID",
            "GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID",
            "GOOGLE_PLAY_PRO_MONTHLY_ID",
            "ADMOB_REWARDED_AD_UNIT_ID",
            "ALPHAMATE_PRIVACY_POLICY_URL",
            "ALPHAMATE_ACCOUNT_DB_PATH",
            "ALPHAMATE_JOURNAL_DB_PATH",
            "ALPHAMATE_ACCESS_DB_PATH",
            "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
            "ALPHAMATE_EVENT_LOG_DB_PATH",
            "ALPHAMATE_CORS_ORIGINS",
            "ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_AI_REVIEW_MAX_CONCURRENT",
            "ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS",
            "ALPHAMATE_JOURNAL_ONCE_MAX_TRADES",
            "ALPHAMATE_AI_REVIEW_MAX_TRADES",
            "ALPHAMATE_JOURNAL_MEMO_MAX_CHARS",
            "ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT",
            "ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES",
            "ALPHAMATE_OPENAI_TIMEOUT_SECONDS",
            "ALPHAMATE_OPENAI_MAX_RETRIES",
            "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
            "ALPHAMATE_OAUTH_TIMEOUT_SECONDS",
        ]

        for name in required_names:
            self.assertIn(name, example)

    def test_backend_release_env_template_is_production_focused(self):
        with open(".env.release.example", encoding="utf-8") as env_file:
            template = env_file.read()

        required_names = [
            "ALPHAMATE_ENV=production",
            "OPENAI_API_KEY",
            "OPENAI_BASIC_REVIEW_MODEL",
            "OPENAI_ADVANCED_REVIEW_MODEL",
            "KAKAO_CLIENT_ID",
            "KAKAO_CLIENT_SECRET",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
            "GOOGLE_PLAY_PACKAGE_NAME",
            "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE",
            "GOOGLE_PLAY_BASIC_REVIEW_30_ID",
            "GOOGLE_PLAY_BASIC_REVIEW_100_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_5_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_10_ID",
            "GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID",
            "GOOGLE_PLAY_PRO_MONTHLY_ID",
            "ADMOB_REWARDED_AD_UNIT_ID",
            "ALPHAMATE_PRIVACY_POLICY_URL",
            "ALPHAMATE_ACCOUNT_DB_PATH",
            "ALPHAMATE_JOURNAL_DB_PATH",
            "ALPHAMATE_ACCESS_DB_PATH",
            "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
            "ALPHAMATE_EVENT_LOG_DB_PATH",
            "ALPHAMATE_ADMIN_TOKEN",
            "ALPHAMATE_CORS_ORIGINS",
            "ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_AI_REVIEW_MAX_CONCURRENT",
            "ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS",
            "ALPHAMATE_JOURNAL_ONCE_MAX_TRADES",
            "ALPHAMATE_AI_REVIEW_MAX_TRADES",
            "ALPHAMATE_JOURNAL_MEMO_MAX_CHARS",
            "ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT",
            "ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES",
            "ALPHAMATE_OPENAI_TIMEOUT_SECONDS",
            "ALPHAMATE_OPENAI_MAX_RETRIES",
            "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
            "ALPHAMATE_OAUTH_TIMEOUT_SECONDS",
        ]

        for name in required_names:
            self.assertIn(name, template)
        self.assertNotIn("ALPHAMATE_ALLOW_DEV_ACCESS", template)
        self.assertNotIn("ALPHAMATE_DEV_AUTH_TOKEN", template)

    def test_gitignore_blocks_filled_release_env_files(self):
        with open(".gitignore", encoding="utf-8") as gitignore_file:
            gitignore = gitignore_file.read()

        ignored_names = [
            ".env.local",
            ".env.release",
            ".env.release.local",
            ".env.production",
            ".env.production.local",
        ]

        for name in ignored_names:
            self.assertIn(name, gitignore)

    def test_release_readiness_report_uses_release_env_files_when_present(self):
        with open("release_readiness_report.bat", encoding="utf-8") as report_file:
            script = report_file.read()

        self.assertIn(".env.release", script)
        self.assertIn("ALPHAMATE_ENV_FILE", script)
        self.assertIn("ALPHAMATE_FRONTEND_ENV_FILE", script)
        self.assertIn("frontend\\.env.release", script)

    def test_format_owner_release_readiness_report_hides_secret_values(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [
                "ai: OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY",
                "admin: ALPHAMATE_ADMIN_TOKEN_MIN_LENGTH_32",
            ],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "ai": {
                        "ready": False,
                        "missing_server_settings": ["OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY"],
                        "required_server_settings": ["OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY"],
                    },
                    "admin": {
                        "ready": False,
                        "missing_server_settings": ["ALPHAMATE_ADMIN_TOKEN_MIN_LENGTH_32"],
                        "required_server_settings": ["ALPHAMATE_ADMIN_TOKEN"],
                    },
                    "privacy_policy": {
                        "ready": True,
                        "missing_server_settings": [],
                        "required_server_settings": ["ALPHAMATE_PRIVACY_POLICY_URL"],
                    },
                },
            },
        })

        self.assertIn("AlphaMate 출시 준비 보고서", report)
        self.assertIn("[필요] AI 복기", report)
        self.assertIn("[준비됨] 개인정보처리방침", report)
        self.assertIn("준비율: 1/3 (33%)", report)
        self.assertIn("OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY", report)
        self.assertIn("다음에 할 일", report)
        self.assertNotIn("sk-", report)
        self.assertNotIn("secret", report.lower())

    def test_rejects_missing_production_backend_settings_without_secret_values(self):
        with patched_env(
            ALPHAMATE_ENV="development",
            OPENAI_API_KEY=None,
            ALPHAMATE_OPENAI_API_KEY=None,
            KAKAO_CLIENT_ID=None,
            KAKAO_CLIENT_SECRET=None,
            NAVER_CLIENT_ID=None,
            NAVER_CLIENT_SECRET=None,
            GOOGLE_PLAY_PACKAGE_NAME=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=None,
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
            ADMOB_REWARDED_AD_UNIT_ID=None,
            ALPHAMATE_PRIVACY_POLICY_URL=None,
            ALPHAMATE_ACCOUNT_DB_PATH=None,
            ALPHAMATE_JOURNAL_DB_PATH=None,
            ALPHAMATE_ACCESS_DB_PATH=None,
            ALPHAMATE_REVIEW_HISTORY_DB_PATH=None,
            ALPHAMATE_EVENT_LOG_DB_PATH=None,
            ALPHAMATE_ADMIN_TOKEN=None,
        ):
            from backend.core.release_check import format_backend_release_check, validate_backend_release_env

            result = validate_backend_release_env()
            formatted = format_backend_release_check(result)

            self.assertFalse(result["ok"])
            self.assertIn("ALPHAMATE_ENV must be production", result["errors"])
            self.assertIn("OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY", "\n".join(result["errors"]))
            self.assertIn("GOOGLE_PLAY_PACKAGE_NAME", "\n".join(result["errors"]))
            self.assertIn("ADMOB_REWARDED_AD_UNIT_ID", "\n".join(result["errors"]))
            self.assertIn("ALPHAMATE_PRIVACY_POLICY_URL", "\n".join(result["errors"]))
            self.assertIn("ALPHAMATE_ACCOUNT_DB_PATH", "\n".join(result["errors"]))
            self.assertIn("ALPHAMATE_REVIEW_HISTORY_DB_PATH", "\n".join(result["errors"]))
            self.assertIn("ALPHAMATE_EVENT_LOG_DB_PATH", "\n".join(result["errors"]))
            self.assertIn("ALPHAMATE_ADMIN_TOKEN", "\n".join(result["errors"]))
            self.assertNotIn("sk-", formatted)
            self.assertNotIn("google-secret-json", formatted)

    def test_accepts_complete_production_backend_settings(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            OPENAI_API_KEY="sk-test-secret",
            KAKAO_CLIENT_ID="kakao-client",
            KAKAO_CLIENT_SECRET="kakao-secret",
            NAVER_CLIENT_ID="naver-client",
            NAVER_CLIENT_SECRET="naver-secret",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.basic.100",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-token-with-at-least-32-characters",
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_PRIVACY_POLICY_URL="https://alphamate.example/privacy",
            ALPHAMATE_ACCOUNT_DB_PATH="D:/secure/alphamate/accounts.sqlite3",
            ALPHAMATE_JOURNAL_DB_PATH="D:/secure/alphamate/trades.sqlite3",
            ALPHAMATE_ACCESS_DB_PATH="D:/secure/alphamate/access.sqlite3",
            ALPHAMATE_REVIEW_HISTORY_DB_PATH="D:/secure/alphamate/review-history.sqlite3",
            ALPHAMATE_EVENT_LOG_DB_PATH="D:/secure/alphamate/events.sqlite3",
            ALPHAMATE_ADMIN_TOKEN="admin-token-with-at-least-32-characters",
        ):
            from backend.core.release_check import format_backend_release_check, validate_backend_release_env

            result = validate_backend_release_env()
            formatted = format_backend_release_check(result)

            self.assertTrue(result["ok"])
            self.assertEqual([], result["errors"])
            self.assertIn("Backend release environment check passed.", formatted)
            self.assertNotIn("sk-test-secret", formatted)
            self.assertNotIn("PRIVATE KEY", formatted)

    def test_accepts_complete_settings_from_explicit_env_file(self):
        env_text = "\n".join([
            "ALPHAMATE_ENV=production",
            "OPENAI_API_KEY=sk-env-file-secret",
            "KAKAO_CLIENT_ID=kakao-client",
            "KAKAO_CLIENT_SECRET=kakao-secret",
            "NAVER_CLIENT_ID=naver-client",
            "NAVER_CLIENT_SECRET=naver-secret",
            "GOOGLE_PLAY_PACKAGE_NAME=com.alphamate.app",
            f"GOOGLE_PLAY_SERVICE_ACCOUNT_JSON={fake_service_account_json()}",
            "GOOGLE_PLAY_BASIC_REVIEW_30_ID=alphamate.basic.30",
            "GOOGLE_PLAY_BASIC_REVIEW_100_ID=alphamate.basic.100",
            "GOOGLE_PLAY_ADVANCED_REVIEW_5_ID=alphamate.advanced.5",
            "GOOGLE_PLAY_ADVANCED_REVIEW_10_ID=alphamate.advanced.10",
            "GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID=alphamate.pro.launch",
            "GOOGLE_PLAY_PRO_MONTHLY_ID=alphamate.pro.monthly",
            "GOOGLE_PLAY_RTDN_SHARED_TOKEN=rtdn-token-with-at-least-32-characters",
            "ADMOB_REWARDED_AD_UNIT_ID=rewarded-unit-1",
            "ALPHAMATE_PRIVACY_POLICY_URL=https://alphamate.example/privacy",
            "ALPHAMATE_ACCOUNT_DB_PATH=D:/secure/alphamate/accounts.sqlite3",
            "ALPHAMATE_JOURNAL_DB_PATH=D:/secure/alphamate/trades.sqlite3",
            "ALPHAMATE_ACCESS_DB_PATH=D:/secure/alphamate/access.sqlite3",
            "ALPHAMATE_REVIEW_HISTORY_DB_PATH=D:/secure/alphamate/review-history.sqlite3",
            "ALPHAMATE_EVENT_LOG_DB_PATH=D:/secure/alphamate/events.sqlite3",
            "ALPHAMATE_ADMIN_TOKEN=admin-token-with-at-least-32-characters",
        ])
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", delete=False) as env_file:
            env_file.write(env_text)
            env_path = env_file.name

        try:
            with patched_env(
                ALPHAMATE_ENV_FILE=env_path,
                ALPHAMATE_ENV=None,
                OPENAI_API_KEY=None,
                ALPHAMATE_OPENAI_API_KEY=None,
                KAKAO_CLIENT_ID=None,
                KAKAO_CLIENT_SECRET=None,
                NAVER_CLIENT_ID=None,
                NAVER_CLIENT_SECRET=None,
                GOOGLE_PLAY_PACKAGE_NAME=None,
                GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=None,
                GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
                GOOGLE_PLAY_BASIC_REVIEW_30_ID=None,
                GOOGLE_PLAY_BASIC_REVIEW_100_ID=None,
                GOOGLE_PLAY_ADVANCED_REVIEW_5_ID=None,
                GOOGLE_PLAY_ADVANCED_REVIEW_10_ID=None,
                GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID=None,
                GOOGLE_PLAY_PRO_MONTHLY_ID=None,
                ADMOB_REWARDED_AD_UNIT_ID=None,
                ALPHAMATE_PRIVACY_POLICY_URL=None,
                ALPHAMATE_ACCOUNT_DB_PATH=None,
                ALPHAMATE_JOURNAL_DB_PATH=None,
                ALPHAMATE_ACCESS_DB_PATH=None,
                ALPHAMATE_REVIEW_HISTORY_DB_PATH=None,
                ALPHAMATE_EVENT_LOG_DB_PATH=None,
            ):
                from backend.core.release_check import format_backend_release_check, validate_backend_release_env

                result = validate_backend_release_env()
                formatted = format_backend_release_check(result)

                self.assertTrue(result["ok"])
                self.assertEqual([], result["errors"])
                self.assertNotIn("sk-env-file-secret", formatted)
                self.assertNotIn("PRIVATE KEY", formatted)
        finally:
            os.unlink(env_path)


if __name__ == "__main__":
    unittest.main()
