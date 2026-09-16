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


class BackendReleaseCheckDocsTest(unittest.TestCase):
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
            "GOOGLE_PLAY_BASIC_REVIEW_15_ID",
            "GOOGLE_PLAY_BASIC_REVIEW_25_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_10_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_20_ID",
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
            "ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_BILLING_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_CALLBACK_RATE_LIMIT_PER_MINUTE",
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
            "ALPHAMATE_OAUTH_APP_SCHEME",
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
            "OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL",
            "KAKAO_CLIENT_ID",
            "KAKAO_CLIENT_SECRET",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
            "GOOGLE_PLAY_PACKAGE_NAME",
            "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE",
            "GOOGLE_PLAY_BASIC_REVIEW_15_ID",
            "GOOGLE_PLAY_BASIC_REVIEW_25_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_10_ID",
            "GOOGLE_PLAY_ADVANCED_REVIEW_20_ID",
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
            "ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_BILLING_RATE_LIMIT_PER_MINUTE",
            "ALPHAMATE_CALLBACK_RATE_LIMIT_PER_MINUTE",
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
            "ALPHAMATE_OAUTH_APP_SCHEME",
        ]

        for name in required_names:
            self.assertIn(name, template)
        self.assertIn("OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL=gpt-5.4-mini", template)
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
            "*.pem",
            "*.p12",
            "*.key",
            "*service-account*.json",
            "google-play*.json",
            "release-private/",
            "*.apk",
            "*.aab",
            "*.apks",
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
        self.assertTrue(script.isascii())
        self.assertIn("Server/app release setting alignment", script)
        self.assertIn("Backend release readiness", script)
        self.assertIn("Frontend/Android release readiness", script)
        self.assertIn("validate_release_alignment.py", script)
        self.assertIn("ALPHAMATE_NO_PAUSE", script)
        self.assertIn("if not \"%ALPHAMATE_NO_PAUSE%\"==\"1\" pause", script)



if __name__ == "__main__":
    unittest.main()
