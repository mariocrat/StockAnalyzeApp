"""Phase 2B-2 production admission/finalizer counterexamples under H4."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import copy
import importlib
import inspect
import json
import os
import unittest
from unittest.mock import patch

import pandas as pd

from tests.api_test_modules import _import_state
from tests.test_review_source_contract import trade, chart, basic_semantic, advanced_semantic, _normal_context
from core import review_source_contract as contract
from core.review_source_projection import semantic_payload


def journal_chart():
    raw = chart()
    return {"ticker": raw["ticker"], "name": raw["name"], "timeframe": raw["timeframe"],
            "interval": raw["interval"], "source": "daily OHLCV", "period_label": raw["period"],
            "candles": [{"time": row["time"], "label": row["t"], "open": row["o"],
                         "high": row["h"], "low": row["l"], "close": row["c"],
                         "volume": row["v"], "ma5": row["ma5"], "ma20": row["ma20"]}
                        for row in raw["candles"]],
            "markers": [], "reviews": raw["rule_based_observations"]}


_DEFAULT_TRADES = object()


class ReviewSourceAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai.__dict__))
        importlib.reload(self.ai)
        self.real_model_call = self.ai._call_openai_review
        self.real_compact = self.ai._compact_chart_snapshot
        self.real_contexts = self.ai._contexts_for_trades
        self.trades = [dict(trade(), id=1)]
        self.chart_mock = self.enterContext(patch.object(self.ai, "_compact_chart_snapshot", return_value=chart()))
        self.context_mock = self.enterContext(patch.object(self.ai, "_contexts_for_trades", return_value=[]))
        self.model = self.enterContext(patch.object(self.ai, "_call_openai_review", side_effect=self.model_output))

    @staticmethod
    def model_output(payload, *, model, instructions):
        return json.dumps(advanced_semantic() if payload["review_type"] == "advanced" else basic_semantic(), ensure_ascii=False)

    def run_builder(self, review_type, trades=_DEFAULT_TRADES):
        approval = {}
        builder = self.ai.build_basic_ai_review if review_type == "basic" else self.ai.build_advanced_ai_review
        result = builder(self.trades if trades is _DEFAULT_TRADES else trades, approval_state=approval)
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual(result["status"], envelope["status"])
        self.assertEqual(result["summary"], envelope["body"]["canonical_text"])
        return result, envelope

    def assert_fixed(self, result, envelope):
        self.assertEqual(("error", "invalid_structured_output"), (result["status"], result["internal_status"]))
        self.assertEqual(("error", "none"), (envelope["status"], envelope["source"]))
        self.assertEqual(([], [], []), (envelope["charts"], envelope["chart_cards"], envelope["trades"]))
        self.assertEqual(0, envelope["objective"]["trade_count"])
        self.assertFalse(envelope["objective"]["has_market_data"])
        self.assertEqual(contract.UNAVAILABLE_REVIEW_TEXT, envelope["notice"]["canonical_text"])

    def test_invalid_full_trade_input_rejects_before_episode_and_providers(self):
        cases = [None, {}, (), [None]]
        for mutate in (lambda v: v.update(future="UNKNOWN_SOURCE"), lambda v: v.pop("source"),
                       lambda v: v.update(price=True), lambda v: v.update(quantity=float("nan"))):
            row = trade()
            mutate(row)
            cases.append([row])
        for review_type in ("basic", "advanced"):
            for rows in cases:
                with self.subTest(review_type=review_type, rows=repr(rows)):
                    self.assert_fixed(*self.run_builder(review_type, rows))
        self.chart_mock.assert_not_called()
        self.context_mock.assert_not_called()
        self.model.assert_not_called()
        charts = importlib.import_module("core.journal_chart")
        for producer in (self.real_compact, self.real_contexts, self.ai._objective_review_snapshot,
                         lambda values: charts.build_journal_charts(values, review_source=True)):
            with self.assertRaises(contract.SourceAdmissionError):
                producer(self.trades)

    def test_invalid_idless_trade_outside_twenty_window_cannot_disappear(self):
        rows = [dict(trade(), id=index) for index in range(1, 202)]
        rows[0].pop("id")
        rows[0]["quantity"] = 0
        for review_type in ("basic", "advanced"):
            self.assert_fixed(*self.run_builder(review_type, rows))
        self.chart_mock.assert_not_called()
        self.model.assert_not_called()

    def test_invalid_name_only_or_unselected_symbol_trade_is_still_admitted(self):
        rows = [dict(trade(), ticker="", name="이름만 있는 종목", future="UNKNOWN_SOURCE"),
                dict(trade(), id=2)]
        for review_type in ("basic", "advanced"):
            self.assert_fixed(*self.run_builder(review_type, rows))
        self.model.assert_not_called()

    def test_raw_compact_absence_and_partial_shapes_never_upgrade(self):
        for raw in ({}, {"candles": ""}, {"candles": []}, {"kind": "unavailable", "reason": "unknown"}):
            self.chart_mock.return_value = raw
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
        self.context_mock.assert_not_called()
        self.model.assert_not_called()

    def test_complete_journal_admission_precedes_window_and_field_projection(self):
        mutations = (lambda v: v.update(future="UNKNOWN_SOURCE"),
                     lambda v: v["candles"][0].update(future="UNKNOWN_SOURCE"),
                     lambda v: v["candles"][0].pop("label"),
                     lambda v: v["candles"][0].update(volume="1000"),
                     lambda v: v["candles"][0].update(close=float("inf")),
                     lambda v: v["reviews"][0]["metrics"].update(future=1))
        for mutate in mutations:
            raw = journal_chart()
            raw["candles"] = [copy.deepcopy(raw["candles"][0]) for _index in range(201)]
            mutate(raw)
            with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
                self.ai, "build_journal_charts", return_value={"charts": [raw]},
            ) as provider:
                for review_type in ("basic", "advanced"):
                    self.assert_fixed(*self.run_builder(review_type))
                self.assertEqual(2, provider.call_count)  # one call per builder, no source retry
        self.model.assert_not_called()

    def test_invalid_second_journal_chart_cannot_be_lost_by_first_selection(self):
        raw = journal_chart()
        bad = copy.deepcopy(raw)
        bad["candles"][0]["l"] = -1
        with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
            self.ai, "build_journal_charts", return_value={"charts": [raw, bad]},
        ):
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
        self.model.assert_not_called()

    def test_invalid_marker_fill_and_label_cannot_be_erased_by_compaction(self):
        marker = {"time": "2026-07-10", "position": "belowBar", "color": "#2962ff",
                  "shape": "arrowUp", "text": "B", "size": 2, "side": "buy",
                  "trades": [{"id": 1, "date": "2026-07-10T09:30", "price": 70000, "quantity": 10}],
                  "tooltip": {"label": "매수", "count": 1, "avg_price": 70000,
                              "total_quantity": 10, "prices": [70000]}}
        for mutate in (lambda v: v["trades"][0].update(future="UNKNOWN_SOURCE"),
                       lambda v: v.update(text="OTHER"), lambda v: v["tooltip"].update(prices=["70000"])):
            raw = journal_chart()
            raw["markers"] = [copy.deepcopy(marker)]
            mutate(raw["markers"][0])
            with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
                self.ai, "build_journal_charts", return_value={"charts": [raw]},
            ):
                self.assert_fixed(*self.run_builder("basic"))
        self.model.assert_not_called()

    def test_context_wrong_and_unknown_shapes_reject_before_quality_and_model(self):
        self.chart_mock.return_value = {"kind": "unavailable", "reason": "no_market_data"}
        cases = [None, {}, (_normal_context(),), [{"error": "매매일 이전 차트 데이터가 없습니다."}]]
        for mutate in (lambda v: v.update(future="UNKNOWN_SOURCE"), lambda v: v.pop("ma20"),
                       lambda v: v.update(close="70400"), lambda v: v.update(next_5d_return=True)):
            context = _normal_context()
            mutate(context)
            cases.append([context])
        for contexts in cases:
            self.context_mock.return_value = contexts
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
        self.model.assert_not_called()

    def test_actual_context_output_is_admitted_before_lossy_consumers(self):
        bad = _normal_context()
        bad["future"] = "UNKNOWN_SOURCE"
        self.chart_mock.return_value = {"kind": "unavailable", "reason": "no_market_data"}
        with patch.object(self.ai, "_contexts_for_trades", self.real_contexts), patch.object(
            self.ai, "get_review_stock_ohlcv", return_value=pd.DataFrame(),
        ), patch.object(self.ai, "_chart_context_for_trade", return_value=bad):
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
        self.model.assert_not_called()

    def test_market_coercion_and_intraday_provider_retry_cannot_hide_source_failure(self):
        charts = importlib.import_module("core.journal_chart")
        frame = pd.DataFrame({"Open": [70000], "High": [71000], "Low": [69000],
                              "Close": ["invalid"], "Volume": [1000]},
                             index=pd.to_datetime(["2026-07-10"]))
        with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
            charts.yf, "download", return_value=frame,
        ) as intraday, patch.object(charts, "_daily_data") as daily:
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
            self.assertEqual(2, intraday.call_count)
            daily.assert_not_called()
        self.model.assert_not_called()

    def test_market_volume_coercion_cannot_make_invalid_rows_ready(self):
        charts = importlib.import_module("core.journal_chart")
        for value in ("1000", None, True, float("nan"), float("inf")):
            frame = pd.DataFrame({"Open": [70000], "High": [71000], "Low": [69000],
                                  "Close": [70400], "Volume": [value]},
                                 index=pd.to_datetime(["2026-07-10"]))
            with self.subTest(value=value), self.assertRaises(contract.SourceAdmissionError):
                charts._prepare_review_ohlcv(frame)
        frame["Volume"] = [1000]
        frame["future"] = "UNKNOWN_SOURCE"
        with self.assertRaises(contract.SourceAdmissionError):
            charts._prepare_review_ohlcv(frame)

    def test_source_rejection_skips_default_builders_and_valid_model_output(self):
        with patch.object(self.ai, "_default_basic_semantics") as basic, patch.object(
            self.ai, "_default_advanced_semantics",
        ) as advanced:
            for review_type in ("basic", "advanced"):
                approval = {}
                result = self.ai._finalize_ai_review(
                    self.model_output({"review_type": review_type}, model="test", instructions=""),
                    source=None, review_type=review_type, payload={"review_type": review_type}, model="test",
                    source_failure="invalid_structured_output", approval_state=approval)
                self.assert_fixed(result, json.loads(approval["snapshot"].json_text))
            basic.assert_not_called()
            advanced.assert_not_called()

    def test_invalid_source_with_missing_api_key_stays_terminal_error(self):
        self.chart_mock.return_value = {}
        self.model.side_effect = self.real_model_call
        self.model.reset_mock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ALPHAMATE_OPENAI_API_KEY": ""}), patch.object(
            self.ai.urllib.request, "urlopen",
        ) as urlopen:
            for review_type in ("basic", "advanced"):
                self.assert_fixed(*self.run_builder(review_type))
        self.model.assert_not_called()
        urlopen.assert_not_called()

    def test_terminal_source_failure_does_not_reuse_previous_ready_snapshot(self):
        for review_type in ("basic", "advanced"):
            builder = (self.ai.build_basic_ai_review if review_type == "basic"
                       else self.ai.build_advanced_ai_review)
            approval = {}
            first = builder(self.trades, approval_state=approval)
            previous = approval["snapshot"]
            self.assertEqual("ready", first["status"])

            self.chart_mock.return_value = {}
            self.model.reset_mock()
            failed = builder(self.trades, approval_state=approval)
            replacement = approval["snapshot"]
            self.assertIsNot(replacement, previous)
            self.assertNotEqual(replacement.digest, previous.digest)
            self.assert_fixed(failed, json.loads(replacement.json_text))
            self.model.assert_not_called()
            self.chart_mock.return_value = chart()

    def test_compiler_has_one_dto_input_and_rejects_raw_or_uninitialized_source(self):
        compiler = importlib.import_module("core.review_envelope_compiler")
        self.assertEqual(["source"], list(inspect.signature(compiler.compile_review_envelope).parameters))
        for raw in ({}, chart(), None, contract.ValidatedReviewSource.__new__(contract.ValidatedReviewSource)):
            with self.assertRaises(compiler.ReviewEnvelopeCompileError):
                compiler.compile_review_envelope(raw)
        original = compiler.compile_review_envelope
        admitted = []

        def track(source):
            self.assertIs(type(source), contract.ValidatedReviewSource)
            admitted.append(source)
            return original(source)

        with patch.object(self.ai, "compile_review_envelope", track):
            for review_type in ("basic", "advanced"):
                self.assertEqual("ready", self.run_builder(review_type)[0]["status"])
        self.assertEqual(2, len(admitted))

    def test_prompt_payload_mutation_does_not_recover_raw_source_at_finalization(self):
        def mutate(payload, *, model, instructions):
            trades = payload["trade_episode"] if payload["review_type"] == "basic" else payload["recent_trades"]
            trades[0]["quantity"] = "invalid"
            snapshots = [payload["trade_chart_snapshot"]] if payload["review_type"] == "basic" else payload["trade_chart_snapshots"]
            snapshots[0]["candles"][0]["c"] = "invalid"
            return self.model_output(payload, model=model, instructions=instructions)

        self.model.side_effect = mutate
        for review_type in ("basic", "advanced"):
            result, envelope = self.run_builder(review_type)
            self.assertEqual("ready", result["status"])
            self.assertEqual(self.trades[0]["quantity"], envelope["trades"][0]["quantity"])
            self.assertEqual(70400, envelope["charts"][0]["candles"][0]["close"])

    def test_explicit_empty_unavailable_and_model_fallback_variants(self):
        for review_type in ("basic", "advanced"):
            result, envelope = self.run_builder(review_type, [])
            self.assertEqual(("empty", "none"), (result["status"], envelope["source"]))
            self.assertEqual(contract.EMPTY_REVIEW_TEXT, result["summary"])
            self.chart_mock.return_value = {"kind": "unavailable", "reason": "no_market_data"}
            self.context_mock.return_value = [{"error": "매매일 이전 차트 데이터가 없습니다.", "trade": trade()}]
            result, envelope = self.run_builder(review_type)
            self.assertEqual("ready", result["status"])
            self.assertEqual([], envelope["charts"])
            self.assertEqual("low", result["structured_review"]["summary"]["data_confidence"]["level"])
            self.model.side_effect = None
            for raw, status in (("", "missing_key"), ("{}", "error")):
                self.model.return_value = raw
                self.assertEqual(status, self.run_builder(review_type)[0]["status"])
            self.model.side_effect = self.model_output

    def test_primary_model_failure_still_uses_existing_fallback_model_once(self):
        models = []

        def call(payload, *, model, instructions):
            models.append(model)
            if len(models) == 1:
                raise RuntimeError("synthetic provider failure")
            return self.model_output(payload, model=model, instructions=instructions)

        self.model.side_effect = call
        self.assertEqual("ready", self.run_builder("advanced")[0]["status"])
        self.assertEqual(2, len(models))
        self.assertNotEqual(models[0], models[1])
        self.model.reset_mock()
        self.model.side_effect = RuntimeError("must not be called for invalid source")
        self.chart_mock.return_value = {}
        self.assert_fixed(*self.run_builder("advanced"))
        self.model.assert_not_called()

    def test_full_objective_and_twenty_prompt_display_window_for_both_builders(self):
        for count in (20, 21, 200):
            rows = [dict(trade(), id=index, quantity=1, fee=0) for index in range(1, count + 1)]
            for review_type in ("basic", "advanced"):
                seen = []

                def call(payload, *, model, instructions):
                    seen.append(len(payload["trade_episode"] if review_type == "basic" else payload["recent_trades"]))
                    return self.model_output(payload, model=model, instructions=instructions)

                self.model.side_effect = call
                result, envelope = self.run_builder(review_type, rows)
                self.assertEqual("ready", result["status"])
                self.assertEqual([20], seen)
                self.assertEqual(count, envelope["objective"]["trade_count"])
                self.assertEqual(count, result["structured_review"]["objective"]["result"]["open_quantity"])
                self.assertEqual(20, len(envelope["trades"]))

    def test_existing_chart_window_selects_only_after_complete_admission(self):
        raw = journal_chart()
        raw["candles"] = [copy.deepcopy(raw["candles"][0]) for _index in range(201)]
        with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
            self.ai, "build_journal_charts", return_value={"charts": [raw]},
        ):
            for review_type in ("basic", "advanced"):
                result, envelope = self.run_builder(review_type)
                self.assertEqual("ready", result["status"])
                self.assertEqual(100, len(envelope["charts"][0]["candles"]))

    def test_invalid_model_shape_does_not_retry_or_survive_low_confidence(self):
        self.chart_mock.return_value = {"kind": "unavailable", "reason": "provider_error"}
        for review_type in ("basic", "advanced"):
            raw = advanced_semantic() if review_type == "advanced" else basic_semantic()
            raw["future"] = "UNKNOWN_SOURCE"
            self.model.side_effect = None
            self.model.return_value = json.dumps(raw)
            self.model.reset_mock()
            result, envelope = self.run_builder(review_type)
            self.assertEqual(("error", "invalid_structured_output"), (result["status"], result["internal_status"]))
            self.assertEqual(1, self.model.call_count)
            self.assertNotIn("UNKNOWN_SOURCE", json.dumps(envelope))

    def test_default_semantics_share_the_factory_admitted_model_dto_types(self):
        trades = contract.admit_trade_sources(self.trades)
        for review_type in ("basic", "advanced"):
            source = contract.compose_review_source(review_type=review_type, trades=trades,
                                                     objective=self.ai._objective_review_snapshot(trades),
                                                     charts=(contract.admit_chart_source(chart()),))
            fallback = self.ai._default_basic_semantics(source) if review_type == "basic" else self.ai._default_advanced_semantics(source)
            same = contract.admit_semantic_source(semantic_payload(fallback), review_type)
            self.assertEqual(fallback, same)
            with self.assertRaises(TypeError):
                type(fallback)()

    def test_actual_market_chart_and_context_producers_pass_valid_data(self):
        charts = importlib.import_module("core.journal_chart")
        frame = pd.DataFrame({"Open": [70000] * 30, "High": [71000] * 30, "Low": [69000] * 30,
                              "Close": [70100, 70400] * 15, "Volume": [1000] * 30},
                             index=pd.date_range("2026-07-10T09:00", periods=30, freq="min"))
        with patch.object(self.ai, "_compact_chart_snapshot", self.real_compact), patch.object(
            charts.yf, "download", return_value=frame,
        ) as provider:
            for review_type in ("basic", "advanced"):
                result, envelope = self.run_builder(review_type)
                self.assertEqual("ready", result["status"])
                self.assertEqual("intraday", envelope["charts"][0]["timeframe"])
                # The trade maps to the last candle: keep the preceding 25
                # plus that candle under the existing marker window policy.
                self.assertEqual(26, len(envelope["charts"][0]["candles"]))
                self.assertEqual("B", envelope["charts"][0]["markers"][0]["label"]["canonical_text"])
            self.assertEqual(2, provider.call_count)
        frame.index = pd.date_range(end="2026-07-10", periods=30, freq="D")
        self.chart_mock.return_value = {"kind": "unavailable", "reason": "no_market_data"}
        with patch.object(self.ai, "_contexts_for_trades", self.real_contexts), patch.object(
            self.ai, "get_review_stock_ohlcv", return_value=frame,
        ):
            for review_type in ("basic", "advanced"):
                result, envelope = self.run_builder(review_type)
                self.assertEqual("ready", result["status"])
                self.assertTrue(envelope["objective"]["has_market_data"])
                self.assertEqual([], envelope["charts"])
                self.assertNotEqual("low", result["structured_review"]["summary"]["data_confidence"]["level"])
