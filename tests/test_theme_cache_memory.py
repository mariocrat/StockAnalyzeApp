from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state

import concurrent.futures
import copy
import gc
import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

import requests


# Minimized synthetic versions of the page-used Naver JSON responses, 2026-10-16.
_RANKINGS = "/api/stockSecurity/rankings/v2/domestic/themes"
_STOCKS = "/api/domestic/market/theme/{}/stocklist"
_NAVER_PAGES = {
    (_RANKINGS, None): {
        "hasNext": True, "cursor": "themes-next",
        "items": [{"code": "11", "name": "검증 테마 가"}],
    },
    (_RANKINGS, "themes-next"): {
        "hasNext": False, "cursor": None,
        "items": [{"code": "22", "name": "검증 테마 나"}],
    },
    (_STOCKS.format("11"), None): {
        "hasNext": True, "cursor": "stocks-next",
        "items": [{"itemCode": "A000001", "itemName": "검증 종목 하나", "krx": {"changeRate": "1.25"}}],
    },
    (_STOCKS.format("11"), "stocks-next"): {
        "hasNext": False, "cursor": None,
        "items": [{"itemCode": "000002", "itemName": "검증 종목 둘", "krx": None}],
    },
    (_STOCKS.format("22"), None): {
        "hasNext": False, "cursor": None,
        "items": [{"itemCode": "000003", "itemName": "검증 종목 셋", "krx": {"changeRate": "-2.5"}}],
    },
}


class _InlineExecutor:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def map(self, function, values):
        return map(function, values)

    def submit(self, function, *args):
        future = concurrent.futures.Future()
        try:
            future.set_result(function(*args))
        except Exception as error:
            future.set_exception(error)
        return future


def _json_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.encoding = "ISO-8859-1"
    response._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return response


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


with _import_state():
    from core import data_fetcher as _data_fetcher


