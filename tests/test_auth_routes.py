from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException


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


class AuthRoutesTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())

    def test_auth_routes_are_registered(self):
        import main

        paths = set(main.app.openapi()["paths"].keys())

        self.assertIn("/", paths)
        self.assertIn("/healthz", paths)
        self.assertIn("/api/healthz", paths)
        self.assertIn("/privacy", paths)
        self.assertIn("/account-deletion", paths)
        self.assertIn("/api/auth/dev-login", paths)
        self.assertIn("/api/auth/review-login", paths)
        self.assertIn("/api/auth/login/kakao", paths)
        self.assertIn("/api/auth/login/naver", paths)
        self.assertIn("/api/auth/login/kakao/code", paths)
        self.assertIn("/api/auth/login/naver/code", paths)
        self.assertIn("/api/auth/oauth-config", paths)
        self.assertIn("/api/me", paths)
        self.assertIn("/api/me/journal-storage", paths)
        self.assertIn("/api/me/data-summary", paths)
        self.assertIn("/api/auth/logout", paths)
        self.assertIn("/api/app/readiness", paths)
        self.assertIn("/api/journal/products", paths)
        self.assertIn("/api/journal/dev-purchase", paths)
        self.assertIn("/api/journal/google-play-purchase", paths)
        self.assertIn("/api/journal/google-play-rtdn", paths)
        self.assertIn("/api/journal/admob-ssv", paths)
        self.assertIn("/api/journal/ad-reward-claim", paths)
        self.assertIn("/api/journal/ad-reward-status", paths)
        self.assertIn("/api/journal/review-history", paths)
        self.assertIn("/api/journal/review-history/{review_id}", paths)
        self.assertIn("/api/client-events", paths)
        self.assertIn("/api/admin/operational-events", paths)
        self.assertIn("/api/admin/operational-events/summary", paths)
        self.assertIn("/api/admin/operational-events/retention", paths)

        rtdn_operation = main.app.openapi()["paths"]["/api/journal/google-play-rtdn"]["post"]
        rtdn_query_parameters = {
            parameter["name"]
            for parameter in rtdn_operation.get("parameters", [])
            if parameter.get("in") == "query"
        }
        self.assertIn("verification_token", rtdn_query_parameters)

    def test_auth_rate_limit_rejects_excessive_login_requests(self):
        with patched_env(ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            self.enterContext(patch.object(main, "_auth_rate_limiter", InMemoryRateLimiter()))

            self.assertTrue(main._enforce_auth_rate_limit("client-a"))
            self.assertTrue(main._enforce_auth_rate_limit("client-a"))
            with self.assertRaises(HTTPException) as blocked:
                main._enforce_auth_rate_limit("client-a")

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)
    def test_auth_rate_limit_has_upper_bound(self):
        with patched_env(ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE="999999"):
            import main

            self.assertEqual(120, main._auth_rate_limit())
    def test_health_payload_does_not_expose_settings(self):
        import main

        with patched_env(RENDER_GIT_COMMIT=None):
            payload = main.healthz()
        payload_text = str(payload)

        self.assertEqual({"ok": True, "service": "alphamate-api"}, payload)
        self.assertNotIn("OPENAI", payload_text)
        self.assertNotIn("TOKEN", payload_text)

    def test_health_payload_exposes_only_short_render_revision(self):
        import main

        with patched_env(RENDER_GIT_COMMIT="1234567890abcdef"):
            payload = main.healthz()

        self.assertEqual("1234567890ab", payload["revision"])
        self.assertEqual({"ok", "service", "revision"}, set(payload))

    def test_privacy_policy_is_public_korean_html(self):
        import main

        response = main.privacy_policy()
        body = response.body.decode("utf-8")

        self.assertEqual("text/html", response.media_type)
        self.assertIn("charset=utf-8", response.headers["content-type"])
        self.assertIn("스톡보다(StockBoda) 개인정보처리방침", body)
        self.assertIn("제3자 제공, 처리위탁 및 국외 이전", body)
        self.assertIn("privacy@render.com", body)
        self.assertIn("privacy@openai.com", body)
        self.assertIn("국외 처리에 동의하지 않는 경우", body)
        self.assertIn("계정 데이터를 삭제", body)
        self.assertIn("store=false", body)
        self.assertIn("Google AdMob", body)

    def test_public_landing_page_is_public_korean_html(self):
        import main

        response = main.public_landing()
        body = response.body.decode("utf-8")

        self.assertEqual("text/html", response.media_type)
        self.assertIn("charset=utf-8", response.headers["content-type"])
        self.assertIn("StockBoda", body)
        self.assertIn("스톡보다", body)
        self.assertIn("Orvetriq Labs", body)
        self.assertIn("support@stockboda.co.kr", body)
        self.assertIn('href="/privacy"', body)
        self.assertIn('href="/account-deletion"', body)
        self.assertIn("주식 시세·차트·테마 정보", body)
        self.assertIn("과거 매매를 복기", body)
        self.assertIn("실제 주식 주문·중개나 투자자문을 제공하지 않으며", body)

    def test_account_deletion_page_is_public_korean_html(self):
        import main

        response = main.account_deletion()
        body = response.body.decode("utf-8")

        self.assertEqual("text/html", response.media_type)
        self.assertIn("StockBoda (스톡보다) 계정 및 데이터 삭제", body)
        self.assertIn("계정 데이터 삭제", body)
        self.assertIn("카카오·네이버 로그인 연결", body)



if __name__ == "__main__":
    unittest.main()
