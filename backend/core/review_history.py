import datetime
import json
import sqlite3
from pathlib import Path

try:
    from core.env import env_value
except ModuleNotFoundError:
    from backend.core.env import env_value


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _db_path() -> Path:
    configured = env_value("ALPHAMATE_REVIEW_HISTORY_DB_PATH")
    return Path(configured) if configured else DATA_DIR / "review_history.sqlite3"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: str, fallback):
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


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
        "trade_snapshot": _json_loads(row["trade_snapshot_json"], {}),
        "recent_trades_snapshot": _json_loads(row["recent_trades_snapshot_json"], []),
        "chart_snapshot": _json_loads(row["chart_snapshot_json"], {}),
        "ai_review": _json_loads(row["ai_review_json"], {}),
        "access_snapshot": _json_loads(row["access_snapshot_json"], {}),
    })
    return data


def add_review_history(
    *,
    user_id: str,
    review_type: str,
    ticker: str = "",
    name: str = "",
    trade_date: str = "",
    target_trade_id=None,
    trade_snapshot=None,
    recent_trades_snapshot=None,
    chart_snapshot=None,
    ai_review=None,
    access_snapshot=None,
    model: str = "",
    source: str = "",
) -> dict:
    normalized_type = "advanced" if review_type == "advanced" else "basic"
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
            (
                str(user_id),
                normalized_type,
                str(ticker or ""),
                str(name or ""),
                str(trade_date or ""),
                target_trade_id,
                _json_dumps(trade_snapshot),
                _json_dumps(recent_trades_snapshot if recent_trades_snapshot is not None else []),
                _json_dumps(chart_snapshot),
                _json_dumps(ai_review),
                _json_dumps(access_snapshot),
                str(model or ""),
                str(source or ""),
                _now(),
            ),
        )
        conn.commit()
        return get_review_history(cur.lastrowid, user_id=user_id)
    finally:
        conn.close()


def list_review_history(*, user_id: str, limit: int = 100) -> list[dict]:
    conn = _connect()
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
        return [_row_to_summary(row) for row in rows]
    finally:
        conn.close()


def get_review_history(review_id: int, *, user_id: str) -> dict | None:
    conn = _connect()
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
