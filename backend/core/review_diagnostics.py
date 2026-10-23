"""Request-local, allowlisted diagnostics; never retain review inputs or errors."""
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
import re
import time
import uuid
from starlette.middleware.errors import ServerErrorMiddleware

_current = ContextVar("review_diagnostics", default=None)
STAGES = frozenset({"access", "trade_context", "source_build", "openai_request",
                    "openai_response", "canonical_finalizer", "history", "cache"})
STATUSES = frozenset({"ready", "error", "request_error", "missing_key", "empty",
                      "invalid_structured_output", "safety_rejected"})


@dataclass
class ReviewDiagnostic:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.monotonic)
    stage: str = "access"
    failed: bool = False
    review_type: str = "unknown"
    internal_status: str = "unknown"
    error_class: str = "none"
    openai_attempted: bool = False
    model: str = "none"
    access_source: str = "unknown"
    refunded: bool = False
    display_generated: bool = False

    def metadata(self):
        return {key: getattr(self, key) for key in (
            "request_id", "stage", "review_type", "internal_status", "error_class",
            "openai_attempted", "model", "access_source", "refunded", "display_generated"
        )} | {"elapsed_ms": round((time.monotonic() - self.started) * 1000, 2)}


def begin():
    diagnostic = ReviewDiagnostic()
    return diagnostic, _current.set(diagnostic)


def stage(value):
    diagnostic = _current.get()
    if diagnostic is not None and not diagnostic.failed and value in STAGES:
        diagnostic.stage = value


def update(**fields):
    diagnostic = _current.get()
    if diagnostic is None:
        return
    for key, value in fields.items():
        if key in {"openai_attempted", "refunded", "display_generated"} and type(value) is bool:
            setattr(diagnostic, key, value)
        elif key == "review_type" and type(value) is str and value in {"basic", "advanced"}:
            diagnostic.review_type = value
        elif key == "internal_status" and type(value) is str and value in STATUSES:
            diagnostic.internal_status = value
        elif key == "model" and type(value) is str and re.fullmatch(r"(?:gpt-[a-zA-Z0-9.-]{1,60}|o[134](?:-mini)?)", value):
            diagnostic.model = value
        elif key == "access_source" and type(value) is str and value in {
            "debug_tester_basic", "debug_tester_advanced", "signup_basic", "signup_advanced",
            "free_daily_basic", "rewarded_ad_basic", "weekly_ad_advanced", "purchased_basic",
            "purchased_advanced", "purchased_advanced_as_basic", "pro_monthly_basic",
            "pro_monthly_advanced", "review_basic", "review_advanced",
        }:
            diagnostic.access_source = value


def fail(error=None, *, status=None):
    diagnostic = _current.get()
    if diagnostic is None:
        return
    if not diagnostic.failed:
        diagnostic.failed = True
        # Exception messages and arbitrary class names can contain caller data.
        diagnostic.error_class = next((name for cls, name in (
            (ValueError, "ValueError"), (TypeError, "TypeError"), (KeyError, "KeyError"),
            (RuntimeError, "RuntimeError"), (TimeoutError, "TimeoutError"),
        ) if isinstance(error, cls)), "Exception" if error is not None else "none")
    update(internal_status=status)


def recovered():
    diagnostic = _current.get()
    if diagnostic is not None:
        diagnostic.failed = False
        diagnostic.error_class = "none"
        diagnostic.internal_status = "unknown"


def finish(diagnostic, token, record):
    try:
        metadata = diagnostic.metadata()
        try:
            record(level="info", event_type="review_diagnostic", method="POST",
                   path="/api/journal/ai-review-once", message="Review diagnostic", details=metadata)
        except Exception:
            pass
        # Keep an independent channel even if SQLite telemetry silently drops a write.
        try:
            import json
            logging.getLogger("uvicorn.error").info("review_diagnostic %s", json.dumps(metadata, sort_keys=True))
        except Exception:
            pass
    finally:
        _current.reset(token)


class ReviewDiagnosticsMiddleware:
    def __init__(self, app, record):
        self.app, self.record = app, record

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/journal/ai-review-once":
            return await self.app(scope, receive, send)
        diagnostic, token = begin()
        scope.setdefault("state", {})["review_request_id"] = diagnostic.request_id

        async def send_response(message):
            if message["type"] == "http.response.start":
                if message["status"] >= 400:
                    fail(status="request_error")
                message = dict(message, headers=[(key, value) for key, value in message.get("headers", [])
                                                if key.lower() != b"x-request-id"] +
                               [(b"x-request-id", diagnostic.request_id.encode("ascii"))])
            await send(message)

        async def run(inner_scope, inner_receive, inner_send):
            try:
                await self.app(inner_scope, inner_receive, inner_send)
            except Exception as error:
                fail(error)
                raise

        try:
            # Preserve Starlette's ordinary 500 body and exception propagation,
            # while ensuring even unhandled failures carry the correlation header.
            await ServerErrorMiddleware(run)(scope, receive, send_response)
        finally:
            finish(diagnostic, token, self.record)
