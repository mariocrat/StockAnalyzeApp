import datetime
import hashlib
import os
import secrets
import sqlite3
import threading
import uuid
from pathlib import Path

from fastapi import HTTPException


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SESSION_DAYS = 30
SUPPORTED_PROVIDERS = {"kakao", "naver"}
_ACCOUNT_LOCK = threading.Lock()


def _env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()

    roots = [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for path in roots:
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, val = raw.split("=", 1)
                if key.strip() == name:
                    return val.strip().strip("\"'")
        except Exception:
            continue
    return ""


def _account_db_path() -> Path:
    configured = _env_value("ALPHAMATE_ACCOUNT_DB_PATH")
    if configured:
        return Path(configured)
    return DATA_DIR / "accounts.sqlite3"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bearer_token(authorization: str | None) -> str:
    text = str(authorization or "").strip()
    if text.lower().startswith("bearer "):
        return text[7:].strip()
    return text


def _connect():
    path = _account_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            journal_storage_enabled INTEGER NOT NULL DEFAULT 0,
            privacy_consent_version TEXT NOT NULL DEFAULT '',
            privacy_consented_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_identities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            email_hash TEXT NOT NULL DEFAULT '',
            connected_at TEXT NOT NULL,
            last_verified_at TEXT NOT NULL,
            UNIQUE(provider, provider_user_id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_token_hash TEXT NOT NULL UNIQUE,
            device_id_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    return conn


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported login provider.")
    return normalized


def _row_to_user(conn, row) -> dict:
    identities = conn.execute(
        """
        SELECT provider, provider_user_id, connected_at, last_verified_at
        FROM user_identities
        WHERE user_id = ?
        ORDER BY connected_at ASC
        """,
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "status": row["status"],
        "journal_storage_enabled": bool(row["journal_storage_enabled"]),
        "privacy_consent_version": row["privacy_consent_version"],
        "privacy_consented_at": row["privacy_consented_at"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "identities": [dict(identity) for identity in identities],
    }


def _get_user(conn, user_id: str) -> dict:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["status"] != "active":
        raise HTTPException(status_code=401, detail="Valid user session is required.")
    return _row_to_user(conn, row)


def _issue_session(conn, user_id: str) -> str:
    token = "ams_" + secrets.token_urlsafe(32)
    created_at = _now()
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=SESSION_DAYS)
    ).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO user_sessions
        (id, user_id, session_token_hash, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (uuid.uuid4().hex, user_id, _hash_token(token), created_at, expires_at),
    )
    return token


def login_dev_provider(*, provider: str, provider_user_id: str, display_name: str = "") -> dict:
    provider = _normalize_provider(provider)
    provider_user_id = str(provider_user_id or "").strip()
    if not provider_user_id:
        raise HTTPException(status_code=400, detail="provider_user_id is required.")

    with _ACCOUNT_LOCK:
        conn = _connect()
        try:
            now = _now()
            identity = conn.execute(
                """
                SELECT user_id
                FROM user_identities
                WHERE provider = ? AND provider_user_id = ?
                """,
                (provider, provider_user_id),
            ).fetchone()
            if identity:
                user_id = identity["user_id"]
                conn.execute(
                    """
                    UPDATE users
                    SET display_name = COALESCE(NULLIF(?, ''), display_name),
                        last_login_at = ?
                    WHERE id = ?
                    """,
                    (str(display_name or "").strip(), now, user_id),
                )
                conn.execute(
                    """
                    UPDATE user_identities
                    SET last_verified_at = ?
                    WHERE provider = ? AND provider_user_id = ?
                    """,
                    (now, provider, provider_user_id),
                )
            else:
                user_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO users
                    (id, display_name, created_at, last_login_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, str(display_name or "").strip(), now, now),
                )
                conn.execute(
                    """
                    INSERT INTO user_identities
                    (id, user_id, provider, provider_user_id, connected_at, last_verified_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (uuid.uuid4().hex, user_id, provider, provider_user_id, now, now),
                )

            token = _issue_session(conn, user_id)
            conn.commit()
            user = _get_user(conn, user_id)
            return {
                "token_type": "bearer",
                "session_token": token,
                "expires_in_days": SESSION_DAYS,
                "user": user,
            }
        finally:
            conn.close()


def authenticate_session(authorization: str | None) -> dict:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Valid user session is required.")

    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT user_id, expires_at, revoked_at
            FROM user_sessions
            WHERE session_token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
        if row is None or row["revoked_at"]:
            raise HTTPException(status_code=401, detail="Valid user session is required.")
        expires_at = datetime.datetime.fromisoformat(row["expires_at"])
        if expires_at <= datetime.datetime.now(datetime.timezone.utc):
            raise HTTPException(status_code=401, detail="User session expired.")
        return _get_user(conn, row["user_id"])
    finally:
        conn.close()


def revoke_session(authorization: str | None) -> dict:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Valid user session is required.")
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = ?
            WHERE session_token_hash = ? AND revoked_at = ''
            """,
            (_now(), _hash_token(token)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def update_journal_storage_setting(*, authorization: str | None, enabled: bool) -> dict:
    user = authenticate_session(authorization)
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE users
            SET journal_storage_enabled = ?
            WHERE id = ?
            """,
            (1 if enabled else 0, user["id"]),
        )
        conn.commit()
        return _get_user(conn, user["id"])
    finally:
        conn.close()
