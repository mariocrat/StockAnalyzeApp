"""H4-B1 deferred chart-provider boundary before the OpenAI fallback override."""

import importlib
import io
import json
import os
import tempfile
import unittest
import urllib.error


class AiReviewChartProviderTest(unittest.TestCase):
    ENV_KEYS = [
        "OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_TIMEOUT_SECONDS",
        "ALPHAMATE_OPENAI_MAX_RETRIES",
        "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
        "ALPHAMATE_ENV_FILE",
        "OPENAI_BASIC_REVIEW_MODEL",
        "OPENAI_ADVANCED_REVIEW_MODEL",
        "OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL",
        "OPENAI_MODEL",
        "OPENAI_BASIC_REVIEW_REASONING_EFFORT",
        "OPENAI_ADVANCED_REVIEW_REASONING_EFFORT",
        "OPENAI_BASIC_REVIEW_MAX_OUTPUT_TOKENS",
        "OPENAI_ADVANCED_REVIEW_MAX_OUTPUT_TOKENS",
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

    def test_advanced_review_override_can_disable_fallback_for_qa_comparison(self):
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "configured-primary"
        os.environ["OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL"] = "configured-fallback"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            raise RuntimeError("model failed")

        self.ai_review_v2._call_openai_review = fake_call
        result = self.ai_review_v2.build_advanced_ai_review(
            [{
                "id": 1,
                "trade_date": "2026-07-10T09:36",
                "ticker": "017900",
                "name": "광전자",
                "side": "buy",
                "price": 6980,
                "quantity": 10,
            }],
            model_override="gpt-5.6-luna",
            allow_fallback=False,
        )

        self.assertEqual(["gpt-5.6-luna"], captured)
        self.assertEqual("error", result["status"])
        self.assertEqual("advanced", result["review_type"])



if __name__ == "__main__":
    unittest.main()
