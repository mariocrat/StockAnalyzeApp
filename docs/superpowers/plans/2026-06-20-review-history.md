# Review History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `복기 보관함` feature that stores eligible AI review results with the trade chart context, lets users revisit them, includes them in export/delete flows, and shows one entry ad for the archive.

**Architecture:** Add a focused backend `review_history` persistence module backed by SQLite. Wire AI review execution to save history only for authenticated users with journal storage enabled. Add a dedicated frontend archive view inside the journal area, with a session-scoped interstitial ad gate on first entry.

**Tech Stack:** FastAPI, SQLite, Python unittest, React, Axios, Capacitor AdMob, Vite.

---

## File Structure

- Create `backend/core/review_history.py`
  - Owns SQLite schema and CRUD for saved AI review history.
  - Stores JSON snapshots as text to avoid coupling history records to changing live trade rows.
- Modify `backend/main.py`
  - Registers review history list/detail/delete endpoints.
  - Saves history after `POST /api/journal/ai-review-once` only when the logged-in user has `journal_storage_enabled`.
  - Adds review history to `/api/me/export-data`.
- Modify `backend/core/account_store.py`
  - Includes review history deletion in account data deletion.
- Create `tests/test_review_history.py`
  - Covers persistence, user isolation, and delete behavior.
- Modify `tests/test_me_data_routes.py`
  - Covers export including review history.
- Modify `tests/test_account_store.py`
  - Covers account deletion removing review history.
- Modify `tests/test_auth_routes.py`
  - Covers route registration.
- Modify `frontend/src/mobile/admobPolicy.js`
  - Adds interstitial ad unit policy guards.
- Modify `frontend/src/mobile/admob.js`
  - Adds `showReviewHistoryInterstitial()`.
- Modify `frontend/src/components/TradingJournal.jsx`
  - Adds archive view state, list/detail API calls, save-status display, and ad-gated entry.
- Modify `frontend/src/App.css`
  - Adds archive list/detail styling.
- Modify docs after implementation:
  - `docs/development_history.md`
  - `docs/manual_test_guide.md`
  - `docs/security_deployment_plan.md`

---

### Task 1: Backend Review History Store

**Files:**
- Create: `backend/core/review_history.py`
- Test: `tests/test_review_history.py`

- [ ] **Step 1: Write failing persistence tests**

Add `tests/test_review_history.py`:

```python
import importlib
import os
import tempfile
import unittest


class ReviewHistoryStoreTest(unittest.TestCase):
    def test_review_history_is_isolated_by_user_and_returns_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            from backend.core import review_history
            review_history = importlib.reload(review_history)

            first = review_history.add_review_history(
                user_id="user-a",
                review_type="advanced",
                ticker="005930",
                name="삼성전자",
                trade_date="2026-06-19T10:30",
                target_trade_id=7,
                trade_snapshot={"id": 7, "ticker": "005930", "name": "삼성전자"},
                recent_trades_snapshot=[{"id": 7}],
                chart_snapshot={"charts": [{"ticker": "005930"}]},
                ai_review={"summary": "심층 복기 요약"},
                access_snapshot={"source": "purchased_advanced"},
                model="gpt-5.5",
                source="openai",
            )
            review_history.add_review_history(
                user_id="user-b",
                review_type="basic",
                ticker="000660",
                name="SK하이닉스",
                trade_date="2026-06-18T10:30",
                target_trade_id=8,
                trade_snapshot={"id": 8},
                recent_trades_snapshot=[],
                chart_snapshot={},
                ai_review={"summary": "다른 사용자 복기"},
                access_snapshot={},
                model="gpt-5.4-mini",
                source="openai",
            )

            rows = review_history.list_review_history(user_id="user-a")
            detail = review_history.get_review_history(first["id"], user_id="user-a")

            self.assertEqual(1, len(rows))
            self.assertEqual(first["id"], rows[0]["id"])
            self.assertEqual("advanced", rows[0]["review_type"])
            self.assertEqual("삼성전자", detail["name"])
            self.assertEqual("심층 복기 요약", detail["ai_review"]["summary"])
            self.assertEqual({"charts": [{"ticker": "005930"}]}, detail["chart_snapshot"])
            self.assertIsNone(review_history.get_review_history(first["id"], user_id="user-b"))

    def test_clear_review_history_removes_only_requested_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
            from backend.core import review_history
            review_history = importlib.reload(review_history)

            review_history.add_review_history(user_id="user-a", review_type="basic", ticker="005930", name="삼성전자")
            review_history.add_review_history(user_id="user-b", review_type="basic", ticker="000660", name="SK하이닉스")

            deleted = review_history.clear_review_history(user_id="user-a")

            self.assertEqual(1, deleted)
            self.assertEqual([], review_history.list_review_history(user_id="user-a"))
            self.assertEqual(1, len(review_history.list_review_history(user_id="user-b")))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history
```

