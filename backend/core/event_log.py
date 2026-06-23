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
MAX_DETAIL_STRING_LENGTH = 1000
MAX_DETAIL_LIST_LENGTH = 50
MAX_DETAIL_DICT_KEYS = 50
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
        safe = {}
        items = list(value.items())
        for key, item in items[:MAX_DETAIL_DICT_KEYS]:
            safe[str(key)] = "[redacted]" if _should_redact_key(str(key)) else _redact(item)
        if len(items) > MAX_DETAIL_DICT_KEYS:
            safe["__truncated_keys__"] = len(items) - MAX_DETAIL_DICT_KEYS
        return safe
    if isinstance(value, list):
        return [_redact(item) for item in value[:MAX_DETAIL_LIST_LENGTH]]
    if isinstance(value, str):
        if len(value) > MAX_DETAIL_STRING_LENGTH:
            return f"{value[:MAX_DETAIL_STRING_LENGTH]}[truncated]"
        return value
    if isinstance(value, (int, float, bool)) or value is None:
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


def record_api_exception(
    *,
    method: str,
    path: str,
    exc: Exception,
    user_id: str = "",
    details: dict | None = None,
) -> dict:
    status_code = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) else exc.__class__.__name__
    safe_details = {"exception_type": exc.__class__.__name__}
    safe_details.update(details or {})
    return record_api_failure(
        method=method,
        path=path,
        status_code=status_code,
        user_id=user_id,
        message=str(detail or ""),
        details=safe_details,
    )


def _json_like_text(value: str) -> str:
    return json.dumps(str(value or "").strip(), ensure_ascii=False)[1:-1]


def list_events(
    *,
    limit: int = 100,
    level: str = "",
    event_type: str = "",
    request_id: str = "",
    user_id: str = "",
    path: str = "",
    status_code: int | None = None,
    event_id: str = "",
    created_after: str = "",
    created_before: str = "",
) -> list[dict]:
    filters = []
    params = []
    if str(event_id or "").strip():
        filters.append("id = ?")
        params.append(str(event_id).strip())
    if str(level or "").strip():
        filters.append("level = ?")
        params.append(str(level).strip())
    if str(event_type or "").strip():
        filters.append("event_type = ?")
        params.append(str(event_type).strip())
    if str(request_id or "").strip():
        filters.append("details_json LIKE ?")
        params.append(f'%"request_id": "{_json_like_text(request_id)}"%')
    if str(user_id or "").strip():
        filters.append("user_id = ?")
        params.append(str(user_id).strip())
    if str(path or "").strip():
        filters.append("path = ?")
        params.append(str(path).strip())
    if status_code is not None:
        filters.append("status_code = ?")
        params.append(int(status_code))
    if str(created_after or "").strip():
        filters.append("created_at >= ?")
        params.append(str(created_after).strip())
    if str(created_before or "").strip():
        filters.append("created_at <= ?")
        params.append(str(created_before).strip())
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 100), 1000)))

    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM operational_events
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
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


def summarize_events(
    *,
    limit: int = 500,
    level: str = "",
    event_type: str = "",
    request_id: str = "",
    user_id: str = "",
    path: str = "",
    status_code: int | None = None,
    event_id: str = "",
    created_after: str = "",
    created_before: str = "",
) -> dict:
    rows = list_events(
        limit=limit,
        level=level,
        event_type=event_type,
        request_id=request_id,
        user_id=user_id,
        path=path,
        status_code=status_code,
        event_id=event_id,
        created_after=created_after,
        created_before=created_before,
    )
    by_level: dict[str, int] = {}
    by_event_type: dict[str, int] = {}
    by_path: dict[str, int] = {}

    for row in rows:
        level = str(row.get("level") or "info")
        event_type = str(row.get("event_type") or "event")
        path = str(row.get("path") or "")
        by_level[level] = by_level.get(level, 0) + 1
        by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
        if path:
            by_path[path] = by_path.get(path, 0) + 1

    def _top_items(values: dict[str, int]) -> list[dict]:
        return [
            {"name": name, "count": count}
            for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

    return {
        "total": len(rows),
        "sample_limit": max(1, min(int(limit or 500), 1000)),
        "by_level": by_level,
        "by_event_type": by_event_type,
        "by_path": by_path,
        "top_events": _top_items(by_event_type),
        "top_paths": _top_items(by_path),
    }


def purge_events_older_than(*, retention_days: int = 90) -> dict:
    days = int(retention_days or 90)
    if days < 7:
        raise ValueError("retention_days must be at least 7.")
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    cutoff_text = cutoff.isoformat(timespec="seconds")

    with _EVENT_LOG_LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM operational_events WHERE created_at < ?",
                (cutoff_text,),
            )
            conn.commit()
            deleted_count = int(cur.rowcount or 0)
        finally:
            conn.close()

    return {
        "deleted_count": deleted_count,
        "retention_days": days,
        "cutoff": cutoff_text,
    }


def purge_configured_retention() -> dict:
    configured = str(_env_value("ALPHAMATE_EVENT_LOG_RETENTION_DAYS") or "").strip()
    if not configured:
        return {"skipped": True, "reason": "not_configured"}
    try:
        retention_days = int(configured)
    except ValueError:
        return {"skipped": True, "reason": "invalid_retention_days"}
    try:
        return purge_events_older_than(retention_days=retention_days)
    except ValueError as exc:
        return {"skipped": True, "reason": str(exc)}
