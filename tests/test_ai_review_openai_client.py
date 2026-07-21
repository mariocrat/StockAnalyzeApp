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
        "OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL",
        "OPENAI_MODEL",
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

    def test_openai_review_applies_review_specific_output_limits(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        captured = []

        def fake_urlopen(req, timeout):
            captured.append(json.loads(req.data.decode("utf-8"))["max_output_tokens"])
            return self._success_response("limited-ok")

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen
        self.ai_review_v2._call_openai_review(
            {"review_type": "basic", "trade": "sample"},
            model="gpt-test",
            instructions="test",
        )
        self.ai_review_v2._call_openai_review(
            {"review_type": "advanced", "trade": "sample"},
            model="gpt-test",
            instructions="test",
        )

        self.assertEqual([1000, 3000], captured)

    def test_openai_review_disables_response_storage(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        captured = {}

        def fake_urlopen(req, timeout):
            captured.update(json.loads(req.data.decode("utf-8")))
            return self._success_response("private-ok")

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen
        result = self.ai_review_v2._call_openai_review(
            {"review_type": "advanced", "private_trade_note": "do-not-store"},
            model="gpt-test",
            instructions="test",
        )

        self.assertEqual("private-ok", result)
        self.assertIs(False, captured["store"])

    def test_openai_review_output_limits_are_safely_bounded(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_BASIC_REVIEW_MAX_OUTPUT_TOKENS"] = "1"
        os.environ["OPENAI_ADVANCED_REVIEW_MAX_OUTPUT_TOKENS"] = "999999"
        captured = []

        def fake_urlopen(req, timeout):
            captured.append(json.loads(req.data.decode("utf-8"))["max_output_tokens"])
            return self._success_response("bounded-ok")

        self.ai_review_v2.urllib.request.urlopen = fake_urlopen
        for review_type in ("basic", "advanced"):
            self.ai_review_v2._call_openai_review(
                {"review_type": review_type},
                model="gpt-test",
                instructions="test",
            )

        self.assertEqual([256, 10000], captured)

    def test_openai_review_records_token_usage_without_prompt_content(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        captured = []
        body = json.dumps({
            "output_text": "usage-ok",
            "usage": {
                "input_tokens": 1200,
                "input_tokens_details": {"cached_tokens": 200},
                "output_tokens": 300,
                "output_tokens_details": {"reasoning_tokens": 100},
                "total_tokens": 1500,
            },
        }).encode("utf-8")

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()

        self.ai_review_v2.record_event = lambda **kwargs: captured.append(kwargs)
        self.ai_review_v2.urllib.request.urlopen = lambda req, timeout: Response(body)
        result = self.ai_review_v2._call_openai_review(
            {"review_type": "advanced", "private_trade_note": "must-not-be-logged"},
            model="gpt-5.6-terra",
            instructions="test",
        )

        self.assertEqual("usage-ok", result)
        self.assertEqual(1, len(captured))
        self.assertEqual("openai_review_usage", captured[0]["event_type"])
        self.assertEqual(1200, captured[0]["details"]["input_tokens"])
        self.assertEqual(100, captured[0]["details"]["reasoning_tokens"])
        self.assertNotIn("private_trade_note", json.dumps(captured[0]))

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
        self.ai_review_v2._compact_chart_snapshot = lambda trades: {}
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
        self.assertEqual("gpt-5.6-terra", advanced["model"])
        self.assertEqual([("basic", "gpt-5.4-mini"), ("advanced", "gpt-5.6-terra")], captured)

    def test_ai_review_model_ids_are_configurable(self):
        os.environ["OPENAI_BASIC_REVIEW_MODEL"] = "custom-basic-model"
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "custom-advanced-model"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            return "ok"

        self.ai_review_v2._contexts_for_trades = lambda trades: []
        self.ai_review_v2._compact_chart_snapshot = lambda trades: {}
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

    def test_advanced_review_uses_configurable_fallback_model_after_primary_failure(self):
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "primary-advanced-model"
        os.environ["OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL"] = "fallback-advanced-model"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            if model == "primary-advanced-model":
                raise RuntimeError("primary failed")
            return "fallback-ok"

        self.ai_review_v2._contexts_for_trades = lambda trades: []
        self.ai_review_v2._compact_chart_snapshot = lambda trades: {}
        self.ai_review_v2._call_openai_review = fake_call
        result = self.ai_review_v2.build_advanced_ai_review([{
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }])

        self.assertEqual("ready", result["status"])
        self.assertEqual("fallback-advanced-model", result["model"])
        self.assertEqual(["primary-advanced-model", "fallback-advanced-model"], captured)

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

    def test_many_trades_keep_basic_episode_and_advanced_history_scopes_separate(self):
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured[payload["review_type"]] = payload
            return "ok"

        self.ai_review_v2._contexts_for_trades = lambda trades: []
        self.ai_review_v2._compact_chart_snapshot = lambda trades: {}
        self.ai_review_v2._call_openai_review = fake_call
        trades = [
            {
                "id": index,
                "trade_date": f"2026-07-{index:02d}T10:30",
                "ticker": "005930" if index % 2 else "000660",
                "name": "Samsung Electronics" if index % 2 else "SK hynix",
                "side": "buy" if index % 3 else "sell",
                "price": 70000 + index * 100,
                "quantity": 1,
            }
            for index in range(1, 13)
        ]

        self.ai_review_v2.build_basic_ai_review(trades, target_trade_id=12)
        self.ai_review_v2.build_advanced_ai_review(trades, target_trade_id=12)

        basic_episode = captured["basic"]["trade_episode"]
        self.assertEqual(6, len(basic_episode))
        self.assertEqual({"000660"}, {trade["ticker"] for trade in basic_episode})
        self.assertEqual(list(range(2, 13, 2)), [trade["id"] for trade in basic_episode])

        advanced_history = captured["advanced"]["recent_trades"]
        self.assertEqual(10, len(advanced_history))
        self.assertEqual(list(range(3, 13)), [trade["id"] for trade in advanced_history])
        self.assertEqual(12, captured["advanced"]["target_trade"]["id"])

    def test_basic_review_anchors_verdict_and_changes_only_analysis_focus(self):
        captured = {}
        trades = [
            {
                "id": 1,
                "trade_date": "2026-07-10T09:30",
                "ticker": "087010",
                "name": "Sample",
                "side": "buy",
                "price": 10000,
                "quantity": 10,
            },
            {
                "id": 2,
                "trade_date": "2026-07-10T09:40",
                "ticker": "087010",
                "name": "Sample",
                "side": "sell",
                "price": 10500,
                "quantity": 10,
            },
        ]
        snapshot = {
            "ticker": "087010",
            "rule_based_observations": [
                {
                    "trade_id": 1,
                    "title": "entry grade",
                    "detail": "entry evidence",
                    "metrics": {"after_5_bars": 1.25, "price_vs_close_pct": -0.2},
                },
                {
                    "trade_id": 2,
                    "title": "exit grade",
                    "detail": "exit evidence",
                    "metrics": {"after_5_bars": -0.8, "price_vs_close_pct": 0.1},
                },
            ],
        }

        def fake_call(payload, *, model, instructions):
            captured["payload"] = payload
            captured["instructions"] = instructions
            return "ok"

        self.ai_review_v2._compact_chart_snapshot = lambda rows: snapshot
        self.ai_review_v2._call_openai_review = fake_call

        result = self.ai_review_v2.build_basic_ai_review(
            trades,
            target_trade_id=2,
            analysis_focus="exit_timing",
        )

        self.assertEqual("ready", result["status"])
        self.assertEqual("exit_timing", captured["payload"]["analysis_focus"]["key"])
        self.assertEqual("profit", captured["payload"]["evaluation_anchor"]["outcome"]["direction"])
        self.assertEqual(2, len(captured["payload"]["evaluation_anchor"]["execution_evidence"]))
        self.assertIn("<consistency_rules>", captured["instructions"])
        self.assertIn("<quality_rules>", captured["instructions"])


if __name__ == "__main__":
    unittest.main()