Expected: fails with `ImportError` or missing `backend.core.review_history`.

- [ ] **Step 3: Implement `backend/core/review_history.py`**

Create:

```python
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
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history
```

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/review_history.py tests/test_review_history.py
git commit -m "Add review history store"
```

---

### Task 2: Backend Routes, Export, and Account Delete

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/core/account_store.py`
- Modify: `tests/test_auth_routes.py`
- Modify: `tests/test_me_data_routes.py`
- Modify: `tests/test_account_store.py`

- [ ] **Step 1: Write failing route/export/delete tests**

Add to `tests/test_auth_routes.py`:

```python
self.assertIn("/api/journal/review-history", paths)
self.assertIn("/api/journal/review-history/{review_id}", paths)
```

Add to `tests/test_me_data_routes.py` inside the existing export test after AI/export setup:

```python
from core import review_history
review_history = importlib.reload(review_history)
review_history.add_review_history(
    user_id=user_id,
    review_type="advanced",
    ticker="005930",
    name="삼성전자",
    ai_review={"summary": "저장된 심층 복기"},
)
exported = main.export_me_data(authorization=token)
self.assertEqual(1, len(exported["review_history"]))
self.assertEqual("저장된 심층 복기", exported["review_history"][0]["ai_review"]["summary"])
```

Add to `tests/test_account_store.py` account deletion test before deletion:

```python
from backend.core import review_history
review_history = importlib.reload(review_history)
review_history.add_review_history(
    user_id=user_id,
    review_type="basic",
    ticker="005930",
    name="삼성전자",
    ai_review={"summary": "삭제될 복기"},
)
```

Then assert:

```python
self.assertEqual(1, result["deleted_review_history"])
self.assertEqual([], review_history.list_review_history(user_id=user_id))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth_routes tests.test_me_data_routes tests.test_account_store
```

Expected: failures because routes/export/delete are not wired.

- [ ] **Step 3: Implement routes and export**

In `backend/main.py`, import:

```python
from core.review_history import list_review_history, get_review_history, delete_review_history
```

Add endpoints:

```python
@app.get("/api/journal/review-history")
def get_journal_review_history(
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        return []
    return list_review_history(user_id=user["id"], limit=limit)


@app.get("/api/journal/review-history/{review_id}")
def get_journal_review_history_detail(
    review_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        raise HTTPException(status_code=403, detail="매매 이력 저장을 켠 계정만 복기 보관함을 사용할 수 있습니다.")
    item = get_review_history(review_id, user_id=user["id"])
    if not item:
        raise HTTPException(status_code=404, detail="복기 이력을 찾을 수 없습니다.")
    return item


@app.delete("/api/journal/review-history/{review_id}")
def remove_journal_review_history(
    review_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    deleted_count = delete_review_history(review_id, user_id=user["id"])
    return {"ok": True, "deleted_count": deleted_count}
```

Update `export_me_data()`:

```python
"review_history": [
    get_review_history(row["id"], user_id=user["id"])
    for row in list_review_history(user_id=user["id"], limit=5000)
],
```

- [ ] **Step 4: Implement account delete hook**

In `backend/core/account_store.py`, import `clear_review_history` in `delete_user_account_data()` and add:

```python
deleted_review_history = clear_review_history(user_id=user_id)
```

Return:

