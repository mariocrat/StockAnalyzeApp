import asyncio
import io
import logging
import sys
import unittest
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from backend.core.credential_redaction import sanitize_text
from backend.core.http_access_log import (
    CredentialRedactingLogFilter,
    CredentialSafeHttpSummaryMiddleware,
    install_credential_safe_error_logging,
)


ROOT = Path(__file__).resolve().parents[1]


class _ListLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(message % args)


class _FailingLogger:
    def info(self, *args, **kwargs):
        raise RuntimeError("synthetic logging sink failure")


class _FailingHandler(logging.Handler):
    def emit(self, record):
        raise RuntimeError("synthetic handler failure")


async def _run_http_request(
    *,
    path,
    query_string,
    route_template,
    headers=(),
    body=b"",
    logger=None,
):
    received = {}
    active_logger = logger if logger is not None else _ListLogger()
    clock_values = iter((10.0, 10.025))

    async def endpoint(scope, receive, send):
        received["path"] = scope["path"]
        received["query_string"] = scope["query_string"]
        received["headers"] = scope["headers"]
        received["body"] = (await receive())["body"]
        scope["route"] = SimpleNamespace(path=route_template)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = CredentialSafeHttpSummaryMiddleware(
        endpoint,
        logger=active_logger,
        clock=lambda: next(clock_values),
    )
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string,
        "headers": list(headers),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        return None

    await middleware(scope, receive, send)
    messages = getattr(active_logger, "messages", [])
    return received, "\n".join(messages)


