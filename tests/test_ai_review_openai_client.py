import importlib
import io
import json
import os
import tempfile
import unittest
import urllib.error


class AiReviewOpenAiClientTest(unittest.TestCase):
    ENV_KEYS = [
        "OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_API_KEY",
        "ALPHAMATE_OPENAI_TIMEOUT_SECONDS",
        "ALPHAMATE_OPENAI_MAX_RETRIES",
        "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
        "ALPHAMATE_ENV_FILE",
        "OPENAI_BASIC_REVIEW_MODEL",
        "OPENAI_ADVANCED_REVIEW_MODEL",
        "OPENAI_MODEL",
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

    def test_openai_review_runtime_settings_have_upper_bounds(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ALPHAMATE_OPENAI_TIMEOUT_SECONDS"] = "999"
        os.environ["ALPHAMATE_OPENAI_MAX_RETRIES"] = "999"
        os.environ["ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS"] = "999"
        calls = {"count": 0}
        captured = {"timeouts": [], "sleeps": []}

        def fake_urlopen(req, timeout):
            calls["count"] += 1
            captured["timeouts"].append(timeout)
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "rate limit",
                hdrs=None,
                fp=io.BytesIO(b'{"error":"rate limited"}'),
            )

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen
        self.ai_review_v2.time.sleep = lambda seconds: captured["sleeps"].append(seconds)

        with self.assertRaises(RuntimeError):
            self.ai_review_v2._call_openai_review(
                {"trade": "sample"},
                model="gpt-test",
                instructions="test",
            )

        self.assertEqual(4, calls["count"])
        self.assertEqual([90, 90, 90, 90], captured["timeouts"])
        self.assertEqual([5.0, 5.0, 5.0], captured["sleeps"])

    def test_openai_review_reads_api_key_from_explicit_env_file(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as env_file:
            env_file.write("OPENAI_API_KEY=sk-env-file\n")
            env_path = env_file.name

        try:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ALPHAMATE_OPENAI_API_KEY", None)
            os.environ["ALPHAMATE_ENV_FILE"] = env_path
            captured = {}

            def fake_urlopen(req, timeout):
                captured["authorization"] = req.headers.get("Authorization")
                return self._success_response("env-file-ok")

            self.ai_review_v2.urllib.request.urlopen = fake_urlopen

            result = self.ai_review_v2._call_openai_review(
                {"trade": "sample"},
                model="gpt-test",
                instructions="test",
            )

            self.assertEqual("env-file-ok", result)
            self.assertEqual("Bearer sk-env-file", captured["authorization"])
        finally:
            os.unlink(env_path)

    def test_ai_review_uses_expected_default_model_ids(self):
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append((payload["review_type"], model))
            return f"{payload['review_type']}-ok"

        self.ai_review_v2._contexts_for_trades = lambda trades: []
        self.ai_review_v2._call_openai_review = fake_call

        basic = self.ai_review_v2.build_basic_ai_review([{
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }])
        advanced = self.ai_review_v2.build_advanced_ai_review([{
            "id": 2,
            "trade_date": "2026-06-20T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "sell",
            "price": 72000,
            "quantity": 1,
        }])

        self.assertEqual("gpt-5.4-mini", basic["model"])
        self.assertEqual("gpt-5.5", advanced["model"])
        self.assertEqual([("basic", "gpt-5.4-mini"), ("advanced", "gpt-5.5")], captured)

    def test_ai_review_model_ids_are_configurable(self):
        os.environ["OPENAI_BASIC_REVIEW_MODEL"] = "custom-basic-model"
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "custom-advanced-model"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            return "ok"

        self.ai_review_v2._contexts_for_trades = lambda trades: []
        self.ai_review_v2._call_openai_review = fake_call
        trade = {
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }

        self.ai_review_v2.build_basic_ai_review([trade])
        self.ai_review_v2.build_advanced_ai_review([trade])

        self.assertEqual(["custom-basic-model", "custom-advanced-model"], captured)

if __name__ == "__main__":
    unittest.main()
