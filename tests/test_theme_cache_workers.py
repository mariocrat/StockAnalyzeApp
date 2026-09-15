import concurrent.futures
import gc
import importlib
import os
import tempfile
import unittest
from unittest import mock


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class ThemeCacheWorkerTests(unittest.TestCase):
    def test_large_theme_fetch_keeps_outstanding_futures_and_results_bounded(self):
        from backend.core import data_fetcher

        data_fetcher = importlib.reload(data_fetcher)
        ticker_count = 2393
        tickers = [f"{index:06d}" for index in range(1, ticker_count + 1)]
        themes = {"대규모 테스트 테마": tickers}
        names = {ticker: f"종목 {ticker}" for ticker in tickers}
        tracker = {
            "outstanding": 0,
            "peak_outstanding": 0,
            "live_results": 0,
            "peak_live_results": 0,
            "submitted": 0,
            "executor_exited": False,
        }

        class TrackedRows(list):
            def __init__(self, rows):
                super().__init__(rows)
                tracker["live_results"] += 1
                tracker["peak_live_results"] = max(
                    tracker["peak_live_results"],
                    tracker["live_results"],
                )

            def __del__(self):
                tracker["live_results"] -= 1

        class TrackedFuture(concurrent.futures.Future):
            def __init__(self):
                super().__init__()
                self._consumed = False

            def result(self, timeout=None):
                if not self._consumed:
                    self._consumed = True
                    tracker["outstanding"] -= 1
                return super().result(timeout=timeout)

        class TrackingExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                tracker["executor_exited"] = True

            def submit(self, fn, *args, **kwargs):
                tracker["submitted"] += 1
                tracker["outstanding"] += 1
                tracker["peak_outstanding"] = max(
                    tracker["peak_outstanding"],
                    tracker["outstanding"],
                )
                future = TrackedFuture()
                try:
                    future.set_result(fn(*args, **kwargs))
                except BaseException as exc:
                    future.set_exception(exc)
                return future

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, _url, **_kwargs):
                return _Response(
                    '["20250109", 100, 100, 100, 100, 1]\n'
                    '["20250110", 110, 110, 110, 110, 1]'
                )

        def track_rows(rows):
            return TrackedRows(rows)

        worker_limit = 8
        with mock.patch.object(data_fetcher, "get_krx_themes", return_value=(themes, names, {})), \
             mock.patch.object(concurrent.futures, "ThreadPoolExecutor", TrackingExecutor), \
             mock.patch.object(data_fetcher, "_adjust_price_rows_for_corporate_actions", side_effect=track_rows), \
             mock.patch("requests.Session", side_effect=FakeSession), \
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": str(worker_limit)}):
            result = data_fetcher._calculate_theme_return_ranges({
                "1D": ("20250101", "20250110"),
            })

        gc.collect()
        self.assertEqual(ticker_count, tracker["submitted"])
        self.assertLessEqual(tracker["peak_outstanding"], worker_limit)
        self.assertLessEqual(tracker["peak_live_results"], worker_limit)
        self.assertEqual(0, tracker["outstanding"])
        self.assertEqual(0, tracker["live_results"])
        self.assertTrue(tracker["executor_exited"])
        self.assertEqual(ticker_count, result["1D"].iloc[0]["Num Stocks"])

    def test_worker_exception_still_exits_bounded_executor(self):
        from backend.core import data_fetcher

        data_fetcher = importlib.reload(data_fetcher)
        themes = {"테스트 테마": ["000001", "000002", "000003"]}
        names = {ticker: ticker for ticker in themes["테스트 테마"]}
        tracker = {"executor_exited": False}

        class FailingExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                tracker["executor_exited"] = True

            def submit(self, _fn, ticker):
                future = concurrent.futures.Future()
                if ticker == "000002":
                    future.set_exception(RuntimeError("worker failed"))
                else:
                    future.set_result((ticker, []))
                return future

        with mock.patch.object(data_fetcher, "get_krx_themes", return_value=(themes, names, {})), \
             mock.patch.object(concurrent.futures, "ThreadPoolExecutor", FailingExecutor), \
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}):
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                data_fetcher._calculate_theme_return_ranges({
                    "1D": ("20250101", "20250110"),
                })

        self.assertTrue(tracker["executor_exited"])

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

    def test_period_returns_use_available_closes_and_exclude_tickers_without_two_rows(self):
        from backend.core import data_fetcher

        data_fetcher = importlib.reload(data_fetcher)
        themes = {"테스트 테마": ["000001", "000002", "000003"]}
        names = {"000001": "가나다", "000002": "라마바", "000003": "누락"}
        rows = {
            "000001": (
                '["20250102", 0, 0, 0, 100, 0]\n'
                '["20250103", 0, 0, 0, 110, 0]\n'
                '["20250108", 0, 0, 0, 120, 0]\n'
                '["20250110", 0, 0, 0, 130, 0]'
            ),
            "000002": (
                '["20250102", 0, 0, 0, 200, 0]\n'
                '["20250108", 0, 0, 0, 180, 0]\n'
                '["20250110", 0, 0, 0, 198, 0]'
            ),
            "000003": (
                '["20241231", 0, 0, 0, 50, 0]\n'
                '["20250110", 0, 0, 0, 55, 0]'
            ),
        }
        requested = []

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, **_kwargs):
                ticker = url.split("symbol=", 1)[1].split("&", 1)[0]
                requested.append(ticker)
                return _Response(rows[ticker])

        with mock.patch.object(data_fetcher, "get_krx_themes", return_value=(themes, names, {})), \
             mock.patch("requests.Session", side_effect=FakeSession), \
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}):
            result = data_fetcher._calculate_theme_return_ranges({
                "1D": ("20250101", "20250110"),
                "1W": ("20250103", "20250110"),
                "1M": ("20250101", "20250110"),
            })

        self.assertCountEqual(["000001", "000002", "000003"], requested)
        self.assertAlmostEqual(9.17, result["1D"].iloc[0]["Avg Return (%)"])
        self.assertEqual("20250108", result["1D"].iloc[0]["Start Date"])
        self.assertAlmostEqual(14.09, result["1W"].iloc[0]["Avg Return (%)"])
        self.assertEqual("20250103", result["1W"].iloc[0]["Start Date"])
        self.assertAlmostEqual(14.5, result["1M"].iloc[0]["Avg Return (%)"])
        self.assertEqual("20250102", result["1M"].iloc[0]["Start Date"])
        for period in ("1D", "1W", "1M"):
            self.assertEqual(2, result[period].iloc[0]["Num Stocks"])
            self.assertNotIn("000003", [row["ticker"] for row in result[period].iloc[0]["Tickers"]])


if __name__ == "__main__":
    unittest.main()
