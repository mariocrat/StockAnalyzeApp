# AI Consent History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store and show the latest AI review privacy consent version/time for logged-in users.

**Architecture:** Reuse the existing `users.privacy_consent_version` and `users.privacy_consented_at` columns in `backend/core/account_store.py`. The AI review endpoint records consent after access validation succeeds and before calling OpenAI/chart analysis. The frontend reads the existing `authSession.user` and `dataSummary` objects to display consent status in the account panel.

**Tech Stack:** FastAPI, SQLite, Python unittest, React, Axios, Vite.

---

## File Structure

- Modify `backend/core/account_store.py`
  - Add `PRIVACY_CONSENT_VERSION`.
  - Add `record_privacy_consent(authorization, version="")`.
  - Return updated user row after recording consent.
- Modify `backend/main.py`
  - Import `record_privacy_consent`.
  - In `POST /api/journal/ai-review-once`, record consent for authenticated users after `verify_ai_review_access()` passes.
  - Add `privacy_consent_version` and `privacy_consented_at` to `/api/me/data-summary`.
- Modify `tests/test_account_store.py`
  - Cover direct consent recording.
- Modify `tests/test_review_history.py`
  - Cover AI review endpoint updating consent for logged-in users.
  - Cover missing consent remains rejected.
- Modify `tests/test_me_data_routes.py`
  - Cover data summary/export exposing consent state.
- Modify `frontend/src/components/TradingJournal.jsx`
  - Show consent status in the account data grid.
  - Refresh account/session summary after successful AI review.
- Modify docs:
  - `docs/development_history.md`
  - `docs/security_deployment_plan.md`

---

### Task 1: Account Consent Store

**Files:**
- Modify: `backend/core/account_store.py`
- Test: `tests/test_account_store.py`

- [ ] **Step 1: Write failing account-store test**

Add to `tests/test_account_store.py`:

```python
def test_privacy_consent_can_be_recorded_for_session_user(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")

        from backend.core import account_store
        account_store = importlib.reload(account_store)

        session = account_store.login_dev_provider(
            provider="kakao",
            provider_user_id="consent-user",
            display_name="동의 사용자",
        )
        token = f"Bearer {session['session_token']}"

        updated = account_store.record_privacy_consent(
            authorization=token,
            version="ai-review-privacy-v2",
        )
        current = account_store.authenticate_session(token)

        self.assertEqual("ai-review-privacy-v2", updated["privacy_consent_version"])
        self.assertEqual("ai-review-privacy-v2", current["privacy_consent_version"])
        self.assertTrue(updated["privacy_consented_at"])
        self.assertTrue(current["privacy_consented_at"])
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_account_store
```

Expected: fails with `AttributeError: module 'backend.core.account_store' has no attribute 'record_privacy_consent'`.

- [ ] **Step 3: Implement account-store consent recording**

In `backend/core/account_store.py`, add near constants:

```python
PRIVACY_CONSENT_VERSION = env_value("ALPHAMATE_PRIVACY_CONSENT_VERSION") or "ai-review-privacy-v1"
```

Add function after `update_journal_storage_setting()`:

```python
def record_privacy_consent(*, authorization: str | None, version: str = "") -> dict:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Valid user session is required.")
    consent_version = str(version or PRIVACY_CONSENT_VERSION).strip() or PRIVACY_CONSENT_VERSION
    consented_at = _now()
    with _ACCOUNT_LOCK:
        conn = _connect()
        try:
            token_hash = _hash_token(token)
            session = conn.execute(
                """
                SELECT user_id
                FROM user_sessions
                WHERE session_token_hash = ? AND revoked_at = ''
                """,
                (token_hash,),
            ).fetchone()
            if session is None:
                raise HTTPException(status_code=401, detail="Valid user session is required.")
            conn.execute(
                """
                UPDATE users
                SET privacy_consent_version = ?,
                    privacy_consented_at = ?
                WHERE id = ?
                """,
                (consent_version, consented_at, session["user_id"]),
            )
            conn.commit()
            return _get_user(conn, session["user_id"])
        finally:
            conn.close()
```

- [ ] **Step 4: Run test and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_account_store
```

Expected: all account store tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/account_store.py tests/test_account_store.py
git commit -m "Record account privacy consent"
```

---

