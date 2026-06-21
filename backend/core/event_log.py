import datetime
import json
import sqlite3
import threading
import uuid
from pathlib import Path

from fastapi import HTTPException

try:
    from core.env import env_value
except ModuleNotFoundError:
    from backend.core.env import env_value


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SECRET_KEY_PARTS = {
    "authorization",
    "code",
    "password",
    "private",
    "purchase_token",
    "secret",
    "signature",
    "token",
}
_EVENT_LOG_LOCK = threading.Lock()


def _env_value(name: str) -> str:
    return env_value(name)


def event_log_db_path() -> Path:
    configured = _env_value("ALPHAMATE_EVENT_LOG_DB_PATH")
    if configured:
        return Path(configured)
    return DATA_DIR / "event_log.sqlite3"


def _connect():
    path = event_log_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operational_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL DEFAULT '',
            status_code INTEGER NOT NULL DEFAULT 0,
            user_id TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operational_events_created_at
        ON operational_events (created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operational_events_type_status
        ON operational_events (event_type, status_code)
        """
    )
    return conn


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _should_redact_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return any(part in normalized for part in SECRET_KEY_PARTS)


def _redact(value):
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if _should_redact_key(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _details_json(details: dict | None) -> str:
    safe_details = _redact(details or {})
    return json.dumps(safe_details, ensure_ascii=False, sort_keys=True)


def record_event(
    *,
    level: str,
    event_type: str,
    method: str = "",
    path: str = "",
    status_code: int = 0,
    user_id: str = "",
    message: str = "",
    details: dict | None = None,
) -> dict:
    event = {
        "id": uuid.uuid4().hex,
        "created_at": _now(),
        "level": str(level or "info"),
        "event_type": str(event_type or "event"),
        "method": str(method or ""),
        "path": str(path or ""),
        "status_code": int(status_code or 0),
        "user_id": str(user_id or ""),
        "message": str(message or "")[:1000],
        "details_json": _details_json(details),
    }
    with _EVENT_LOG_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO operational_events (
                    id, created_at, level, event_type, method, path,
                    status_code, user_id, message, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["created_at"],
                    event["level"],
                    event["event_type"],
                    event["method"],
                    event["path"],
                    event["status_code"],
                    event["user_id"],
                    event["message"],
                    event["details_json"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return event


def record_api_failure(
    *,
    method: str,
    path: str,
    status_code: int,
    message: str = "",
    user_id: str = "",
    details: dict | None = None,
) -> dict:
    return record_event(
        level="error" if int(status_code or 0) >= 500 else "warning",
        event_type="api_request_failed",
        method=method,
        path=path,
        status_code=status_code,
        user_id=user_id,
        message=message or f"HTTP {status_code}",
        details=details,
    )


def record_api_exception(*, method: str, path: str, exc: Exception, user_id: str = "") -> dict:
    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) else exc.__class__.__name__
    return record_api_failure(
        method=method,
        path=path,
        status_code=status_code,
        user_id=user_id,
        message=str(detail or ""),
        details={"exception_type": exc.__class__.__name__},
    )


def list_events(*, limit: int = 100) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM operational_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 100), 1000)),),
        ).fetchall()
        return [
            {
                **dict(row),
                "details": json.loads(row["details_json"] or "{}"),
            }
            for row in rows
        ]
    finally:
        conn.close()
