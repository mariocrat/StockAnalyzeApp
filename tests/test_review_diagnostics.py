"""Synthetic H4-only diagnostic failures; no provider calls or private inputs."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import asyncio
import json
import unittest
from unittest.mock import Mock, patch

from core import review_diagnostics as diagnostic
from tests import test_review_display_client_gate as support
from tests.test_review_finalizer_compatibility import model_output


class ReviewDiagnosticsTest(unittest.TestCase):
    def test_metadata_rejects_private_values_and_keeps_first_failure(self):
        value, token = diagnostic.begin()
        try:
            diagnostic.stage("trade_context")
            diagnostic.update(user_id="PRIVATE", model="sk-PRIVATE", access_source="PRIVATE",
                              internal_status="PRIVATE", review_type="basic")
            diagnostic.fail(ValueError("PRIVATE trade token prompt"), status="invalid_structured_output")
            diagnostic.stage("history")
            self.assertEqual(value.stage, "trade_context")
            self.assertNotIn("PRIVATE", json.dumps(value.metadata()))
            self.assertEqual(value.error_class, "ValueError")
            self.assertEqual(set(value.metadata()), {"request_id", "stage", "review_type", "internal_status",
                "error_class", "openai_attempted", "model", "access_source", "refunded",
                "display_generated", "elapsed_ms"})
        finally:
            diagnostic.finish(value, token, Mock())

    def test_telemetry_and_logger_failure_do_not_escape_or_leave_context(self):
        value, token = diagnostic.begin()
        with patch.object(diagnostic.logging, "getLogger", side_effect=RuntimeError("PRIVATE")):
            diagnostic.finish(value, token, Mock(side_effect=RuntimeError("PRIVATE")))
        self.assertIsNone(diagnostic._current.get())

    def test_telemetry_failure_still_emits_allowlisted_application_log(self):
        value, token = diagnostic.begin()
        with patch.object(diagnostic.logging, "getLogger") as logger:
            diagnostic.finish(value, token, Mock(side_effect=RuntimeError("PRIVATE")))
        payload = json.loads(logger.return_value.info.call_args.args[1])
        self.assertEqual(payload["request_id"], value.request_id)
        self.assertNotIn("PRIVATE", str(payload))

    def test_all_stages_and_fallback_recovery_are_request_local(self):
        diagnostic.update(model="gpt-6-luna")
        value, token = diagnostic.begin()
        try:
            for stage in diagnostic.STAGES:
                diagnostic.stage(stage)
                self.assertEqual(value.stage, stage)
            diagnostic.fail(RuntimeError("PRIVATE"), status="request_error")
            diagnostic.recovered()
            diagnostic.stage("openai_response")
            self.assertFalse(value.failed)
            self.assertEqual(value.stage, "openai_response")
            self.assertEqual(value.error_class, "none")
        finally:
            diagnostic.finish(value, token, Mock())

    def test_http_success_401_402_500_have_generated_id_without_body_changes(self):
        async def run(status, raises=False):
            records, messages = [], []
            async def application(scope, receive, send):
                diagnostic.update(review_type="basic")
                if raises:
                    raise ValueError("PRIVATE")
                await send({"type": "http.response.start", "status": status, "headers": []})
                await send({"type": "http.response.body", "body": b"original"})
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(message):
                messages.append(message)
            app = diagnostic.ReviewDiagnosticsMiddleware(application, lambda **k: records.append(k["details"]))
            scope = {"type": "http", "method": "POST", "path": "/api/journal/ai-review-once"}
            try:
                await app(scope, receive, send)
            except ValueError:
                self.assertTrue(raises)
            self.assertEqual(messages[0]["status"], status)
            headers = dict(messages[0]["headers"])
            self.assertEqual(headers[b"x-request-id"].decode(), records[0]["request_id"])
            self.assertEqual(messages[1]["body"], b"Internal Server Error" if raises else b"original")
            self.assertNotIn("PRIVATE", str(records) + str(messages))
            self.assertIsNone(diagnostic._current.get())
            return records[0]["request_id"]
        ids = [asyncio.run(run(status, status == 500)) for status in (200, 401, 402, 500)]
        self.assertEqual(len(set(ids)), 4)

    def test_actual_route_failure_stage_matrix_without_ai_or_private_data(self):
        fixture = support.ReviewDisplayClientGateTest()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        main, ai, case = fixture.main, fixture.ai, fixture.case
        cases = [
            (main, "verify_ai_review_access", "access", RuntimeError("PRIVATE")),
            (ai, "admit_trade_sources", "trade_context", ValueError("PRIVATE")),
            (ai, "compose_review_source", "source_build", ValueError("PRIVATE")),
            (ai, "_call_openai_review", "openai_request", RuntimeError("PRIVATE")),
            (main, "_normalize_ai_review_result", "canonical_finalizer", ValueError("PRIVATE")),
            (main, "_save_ai_review_history_if_enabled", "history", ValueError("PRIVATE")),
        ]
        for index, (owner, name, expected, error) in enumerate(cases):
            # Each probe starts without earlier cached results: cache validation
            # also calls the response normalizer before the new execution starts.
            main._ai_review_idempotency_cache.clear()
            with self.subTest(stage=expected), patch.object(diagnostic, "finish", wraps=diagnostic.finish) as finish, \
                 patch.object(ai, "_call_openai_review", return_value=json.dumps(model_output("basic"))), \
                 patch.object(owner, name, side_effect=error):
                response = fixture.request("POST", "/api/journal/ai-review-once", support.SUPPORTED,
                                           key=f"diagnostic-{index}", batch=case.batch("basic"))
                metadata = finish.call_args.args[0].metadata()
                self.assertEqual(metadata["stage"], expected)
                self.assertFalse(metadata["openai_attempted"])
                self.assertEqual(response.headers["x-request-id"], metadata["request_id"])
                self.assertNotIn("PRIVATE", json.dumps(metadata))
                self.assertNotIn("stage", response.text)
                self.assertIn(response.status_code, (200, 500))

    def test_actual_invalid_model_response_is_openai_response_stage(self):
        fixture = support.ReviewDisplayClientGateTest()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        import os
        before = fixture.case.balance("basic")
        with patch.object(diagnostic, "finish", wraps=diagnostic.finish) as finish, \
             patch.dict(os.environ, {"ALPHAMATE_DEBUG_REVIEW_TESTER_USER_IDS": fixture.case.user_id}), \
             patch.object(fixture.ai, "_call_openai_review", return_value="not-json PRIVATE"):
            response = fixture.request("POST", "/api/journal/ai-review-once", support.SUPPORTED + [("X-StockBoda-Client", "debug")],
                                       key="diagnostic-invalid-output", batch=fixture.case.batch("basic"))
        metadata = finish.call_args.args[0].metadata()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(metadata["stage"], "openai_response")
        self.assertEqual(metadata["access_source"], "debug_tester_basic")
        self.assertTrue(metadata["refunded"])
        self.assertEqual(before, fixture.case.balance("basic"))
        self.assertNotIn("PRIVATE", json.dumps(metadata))

    def test_actual_urlopen_attempt_and_response_decode_are_tracked(self):
        fixture = support.ReviewDisplayClientGateTest()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        import os
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic", "ALPHAMATE_OPENAI_MAX_RETRIES": "0"}):
            value, token = diagnostic.begin()
            try:
                with patch.object(fixture.ai.urllib.request, "urlopen", side_effect=TimeoutError("PRIVATE")) as provider:
                    with self.assertRaises(RuntimeError):
                        fixture.ai._call_openai_review({"review_type": "basic"}, model="gpt-6-luna", instructions="PRIVATE")
                self.assertEqual(provider.call_count, 1)
                self.assertTrue(value.openai_attempted)
                self.assertEqual(value.stage, "openai_request")
                self.assertNotIn("PRIVATE", json.dumps(value.metadata()))
            finally:
                diagnostic.finish(value, token, Mock())
            value, token = diagnostic.begin()
            try:
                response = Mock()
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                response.read.return_value = b"invalid json PRIVATE"
                with patch.object(fixture.ai.urllib.request, "urlopen", return_value=response):
                    with self.assertRaises(RuntimeError):
                        fixture.ai._call_openai_review({"review_type": "basic"}, model="gpt-6-luna", instructions="PRIVATE")
                self.assertTrue(value.openai_attempted)
                self.assertEqual(value.stage, "openai_response")
                self.assertNotIn("PRIVATE", json.dumps(value.metadata()))
            finally:
                diagnostic.finish(value, token, Mock())
