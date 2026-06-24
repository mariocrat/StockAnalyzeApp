import importlib
import io
import json
import os
import unittest
import urllib.error


class AiReviewOpenAiClientTest(unittest.TestCase):
    ENV_KEYS = [
        "OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_TIMEOUT_SECONDS",
        "ALPHAMATE_OPENAI_MAX_RETRIES",
        "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
    ]

    def setUp(self):
        self._previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in os.sys.path:
            os.sys.path.insert(0, backend_dir)
        self.ai_review_v2 = importlib.reload(importlib.import_module("core.ai_review_v2"))

    def tearDown(self):
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(self.ai_review_v2)

    def _success_response(self, text="ok"):
        body = json.dumps({"output_text": text}).encode("utf-8")

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()

        return Response(body)

    def test_openai_review_retries_transient_rate_limit_once(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ALPHAMATE_OPENAI_MAX_RETRIES"] = "1"
        os.environ["ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS"] = "0"
        calls = {"count": 0}

        def fake_urlopen(req, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                raise urllib.error.HTTPError(
                    req.full_url,
                    429,
                    "rate limit",
                    hdrs=None,
                    fp=io.BytesIO(b'{"error":"rate limited"}'),
                )
            return self._success_response("retry-ok")

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen

        result = self.ai_review_v2._call_openai_review(
            {"trade": "sample"},
            model="gpt-test",
            instructions="test",
        )

        self.assertEqual("retry-ok", result)
        self.assertEqual(2, calls["count"])

    def test_openai_review_timeout_is_configurable(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ALPHAMATE_OPENAI_TIMEOUT_SECONDS"] = "12"
        captured = {}

        def fake_urlopen(req, timeout):
            captured["timeout"] = timeout
            return self._success_response("timeout-ok")

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen

        result = self.ai_review_v2._call_openai_review(
            {"trade": "sample"},
            model="gpt-test",
            instructions="test",
        )

        self.assertEqual("timeout-ok", result)
        self.assertEqual(12, captured["timeout"])


if __name__ == "__main__":
    unittest.main()
