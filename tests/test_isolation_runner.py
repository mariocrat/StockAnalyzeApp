"""Coordinator self-tests: import only the runner, never child target modules.

Run explicitly: python -B -m unittest tests.test_isolation_runner
"""
import os
from pathlib import Path
import sys
import unittest

from tests.run_isolated_tests import REPOSITORY, run_module


class IsolationRunnerTest(unittest.TestCase):
    def test_synthetic_boundaries_and_sanitized_child(self):
        host = dict(os.environ)
        for key in ("OPENAI_API_KEY", "KAKAO_CLIENT_SECRET", "VITE_API_BASE_URL", "RENDER_SERVICE_ID",
                    "HTTPS_PROXY", "PYTHONPATH", "ARBITRARY_PROVIDER_SECRET"):
            host[key] = "SYNTHETIC_HOST_SECRET"
        # Path values are synthetic, nonexistent, and never read.
        for key in ("ALPHAMATE_ENV_FILE", "ALPHAMATE_FRONTEND_ENV_FILE", "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE"):
            host[key] = str(REPOSITORY / "synthetic-never-opened" / key)
        result = run_module("tests.isolation_probes", host)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["tests"], 9)
        self.assertGreater(result["violations"], 0)
        self.assertEqual(result["unexpected"], 0)
        self.assertTrue(result["patches_restored"])
        self.assertTrue(result["restored"])
        self.assertTrue(result["cleanup"])
        self.assertFalse(Path(result["root"]).parent.exists())
        self.assertNotIn("tests.isolation_probes", sys.modules)
        print("synthetic probes:", {k: v for k, v in result.items() if k not in {"stderr", "root"}})

    def test_swallowed_import_violation_fails_child(self):
        result = run_module("tests.isolation_swallowed_probe")
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["violations"], 1)
        self.assertEqual(result["unexpected"], 1)
        self.assertTrue(result["cleanup"])
        self.assertTrue(result["patches_restored"])
        self.assertTrue(result["restored"])
        self.assertNotIn("tests.isolation_swallowed_probe", sys.modules)
        print("expected failing probe:", {k: v for k, v in result.items() if k not in {"stderr", "root"}})

    def test_rate_limiter_has_unique_clean_roots(self):
        results = [run_module("tests.test_rate_limit") for _ in range(2)]
        for result in results:
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["tests"], 3)
            self.assertEqual(result["violations"], 0)
            self.assertTrue(result["cleanup"])
            self.assertFalse(Path(result["root"]).exists())
        self.assertNotEqual(results[0]["root"], results[1]["root"])
        self.assertNotIn("tests.test_rate_limit", sys.modules)


if __name__ == "__main__":
    unittest.main()