class CredentialSafeHttpSummaryTest(unittest.TestCase):
    def test_oauth_callback_query_reaches_endpoint_but_not_summary(self):
        query = (
            b"code=SYNTHETIC_OAUTH_CODE_DO_NOT_LOG"
            b"&state=SYNTHETIC_OAUTH_STATE_DO_NOT_LOG"
            b"&code=SYNTHETIC_DUPLICATE_CODE?part=value#fragment"
        )
        headers = ((b"authorization", b"Bearer SYNTHETIC_HEADER_DO_NOT_LOG"),)
        body = b"SYNTHETIC_BODY_MUST_REACH_ENDPOINT"

        received, summary = asyncio.run(
            _run_http_request(
                path="/api/auth/kakao/callback",
                query_string=query,
                route_template="/api/auth/kakao/callback",
                headers=headers,
                body=body,
            )
        )

        self.assertEqual(query, received["query_string"])
        self.assertEqual(list(headers), received["headers"])
        self.assertEqual(body, received["body"])
        self.assertIn("route=/api/auth/kakao/callback", summary)
        self.assertIn("status=204", summary)
        self.assertNotIn("?", summary)
        self.assertNotIn("SYNTHETIC_", summary)

    def test_admob_ssv_query_reaches_endpoint_but_not_summary(self):
        query = (
            b"signature=SYNTHETIC_SIGNATURE_DO_NOT_LOG"
            b"&key_id=synthetic-key&custom_data=synthetic-user"
        )
        headers = ((b"x-alphamate-rtdn-token", b"SYNTHETIC_RTDN_HEADER_DO_NOT_LOG"),)
        body = b"SYNTHETIC_SSV_BODY_MUST_REACH_ENDPOINT"

        received, summary = asyncio.run(
            _run_http_request(
                path="/api/journal/admob-ssv",
                query_string=query,
                route_template="/api/journal/admob-ssv",
                headers=headers,
                body=body,
            )
        )

        self.assertEqual(query, received["query_string"])
        self.assertEqual(list(headers), received["headers"])
        self.assertEqual(body, received["body"])
        self.assertIn("route=/api/journal/admob-ssv", summary)
        self.assertNotIn("SYNTHETIC_", summary)
        self.assertNotIn("custom_data", summary)

    def test_summary_logging_failure_does_not_change_response(self):
        logger = logging.Logger("stockboda_http_failing_handler")
        logger.addHandler(_FailingHandler())
        logger.propagate = False
        received, summary = asyncio.run(
            _run_http_request(
                path="/ok",
                query_string=b"verification_token=SYNTHETIC_QUERY_DO_NOT_LOG",
                route_template="/ok",
                logger=logger,
            )
        )

        self.assertEqual("/ok", received["path"])
        self.assertEqual("", summary)

    def test_summary_logging_failure_does_not_replace_endpoint_exception(self):
        original_error = RuntimeError("synthetic endpoint failure")

        async def failing_endpoint(scope, receive, send):
            scope["route"] = SimpleNamespace(path="/failure")
            raise original_error

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            return None

        middleware = CredentialSafeHttpSummaryMiddleware(
            failing_endpoint,
            logger=_FailingLogger(),
            clock=lambda: 10.0,
        )
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/failure",
            "query_string": b"",
            "headers": [],
        }

        with self.assertRaises(RuntimeError) as raised:
            asyncio.run(middleware(scope, receive, send))
        self.assertIs(original_error, raised.exception)

    def test_formatted_chained_exception_log_redacts_credentials(self):
        output = io.StringIO()
        logger = logging.Logger("uvicorn.error.stockboda_test", logging.ERROR)
        handler = logging.StreamHandler(output)
        logger.addHandler(handler)
        logger.propagate = False
        install_credential_safe_error_logging(logger)

        cause_message = (
            "callback?code=SYNTHETIC_TRACE_CODE_DO_NOT_LOG"
            "&state=SYNTHETIC_TRACE_STATE_DO_NOT_LOG"
        )
        outer_message = "verification_token=SYNTHETIC_CHAINED_TOKEN_DO_NOT_LOG"
        try:
            try:
                raise ValueError(cause_message)
            except ValueError as cause:
                raise RuntimeError(outer_message) from cause
        except RuntimeError as error:
            logger.error(
                "Unhandled URL?shared_token=SYNTHETIC_LOG_MESSAGE_DO_NOT_LOG",
                exc_info=sys.exc_info(),
            )
            self.assertEqual(outer_message, str(error))
            self.assertEqual(cause_message, str(error.__cause__))

        formatted = output.getvalue()
        self.assertNotIn("SYNTHETIC_", formatted)
        self.assertIn("ValueError", formatted)
        self.assertIn("RuntimeError", formatted)
        self.assertIn("direct cause", formatted)

    def test_unknown_route_never_falls_back_to_raw_path(self):
        received, summary = asyncio.run(
            _run_http_request(
                path="/private/SYNTHETIC_PATH_VALUE_DO_NOT_LOG",
                query_string=b"",
                route_template="",
            )
        )

        self.assertEqual("/private/SYNTHETIC_PATH_VALUE_DO_NOT_LOG", received["path"])
        self.assertIn("route=<unmatched>", summary)
        self.assertNotIn("SYNTHETIC_", summary)

    def test_owned_uvicorn_starts_disable_default_access_log(self):
        render = (ROOT / "render.yaml").read_text(encoding="utf-8")
        local_wrapper = (ROOT / "run_backend.bat").read_text(encoding="utf-8")
        main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log", render)
        self.assertIn("uvicorn main:app --host 127.0.0.1 --port 8002 --no-access-log", local_wrapper)
        self.assertIn("reload=True, access_log=False", main)
        self.assertIn("install_credential_safe_error_logging()", main)
        self.assertIn("uvicorn main:app --host 0.0.0.0 --port $PORT --no-access-log", env_example)


