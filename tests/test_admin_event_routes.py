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


class AdminEventRoutesTest(unittest.TestCase):
    def setUp(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

    def test_admin_operational_events_route_is_registered(self):
        import main

        paths = set(main.app.openapi()["paths"].keys())

        self.assertIn("/api/admin/operational-events", paths)

    def test_admin_event_route_requires_admin_token(self):
        with patched_env(ALPHAMATE_ADMIN_TOKEN="admin-secret"):
            import main

            with self.assertRaises(HTTPException) as missing:
                main._require_admin_token(None)
            self.assertEqual(401, missing.exception.status_code)

            with self.assertRaises(HTTPException) as wrong:
                main._require_admin_token("Bearer wrong")
            self.assertEqual(403, wrong.exception.status_code)

            self.assertTrue(main._require_admin_token("Bearer admin-secret"))


if __name__ == "__main__":
    unittest.main()
