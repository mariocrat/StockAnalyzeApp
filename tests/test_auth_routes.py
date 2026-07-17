import asyncio
import os
import sys
import unittest
from contextlib import contextmanager

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
    def test_auth_routes_are_registered(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        paths = set(main.app.openapi()["paths"].keys())

        self.assertIn("/healthz", paths)
        self.assertIn("/api/healthz", paths)
        self.assertIn("/privacy", paths)
        self.assertIn("/account-deletion", paths)
        self.assertIn("/api/auth/dev-login", paths)
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
        self.assertIn("/api/journal/review-history", paths)
        self.assertIn("/api/journal/review-history/{review_id}", paths)
        self.assertIn("/api/client-events", paths)
        self.assertIn("/api/admin/operational-events", paths)
        self.assertIn("/api/admin/operational-events/summary", paths)
        self.assertIn("/api/admin/operational-events/retention", paths)

    def test_auth_rate_limit_rejects_excessive_login_requests(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        with patched_env(ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._auth_rate_limiter = InMemoryRateLimiter()

            self.assertTrue(main._enforce_auth_rate_limit("client-a"))
            self.assertTrue(main._enforce_auth_rate_limit("client-a"))
            with self.assertRaises(HTTPException) as blocked:
                main._enforce_auth_rate_limit("client-a")

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)
    def test_auth_rate_limit_has_upper_bound(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        with patched_env(ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE="999999"):
            import main

            self.assertEqual(120, main._auth_rate_limit())
    def test_health_payload_does_not_expose_settings(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        with patched_env(RENDER_GIT_COMMIT=None):
            payload = main.healthz()
        payload_text = str(payload)

        self.assertEqual({"ok": True, "service": "alphamate-api"}, payload)
        self.assertNotIn("OPENAI", payload_text)
        self.assertNotIn("TOKEN", payload_text)

    def test_health_payload_exposes_only_short_render_revision(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        with patched_env(RENDER_GIT_COMMIT="1234567890abcdef"):
            payload = main.healthz()

        self.assertEqual("1234567890ab", payload["revision"])
        self.assertEqual({"ok", "service", "revision"}, set(payload))

    def test_privacy_policy_is_public_korean_html(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        response = main.privacy_policy()
        body = response.body.decode("utf-8")

        self.assertEqual("text/html", response.media_type)
        self.assertIn("charset=utf-8", response.headers["content-type"])
        self.assertIn("AlphaMate 개인정보처리방침", body)
        self.assertIn("제3자 제공, 처리위탁 및 국외 이전", body)
        self.assertIn("privacy@render.com", body)
        self.assertIn("privacy@openai.com", body)
        self.assertIn("국외 처리에 동의하지 않는 경우", body)
        self.assertIn("계정 데이터를 삭제", body)
        self.assertIn("store=false", body)
        self.assertIn("Google AdMob", body)

    def test_account_deletion_page_is_public_korean_html(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        response = main.account_deletion()
        body = response.body.decode("utf-8")

        self.assertEqual("text/html", response.media_type)
        self.assertIn("AlphaMate 계정 및 데이터 삭제", body)
        self.assertIn("계정 데이터 삭제", body)
        self.assertIn("카카오·네이버 로그인 연결", body)

    def test_lifespan_skips_theme_warmup_when_disabled_for_render(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        started = []

        class FakeThread:
            def __init__(self, target, daemon):
                started.append({"target": target, "daemon": daemon})

            def start(self):
                started.append("started")

        original_thread = main.threading.Thread
        try:
            main.threading.Thread = FakeThread
            with patched_env(ALPHAMATE_WARM_CACHE_ON_STARTUP="false"):
                async def run_lifespan():
                    async with main.lifespan(main.app):
                        pass

                asyncio.run(run_lifespan())
        finally:
            main.threading.Thread = original_thread

        self.assertEqual(2, len(started))
        self.assertTrue(callable(started[0]["target"]))
        self.assertNotEqual(main._warm_cache, started[0]["target"])
        self.assertTrue(started[0]["daemon"])
        self.assertEqual("started", started[1])

    def test_lifespan_can_enable_theme_warmup_for_manual_prewarming(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        started = []

        class FakeThread:
            def __init__(self, target, daemon):
                started.append({"target": target, "daemon": daemon})

            def start(self):
                started.append("started")

        original_thread = main.threading.Thread
        try:
            main.threading.Thread = FakeThread
            with patched_env(ALPHAMATE_WARM_CACHE_ON_STARTUP="true"):
                async def run_lifespan():
                    async with main.lifespan(main.app):
                        pass

                asyncio.run(run_lifespan())
        finally:
            main.threading.Thread = original_thread

        self.assertEqual(main._warm_cache, started[0]["target"])
        self.assertTrue(started[0]["daemon"])
        self.assertEqual("started", started[1])
        self.assertTrue(callable(started[2]["target"]))
        self.assertNotEqual(main._warm_cache, started[2]["target"])
        self.assertTrue(started[2]["daemon"])
        self.assertEqual("started", started[3])


if __name__ == "__main__":
    unittest.main()
