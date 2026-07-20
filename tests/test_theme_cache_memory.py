import importlib
import os
import tempfile
import unittest
from unittest import mock


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class ThemeCacheMemoryTests(unittest.TestCase):
    def test_multiple_periods_are_calculated_from_one_bounded_fetch_pass(self):
        from backend.core import data_fetcher

        data_fetcher = importlib.reload(data_fetcher)
        themes = {"테스트 테마": ["000001", "000002"]}
        names = {"000001": "가나다", "000002": "라마바"}
        rows = {
            "000001": '["20250101", 0, 0, 0, 100, 0]\n["20250109", 0, 0, 0, 120, 0]\n["20250110", 0, 0, 0, 150, 0]',
            "000002": '["20250101", 0, 0, 0, 200, 0]\n["20250109", 0, 0, 0, 180, 0]\n["20250110", 0, 0, 0, 198, 0]',
        }
        requested = []
        sessions = []

        class FakeSession:
            def __init__(self):
                self.headers = {}
                sessions.append(self)

            def get(self, url, **_kwargs):
                ticker = url.split("symbol=", 1)[1].split("&", 1)[0]
                requested.append(ticker)
                return _Response(rows[ticker])

        with mock.patch.object(data_fetcher, "get_krx_themes", return_value=(themes, names, {})), \
             mock.patch("requests.Session", side_effect=FakeSession), \
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}):
            result = data_fetcher._calculate_theme_return_ranges({
                "1Y": ("20250101", "20250111"),
                "1D": ("20250109", "20250111"),
            })

        self.assertCountEqual(["000001", "000002"], requested)
        self.assertLessEqual(len(sessions), 2)
        self.assertEqual(1, len(result["1Y"]))
        self.assertEqual(1, len(result["1D"]))
        self.assertAlmostEqual(24.5, result["1Y"].iloc[0]["Avg Return (%)"])
        self.assertAlmostEqual(17.5, result["1D"].iloc[0]["Avg Return (%)"])
        self.assertEqual("20250110", result["1Y"].iloc[0]["End Date"])
        self.assertEqual("20250110", result["1D"].iloc[0]["End Date"])

    def test_warm_cache_writes_separate_period_results_without_close_history_file(self):
        from backend.core import data_fetcher

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ALPHAMATE_CACHE_DIR": tmp}):
                data_fetcher = importlib.reload(data_fetcher)
                calculated = {
                    "1D": data_fetcher._build_theme_return_stats(
                        themes={"테마": ["000001"]},
                        names={"000001": "종목"},
                        ticker_returns={"000001": 3.5},
                        start_date="20250109",
                        end_date="20250110",
                    ),
                    "1Y": data_fetcher._build_theme_return_stats(
                        themes={"테마": ["000001"]},
                        names={"000001": "종목"},
                        ticker_returns={"000001": 30.0},
                        start_date="20240110",
                        end_date="20250110",
                    ),
                }
                ranges = {
                    "1D": ("20250109", "20250110"),
                    "1Y": ("20240110", "20250110"),
                }
                with mock.patch.object(data_fetcher, "_calculate_theme_return_ranges", return_value=calculated):
                    counts = data_fetcher.warm_theme_return_caches(ranges)

                self.assertEqual({"1D": 1, "1Y": 1}, counts)
                files = os.listdir(tmp)
                self.assertEqual(2, len([name for name in files if name.startswith("theme_returns_v4_")]))
                self.assertFalse(any(name.startswith("naver_closes_") for name in files))

    def test_reverse_split_is_normalized_before_return_calculation(self):
        from backend.core import data_fetcher

        rows = [
            {"date": "20260716", "open": 181, "high": 181, "low": 181, "close": 181, "volume": 0},
            {"date": "20260720", "open": 1600, "high": 1800, "low": 1550, "close": 1726, "volume": 1000},
        ]

        adjusted = data_fetcher._adjust_price_rows_for_corporate_actions(rows)

        self.assertEqual(1810, adjusted[0]["close"])
        self.assertEqual(1726, adjusted[1]["close"])
        self.assertAlmostEqual(-4.64, ((adjusted[1]["close"] / adjusted[0]["close"]) - 1) * 100, places=2)

    def test_gradual_market_move_is_not_treated_as_corporate_action(self):
        from backend.core import data_fetcher

        rows = [
            {"date": "20260716", "open": 100, "high": 130, "low": 100, "close": 130, "volume": 100},
            {"date": "20260717", "open": 130, "high": 169, "low": 130, "close": 169, "volume": 100},
            {"date": "20260720", "open": 169, "high": 219, "low": 169, "close": 219, "volume": 100},
        ]

        adjusted = data_fetcher._adjust_price_rows_for_corporate_actions(rows)

        self.assertEqual([130, 169, 219], [row["close"] for row in adjusted])


if __name__ == "__main__":
    unittest.main()
