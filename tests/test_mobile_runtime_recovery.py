from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state, api_module_state
import importlib

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
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        data_fetcher = importlib.import_module("core.data_fetcher")
        self.enterContext(patch.dict(data_fetcher.__dict__))
        importlib.reload(data_fetcher)
        modules = self.enterContext(api_module_state())
        # Clear only this case's fresh cache before restoring the baseline module.
        self.addCleanup(modules.main.get_themes.cache_clear)

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

    def test_daily_theme_refresh_targets_after_market_close_kst(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime(2026, 7, 13, 15, 39, 30, tzinfo=kst)
        self.assertEqual(30.0, main._seconds_until_next_theme_refresh(now))

        after_refresh = datetime.datetime(2026, 7, 13, 15, 41, 0, tzinfo=kst)
        self.assertEqual(86340.0, main._seconds_until_next_theme_refresh(after_refresh))

    def test_theme_basis_switches_to_today_after_market_data_is_ready(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        kst = datetime.timezone(datetime.timedelta(hours=9))
        before_ready = datetime.datetime(2026, 7, 13, 15, 39, tzinfo=kst)
        after_ready = datetime.datetime(2026, 7, 13, 15, 40, tzinfo=kst)
        sunday = datetime.datetime(2026, 7, 12, 18, 0, tzinfo=kst)

        self.assertEqual(datetime.date(2026, 7, 10), main._last_completed_market_date(before_ready))
        self.assertEqual(datetime.date(2026, 7, 13), main._last_completed_market_date(after_ready))
        self.assertEqual(datetime.date(2026, 7, 10), main._last_completed_market_date(sunday))

    def test_theme_cache_key_tracks_resolved_period_dates(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        main.get_themes.cache_clear()
        period_ranges = iter([
            ("20260708", "20260714"),
            ("20260709", "20260715"),
        ])

        def cached_returns(start_date, end_date, period="custom"):
            return pd.DataFrame([{
                "Theme": "반도체",
                "Avg Return (%)": 1.0,
                "End Date": end_date,
            }])

        with (
            patch.object(main, "_period_date_range", side_effect=lambda _period: next(period_ranges)),
            patch.object(main, "get_cached_theme_returns", side_effect=cached_returns),
        ):
            first = main.get_themes(period="1W")
            second = main.get_themes(period="1W")

        self.assertEqual("20260714", first[0]["End Date"])
        self.assertEqual("20260715", second[0]["End Date"])
        main.get_themes.cache_clear()

    def test_stale_theme_cache_is_returned_while_latest_close_is_calculated(self):
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import main

        main.get_themes.cache_clear()
        fallback = pd.DataFrame([{
            "Theme": "반도체",
            "Avg Return (%)": 12.5,
            "End Date": "20260714",
        }])
        scheduled = []
        with (
            patch.object(main, "_period_date_range", return_value=("20260708", "20260715")),
            patch.object(main, "get_cached_theme_returns", return_value=pd.DataFrame()),
            patch.object(main, "get_latest_cached_theme_returns", return_value=fallback),
            patch.object(main, "_schedule_theme_cache_refresh", side_effect=lambda start, end: scheduled.append((start, end))),
        ):
            records = main.get_themes(period="1W")

        self.assertEqual("20260714", records[0]["End Date"])
        self.assertEqual("updating", records[0]["Data Status"])
        self.assertEqual("20260715", records[0]["Expected End Date"])
        self.assertEqual([("20260708", "20260715")], scheduled)
        main.get_themes.cache_clear()


if __name__ == "__main__":
    unittest.main()
