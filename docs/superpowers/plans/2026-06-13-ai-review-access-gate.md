# AI Review Access Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI trade review follow the future production flow: consent, authenticated request, rewarded-ad proof, server-side AI call, and no persisted trade history by default.

**Architecture:** Add a small backend access-control module that validates a development auth token, a development ad reward token, privacy consent, and an in-memory hourly limit. Wire the one-time AI review endpoint through that gate, then update the journal UI to request consent and send the dev tokens in the same shape a real mobile client will later use.

**Tech Stack:** FastAPI, Pydantic, React/Vite, Axios.

---

### Task 1: Backend AI Access Gate

**Files:**
- Create: `backend/core/access_control.py`
- Modify: `backend/main.py`

- [ ] Create an access-control module with environment-aware development token verification.
- [ ] Add request fields for `ad_reward_token` and `privacy_consent`.
- [ ] Apply the gate to `POST /api/journal/ai-review-once`.
- [ ] Return clear HTTP errors for missing consent, auth, ad reward, and rate limit.

### Task 2: Frontend AI Review Flow

**Files:**
- Modify: `frontend/src/components/TradingJournal.jsx`
- Modify: `frontend/src/App.css`

- [ ] Stop automatic AI calls on initial load and trade add/remove.
- [ ] Add a consent checkbox near the AI review action.
- [ ] Send `Authorization`, `ad_reward_token`, and `privacy_consent` when the user asks for AI analysis.
- [ ] Keep chart/rule-based review working without AI access.

### Task 3: Documentation And Verification

**Files:**
- Modify: `docs/security_deployment_plan.md`

- [ ] Document the development tokens and production replacement points.
- [ ] Verify backend compilation.
- [ ] Verify frontend lint and production build.
- [ ] Directly test the AI endpoint rejects missing access and accepts development access.
