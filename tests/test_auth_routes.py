import os
import sys
import unittest


class AuthRoutesTest(unittest.TestCase):
    def test_auth_routes_are_registered(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import main

        paths = set(main.app.openapi()["paths"].keys())

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


if __name__ == "__main__":
    unittest.main()
