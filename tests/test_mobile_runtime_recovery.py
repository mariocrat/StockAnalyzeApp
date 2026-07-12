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


class MobileRuntimeRecoveryTest(unittest.TestCase):
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

    def test_cache_directory_and_worker_limit_are_configurable(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        from core import data_fetcher

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ALPHAMATE_CACHE_DIR": temp_dir, "ALPHAMATE_THEME_FETCH_WORKERS": "99"}):
                self.assertEqual(Path(temp_dir), data_fetcher._cache_dir())
                self.assertEqual(16, data_fetcher._theme_fetch_workers(100))

    def test_production_cache_miss_returns_quick_preparing_response(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        main.get_themes.cache_clear()
        scheduled = []
        with (
            patch.dict(os.environ, {"ALPHAMATE_ENV": "production"}),
            patch.object(main, "get_cached_theme_returns", return_value=pd.DataFrame()),
            patch.object(main, "get_latest_cached_theme_returns", return_value=pd.DataFrame()),
            patch.object(main, "_schedule_theme_cache_refresh", side_effect=lambda start, end: scheduled.append((start, end))),
            patch.object(main, "get_theme_returns_historical") as calculate,
        ):
            with self.assertRaises(HTTPException) as raised:
                main.get_themes(period="1W")

        self.assertEqual(503, raised.exception.status_code)
        self.assertIn("업데이트 중", raised.exception.detail)
        self.assertEqual(1, len(scheduled))
        calculate.assert_not_called()

    def test_render_uses_persistent_cache_and_bounded_workers(self):
        blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("ALPHAMATE_CACHE_DIR", blueprint)
        self.assertIn("/var/data/alphamate/cache", blueprint)
        self.assertIn("ALPHAMATE_THEME_FETCH_WORKERS", blueprint)
        self.assertIn("ALPHAMATE_WARM_CACHE_ON_STARTUP", blueprint)

    def test_daily_theme_refresh_targets_just_after_midnight_kst(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime(2026, 7, 13, 23, 59, 30, tzinfo=kst)
        self.assertEqual(90.0, main._seconds_until_next_theme_refresh(now))

        after_midnight = datetime.datetime(2026, 7, 13, 0, 2, 0, tzinfo=kst)
        self.assertEqual(86340.0, main._seconds_until_next_theme_refresh(after_midnight))

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