class ThemeCacheMemoryTests(unittest.TestCase):
    def setUp(self):
        self.storage = self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.enterContext(mock.patch.dict(_data_fetcher.__dict__))
        importlib.reload(_data_fetcher)

    def _mock_naver(self, pages=None):
        pages = copy.deepcopy(_NAVER_PAGES) if pages is None else pages
        responses = []

        def get(url, *, params, headers, timeout):
            self.assertTrue(url.startswith("https://stock.naver.com/api/"))
            self.assertEqual(headers, {"User-Agent": "Mozilla/5.0"})
            self.assertEqual(timeout, 8)
            path = url.removeprefix("https://stock.naver.com")
            self.assertEqual(params["size"], 100)
            if path == _RANKINGS:
                self.assertEqual((params["sortType"], params["period"]), ("changeRate", "daily"))
            else:
                self.assertEqual((params["sortType"], params["sortDirection"]), ("tradingValue", "desc"))
            payload = pages[(path, params.get("cursor"))]
            response = payload if isinstance(payload, requests.Response) else _json_response(payload)
            responses.append(response)
            return response

        get_mock = self.enterContext(mock.patch.object(requests, "get", side_effect=get))
        self.enterContext(mock.patch.object(concurrent.futures, "ThreadPoolExecutor", _InlineExecutor))
        return get_mock, responses

    def test_current_naver_json_parses_paginated_utf8_themes_and_stocks(self):
        get, responses = self._mock_naver()
        themes, names, returns = _data_fetcher.get_krx_themes()

        self.assertEqual(themes, {"검증 테마 가": ["000001", "000002"], "검증 테마 나": ["000003"]})
        self.assertEqual(names, {"000001": "검증 종목 하나", "000002": "검증 종목 둘", "000003": "검증 종목 셋"})
        self.assertEqual(returns, {"검증 테마 가": {"000001": 1.25}, "검증 테마 나": {"000003": -2.5}})
        self.assertEqual(get.call_count, 5)
        self.assertTrue(all(response.encoding == "utf-8" for response in responses))
        self.assertEqual(_data_fetcher.get_cached_naver_themes(), (themes, names, returns))

    def test_invalid_naver_responses_never_publish_cache(self):
        malformed_json = _json_response(None)
        malformed_json._content = b"not JSON"
        invalid_cases = {
            "empty": {"items": [], "hasNext": False, "cursor": None},
            "missing-items": {"hasNext": False},
            "wrong-items": {"items": {}, "hasNext": False},
            "invalid-item": {"items": [None], "hasNext": False},
            "wrong-hasNext": {"items": [], "hasNext": "false"},
            "missing-cursor": {"items": [{"code": "11", "name": "검증"}], "hasNext": True},
            "empty-continuation": {"items": [], "hasNext": True, "cursor": "next"},
            "bad-theme-id": {"items": [{"code": "../11", "name": "검증"}], "hasNext": False},
            "bad-theme-name": {"items": [{"code": "11", "name": ""}], "hasNext": False},
            "http-error": _json_response({}, status=503),
            "malformed-json": malformed_json,
        }
        for label, payload in invalid_cases.items():
            with self.subTest(label=label):
                self._mock_naver({(_RANKINGS, None): payload})
                with mock.patch.object(_data_fetcher, "_write_json_cache") as write:
                    with self.assertRaisesRegex(RuntimeError, "previous cache preserved"):
                        _data_fetcher.get_krx_themes()
                    write.assert_not_called()
                self.assertEqual(list(self.storage.cache.iterdir()), [])

    def test_invalid_constituents_and_repeated_cursors_cannot_publish_partial_cache(self):
        for label in ("empty-stocks", "empty-final-stock-page", "malformed-detail", "bad-stock",
                      "bad-quote", "nan-return", "repeated-cursor"):
            with self.subTest(label=label):
                pages = copy.deepcopy(_NAVER_PAGES)
                if label == "empty-stocks":
                    pages[(_STOCKS.format("22"), None)] = {"items": [], "hasNext": False, "cursor": None}
                elif label == "empty-final-stock-page":
                    pages[(_STOCKS.format("11"), "stocks-next")] = {"items": [], "hasNext": False, "cursor": None}
                elif label == "malformed-detail":
                    pages[(_STOCKS.format("22"), None)] = {"items": {}, "hasNext": False, "cursor": None}
                elif label == "repeated-cursor":
                    pages[(_RANKINGS, "themes-next")]["hasNext"] = True
                    pages[(_RANKINGS, "themes-next")]["cursor"] = "themes-next"
                else:
                    stock = pages[(_STOCKS.format("22"), None)]["items"][0]
                    if label == "bad-stock":
                        stock["itemName"] = ""
                    elif label == "bad-quote":
                        stock["krx"] = []
                    else:
                        stock["krx"]["changeRate"] = "NaN"
                self._mock_naver(pages)
                with mock.patch.object(_data_fetcher, "_write_json_cache") as write:
                    with self.assertRaises(RuntimeError):
                        _data_fetcher.get_krx_themes()
                    write.assert_not_called()
                self.assertEqual(list(self.storage.cache.iterdir()), [])

    def test_poisoned_empty_theme_cache_is_ignored_and_replaced(self):
        _data_fetcher._write_json_cache("naver_themes_v3.json", {"themes": {}, "names": {}, "returns": {}})
        self.assertIsNone(_data_fetcher.get_cached_naver_themes())
        self._mock_naver()

        expected = _data_fetcher.get_krx_themes()

        self.assertTrue(expected[0])
        self.assertEqual(_data_fetcher.get_cached_naver_themes(), expected)

    def test_valid_theme_cache_is_reused_without_network(self):
        payload = {"themes": {"기존 테마": ["000001"]}, "names": {"000001": "기존 종목"}, "returns": {}}
        _data_fetcher._write_json_cache("naver_themes_v3.json", payload)
        with mock.patch.object(requests, "get") as get:
            self.assertEqual(_data_fetcher.get_krx_themes(), (payload["themes"], payload["names"], payload["returns"]))
            get.assert_not_called()

    def test_failed_refresh_preserves_expired_last_good_and_period_caches(self):
        payload = {"themes": {"기존 테마": ["000001"]}, "names": {"000001": "기존 종목"}, "returns": {}}
        _data_fetcher._write_json_cache("naver_themes_v3.json", payload)
        theme_path = self.storage.cache / "naver_themes_v3.json"
        expired = theme_path.stat().st_mtime - 8 * 24 * 3600
        os.utime(theme_path, (expired, expired))
        ranges = {"1D": ("20251001", "20251015"), "1W": ("20251008", "20251015"),
                  "1M": ("20250915", "20251015"), "1Y": ("20241015", "20251015")}
        for period, dates in ranges.items():
            _data_fetcher._write_json_cache(_data_fetcher._theme_return_cache_name(*dates, period),
                [{"Theme": "기존 테마", "Avg Return (%)": 2.5}])
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.storage.cache.iterdir()}
        pages = copy.deepcopy(_NAVER_PAGES)
        pages[(_STOCKS.format("22"), None)] = {"items": [], "hasNext": False, "cursor": None}
        self._mock_naver(pages)
        pending_ranges = {period: (dates[0], "20251016") for period, dates in ranges.items()}
        with (mock.patch.object(_data_fetcher, "_write_json_cache") as write,
              mock.patch.object(requests, "Session") as closes):
            with self.assertRaises(RuntimeError):
                _data_fetcher.get_krx_themes()
            with self.assertRaises(RuntimeError):
                _data_fetcher.warm_theme_return_caches(pending_ranges)
            write.assert_not_called()
            closes.assert_not_called()

        self.assertEqual(before, {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                                 for path in self.storage.cache.iterdir()})
        for period in ranges:
            self.assertFalse(_data_fetcher.get_latest_cached_theme_returns(period=period).empty)
            self.assertTrue(_data_fetcher.get_cached_theme_returns(*pending_ranges[period], period=period).empty)
        self.assertEqual(theme_path.stat().st_mtime, expired)

    def test_failed_refresh_is_not_memoized_and_can_recover(self):
        pages = copy.deepcopy(_NAVER_PAGES)
        pages[(_STOCKS.format("22"), None)] = {"items": [], "hasNext": False, "cursor": None}
        get, _ = self._mock_naver(pages)
        with self.assertRaises(RuntimeError):
            _data_fetcher.get_krx_themes()
        self.assertEqual(get.call_count, 5)
        pages[(_STOCKS.format("22"), None)] = copy.deepcopy(_NAVER_PAGES[(_STOCKS.format("22"), None)])

        self.assertEqual(set(_data_fetcher.get_krx_themes()[0]), {"검증 테마 가", "검증 테마 나"})
        self.assertEqual(get.call_count, 10)

    def test_new_naver_membership_warms_all_periods_and_failure_writes_none(self):
        ranges = {"1D": ("20250926", "20251010"), "1W": ("20251003", "20251010"),
                  "1M": ("20250910", "20251010"), "1Y": ("20241010", "20251010")}
        pages = copy.deepcopy(_NAVER_PAGES)
        pages[(_STOCKS.format("22"), None)] = {"items": [], "hasNext": False, "cursor": None}
        self._mock_naver(pages)
        with mock.patch.object(_data_fetcher, "_write_json_cache") as write:
            with self.assertRaises(RuntimeError):
                _data_fetcher.warm_theme_return_caches(ranges)
            write.assert_not_called()
        self.assertEqual(list(self.storage.cache.iterdir()), [])

        pages[(_STOCKS.format("22"), None)] = copy.deepcopy(_NAVER_PAGES[(_STOCKS.format("22"), None)])
        chart = str([[date, price, price, price, price, 100] for date, price in
                    (("20241010", 100), ("20251001", 105), ("20251008", 110),
                     ("20251009", 115), ("20251010", 120))]).replace("'", '"')
        session = mock.Mock(headers={})
        session.get.return_value = _Response(chart)
        with mock.patch.object(requests, "Session", return_value=session):
            self.assertEqual(_data_fetcher.warm_theme_return_caches(ranges), dict.fromkeys(ranges, 2))
        for period, dates in ranges.items():
            self.assertEqual(len(_data_fetcher.get_cached_theme_returns(*dates, period=period)), 2)
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(len(list(self.storage.cache.glob("theme_returns_v4_*.json"))), 4)

    def test_warm_cache_writes_separate_period_results_without_close_history_file(self):
        from core import data_fetcher

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
        from core import data_fetcher

        rows = [
            {"date": "20260716", "open": 181, "high": 181, "low": 181, "close": 181, "volume": 0},
            {"date": "20260720", "open": 1600, "high": 1800, "low": 1550, "close": 1726, "volume": 1000},
        ]

        adjusted = data_fetcher._adjust_price_rows_for_corporate_actions(rows)

        self.assertEqual(1810, adjusted[0]["close"])
        self.assertEqual(1726, adjusted[1]["close"])
        self.assertAlmostEqual(-4.64, ((adjusted[1]["close"] / adjusted[0]["close"]) - 1) * 100, places=2)

    def test_gradual_market_move_is_not_treated_as_corporate_action(self):
        from core import data_fetcher

        rows = [
            {"date": "20260716", "open": 100, "high": 130, "low": 100, "close": 130, "volume": 100},
            {"date": "20260717", "open": 130, "high": 169, "low": 130, "close": 169, "volume": 100},
            {"date": "20260720", "open": 169, "high": 219, "low": 169, "close": 219, "volume": 100},
        ]

        adjusted = data_fetcher._adjust_price_rows_for_corporate_actions(rows)

        self.assertEqual([130, 169, 219], [row["close"] for row in adjusted])


if __name__ == "__main__":
    unittest.main()
