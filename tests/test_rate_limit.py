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

    def test_prunes_expired_keys_when_key_count_exceeds_cap(self):
        from backend.core.rate_limit import InMemoryRateLimiter

        limiter = InMemoryRateLimiter(max_keys=2)
        limiter.check("expired-a", limit=1, window_seconds=60, now=1000.0)
        limiter.check("expired-b", limit=1, window_seconds=60, now=1001.0)

        result = limiter.check("client-c", limit=1, window_seconds=60, now=1062.0)

        self.assertTrue(result["allowed"])
        self.assertEqual(["client-c"], list(limiter._hits.keys()))


if __name__ == "__main__":
    unittest.main()
