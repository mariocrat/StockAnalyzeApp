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

        payload = main.healthz()
        payload_text = str(payload)

        self.assertEqual({"ok": True, "service": "alphamate-api"}, payload)
        self.assertNotIn("OPENAI", payload_text)
        self.assertNotIn("TOKEN", payload_text)


if __name__ == "__main__":
    unittest.main()
