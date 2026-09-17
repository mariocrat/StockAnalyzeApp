from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state

import concurrent.futures
from contextlib import contextmanager
import gc
import importlib
import logging
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import weakref
from unittest import mock

import requests

with _import_state():
    from backend.core import data_fetcher as _data_fetcher
    from core import data_fetcher as _core_data_fetcher


def _state():
    return (
        dict(os.environ), list(sys.path), Path.cwd(), tempfile.tempdir,
        [{key: id(value) for key, value in module.__dict__.items()}
         for module in (_data_fetcher, _core_data_fetcher)],
        logging.getLogger("yfinance").level,
        requests.Session, concurrent.futures.ThreadPoolExecutor, concurrent.futures.wait,
        frozenset(threading.enumerate()),
    )


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class ThemeCacheWorkerTests(unittest.TestCase):
    def setUp(self):
        baseline = _state()
        self.addCleanup(lambda: self.assertEqual(baseline, _state()))
        roots = []
        self.addCleanup(lambda: self.assertTrue(all(not root.exists() for root in roots)))
        storage = self.enterContext(storage_fixture())
        roots.append(storage.root)
        self.enterContext(_import_state())
        self.enterContext(mock.patch.dict(_data_fetcher.__dict__))
        importlib.reload(_data_fetcher)
        self.session_refs = []
        # Runs before module/env/storage restoration, after the testcase's
        # original local session list and provider patches have been released.
        self.addCleanup(self._check_sessions_released)

    def _check_sessions_released(self):
        gc.collect()
        self.assertTrue(all(reference() is None for reference in self.session_refs))

    @contextmanager
    def _real_workers(self, outcome="success", failure=None):
        case = self
        executor_type = concurrent.futures.ThreadPoolExecutor
        session_factory = requests.Session
        wait = concurrent.futures.wait
        pools, futures, session_refs = [], [], []
        release = threading.Event()
        entered = threading.Event()
        provider_errors = []

        class Session:
            def __init__(self):
                self.inner = session_factory()
                self.headers = self.inner.headers
                self.owner = threading.current_thread()
                session_refs.extend((weakref.ref(self), weakref.ref(self.inner)))

            def get(self, *args, **kwargs):
                case.assertIs(self.owner, threading.current_thread())
                entered.set()
                if outcome in ("assertion", "setup"):
                    if not release.wait(timeout=5):
                        raise TimeoutError("worker cleanup did not release session")
                if outcome == "provider":
                    provider_errors.append(failure)
                    raise failure
                return self.inner.get(*args, **kwargs)

        class OwnedExecutor(executor_type):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                pools.append(self)

            def submit(self, fn, *args, **kwargs):
                index = len(futures)
                if outcome == "setup" and index == 1:
                    case.assertTrue(entered.wait(timeout=5))
                    raise failure

                def run():
                    result = fn(*args, **kwargs)
                    if outcome == "worker" and index == 0:
                        raise failure
                    return result

                future = super().submit(run)
                futures.append(future)
                return future

            def __exit__(self, *args):
                release.set()
                result = super().__exit__(*args)
                case.assertTrue(self._threads)
                case.assertTrue(all(not worker.is_alive() for worker in self._threads))
                return result

        def observed_wait(*args, **kwargs):
            case.assertEqual(concurrent.futures.FIRST_COMPLETED, kwargs["return_when"])
            if outcome == "assertion":
                case.assertTrue(entered.wait(timeout=5))
                raise failure
            return wait(*args, **kwargs)

        with mock.patch.object(concurrent.futures, "ThreadPoolExecutor", OwnedExecutor), \
             mock.patch.object(concurrent.futures, "wait", side_effect=observed_wait), \
             mock.patch.object(requests, "Session", Session):
            try:
                yield
            finally:
                release.set()
                for pool in pools:
                    pool.shutdown(wait=True)
                    self.assertTrue(all(not worker.is_alive() for worker in pool._threads))
                self.assertTrue(pools)
                self.assertTrue(all(future.done() for future in futures))
                self.assertIs(requests.Session, Session)
                self.assertTrue(Path(os.environ["ALPHAMATE_TEST_ROOT"]).is_dir())
                if outcome == "provider":
                    self.assertTrue(provider_errors)
                    self.assertTrue(all(error is failure for error in provider_errors))
                self.session_refs.extend(session_refs)

    def _failure_paths(self, themes, names, rows):
        # Additional paths within the existing real-executor testcase, each
        # with its own storage/module scope and no additional discovered test.
        for outcome in ("assertion", "worker", "provider", "setup"):
            with self.subTest(cleanup=outcome):
                baseline = _state()
                failure = (AssertionError("synthetic calculation assertion") if outcome == "assertion"
                           else RuntimeError("synthetic " + outcome))

                class FakeSession:
                    def __init__(self):
                        self.headers = {}

                    def get(self, url, **kwargs):
                        ticker = url.split("symbol=", 1)[1].split("&", 1)[0]
                        return _Response(rows[ticker])

                try:
                    with storage_fixture() as storage, _import_state(), mock.patch.dict(_data_fetcher.__dict__):
                        importlib.reload(_data_fetcher)
                        original_provider = _data_fetcher.get_krx_themes
                        try:
                            with mock.patch.object(_data_fetcher, "get_krx_themes", return_value=(themes, names, {})), \
                                 mock.patch.object(requests, "Session", side_effect=FakeSession), \
                                 mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}):
                                if outcome == "provider":
                                    with self._real_workers(outcome, failure):
                                        result = _data_fetcher._calculate_theme_return_ranges({"1D": ("20250101", "20250111")})
                                    self.assertTrue(result["1D"].empty)
                                else:
                                    with self.assertRaises(type(failure)) as caught:
                                        with self._real_workers(outcome, failure):
                                            _data_fetcher._calculate_theme_return_ranges({"1D": ("20250101", "20250111")})
                                    self.assertIs(caught.exception, failure)
                        finally:
                            self.assertIs(requests.Session, baseline[6])
                            self.assertIs(_data_fetcher.get_krx_themes, original_provider)
                            self.assertTrue(storage.root.is_dir())
                finally:
                    # Clear retained synthetic provider tracebacks before the
                    # weakref check, not just when the A1 child exits.
                    failure.__traceback__ = None
                    self.assertFalse(storage.root.exists())
                    self.assertEqual(baseline, _state())

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
        future_refs = []

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
                future_refs.append(weakref.ref(future))
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
        self.assertTrue(all(reference() is None for reference in future_refs))
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
        future_refs = []

        class FailingExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                tracker["executor_exited"] = True

            def submit(self, _fn, ticker):
                future = concurrent.futures.Future()
                future_refs.append(weakref.ref(future))
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

        gc.collect()
        self.assertTrue(all(reference() is None for reference in future_refs))

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
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}), \
             self._real_workers():
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
        self._failure_paths(themes, names, rows)

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
             mock.patch.dict(os.environ, {"ALPHAMATE_THEME_FETCH_WORKERS": "2"}), \
             self._real_workers():
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
        self._failure_paths(themes, names, rows)


if __name__ == "__main__":
    unittest.main()
