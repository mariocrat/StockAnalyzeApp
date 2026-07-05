import os
import sys
import unittest
from contextlib import contextmanager
from types import SimpleNamespace


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


class MarketRateLimitTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

    def test_market_rate_limit_has_upper_bound(self):
        with patched_env(ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE="999999"):
            import main

            self.assertEqual(600, main._market_rate_limit())

    async def test_public_market_middleware_rejects_excessive_requests(self):
        with patched_env(ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._market_rate_limiter = InMemoryRateLimiter()
            request = SimpleNamespace(
                url=SimpleNamespace(path="/api/stock/005930"),
                headers={},
                client=SimpleNamespace(host="127.0.0.1"),
            )
            calls = {"count": 0}

            async def call_next(_request):
                calls["count"] += 1
                return SimpleNamespace(status_code=200, headers={})

            first = await main.limit_public_market_requests(request, call_next)
            second = await main.limit_public_market_requests(request, call_next)
            blocked = await main.limit_public_market_requests(request, call_next)

            self.assertEqual(200, first.status_code)
            self.assertEqual(200, second.status_code)
            self.assertEqual(429, blocked.status_code)
            self.assertEqual(2, calls["count"])
            self.assertIn("Retry-After", blocked.headers)


if __name__ == "__main__":
    unittest.main()
