import datetime
import json
import sqlite3
from pathlib import Path

from backend.core.review_history_approved_write import ApprovedHistoryWrite, validate_approved_history_write

try:
    from core.env import database_path, env_value
except ModuleNotFoundError:
    from backend.core.env import database_path, env_value


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _db_path() -> Path:
    return database_path("ALPHAMATE_REVIEW_HISTORY_DB_PATH")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: str):
    def unique_object(pairs):
        result = {}
        for key, child in pairs:
            if key in result:
                raise ValueError("duplicate history snapshot key")
            result[key] = child
        return result

    try:
        return json.loads(value, object_pairs_hook=unique_object)
    except (TypeError, ValueError, RecursionError):
        # Do not turn a corrupt snapshot into a supported empty legacy shape.
        return None


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            review_type TEXT NOT NULL CHECK(review_type IN ('basic', 'advanced')),
            ticker TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            trade_date TEXT NOT NULL DEFAULT '',
            target_trade_id INTEGER,
            trade_snapshot_json TEXT NOT NULL DEFAULT '{}',
            recent_trades_snapshot_json TEXT NOT NULL DEFAULT '[]',
            chart_snapshot_json TEXT NOT NULL DEFAULT '{}',
            ai_review_json TEXT NOT NULL DEFAULT '{}',
            access_snapshot_json TEXT NOT NULL DEFAULT '{}',
            model TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def _row_to_summary(row) -> dict:
    return {
        "id": row["id"],
        "review_type": row["review_type"],
        "ticker": row["ticker"],
        "name": row["name"],
        "trade_date": row["trade_date"],
        "target_trade_id": row["target_trade_id"],
        "model": row["model"],
        "source": row["source"],
        "created_at": row["created_at"],
    }


def _row_to_detail(row) -> dict:
    data = _row_to_summary(row)
    data.update({
        "trade_snapshot": _json_loads(row["trade_snapshot_json"]),
        "recent_trades_snapshot": _json_loads(row["recent_trades_snapshot_json"]),
        "chart_snapshot": _json_loads(row["chart_snapshot_json"]),
        "ai_review": _json_loads(row["ai_review_json"]),
        "access_snapshot": _json_loads(row["access_snapshot_json"]),
    })
    return data


def _read_connect():
    """Existing rows only: reads never create a DB or initialize its schema."""
    path = _db_path().resolve()
    if not path.is_file():
        return None
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def add_review_history(approved: ApprovedHistoryWrite) -> dict:
    """Write only already admitted immutable parameters, before any DB access."""
    validate_approved_history_write(approved)
    parameters = approved.bind_values
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO review_history (
                user_id, review_type, ticker, name, trade_date, target_trade_id,
                trade_snapshot_json, recent_trades_snapshot_json, chart_snapshot_json,
                ai_review_json, access_snapshot_json, model, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            parameters,
        )
        conn.commit()
        return get_review_history(cur.lastrowid, user_id=parameters[0])
    finally:
        conn.close()


def list_review_history(*, user_id: str, limit: int = 100) -> list[dict]:
    conn = _read_connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT * FROM review_history
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (str(user_id), int(limit or 100)),
        ).fetchall()
        # Every caller receives a whole row. The API may project a list item
        # only after the same admission used for detail and export.
        return [_row_to_detail(row) for row in rows]
    finally:
        conn.close()


def get_review_history(review_id: int, *, user_id: str) -> dict | None:
    conn = _read_connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM review_history WHERE id = ? AND user_id = ?",
            (int(review_id), str(user_id)),
        ).fetchone()
        return _row_to_detail(row) if row else None
    finally:
        conn.close()


def delete_review_history(review_id: int, *, user_id: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "DELETE FROM review_history WHERE id = ? AND user_id = ?",
            (int(review_id), str(user_id)),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def clear_review_history(*, user_id: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM review_history WHERE user_id = ?", (str(user_id),))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
