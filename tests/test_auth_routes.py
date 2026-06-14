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
        self.assertIn("/api/me", paths)
        self.assertIn("/api/auth/logout", paths)


if __name__ == "__main__":
    unittest.main()
