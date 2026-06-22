import unittest


class RateLimitTest(unittest.TestCase):
    def test_allows_until_limit_then_returns_retry_after(self):
        from backend.core.rate_limit import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        first = limiter.check("client-a", limit=2, window_seconds=60, now=1000.0)
        second = limiter.check("client-a", limit=2, window_seconds=60, now=1010.0)
        third = limiter.check("client-a", limit=2, window_seconds=60, now=1020.0)

        self.assertTrue(first["allowed"])
        self.assertEqual(1, first["remaining"])
        self.assertTrue(second["allowed"])
        self.assertEqual(0, second["remaining"])
        self.assertFalse(third["allowed"])
        self.assertEqual(40, third["retry_after_seconds"])

    def test_prunes_old_attempts_after_window(self):
        from backend.core.rate_limit import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()
        limiter.check("client-a", limit=1, window_seconds=60, now=1000.0)

        result = limiter.check("client-a", limit=1, window_seconds=60, now=1061.0)

        self.assertTrue(result["allowed"])
        self.assertEqual(0, result["remaining"])


if __name__ == "__main__":
    unittest.main()
