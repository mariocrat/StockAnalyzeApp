"""P1 raw-provider/cache counterexamples through production AI builders in H4."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from contextlib import nullcontext
import datetime
import importlib
import json
import os
import unittest
from unittest.mock import patch

import pandas as pd

from tests.api_test_modules import _import_state
from tests.test_review_source_contract import trade, basic_semantic, advanced_semantic
from core import review_source_contract as contract


class ReviewMarketSourceAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai.__dict__))
        importlib.reload(self.ai)
        self.fetch = importlib.import_module("core.data_fetcher")
        self.charts = importlib.import_module("core.journal_chart")
        fdr = importlib.import_module("FinanceDataReader")
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}))
        self.trades = [dict(trade(), id=1, trade_date="2026-07-09T09:30"),
                       dict(trade(), id=2, trade_date="2026-07-10T09:30")]
        self.frame = pd.DataFrame({"Open": [70000] * 100, "High": [71000] * 100,
                                   "Low": [69000] * 100, "Close": [70100, 70400] * 50,
                                   "Volume": [1000] * 100},
                                  index=pd.date_range(end="2026-08-20", periods=100, freq="D"))
        self.primary = self.enterContext(patch.object(fdr, "DataReader", return_value=self.frame.copy()))
        self.fallback = self.enterContext(patch.object(self.fetch.yf, "download", return_value=self.frame.copy()))
        self.model = self.enterContext(patch.object(self.ai, "_call_openai_review", side_effect=self.model_output))
        # Restore the legacy cache too; no test may leave provenance-free entries.
        cache = self.fetch.get_stock_ohlcv.cache
        with self.fetch.get_stock_ohlcv.cache_lock:
            previous = list(cache.items())
            cache.clear()
        self.addCleanup(self.restore_cache, cache, previous)

    def restore_cache(self, cache, previous):
        with self.fetch.get_stock_ohlcv.cache_lock:
            cache.clear()
            cache.update(previous)

    @staticmethod
    def model_output(payload, *, model, instructions):
        raw = advanced_semantic() if payload["review_type"] == "advanced" else basic_semantic()
        return json.dumps(raw, ensure_ascii=False)

    def run_review(self, review_type, path="daily"):
        context_only = (patch.object(self.ai, "_compact_chart_snapshot", return_value={
            "kind": "unavailable", "reason": "no_market_data"}) if path == "context" else nullcontext())
        with context_only:
            approval = {}
            builder = self.ai.build_basic_ai_review if review_type == "basic" else self.ai.build_advanced_ai_review
            result = builder(self.trades, approval_state=approval)
            envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual(result["status"], envelope["status"])
        return result, envelope

    def assert_terminal(self, result, envelope):
        self.assertEqual(("error", "invalid_structured_output"),
                         (result["status"], result["internal_status"]))
        self.assertEqual(("error", "none"), (envelope["status"], envelope["source"]))
        self.assertEqual(([], [], []), (envelope["charts"], envelope["chart_cards"], envelope["trades"]))
        self.assertFalse(envelope["objective"]["has_market_data"])
        self.assertEqual(0, envelope["objective"]["trade_count"])
        self.assertEqual(contract.UNAVAILABLE_REVIEW_TEXT, envelope["notice"]["canonical_text"])

    def assert_rejected(self, raw, path="daily", provider="fdr"):
        for review_type in ("basic", "advanced"):
            with self.subTest(path=path, provider=provider, review_type=review_type):
                self.primary.reset_mock()
                self.fallback.reset_mock()
                self.model.reset_mock()
                self.primary.return_value = raw if provider == "fdr" else pd.DataFrame()
                self.fallback.return_value = raw
                original = raw.copy(deep=True) if isinstance(raw, pd.DataFrame) else None
                with patch.object(self.charts, "_prepare_ohlcv", wraps=self.charts._prepare_ohlcv) as prepare, patch.object(
                    pd, "to_numeric", wraps=pd.to_numeric,
                ) as coerce:
                    self.assert_terminal(*self.run_review(review_type, path))
                    prepare.assert_not_called()
                    coerce.assert_not_called()
                self.assertEqual(1, self.primary.call_count)
                self.assertEqual(0 if provider == "fdr" else 1, self.fallback.call_count)
                if provider != "fdr":
                    self.assertEqual("005930.KS", self.fallback.call_args.args[0])
                self.model.assert_not_called()
                if original is not None:
                    pd.testing.assert_frame_equal(original, raw)

    def assert_ready(self, path="daily"):
        for review_type in ("basic", "advanced"):
            with self.subTest(path=path, review_type=review_type):
                self.primary.reset_mock()
                self.fallback.reset_mock()
                self.model.reset_mock()
                result, envelope = self.run_review(review_type, path)
                self.assertEqual(("ready", "openai"), (envelope["status"], envelope["source"]))
                self.assertTrue(envelope["objective"]["has_market_data"])
                self.assertEqual(2, envelope["objective"]["trade_count"])
                self.assertEqual(1, self.primary.call_count)
                self.assertEqual(1, self.model.call_count)
                if path == "daily":
                    self.assertEqual("daily", envelope["charts"][0]["timeframe"])
                else:
                    self.assertEqual([], envelope["charts"])
                    self.assertNotEqual("low", result["structured_review"]["summary"]["data_confidence"]["level"])

    def test_daily_unknown_provider_column_is_terminal(self):
        self.assert_rejected(self.frame.assign(Future="UNKNOWN_PROVIDER_SOURCE"))

    def test_daily_partial_missing_close_row_is_terminal(self):
        raw = self.frame.copy()
        raw.iloc[-1, raw.columns.get_loc("Close")] = float("nan")
        self.assert_rejected(raw)

    def test_daily_all_missing_close_rows_do_not_fallback_or_retry(self):
        self.assert_rejected(self.frame.assign(Close=float("nan")))

    def test_context_unknown_provider_column_is_terminal(self):
        self.assert_rejected(self.frame.assign(Future="UNKNOWN_PROVIDER_SOURCE"), "context")

    def test_missing_close_column_is_terminal_for_daily_and_context(self):
        for path in ("daily", "context"):
            self.assert_rejected(self.frame.drop(columns=["Close"]), path)

    def test_context_partial_missing_close_row_is_terminal(self):
        raw = self.frame.copy()
        raw.iloc[-1, raw.columns.get_loc("Close")] = float("nan")
        self.assert_rejected(raw, "context")

    def test_context_all_missing_close_rows_do_not_fallback_or_retry(self):
        self.assert_rejected(self.frame.assign(Close=float("nan")), "context")

    def test_yfinance_unknown_column_stops_before_alternate_provider(self):
        for path in ("daily", "context"):
            self.assert_rejected(self.frame.assign(Future=1), path, "yfinance")

    def test_yfinance_missing_close_stops_before_alternate_provider(self):
        for path in ("daily", "context"):
            self.assert_rejected(self.frame.assign(Close=float("nan")), path, "yfinance")

    def test_provider_wrong_frame_type_is_terminal(self):
        for raw in (None, {}, [], "invalid"):
            self.assert_rejected(raw)

    def test_provider_numeric_strings_are_rejected_before_coercion(self):
        for path in ("daily", "context"):
            self.assert_rejected(self.frame.assign(Close="70400"), path)

    def test_provider_date_strings_are_rejected_before_normalization(self):
        raw = self.frame.copy()
        raw.index = raw.index.strftime("%Y-%m-%d")
        self.assert_rejected(raw)

    def test_nonempty_index_without_columns_is_not_unavailability(self):
        self.assert_rejected(pd.DataFrame(index=self.frame.index))

    def test_empty_unknown_columns_are_not_unavailability(self):
        self.assert_rejected(pd.DataFrame(columns=["Future"]))

    def test_normal_daily_provider_source_remains_ready(self):
        self.assert_ready()
        self.fallback.assert_not_called()

    def test_normal_context_provider_source_remains_ready(self):
        self.assert_ready("context")
        self.fallback.assert_not_called()

    def test_declared_fdr_change_metadata_is_admitted_before_projection(self):
        raw = self.frame.assign(Change=0.01)
        raw.iloc[0, raw.columns.get_loc("Change")] = float("nan")
        self.primary.return_value = raw
        for path in ("daily", "context"):
            self.assert_ready(path)
            self.fallback.assert_not_called()
        self.assertIn("Change", raw.columns)

    def test_invalid_declared_metadata_is_not_silently_dropped(self):
        for path in ("daily", "context"):
            self.assert_rejected(self.frame.assign(Change="invalid"), path)

    def test_normal_single_symbol_yfinance_layout_remains_ready(self):
        raw = self.frame.copy()
        raw.columns = pd.MultiIndex.from_product([raw.columns, ["005930.KS"]], names=["Price", "Ticker"])
        self.primary.return_value = pd.DataFrame()
        self.fallback.return_value = raw
        for path in ("daily", "context"):
            self.assert_ready(path)
            self.assertEqual(1, self.fallback.call_count)
            self.assertEqual("005930.KS", self.fallback.call_args.args[0])
        self.assertIsInstance(raw.columns, pd.MultiIndex)

    def test_yfinance_layout_cannot_hide_extra_columns_or_wrong_symbol(self):
        for path in ("daily", "context"):
            for symbol, extra in (("005930.KS", True), ("UNKNOWN.KS", False)):
                raw = self.frame.assign(Future=1) if extra else self.frame.copy()
                raw.columns = pd.MultiIndex.from_product([raw.columns, [symbol]])
                self.assert_rejected(raw, path, "yfinance")

    def test_genuine_unavailability_preserves_explicit_unavailable_variant(self):
        self.primary.return_value = pd.DataFrame()
        self.fallback.return_value = pd.DataFrame()
        for review_type in ("basic", "advanced"):
            self.primary.reset_mock()
            self.fallback.reset_mock()
            self.model.reset_mock()
            _result, envelope = self.run_review(review_type)
            self.assertEqual("ready", envelope["status"])
            self.assertEqual([], envelope["charts"])
            self.assertFalse(envelope["objective"]["has_market_data"])
            self.assertEqual(2, self.primary.call_count)  # journal, then context
            self.assertEqual(4, self.fallback.call_count)
            self.assertEqual(1, self.model.call_count)

    def test_transport_failure_can_still_use_a_valid_fallback(self):
        self.primary.side_effect = RuntimeError("synthetic transport failure")
        for path in ("daily", "context"):
            self.assert_ready(path)
            self.assertEqual(1, self.fallback.call_count)

    def assert_sanitized_cache_cannot_bypass(self, path):
        start, end = datetime.date(2026, 7, 9), datetime.date(2026, 7, 10)
        before, after = (90, 30) if path == "daily" else (140, 45)
        args = ("005930", (start - datetime.timedelta(days=before)).strftime("%Y%m%d"),
                (end + datetime.timedelta(days=after)).strftime("%Y%m%d"))
        raw = self.frame.assign(Future="UNKNOWN_PROVIDER_SOURCE")
        self.primary.return_value = raw
        sanitized = self.fetch.get_stock_ohlcv(*args)
        self.assertNotIn("Future", sanitized.columns)
        self.assertEqual(1, self.primary.call_count)
        self.assertIs(sanitized, self.fetch.get_stock_ohlcv(*args))
        self.assertEqual(1, self.primary.call_count)
        cache_before = dict(self.fetch.get_stock_ohlcv.cache.items())
        self.assertEqual(1, len(cache_before))
        self.assert_rejected(raw, path)
        cache_after = dict(self.fetch.get_stock_ohlcv.cache.items())
        self.assertEqual(set(cache_before), set(cache_after))
        for key in cache_before:
            self.assertIs(cache_before[key], cache_after[key])

    def test_daily_sanitized_shared_cache_cannot_bypass_raw_admission(self):
        self.assert_sanitized_cache_cannot_bypass("daily")

    def test_context_sanitized_shared_cache_cannot_bypass_raw_admission(self):
        self.assert_sanitized_cache_cannot_bypass("context")

    def test_strict_success_is_not_reused_to_hide_a_later_invalid_source(self):
        for path in ("daily", "context"):
            self.primary.return_value = self.frame.copy()
            self.assert_ready(path)
            self.assert_rejected(self.frame.assign(Future=1), path)
        self.assertEqual(0, len(self.fetch.get_stock_ohlcv.cache))

    def test_intraday_transport_is_admitted_before_column_flattening(self):
        raw = self.frame.assign(Future=1)
        raw.columns = pd.MultiIndex.from_product([raw.columns, ["005930.KS"]])
        self.fallback.return_value = raw
        with self.assertRaises(contract.SourceAdmissionError):
            self.charts._try_intraday("005930", datetime.date(2026, 7, 10),
                                      datetime.date(2026, 7, 10), "1m", review_source=True)
        self.assertEqual(1, self.fallback.call_count)
        self.primary.assert_not_called()
        self.model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