```python
"deleted_review_history": deleted_review_history,
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth_routes tests.test_me_data_routes tests.test_account_store tests.test_review_history
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/main.py backend/core/account_store.py tests/test_auth_routes.py tests/test_me_data_routes.py tests/test_account_store.py
git commit -m "Wire review history account APIs"
```

---

### Task 3: Save AI Review Results

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_review_history.py`

- [ ] **Step 1: Write failing save-on-review test**

Add to `tests/test_review_history.py`:

```python
def test_ai_review_once_saves_history_for_authenticated_storage_user(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
        os.environ["ALPHAMATE_JOURNAL_DB_PATH"] = os.path.join(tmpdir, "trades.sqlite3")
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
        os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        account_store = importlib.reload(importlib.import_module("core.account_store"))
        review_history = importlib.reload(importlib.import_module("core.review_history"))
        main = importlib.reload(importlib.import_module("main"))

        session = account_store.login_dev_provider(provider="kakao", provider_user_id="review-save-user", display_name="복기 저장")
        token = f"Bearer {session['session_token']}"
        account_store.update_journal_storage_setting(authorization=token, enabled=True)
        batch = main.JournalAiReviewIn(
            privacy_consent=True,
            review_type="advanced",
            trades=[main.JournalTradeIn(
                trade_date="2026-06-19T10:30",
                ticker="005930",
                name="삼성전자",
                side="buy",
                price=70000,
                quantity=1,
            )],
        )

        result = main.get_journal_ai_review_once(batch, authorization=token)
        rows = review_history.list_review_history(user_id=session["user"]["id"])

        self.assertIn("review_history_id", result)
        self.assertEqual(1, len(rows))
        self.assertEqual("advanced", rows[0]["review_type"])
```

Also add storage-off behavior:

```python
def test_ai_review_once_does_not_save_history_when_storage_is_off(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
        os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        account_store = importlib.reload(importlib.import_module("core.account_store"))
        review_history = importlib.reload(importlib.import_module("core.review_history"))
        main = importlib.reload(importlib.import_module("main"))

        session = account_store.login_dev_provider(provider="naver", provider_user_id="review-nosave-user", display_name="복기 미저장")
        token = f"Bearer {session['session_token']}"
        batch = main.JournalAiReviewIn(
            privacy_consent=True,
            review_type="basic",
            trades=[main.JournalTradeIn(
                trade_date="2026-06-19T10:30",
                ticker="005930",
                name="삼성전자",
                side="buy",
                price=70000,
                quantity=1,
            )],
        )

        result = main.get_journal_ai_review_once(batch, authorization=token)

        self.assertNotIn("review_history_id", result)
        self.assertEqual([], review_history.list_review_history(user_id=session["user"]["id"]))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history
```

Expected: fails because AI review does not save history.

- [ ] **Step 3: Implement save helper in `backend/main.py`**

Add import:

```python
from core.review_history import add_review_history
```

Add helper:

```python
def _save_ai_review_history_if_enabled(
    *,
    authorization: Optional[str],
    batch: JournalAiReviewIn,
    trades: list[dict],
    result: dict,
):
    user = _optional_session_user(authorization)
    if not user or not user.get("journal_storage_enabled"):
        return None
    target_trade = None
    if batch.target_trade_id is not None:
        for trade in trades:
            if str(trade.get("id")) == str(batch.target_trade_id):
                target_trade = trade
                break
    if target_trade is None and trades:
        target_trade = trades[-1]
    item = add_review_history(
        user_id=user["id"],
        review_type=result.get("review_type") or batch.review_type,
        ticker=str((target_trade or {}).get("ticker") or ""),
        name=str((target_trade or {}).get("name") or ""),
        trade_date=str((target_trade or {}).get("trade_date") or ""),
        target_trade_id=batch.target_trade_id,
        trade_snapshot=target_trade or {},
        recent_trades_snapshot=trades[-10:],
        chart_snapshot={"chart_contexts": result.get("chart_contexts") or [], "chart_reviews": result.get("chart_reviews") or []},
        ai_review=result,
        access_snapshot=result.get("access") or {},
        model=str(result.get("model") or ""),
        source=str(result.get("source") or ""),
    )
    return item["id"]
```

In `get_journal_ai_review_once()` after adding `result["access"]`:

```python
review_history_id = _save_ai_review_history_if_enabled(
    authorization=authorization,
    batch=batch,
    trades=trades,
    result=result,
)
if review_history_id:
    result["review_history_id"] = review_history_id
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history tests.test_me_data_routes tests.test_account_store
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/main.py tests/test_review_history.py
git commit -m "Save AI review history"
```

---

### Task 4: Frontend Review Archive UI

**Files:**
- Modify: `frontend/src/components/TradingJournal.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Add archive state and API helpers**

In `TradingJournal.jsx`, add state:

```jsx
const [journalSubView, setJournalSubView] = useState('review');
const [reviewHistory, setReviewHistory] = useState([]);
const [activeReviewHistory, setActiveReviewHistory] = useState(null);
const [reviewHistoryLoading, setReviewHistoryLoading] = useState(false);
```

Add helper functions:

```jsx
const loadReviewHistory = async () => {
  if (!authSession?.session_token || !authSession?.user?.journal_storage_enabled) {
    setReviewHistory([]);
    setActiveReviewHistory(null);
    return;
  }
  setReviewHistoryLoading(true);
  try {
    const res = await axios.get(`${apiBase}/api/journal/review-history`, {
      headers: { Authorization: `Bearer ${authSession.session_token}` },
    });
    setReviewHistory(res.data || []);
  } catch (err) {
    setMessage(err.response?.data?.detail || '복기 보관함을 불러오지 못했습니다.');
  } finally {
    setReviewHistoryLoading(false);
  }
};

const openReviewHistoryDetail = async (id) => {
  if (!authSession?.session_token) return;
  setReviewHistoryLoading(true);
  try {
    const res = await axios.get(`${apiBase}/api/journal/review-history/${id}`, {
      headers: { Authorization: `Bearer ${authSession.session_token}` },
    });
    setActiveReviewHistory(res.data || null);
  } catch (err) {
    setMessage(err.response?.data?.detail || '복기 상세를 불러오지 못했습니다.');
  } finally {
    setReviewHistoryLoading(false);
  }
};

const deleteReviewHistoryItem = async (id) => {
  if (!authSession?.session_token) return;
  const ok = window.confirm('선택한 복기 이력을 삭제할까요?');
  if (!ok) return;
  await axios.delete(`${apiBase}/api/journal/review-history/${id}`, {
    headers: { Authorization: `Bearer ${authSession.session_token}` },
  });
  setReviewHistory(prev => prev.filter(item => item.id !== id));
  if (activeReviewHistory?.id === id) setActiveReviewHistory(null);
};
```

- [ ] **Step 2: Add archive navigation**

Inside the journal header area, add:

```jsx
<div className="journal-subnav">
  <button className={journalSubView === 'review' ? 'active' : ''} onClick={() => setJournalSubView('review')}>
    매매복기
  </button>
  <button className={journalSubView === 'history' ? 'active' : ''} onClick={enterReviewHistory}>
    복기 보관함
  </button>
</div>
```

- [ ] **Step 3: Add `ReviewHistoryArchive` render block**

Add a local render function or inline JSX:

```jsx
const activeSavedReview = activeReviewHistory?.ai_review || null;
const activeSavedChart = activeReviewHistory?.chart_snapshot || {};
```

Render when `journalSubView === 'history'`:

```jsx
<section className="journal-panel review-history-panel">
  <div className="journal-panel-title">
    <h3>복기 보관함</h3>
    <span className="journal-chart-mode">{reviewHistory.length}건</span>
  </div>
  {!authSession?.user?.journal_storage_enabled ? (
    <p className="journal-privacy-note">복기 보관함은 로그인 후 매매 이력 저장을 켠 경우에 사용할 수 있습니다.</p>
  ) : reviewHistoryLoading ? (
    <p className="journal-privacy-note">복기 이력을 불러오는 중입니다.</p>
  ) : (
    <div className="review-history-layout">
      <div className="review-history-list">
        {reviewHistory.map(item => (
          <button
            key={item.id}
            className={activeReviewHistory?.id === item.id ? 'active' : ''}
            onClick={() => openReviewHistoryDetail(item.id)}
          >
            <strong>{item.name || item.ticker}</strong>
            <span>{item.review_type === 'advanced' ? '심층 복기' : '일반 복기'} · {item.trade_date || item.created_at}</span>
          </button>
        ))}
      </div>
      <div className="review-history-detail">
        {activeReviewHistory ? (
          <>
            <div className="journal-panel-title">
              <h4>{activeReviewHistory.name || activeReviewHistory.ticker}</h4>
              <button className="journal-danger journal-danger-outline" onClick={() => deleteReviewHistoryItem(activeReviewHistory.id)}>삭제</button>
            </div>
            <JournalTradeChart chartData={(activeSavedChart.charts || [])[0]} />
            <p className="journal-ai-summary">{activeSavedReview?.summary || '저장된 복기 내용이 없습니다.'}</p>
          </>
        ) : (
          <p className="journal-privacy-note">왼쪽에서 저장된 복기를 선택하세요.</p>
        )}
      </div>
    </div>
  )}
</section>
```

- [ ] **Step 4: Add CSS**

In `App.css`:

```css
.journal-subnav {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.journal-subnav button {
  border: 1px solid #2a3142;
  background: #151b27;
  color: #9aa6ba;
  border-radius: 6px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}

.journal-subnav button.active {
  background: #2962ff;
  color: #fff;
  border-color: #2962ff;
}

.review-history-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 14px;
}

.review-history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-history-list button {
  text-align: left;
  border: 1px solid #252c3b;
  background: #111722;
  color: #d9e3f5;
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
}

.review-history-list button.active {
  border-color: #2962ff;
  background: #142753;
}

.review-history-list span {
  display: block;
  color: #8c93a3;
  font-size: 12px;
  margin-top: 4px;
}

.review-history-detail {
  min-width: 0;
}

@media (max-width: 760px) {
  .review-history-layout {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Run frontend checks**

Run:

```powershell
cd frontend
npm.cmd run lint
$env:VITE_APP_NAME='AlphaMate'; npm.cmd run build
```

Expected: lint and build pass.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/components/TradingJournal.jsx frontend/src/App.css
git commit -m "Add review history archive UI"
```

---

### Task 5: Review Archive Entry Ad

**Files:**
- Modify: `frontend/src/mobile/admobPolicy.js`
- Modify: `frontend/src/mobile/admob.js`
- Modify: `frontend/src/components/TradingJournal.jsx`
- Test: existing frontend scripts or add `frontend/scripts/test-mobile-admob.js` coverage if present.

- [ ] **Step 1: Add interstitial policy guards**

In `admobPolicy.js`, add:

```js
export const DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID = 'ca-app-pub-3940256099942544/1033173712';

export function isProductionInterstitialMisconfigured({ appEnv, interstitialAdId }) {
  return appEnv === 'production' && interstitialAdId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
}

export function assertInterstitialAdCanRun({ appEnv, interstitialAdId }) {
  if (isProductionInterstitialMisconfigured({ appEnv, interstitialAdId })) {
    throw new Error('Production AdMob interstitial ad unit is not configured.');
  }
}
```

Update `createAdMobRuntimeStatus()` to include:

```js
interstitialAvailable: Boolean(native && !isProductionInterstitialMisconfigured({ appEnv, interstitialAdId })),
```

Pass `interstitialAdId` through callers.

- [ ] **Step 2: Add interstitial runtime**

In `admob.js`, import `DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID` and `assertInterstitialAdCanRun`.

Add:

```js
const INTERSTITIAL_AD_ID = import.meta.env.VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID || DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const USING_TEST_INTERSTITIAL_AD_UNIT = INTERSTITIAL_AD_ID === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;

export async function showReviewHistoryInterstitial() {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  assertInterstitialAdCanRun({ appEnv: APP_ENV, interstitialAdId: INTERSTITIAL_AD_ID });
  await initializeAdMob();
  await AdMob.prepareInterstitial({
    adId: INTERSTITIAL_AD_ID,
    isTesting: APP_ENV !== 'production' || USING_TEST_INTERSTITIAL_AD_UNIT,
    npa: true,
  });
  await AdMob.showInterstitial();
  return { shown: true };
}
```

- [ ] **Step 3: Gate archive entry once per session**

In `TradingJournal.jsx`, import `showReviewHistoryInterstitial`.

Add:

```jsx
const reviewHistoryAdShownRef = useRef(false);

const enterReviewHistory = async () => {
  if (!authSession?.user?.journal_storage_enabled) {
    setJournalSubView('history');
    return;
  }
  if (!reviewHistoryAdShownRef.current && entitlements?.plan !== 'pro') {
    reviewHistoryAdShownRef.current = true;
    try {
      await showReviewHistoryInterstitial();
    } catch {
      // Ad failure must not block access to saved user data.
    }
  }
  setJournalSubView('history');
  await loadReviewHistory();
};
```

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd frontend
npm.cmd run lint
npm.cmd run test:mobile-admob
$env:VITE_APP_NAME='AlphaMate'; npm.cmd run build
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/mobile/admobPolicy.js frontend/src/mobile/admob.js frontend/src/components/TradingJournal.jsx frontend/src/App.css
git commit -m "Gate review archive with interstitial ad"
```

---

### Task 6: Docs and Full Verification

**Files:**
- Modify: `docs/development_history.md`
- Modify: `docs/manual_test_guide.md`
- Modify: `docs/security_deployment_plan.md`

- [ ] **Step 1: Update docs**

Add to `docs/development_history.md`:

```markdown
### 복기 보관함과 저장된 AI 복기

- 일반/심층 AI 복기 결과를 로그인 및 매매 이력 저장이 켜진 사용자 기준으로 저장하는 `복기 보관함`을 추가했다.
- 심층 복기는 차트 이미지 재전송이 아니라 서버가 계산한 차트 기술 요약을 AI에 전달하고, 그 결과와 차트 스냅샷을 함께 저장한다.
- 계정 데이터 삭제와 내 데이터 내보내기에 복기 이력을 포함했다.
- 복기 보관함 진입 시 전면 광고를 세션당 1회 시도하고, 광고 실패는 보관함 접근을 막지 않는다.
```

Add to `docs/manual_test_guide.md`:

```markdown
## 복기 보관함 확인

1. 로그인 후 `매매 이력 저장`을 켭니다.
2. 일반 복기를 실행하고 `복기 보관함`에 저장되는지 확인합니다.
3. 심층 복기를 실행하고 차트 기반 기술 분석 내용이 저장되는지 확인합니다.
4. 복기 보관함에 처음 들어갈 때 전면 광고가 시도되는지 확인합니다.
5. 같은 세션에서 보관함 안의 여러 복기를 눌러도 광고가 반복되지 않는지 확인합니다.
6. 계정 데이터 삭제 후 복기 보관함이 비어 있는지 확인합니다.
```

Update `docs/security_deployment_plan.md` privacy wording:

```markdown
사용자가 매매 이력 저장 기능을 켠 상태에서 AI 복기를 실행하는 경우, 복기 결과와 당시 차트 요약 데이터가 계정별 복기 보관함에 저장될 수 있습니다.
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m compileall backend
cd frontend
npm.cmd run lint
npm.cmd run test:mobile-admob
$env:VITE_APP_NAME='AlphaMate'; npm.cmd run build
```

Expected:

- Python tests: `OK`
- Compileall exits 0
- ESLint exits 0
- Mobile AdMob tests exit 0
- Vite build exits 0

- [ ] **Step 3: Commit and push**

```powershell
git add docs/development_history.md docs/manual_test_guide.md docs/security_deployment_plan.md
git commit -m "Document review history feature"
git push origin main
```

---

## Self-Review

- Spec coverage: covered storage, archive UI, advanced technical chart analysis, entry ad, export/delete, privacy, and tests.
- Placeholder scan: no placeholder steps; all tasks have concrete files, code snippets, and verification commands.
- Type consistency: backend uses `review_history`, `review_history_id`, `chart_snapshot`, `ai_review`, `access_snapshot`; frontend reads the same names.