### Task 2: Wire Consent Into AI Review APIs

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_review_history.py`
- Test: `tests/test_me_data_routes.py`

- [ ] **Step 1: Write failing AI endpoint consent tests**

Add to `tests/test_review_history.py`:

```python
def test_ai_review_once_records_privacy_consent_for_authenticated_user(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
        os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(tmpdir, "review_history.sqlite3")
        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"
        os.environ["ALPHAMATE_PRIVACY_CONSENT_VERSION"] = "ai-review-privacy-test"

        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        account_store = importlib.reload(importlib.import_module("core.account_store"))
        main = importlib.reload(importlib.import_module("main"))
        main.build_basic_ai_review = lambda trades, target_trade_id=None: {
            "status": "ready",
            "source": "openai",
            "review_type": "basic",
            "model": "gpt-5.4-mini",
            "summary": "consent saved",
        }

        session = account_store.login_dev_provider(
            provider="kakao",
            provider_user_id="ai-consent-user",
            display_name="AI 동의",
        )
        token = f"Bearer {session['session_token']}"
        batch = main.JournalAiReviewIn(
            privacy_consent=True,
            review_type="basic",
            trades=[main.JournalTradeIn(
                trade_date="2026-06-21T10:30",
                ticker="005930",
                name="삼성전자",
                side="buy",
                price=70000,
                quantity=1,
            )],
        )

        main.get_journal_ai_review_once(batch, authorization=token)
        current = account_store.authenticate_session(token)

        self.assertEqual("ai-review-privacy-test", current["privacy_consent_version"])
        self.assertTrue(current["privacy_consented_at"])
```

Add missing-consent behavior if not already covered:

```python
def test_ai_review_once_rejects_missing_privacy_consent(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(tmpdir, "accounts.sqlite3")
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(tmpdir, "access.sqlite3")
        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"

        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        account_store = importlib.reload(importlib.import_module("core.account_store"))
        main = importlib.reload(importlib.import_module("main"))
        session = account_store.login_dev_provider(
            provider="naver",
            provider_user_id="ai-no-consent-user",
            display_name="AI 미동의",
        )
        token = f"Bearer {session['session_token']}"
        batch = main.JournalAiReviewIn(
            privacy_consent=False,
            review_type="basic",
            trades=[main.JournalTradeIn(
                trade_date="2026-06-21T10:30",
                ticker="005930",
                name="삼성전자",
                side="buy",
                price=70000,
                quantity=1,
            )],
        )

        with self.assertRaises(Exception) as ctx:
            main.get_journal_ai_review_once(batch, authorization=token)

        self.assertIn("Privacy consent is required", str(ctx.exception))
```

- [ ] **Step 2: Write failing data-summary test**

In `tests/test_me_data_routes.py`, update `test_data_summary_counts_only_the_session_users_saved_trades` expected dict with:

```python
"privacy_consent_version": "",
"privacy_consented_at": "",
```

In export test, after recording consent:

```python
account_store.record_privacy_consent(authorization=token, version="ai-review-privacy-export")
```

Assert:

```python
self.assertEqual("ai-review-privacy-export", exported["user"]["privacy_consent_version"])
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history tests.test_me_data_routes
```

Expected: consent recording assertions fail before wiring.

- [ ] **Step 4: Implement main route wiring**

In `backend/main.py`, update import:

```python
from core.account_store import login_dev_provider, authenticate_session, revoke_session, update_journal_storage_setting, record_privacy_consent, delete_user_account_data
```

In `get_me_data_summary()`, add:

```python
"privacy_consent_version": user.get("privacy_consent_version", ""),
"privacy_consented_at": user.get("privacy_consented_at", ""),
```

In `get_journal_ai_review_once()`, after `verify_ai_review_access(...)`:

```python
    if batch.privacy_consent and authorization:
        record_privacy_consent(authorization=authorization)
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_history tests.test_me_data_routes tests.test_account_store
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/main.py tests/test_review_history.py tests/test_me_data_routes.py
git commit -m "Store AI review consent on execution"
```

---

### Task 3: Frontend Consent Status and Docs

**Files:**
- Modify: `frontend/src/components/TradingJournal.jsx`
- Modify: `docs/development_history.md`
- Modify: `docs/security_deployment_plan.md`

- [ ] **Step 1: Add frontend display**

In `TradingJournal.jsx`, near `connectedProviderText`, add:

```jsx
const consentRecordedAt = dataSummary?.privacy_consented_at || authSession?.user?.privacy_consented_at || '';
const consentVersion = dataSummary?.privacy_consent_version || authSession?.user?.privacy_consent_version || '';
const consentStatusText = consentRecordedAt ? '동의 완료' : '미기록';
const consentDetailText = consentRecordedAt ? `${consentVersion || '현재 버전'} · ${consentRecordedAt.slice(0, 10)}` : 'AI 복기 실행 전 동의 필요';
```

In the `.journal-data-grid`, add:

```jsx
<div>
  <span>AI 동의 기록</span>
  <strong>{consentStatusText}</strong>
  <em>{consentDetailText}</em>
</div>
```

After successful AI review in `loadAiReview()`, add:

```jsx
if (authSession?.session_token) {
  await loadDataSummary(authSession.session_token);
}
```

- [ ] **Step 2: Update docs**

Add to `docs/development_history.md`:

```markdown
## 2026-06-21 AI 복기 개인정보 동의 이력

- AI 복기 실행 시 로그인 계정에 최신 개인정보/매매 기록 전송 동의 버전과 시각을 저장하도록 했다.
- 계정 관리 영역에 `AI 동의 기록`을 표시해 사용자가 동의 기록 존재 여부를 확인할 수 있게 했다.
- 내 데이터 내보내기에는 기존 `user` 객체를 통해 동의 버전과 시각이 포함된다.
```

Add to `docs/security_deployment_plan.md`:

```markdown
## 2026-06-21 AI 복기 동의 기록

- AI 복기 동의는 `ALPHAMATE_PRIVACY_CONSENT_VERSION` 값과 UTC 시각으로 계정에 저장된다.
- 동의 이력은 최신 상태만 저장하며, 계정 데이터 내보내기와 계정 삭제 범위에 포함된다.
- 개인정보처리방침 문구를 바꾸는 경우 `ALPHAMATE_PRIVACY_CONSENT_VERSION`도 함께 올려야 한다.
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m compileall backend
cd frontend
npm.cmd run lint
$env:VITE_APP_NAME='AlphaMate'; npm.cmd run build
```

Expected:

- Python tests: `OK`
- Compileall exits 0
- ESLint exits 0
- Vite build exits 0

- [ ] **Step 4: Commit and push**

```powershell
git add frontend/src/components/TradingJournal.jsx docs/development_history.md docs/security_deployment_plan.md
git commit -m "Show AI review consent history"
git push origin main
```

---

## Self-Review

- Spec coverage: account storage, AI route wiring, data export/summary, frontend status, and docs are covered.
- Placeholder scan: no TBD/TODO/fill-in steps remain.
- Type consistency: uses `privacy_consent_version`, `privacy_consented_at`, `record_privacy_consent`, and `ALPHAMATE_PRIVACY_CONSENT_VERSION` consistently.
