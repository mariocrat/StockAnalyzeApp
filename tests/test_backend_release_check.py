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
            "release-private/",
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
        self.assertIn("서버/앱 출시 설정 일치 검사", script)
        self.assertIn("서버 출시 준비 상태", script)
        self.assertIn("프론트/Android 출시 준비 상태", script)
        self.assertIn("validate_release_alignment.py", script)

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
                    "cors": {
                        "ready": False,
                        "missing_server_settings": ["ALPHAMATE_CORS_ORIGINS_PLACEHOLDER"],
                        "required_server_settings": ["ALPHAMATE_CORS_ORIGINS"],
                    },
                    "privacy_policy": {
                        "ready": False,
                        "missing_server_settings": ["ALPHAMATE_PRIVACY_POLICY_URL_PLACEHOLDER"],
                        "required_server_settings": ["ALPHAMATE_PRIVACY_POLICY_URL"],
                    },
                    "google_play": {
                        "ready": False,
                        "missing_server_settings": [
                            "GOOGLE_PLAY_RTDN_SHARED_TOKEN",
                            "GOOGLE_PLAY_PRODUCT_ID_DUPLICATE: alphamate.duplicate",
                            "GOOGLE_PLAY_RTDN_OIDC_AUDIENCE_PLACEHOLDER",
                            "GOOGLE_PLAY_RTDN_OIDC_EMAIL_PLACEHOLDER",
                        ],
                        "required_server_settings": ["GOOGLE_PLAY_RTDN_SHARED_TOKEN"],
                    },
                    "admob": {
                        "ready": False,
                        "missing_server_settings": ["ADMOB_REWARDED_AD_UNIT_ID_PLACEHOLDER"],
                        "required_server_settings": ["ADMOB_REWARDED_AD_UNIT_ID"],
                    },
                },
            },
        })

        self.assertIn("AlphaMate 출시 준비 보고서", report)
        self.assertIn("[필요] AI 복기", report)
        self.assertIn("[필요] 개인정보처리방침", report)
        self.assertIn("준비율: 0/6 (0%)", report)
        self.assertIn("OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY", report)
        self.assertIn("OpenAI API Key를 발급해서 서버 설정에 넣기", report)
        self.assertIn("https://platform.openai.com/api-keys", report)
        self.assertIn("generate_release_secrets.bat를 실행해서 운영 로그 관리자 토큰 빈 값을 채우기", report)
        self.assertIn("운영 웹/앱 API 허용 주소를 실제 배포 주소로 바꾸기", report)
        self.assertIn("공개 개인정보처리방침 HTTPS 주소로 바꾸기", report)
        self.assertIn("AdMob 운영 보상형 광고 단위 ID로 바꾸기", report)
        self.assertIn("generate_release_secrets.bat를 실행해서 Google Play 결제 알림용 공유 토큰 빈 값을 채우기", report)
        self.assertIn("Google Play Console 상품 ID가 서로 겹치지 않게 바꾸기", report)
        self.assertIn("Google Play RTDN OIDC audience를 운영 웹훅 주소로 바꾸기", report)
        self.assertIn("Google Play RTDN OIDC email을 실제 Pub/Sub push 서비스 계정으로 바꾸기", report)
        self.assertIn("다음에 할 일", report)
        self.assertIn("내가 나중에 받아야 하는 정보/파일", report)
        self.assertIn("OpenAI API Key 값", report)
        self.assertIn("운영 웹/앱 API 허용 주소", report)
        self.assertIn("개인정보처리방침 공개 HTTPS 주소", report)
        self.assertIn("Google Play Console 상품 ID 목록", report)
        self.assertIn("AdMob 보상형 광고 단위 ID", report)
        self.assertNotIn("Google Play 결제 알림용 공유 토큰 값", report)
        self.assertNotIn("sk-", report)
        self.assertNotIn("google-secret-json", report)

    def test_owner_release_report_shows_top_level_release_errors(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": ["ALPHAMATE_ENV must be production"],
            "readiness": {
                "overall_ready": False,
                "sections": {},
            },
        })

        self.assertIn("ALPHAMATE_ENV must be production", report)
        self.assertIn("운영 모드", report)

    def test_owner_release_report_explains_missing_oauth_redirect_uri_inputs(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [
                "login.kakao: KAKAO_REDIRECT_URI",
                "login.naver: NAVER_REDIRECT_URI",
            ],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "login": {
                        "ready": False,
                        "providers": {
                            "kakao": {
                                "server_ready": False,
                                "missing_server_settings": ["KAKAO_REDIRECT_URI"],
                            },
                            "naver": {
                                "server_ready": False,
                                "missing_server_settings": ["NAVER_REDIRECT_URI"],
                            },
                        },
                    },
                },
            },
        })

        self.assertIn("카카오 Redirect URI", report)
        self.assertIn("네이버 Redirect URI", report)
        self.assertIn("KAKAO_REDIRECT_URI", report)
        self.assertIn("NAVER_REDIRECT_URI", report)

    def test_owner_release_report_explains_unsafe_data_storage_paths(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "data_storage": {
                        "ready": False,
                        "missing_server_settings": [
                            "ALPHAMATE_ACCOUNT_DB_PATH_LOCAL_DEV_PATH",
                            "ALPHAMATE_JOURNAL_DB_PATH_ABSOLUTE_PATH",
                        ],
                        "required_server_settings": ["ALPHAMATE_ACCOUNT_DB_PATH", "ALPHAMATE_JOURNAL_DB_PATH"],
                    },
                },
            },
        })

        self.assertIn("운영 데이터 DB 경로를 백업 가능한 서버 절대 경로로 바꾸기", report)
        self.assertIn("운영 데이터 DB 절대 경로", report)
        self.assertNotIn("backend/data/accounts.sqlite3", report)

    def test_owner_release_report_explains_missing_data_storage_path_inputs(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "data_storage": {
                        "ready": False,
                        "missing_server_settings": [
                            "ALPHAMATE_ACCOUNT_DB_PATH",
                            "ALPHAMATE_JOURNAL_DB_PATH",
                            "ALPHAMATE_ACCESS_DB_PATH",
                            "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
                            "ALPHAMATE_EVENT_LOG_DB_PATH",
                        ],
                        "required_server_settings": [
                            "ALPHAMATE_ACCOUNT_DB_PATH",
                            "ALPHAMATE_JOURNAL_DB_PATH",
                            "ALPHAMATE_ACCESS_DB_PATH",
                            "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
                            "ALPHAMATE_EVENT_LOG_DB_PATH",
                        ],
                    },
                },
            },
        })

        self.assertIn("계정 DB", report)
        self.assertIn("매매 기록 DB", report)
        self.assertIn("복기 보관함 DB", report)
        self.assertIn("운영 로그 DB", report)
        self.assertIn("ALPHAMATE_ACCOUNT_DB_PATH", report)

    def test_owner_release_report_explains_missing_billing_ad_and_legal_inputs(self):
        from backend.core.release_check import format_owner_release_readiness_report

        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "google_play": {
                        "ready": False,
                        "missing_server_settings": [
                            "GOOGLE_PLAY_PACKAGE_NAME",
                            "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON or GOOGLE_PLAY_SERVICE_ACCOUNT_FILE",
                        ],
                    },
                    "privacy_policy": {
                        "ready": False,
                        "missing_server_settings": ["ALPHAMATE_PRIVACY_POLICY_URL"],
                    },
                    "admob": {
                        "ready": False,
                        "missing_server_settings": ["ADMOB_REWARDED_AD_UNIT_ID"],
                    },
                },
            },
        })

        self.assertIn("Google Play 패키지명", report)
        self.assertIn("Google Play 서비스 계정 JSON", report)
        self.assertIn("개인정보처리방침", report)
        self.assertIn("AdMob 보상형 광고 단위 ID", report)
        self.assertIn("GOOGLE_PLAY_PACKAGE_NAME", report)
        self.assertIn("ADMOB_REWARDED_AD_UNIT_ID", report)

    def test_owner_release_report_lists_all_next_actions(self):
        from backend.core.release_check import format_owner_release_readiness_report

        missing = [f"SETTING_{index}" for index in range(12)]
        report = format_owner_release_readiness_report({
            "ok": False,
            "errors": [],
            "readiness": {
                "overall_ready": False,
                "sections": {
                    "sample": {
                        "ready": False,
                        "missing_server_settings": missing,
                    },
                },
            },
        })

        self.assertIn("SETTING_0", report)
        self.assertIn("SETTING_11", report)
        self.assertNotIn("그 외 누락 항목", report)

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
            ALPHAMATE_CORS_ORIGINS=None,
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
            self.assertIn("ALPHAMATE_CORS_ORIGINS", "\n".join(result["errors"]))
            self.assertNotIn("sk-", formatted)
            self.assertNotIn("google-secret-json", formatted)

    def test_rejects_missing_production_oauth_redirect_uris(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            OPENAI_API_KEY="sk-test-secret",
            KAKAO_CLIENT_ID="kakao-client",
            KAKAO_CLIENT_SECRET="kakao-secret",
            KAKAO_REDIRECT_URI=None,
            NAVER_CLIENT_ID="naver-client",
            NAVER_CLIENT_SECRET="naver-secret",
            NAVER_REDIRECT_URI=None,
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.basic.100",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-token-with-at-least-32-characters",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE=None,
            GOOGLE_PLAY_RTDN_OIDC_EMAIL=None,
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_PRIVACY_POLICY_URL="https://alphamate.example/privacy",
            ALPHAMATE_ACCOUNT_DB_PATH="D:/secure/alphamate/accounts.sqlite3",
            ALPHAMATE_JOURNAL_DB_PATH="D:/secure/alphamate/trades.sqlite3",
            ALPHAMATE_ACCESS_DB_PATH="D:/secure/alphamate/access.sqlite3",
            ALPHAMATE_REVIEW_HISTORY_DB_PATH="D:/secure/alphamate/review-history.sqlite3",
            ALPHAMATE_EVENT_LOG_DB_PATH="D:/secure/alphamate/events.sqlite3",
            ALPHAMATE_ADMIN_TOKEN="admin-token-with-at-least-32-characters",
            ALPHAMATE_CORS_ORIGINS="https://app.alphamate.example,capacitor://localhost",
        ):
            from backend.core.release_check import validate_backend_release_env

            result = validate_backend_release_env()
            joined_errors = "\n".join(result["errors"])

            self.assertFalse(result["ok"])
            self.assertIn("login.kakao: KAKAO_REDIRECT_URI", joined_errors)
            self.assertIn("login.naver: NAVER_REDIRECT_URI", joined_errors)

    def test_accepts_complete_production_backend_settings(self):
        with patched_env(
            ALPHAMATE_ENV="production",
            OPENAI_API_KEY="sk-test-secret",
            KAKAO_CLIENT_ID="kakao-client",
            KAKAO_CLIENT_SECRET="kakao-secret",
            KAKAO_REDIRECT_URI="https://api.alphamate.example/api/auth/kakao/callback",
            NAVER_CLIENT_ID="naver-client",
            NAVER_CLIENT_SECRET="naver-secret",
            NAVER_REDIRECT_URI="https://api.alphamate.example/api/auth/naver/callback",
            GOOGLE_PLAY_PACKAGE_NAME="com.alphamate.app",
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=fake_service_account_json(),
            GOOGLE_PLAY_BASIC_REVIEW_30_ID="alphamate.basic.30",
            GOOGLE_PLAY_BASIC_REVIEW_100_ID="alphamate.basic.100",
            GOOGLE_PLAY_ADVANCED_REVIEW_5_ID="alphamate.advanced.5",
            GOOGLE_PLAY_ADVANCED_REVIEW_10_ID="alphamate.advanced.10",
            GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID="alphamate.pro.launch",
            GOOGLE_PLAY_PRO_MONTHLY_ID="alphamate.pro.monthly",
            GOOGLE_PLAY_RTDN_SHARED_TOKEN="rtdn-token-with-at-least-32-characters",
            GOOGLE_PLAY_RTDN_OIDC_AUDIENCE=None,
            GOOGLE_PLAY_RTDN_OIDC_EMAIL=None,
            ADMOB_REWARDED_AD_UNIT_ID="rewarded-unit-1",
            ALPHAMATE_PRIVACY_POLICY_URL="https://alphamate.example/privacy",
            ALPHAMATE_ACCOUNT_DB_PATH="D:/secure/alphamate/accounts.sqlite3",
            ALPHAMATE_JOURNAL_DB_PATH="D:/secure/alphamate/trades.sqlite3",
            ALPHAMATE_ACCESS_DB_PATH="D:/secure/alphamate/access.sqlite3",
            ALPHAMATE_REVIEW_HISTORY_DB_PATH="D:/secure/alphamate/review-history.sqlite3",
            ALPHAMATE_EVENT_LOG_DB_PATH="D:/secure/alphamate/events.sqlite3",
            ALPHAMATE_ADMIN_TOKEN="admin-token-with-at-least-32-characters",
            ALPHAMATE_CORS_ORIGINS="https://app.alphamate.example,capacitor://localhost",
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
            "KAKAO_REDIRECT_URI=https://api.alphamate.example/api/auth/kakao/callback",
            "NAVER_CLIENT_ID=naver-client",
            "NAVER_CLIENT_SECRET=naver-secret",
            "NAVER_REDIRECT_URI=https://api.alphamate.example/api/auth/naver/callback",
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
            "ALPHAMATE_CORS_ORIGINS=https://app.alphamate.example,capacitor://localhost",
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
                KAKAO_REDIRECT_URI=None,
                NAVER_CLIENT_ID=None,
                NAVER_CLIENT_SECRET=None,
                NAVER_REDIRECT_URI=None,
                GOOGLE_PLAY_PACKAGE_NAME=None,
                GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=None,
                GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=None,
                GOOGLE_PLAY_BASIC_REVIEW_30_ID=None,
                GOOGLE_PLAY_BASIC_REVIEW_100_ID=None,
                GOOGLE_PLAY_ADVANCED_REVIEW_5_ID=None,
                GOOGLE_PLAY_ADVANCED_REVIEW_10_ID=None,
                GOOGLE_PLAY_PRO_MONTHLY_LAUNCH_ID=None,
                GOOGLE_PLAY_PRO_MONTHLY_ID=None,
                GOOGLE_PLAY_RTDN_OIDC_AUDIENCE=None,
                GOOGLE_PLAY_RTDN_OIDC_EMAIL=None,
                ADMOB_REWARDED_AD_UNIT_ID=None,
                ALPHAMATE_PRIVACY_POLICY_URL=None,
                ALPHAMATE_ACCOUNT_DB_PATH=None,
                ALPHAMATE_JOURNAL_DB_PATH=None,
                ALPHAMATE_ACCESS_DB_PATH=None,
                ALPHAMATE_REVIEW_HISTORY_DB_PATH=None,
                ALPHAMATE_EVENT_LOG_DB_PATH=None,
                ALPHAMATE_CORS_ORIGINS=None,
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
