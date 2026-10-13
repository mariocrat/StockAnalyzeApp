import datetime
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from backend.core.review_history_approved_write import ApprovedHistoryWrite, validate_approved_history_write
from backend.core.review_durable_storage_approval import (
    ApprovedDurableHistoryEnvelope, issue_durable_history, validate_durable_write, validate_paired_history_input,
)
from backend.core.review_history_json_codec import require, sql_json
from backend.core.review_history_paired import (
    StoredPairedHistoryRow, admit_stored_paired_history, paired_history_projection, paired_marker, paired_marker_in_text,
)

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


def _row_to_detail(row) -> dict | StoredPairedHistoryRow:
    raw = row["ai_review_json"]
    if paired_marker_in_text(raw):
        return StoredPairedHistoryRow.from_row(row)
    review = _json_loads(raw)
    # Ambiguous/malformed input cannot acquire legacy admission after parsing.
    if review is None or paired_marker(review):
        return StoredPairedHistoryRow.from_row(row)
    data = _row_to_summary(row)
    data.update({
        "trade_snapshot": _json_loads(row["trade_snapshot_json"]),
        "recent_trades_snapshot": _json_loads(row["recent_trades_snapshot_json"]),
        "chart_snapshot": _json_loads(row["chart_snapshot_json"]),
        "ai_review": review,
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


_COMMITTED_RESULT = object()


@dataclass(frozen=True, slots=True, init=False)
class CommittedPairedHistoryWrite:
    """Post-commit identity and pre-commit frozen admitted view; no write authority."""
    id: int
    user_id: str
    _record: bytes
    _acknowledged: bool

    def __init__(self, row_id, user_id, record, *, _authority=None):
        require(_authority is _COMMITTED_RESULT, "COMMITTED_RESULT_AUTHORITY_REQUIRED")
        object.__setattr__(self, "id", row_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_acknowledged", False)

    @property
    def record(self):
        require(self._acknowledged, "HISTORY_NOT_COMMITTED")
        return json.loads(self._record)

    @property
    def committed(self):
        return self._acknowledged


class PairedHistoryCommitUnknown(RuntimeError):
    """Commit did not acknowledge an outcome; callers must reconcile, not retry."""
    def __init__(self, row_id, user_id):
        super().__init__("paired history commit outcome unknown")
        self.row_id, self.user_id = row_id, user_id


class PairedHistoryPublicationError(RuntimeError):
    def __init__(self, committed):
        super().__init__("paired history committed; publication failed")
        self.committed_result = committed


def _insert_paired_review_history(conn, approved: ApprovedDurableHistoryEnvelope):
    """Only issued envelope authority can supply the complete fifteen SQL binds."""
    validate_durable_write(approved)
    conn.execute("""INSERT INTO review_history (
        id, user_id, review_type, ticker, name, trade_date, target_trade_id,
        trade_snapshot_json, recent_trades_snapshot_json, chart_snapshot_json,
        ai_review_json, access_snapshot_json, model, source, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", approved.sql_bind_values)


def add_paired_review_history(capture, approved_write: ApprovedHistoryWrite, *, unsafe_text):
    """Reserve an actual ID and issue/insert one full pair under one write lock.

    No runtime generation caller uses this separate boundary. Successful commit
    returns its known identity/view without a post-commit SELECT dependency.
    """
    validate_paired_history_input(capture, approved_write)
    require(callable(unsafe_text), "INVALID_SAFETY_PREDICATE")
    conn = _connect()
    committed, row_id, commit_started, pending_unknown = None, None, False, None
    owner = approved_write.bind_values[0]
    try:
        conn.execute("BEGIN IMMEDIATE")
        maximum = conn.execute("SELECT max(id) FROM review_history").fetchone()[0] or 0
        sequence = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'review_history'").fetchone()
        row_id = max(maximum, (sequence[0] or 0) if sequence else 0) + 1
        require(type(row_id) is int and 1 <= row_id <= 2**53 - 1, "INVALID_ROW_ID")
        envelope = issue_durable_history(capture=capture, approved_write=approved_write, row_id=row_id)
        parameters = envelope.sql_bind_values
        row = dict(zip(("id", "user_id", "review_type", "ticker", "name", "trade_date", "target_trade_id",
            "trade_snapshot_json", "recent_trades_snapshot_json", "chart_snapshot_json", "ai_review_json",
            "access_snapshot_json", "model", "source", "created_at"), parameters))
        admission = admit_stored_paired_history(StoredPairedHistoryRow.from_row(row), unsafe_text=unsafe_text)
        frozen = sql_json(paired_history_projection(admission, unsafe_text=unsafe_text))
        # Allocate/freeze the complete result before INSERT/commit; publish its
        # committed state only after SQLite acknowledges the commit.
        prepared_result = CommittedPairedHistoryWrite(row_id, owner, frozen, _authority=_COMMITTED_RESULT)
        _insert_paired_review_history(conn, envelope)
        commit_started = True
        conn.commit()
        object.__setattr__(prepared_result, "_acknowledged", True)
        committed = prepared_result
        return committed
    except Exception as error:
        if commit_started and not conn.in_transaction:
            pending_unknown = PairedHistoryCommitUnknown(row_id, owner)
            raise pending_unknown from error
        conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception as error:
            if committed is not None:
                raise PairedHistoryPublicationError(committed) from error
            if pending_unknown is not None:
                raise pending_unknown from error
            raise


def reread_paired_review_history(committed: CommittedPairedHistoryWrite):
    """Optional publication read; failure retains the already committed identity."""
    require(type(committed) is CommittedPairedHistoryWrite, "INVALID_COMMITTED_RESULT")
    require(committed.committed, "HISTORY_NOT_COMMITTED")
    try:
        result = get_review_history(committed.id, user_id=committed.user_id)
        if result is None:
            raise RuntimeError("committed history row unavailable")
        return result
    except Exception as error:
        raise PairedHistoryPublicationError(committed) from error


def list_review_history(*, user_id: str, limit: int = 100) -> list[dict | StoredPairedHistoryRow]:
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


def get_review_history(review_id: int, *, user_id: str) -> dict | StoredPairedHistoryRow | None:
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
