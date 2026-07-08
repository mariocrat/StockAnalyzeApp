# Release OAuth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the Android release identity and add a safer OAuth app-return path before production key issuance.

**Architecture:** Keep OpenAI and OAuth token exchange on the backend. The mobile app starts provider login in the browser, the provider returns to the backend callback, the backend creates a short-lived one-time app login ticket, and Android returns to the app through the package-name custom scheme.

**Tech Stack:** FastAPI, React/Vite, Capacitor Android, Python unittest, Node test runner.

---

### Task 1: Release Identity Validation

**Files:**
- Modify: `frontend/scripts/validate-release-env.js`
- Modify: `frontend/scripts/validate-release-env.test.js`
- Modify: `tests/test_release_alignment.py`
- Modify: `backend/scripts/validate_release_alignment.py`

- [ ] Add tests that reject release package names other than `com.mariocrat.stockanalyze`.
- [ ] Add validation in frontend and backend release checks.
- [ ] Run release validation tests.

### Task 2: OAuth App Return Ticket Flow

**Files:**
- Modify: `backend/core/oauth_login.py`
- Modify: `backend/main.py`
- Modify: `tests/test_oauth_login.py`
- Modify: `tests/test_auth_routes.py`
- Modify: `frontend/src/components/TradingJournal.jsx`
- Modify: `frontend/android/app/src/main/AndroidManifest.xml`
- Modify: `frontend/scripts/android-branding.test.js`

- [ ] Add tests for one-time ticket issue/consume and Android manifest deep link.
- [ ] Add backend callback and ticket login routes.
- [ ] Add frontend ticket handling.
- [ ] Add Android intent-filter for the package-name scheme.
- [ ] Run targeted backend and frontend tests.