class CredentialRedactionPerformanceTest(unittest.TestCase):
    @staticmethod
    def _elapsed(value: str) -> float:
        started_at = perf_counter()
        sanitize_text(value)
        return perf_counter() - started_at

    def test_adversarial_non_matches_have_bounded_linear_sanity(self):
        sizes = (1_000, 2_000, 4_000, 16_000)
        input_factories = (
            lambda size: "-" * size,
            lambda size: "." * size,
            lambda size: ("alpha-._" * ((size // 8) + 1))[:size],
        )

        for make_input in input_factories:
            with self.subTest(input=make_input(16)[:16]):
                elapsed = [self._elapsed(make_input(size)) for size in sizes]
                self.assertLess(elapsed[2], 0.35)
                self.assertLess(elapsed[3], 1.0)
                self.assertLess(elapsed[3], max(0.10, elapsed[0] * 64))

    def test_bounded_multiline_quoted_credentials_fail_closed(self):
        limit = 256
        inputs = {
            "plain_quote": (
                "x" * 120
                + ' private_key="SYNTHETIC_FIRST_LINE\nSYNTHETIC_SECOND_LINE'
                + "y" * 300
                + '"'
            ),
            "escaped_quote": (
                "x" * 120
                + r' {\"verification_token\":\"SYNTHETIC_FIRST_LINE'
                + "\nSYNTHETIC_SECOND_LINE"
                + "y" * 300
                + r'\"}'
            ),
        }

        for label, raw in inputs.items():
            with self.subTest(label=label):
                original = raw[:]
                safe = sanitize_text(raw, limit=limit)
                self.assertEqual(original, raw)
                self.assertLessEqual(len(safe), limit)
                self.assertNotIn("SYNTHETIC_", safe)
                self.assertIn("[redacted]", safe)
                self.assertIn("[truncated]", safe)

    def test_truncation_boundaries_do_not_expose_credential_content(self):
        limit = 160
        secret = "SYNTHETIC_BOUNDARY_SECRET_DO_NOT_LOG"

        def near_limit(suffix: str, visible_suffix: int) -> str:
            return "x" * max(0, limit - visible_suffix) + suffix

        inputs = {
            "key_start": near_limit(f" private_key={secret}", 5),
            "encoded_key_crossing": near_limit(f" %63ode={secret}", 3),
            "between_key_and_equal": near_limit(f" private_key   ={secret}", 14),
            "immediately_after_equal": near_limit(f" private_key={secret}", 13),
            "quoted_value_start": near_limit(f' private_key="{secret}"', 15),
            "value_middle": near_limit(f' private_key="{secret}"', 36),
            "escaped_quote": near_limit(f' private_key="AA\\\"{secret}"', 46),
            "escaped_backslash": near_limit(f' private_key="AA\\\\{secret}"', 46),
            "before_lf": near_limit(f' private_key="AA\n{secret}"', 28),
            "after_crlf": near_limit(f' private_key="AA\r\n{secret}"', 30),
            "multiline": near_limit(f' private_key="AA\n{secret}' + "z" * 200 + '"', 48),
            "duplicate_query": near_limit(f" code={secret}&code={secret}", 48),
            "long_benign_prefix": "benign " * 40 + f' private_key="{secret}"',
            "empty_value": near_limit(" verification_token=", 24),
            "dangling_backslash": near_limit(" verification_token=\\", 25),
            "malformed_percent_value": near_limit(" code=%GZ", 12),
            "trailing_cr": near_limit(" Cookie: value\r", 15),
            "trailing_lf": near_limit(" Cookie: value\n", 15),
            "control_character": near_limit(f" code={secret}\x00tail", 48),
        }

        for label, raw in inputs.items():
            with self.subTest(label=label):
                original = raw[:]
                safe = sanitize_text(raw, limit=limit)
                self.assertEqual(original, raw)
                self.assertLessEqual(len(safe), limit)
                self.assertNotIn("SYNTHETIC_", safe)

    def test_uvicorn_filter_multiline_inputs_avoid_quadratic_scaling(self):
        sizes = (128 * 1024, 256 * 1024, 512 * 1024)
        patterns = {
            "lf_header": "Cookie: SYNTHETIC_HEADER_VALUE\n",
            "crlf_header": "Cookie: SYNTHETIC_HEADER_VALUE\r\n",
            "cr_header": "Cookie: SYNTHETIC_HEADER_VALUE\r",
            "quoted_multiline": 'private_key="SYNTHETIC_FIRST\nSYNTHETIC_SECOND"\n',
            "escaped_multiline": r'{\"verification_token\":\"SYNTHETIC_ESCAPED\"}' + "\n",
        }
        credential_filter = CredentialRedactingLogFilter()

        for label, pattern in patterns.items():
            elapsed = []
            for size in sizes:
                message = (pattern * ((size // len(pattern)) + 1))[:size]
                record = logging.LogRecord(
                    "uvicorn.error",
                    logging.ERROR,
                    "",
                    0,
                    message,
                    (),
                    None,
                )
                started_at = perf_counter()
                credential_filter.filter(record)
                elapsed.append(perf_counter() - started_at)
                self.assertNotIn("SYNTHETIC_", str(record.msg))

            with self.subTest(label=label, elapsed=elapsed):
                self.assertLess(elapsed[-1], 2.0)
                self.assertLess(elapsed[-1], max(0.20, elapsed[0] * 7))

        final_record = logging.LogRecord(
            "uvicorn.error",
            logging.ERROR,
            "",
            0,
            'trace tail private_key="SYNTHETIC_AT_STRING_END',
            (),
            None,
        )
        credential_filter.filter(final_record)
        self.assertNotIn("SYNTHETIC_", str(final_record.msg))

if __name__ == "__main__":
    unittest.main()
