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


class BillingRateLimitTest(unittest.TestCase):
    def setUp(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

    def test_billing_rate_limit_rejects_excessive_purchase_requests(self):
        with patched_env(ALPHAMATE_BILLING_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._billing_rate_limiter = InMemoryRateLimiter()

            self.assertTrue(main._enforce_billing_rate_limit("Bearer user-token", "client-a"))
            self.assertTrue(main._enforce_billing_rate_limit("Bearer user-token", "client-a"))
            with self.assertRaises(HTTPException) as blocked:
                main._enforce_billing_rate_limit("Bearer user-token", "client-a")

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)

    def test_billing_rate_limit_has_upper_bound(self):
        with patched_env(ALPHAMATE_BILLING_RATE_LIMIT_PER_MINUTE="999999"):
            import main

            self.assertEqual(120, main._billing_rate_limit())


if __name__ == "__main__":
    unittest.main()
