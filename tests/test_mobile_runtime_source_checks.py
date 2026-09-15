"""Deferred C frontend (6), D Render (1), OUT admin-source (1) checks."""

import os
import sys
import tempfile
import unittest
import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


class MobileRuntimeSourceChecksTest(unittest.TestCase):
    def test_mobile_layout_stacks_navigation_and_content(self):
        css = (ROOT / "frontend" / "src" / "App.css").read_text(encoding="utf-8")
        root_css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

        mobile = css.split("@media (max-width: 720px)", 1)[1].split("@media (max-width: 520px)", 1)[0]
        self.assertIn("flex-direction: column", mobile)
        self.assertIn("width: 100%", mobile)
        self.assertIn(".app-container.journal-view .sidebar", mobile)
        self.assertIn("overflow-x: hidden", mobile)
        self.assertIn("journal-view", app)
        self.assertIn("themes-view", app)
        self.assertIn("#root {\n  width: 100%;", root_css)
        self.assertNotIn("width: 1126px", root_css)

    def test_production_journal_hides_developer_diagnostics(self):
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn("!authSession && DEV_TOOLS_ENABLED", journal)
        self.assertIn("{DEV_TOOLS_ENABLED && (", journal)
        self.assertIn("배포 준비 상태", journal)

    def test_oauth_handles_cold_launch_url_once(self):
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn("CapacitorApp.getLaunchUrl()", journal)
        self.assertIn("handledOAuthReturnUrlRef", journal)
        self.assertIn("appUrlOpen", journal)

        kakao_svg = (ROOT / "frontend" / "src" / "assets" / "kakao-login-symbol.svg").read_text(encoding="utf-8")
        naver_svg = (ROOT / "frontend" / "src" / "assets" / "naver-login-symbol.svg").read_text(encoding="utf-8")
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', kakao_svg)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', naver_svg)

    def test_theme_requests_timeout_and_retry(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

        self.assertIn("THEME_REQUEST_TIMEOUT_MS", app)
        self.assertIn("THEME_RETRY_DELAY_MS", app)
        self.assertIn("자동으로 다시 확인합니다", app)
        self.assertIn("themeAbortControllerRef", app)
        self.assertIn("axios.isCancel", app)
        self.assertIn("activeView === 'themes'", app)

    def test_empty_journal_does_not_require_an_initial_api_round_trip(self):
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        transient_branch = journal.split("if (transientJournalMode)", 1)[1].split("const reviewRes", 1)[0]
        self.assertIn("if (!nextTrades.length)", transient_branch)
        self.assertIn("setReview(null)", transient_branch)

    def test_render_uses_persistent_cache_and_bounded_workers(self):
        blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("ALPHAMATE_CACHE_DIR", blueprint)
        self.assertIn("/var/data/alphamate/cache", blueprint)
        self.assertIn("ALPHAMATE_THEME_FETCH_WORKERS", blueprint)
        self.assertIn("ALPHAMATE_WARM_CACHE_ON_STARTUP", blueprint)

    def test_admin_can_trigger_and_inspect_initial_theme_cache(self):
        source = (BACKEND / "main.py").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/admin/theme-cache/status")', source)
        self.assertIn('@app.post("/api/admin/theme-cache/refresh")', source)
        self.assertIn("_require_admin_token(authorization)", source)
        self.assertIn("_theme_cache_status_payload", source)

    def test_oauth_success_and_app_failure_stages_are_logged_without_credentials(self):
        backend_source = (BACKEND / "main.py").read_text(encoding="utf-8")
        frontend_source = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn('event_type="oauth_callback_completed"', backend_source)
        self.assertIn('event_type="oauth_app_ticket_consumed"', backend_source)
        self.assertIn("oauth_app_ticket_login_failed", frontend_source)
        self.assertNotIn('details={"code"', backend_source)
        self.assertNotIn('details={"ticket"', backend_source)


if __name__ == "__main__":
    unittest.main()
