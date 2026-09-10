import logging
import time
import traceback

try:
    from core.credential_redaction import sanitize_text as _sanitize_text
except ModuleNotFoundError:
    from backend.core.credential_redaction import sanitize_text as _sanitize_text


HTTP_SUMMARY_LOGGER = logging.getLogger("uvicorn.error.stockboda_http")
UNKNOWN_ROUTE_TEMPLATE = "<unmatched>"


class CredentialRedactingLogFilter(logging.Filter):
    """Sanitize formatted messages and tracebacks without changing exceptions."""

    def filter(self, record):
        try:
            record.msg = _sanitize_text(record.getMessage())
            record.args = ()
            if record.exc_info:
                formatted_exception = "".join(traceback.format_exception(*record.exc_info))
                record.exc_text = _sanitize_text(formatted_exception)
            elif record.exc_text:
                record.exc_text = _sanitize_text(record.exc_text)
            if record.stack_info:
                record.stack_info = _sanitize_text(record.stack_info)
        except Exception:
            # Fail closed for log content without touching the original exception.
            record.msg = "credential-safe log content unavailable"
            record.args = ()
            record.exc_info = None
            record.exc_text = "[credential-safe traceback redacted]"
            record.stack_info = None
        return True


def _has_credential_filter(filters) -> bool:
    return any(isinstance(item, CredentialRedactingLogFilter) for item in filters)


def install_credential_safe_error_logging(logger=None) -> None:
    target = logger or logging.getLogger("uvicorn.error")
    if not _has_credential_filter(target.filters):
        target.addFilter(CredentialRedactingLogFilter())

    current = target
    visited_handlers = set()
    while current is not None:
        for handler in current.handlers:
            handler_id = id(handler)
            if handler_id in visited_handlers:
                continue
            visited_handlers.add(handler_id)
            if not _has_credential_filter(handler.filters):
                handler.addFilter(CredentialRedactingLogFilter())
        if not current.propagate:
            break
        current = current.parent


def _safe_method(scope: dict) -> str:
    method = str(scope.get("method") or "").upper()
    if method.isalpha() and len(method) <= 16:
        return method
    return "UNKNOWN"


def _safe_route_template(scope: dict) -> str:
    route = scope.get("route")
    template = getattr(route, "path", "")
    if (
        isinstance(template, str)
        and template.startswith("/")
        and "?" not in template
        and "#" not in template
        and len(template) <= 250
    ):
        return template
    return UNKNOWN_ROUTE_TEMPLATE


class CredentialSafeHttpSummaryMiddleware:
    """Log an HTTP summary without reading or rendering the raw request target."""

    def __init__(self, app, *, logger=None, clock=None):
        self.app = app
        self.logger = logger or HTTP_SUMMARY_LOGGER
        self.clock = clock or time.perf_counter

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started_at = self.clock()
        status_code = 500

        async def send_with_status(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            try:
                duration_ms = max(0.0, (self.clock() - started_at) * 1000)
                self.logger.info(
                    "http_request method=%s route=%s status=%d duration_ms=%.2f",
                    _safe_method(scope),
                    _safe_route_template(scope),
                    status_code,
                    duration_ms,
                )
            except Exception:
                # Summary logging must never change the original request result.
                pass
