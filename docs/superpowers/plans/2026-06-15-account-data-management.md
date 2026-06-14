# Account Data Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simple account/data management area so a logged-in user can see what AlphaMate stores for the current account.

**Architecture:** Keep the stored trade data in the existing journal SQLite store and expose a small authenticated summary endpoint from FastAPI. The frontend reads that endpoint and shows account state, connected login providers, saved trade count, and AI review storage status in the trading journal screen.

**Tech Stack:** FastAPI, SQLite, Python unittest, React, Axios, Vite.

---

### Task 1: Authenticated Data Summary API

**Files:**
- Modify: `backend/core/journal.py`
- Modify: `backend/main.py`
- Test: `tests/test_me_data_routes.py`
- Test: `tests/test_auth_routes.py`

- [x] **Step 1: Write the failing test**

Add a unittest that logs in two development users, creates one saved trade for each, and calls `main.get_me_data_summary()` with the Kakao session token.

- [x] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_me_data_routes`

Expected: FAIL because `main.get_me_data_summary` does not exist.

- [x] **Step 3: Write minimal implementation**

Add `count_trades(user_id=...)` to `backend/core/journal.py` and `GET /api/me/data-summary` to `backend/main.py`.

- [x] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_me_data_routes tests.test_auth_routes`

Expected: PASS.

### Task 2: Frontend Account/Data Management Panel

**Files:**
- Modify: `frontend/src/components/TradingJournal.jsx`
- Modify: `frontend/src/App.css`

- [x] **Step 1: Add account summary state**

Add `dataSummary` state and `loadDataSummary()` using `GET /api/me/data-summary`.

- [x] **Step 2: Refresh data summary after account changes**

Call `loadDataSummary()` after development login, storage toggle, saved trade create/delete, and saved trade clear.

- [x] **Step 3: Replace the login panel title**

Change the panel label from `로그인` to `계정/데이터 관리`.

- [x] **Step 4: Show safe summary fields**

Display account state, connected login provider, saved trade count, and whether AI review history is stored on the server.

### Task 3: Documentation And Verification

**Files:**
- Modify: `docs/manual_test_guide.md`
- Modify: `docs/development_history.md`

- [x] **Step 1: Update manual test guide**

Add checks for the account/data management panel and saved trade count.

- [x] **Step 2: Update development history**

Record the new data summary API and UI area.

- [x] **Step 3: Run full verification**

Run backend unittest, backend compile, frontend lint, and frontend build before committing.
