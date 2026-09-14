from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch


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
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())

    def test_market_rate_limit_has_upper_bound(self):
        with patched_env(ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE="999999"):
            import main

            self.assertEqual(600, main._market_rate_limit())

    async def test_public_market_middleware_rejects_excessive_requests(self):
        with patched_env(ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            self.enterContext(patch.object(main, "_market_rate_limiter", InMemoryRateLimiter()))
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
