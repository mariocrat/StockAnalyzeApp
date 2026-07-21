import datetime
import json
import sqlite3
from pathlib import Path

try:
    from core.env import env_value
except ModuleNotFoundError:
    from backend.core.env import env_value


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
COMPARISON_VERSION = "luna-terra-v1"
ALLOWED_MODELS = {
    "luna": "gpt-5.6-luna",
    "terra": "gpt-5.6-terra",
}


class QaComparisonUnavailable(RuntimeError):
    pass


def _db_path() -> Path:
    configured = env_value("ALPHAMATE_ACCESS_DB_PATH")
    return Path(configured) if configured else DATA_DIR / "access.sqlite3"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qa_advanced_comparison_owner (
            version TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            claimed_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qa_advanced_comparison_runs (
            version TEXT NOT NULL,
            model_variant TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (version, model_variant)
        )
        """
    )
    return conn


def begin_comparison(*, user_id: str, model_variant: str) -> dict:
    variant = str(model_variant or "").strip().lower()
    if variant not in ALLOWED_MODELS:
        raise ValueError("지원하지 않는 심화 복기 비교 모델입니다.")

    now = _now()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        owner = conn.execute(
            "SELECT user_id FROM qa_advanced_comparison_owner WHERE version = ?",
            (COMPARISON_VERSION,),
        ).fetchone()
        if owner is None:
            conn.execute(
                "INSERT INTO qa_advanced_comparison_owner (version, user_id, claimed_at) VALUES (?, ?, ?)",
                (COMPARISON_VERSION, str(user_id), now.isoformat(timespec="seconds")),
            )
        elif owner["user_id"] != str(user_id):
            raise QaComparisonUnavailable("이 QA 비교 이용권은 다른 테스트 계정에서 이미 시작했습니다.")

        row = conn.execute(
            """
            SELECT status, result_json, started_at
            FROM qa_advanced_comparison_runs
            WHERE version = ? AND model_variant = ?
            """,
            (COMPARISON_VERSION, variant),
        ).fetchone()
        if row and row["status"] == "completed":
            conn.commit()
            return {
                "run": False,
                "cached_result": json.loads(row["result_json"] or "{}"),
            }

        if row and row["status"] == "running":
            try:
                started_at = datetime.datetime.fromisoformat(row["started_at"])
            except (TypeError, ValueError):
                started_at = now - datetime.timedelta(minutes=10)
            if now - started_at < datetime.timedelta(minutes=3):
                raise QaComparisonUnavailable("같은 모델의 테스트가 이미 진행 중입니다. 잠시 후 다시 확인해 주세요.")

        conn.execute(
            """
            INSERT INTO qa_advanced_comparison_runs (
                version, model_variant, user_id, status, result_json, started_at, completed_at
            ) VALUES (?, ?, ?, 'running', '{}', ?, '')
            ON CONFLICT(version, model_variant) DO UPDATE SET
                user_id = excluded.user_id,
                status = 'running',
                result_json = '{}',
                started_at = excluded.started_at,
                completed_at = ''
            """,
            (COMPARISON_VERSION, variant, str(user_id), now.isoformat(timespec="seconds")),
        )
        conn.commit()
        return {"run": True, "cached_result": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_comparison(*, user_id: str, model_variant: str, result: dict):
    variant = str(model_variant or "").strip().lower()
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE qa_advanced_comparison_runs
            SET status = 'completed', result_json = ?, completed_at = ?
            WHERE version = ? AND model_variant = ? AND user_id = ?
            """,
            (
                json.dumps(result or {}, ensure_ascii=False),
                _now().isoformat(timespec="seconds"),
                COMPARISON_VERSION,
                variant,
                str(user_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def release_comparison(*, user_id: str, model_variant: str):
    variant = str(model_variant or "").strip().lower()
    conn = _connect()
    try:
        conn.execute(
            """
            DELETE FROM qa_advanced_comparison_runs
            WHERE version = ? AND model_variant = ? AND user_id = ? AND status = 'running'
            """,
            (COMPARISON_VERSION, variant, str(user_id)),
        )
        conn.commit()
    finally:
        conn.close()
