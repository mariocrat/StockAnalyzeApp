"""Step 3: real producer content and closed-shape mutation matrices under H4."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
import datetime
import importlib
import json
import os
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.core import review_history_content_contract as contract
from backend.core.review_history_write_contract import HistoryWriteContractError
from tests import test_review_history_write_access as access_tests
from tests.review_source_fixtures import approved_chart_fixture


# Expected fields come from the Step 1 source inventory, not validator schemas.
META_KEYS = {"ticker", "name", "trade_date", "target_trade_id", "trade_snapshot", "recent_trades_snapshot", "chart_snapshot"}
TRADE_KEYS = {"trade_date", "ticker", "name", "side", "price", "quantity", "fee", "tax", "memo", "source", "display_snapshot"}
OBJECTIVE_KEYS = {"trade_count", "closed_count", "realized_pnl", "realized_return_pct", "win_rate_pct",
                  "weighted_buy_price", "weighted_sell_price", "total_fee", "total_tax",
                  "buy_fill_count", "sell_fill_count", "open_quantity", "symbol_count"}
RESULT_KEYS = {"status", "source", "review_type", "model", "summary", "display_snapshot", "structured_review",
               "chart_display_snapshot", "chart_contexts", "chart_reviews", "access"}


def nodes(value, path=()):
    yield path, value
    if type(value) is dict:
        for key, child in value.items():
            yield from nodes(child, path + (key,))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from nodes(child, path + (index,))


def at(value, path):
    for key in path:
        value = value[key]
    return value


def changed(value, path, replacement):
    value = copy.deepcopy(value)
    if not path:
        return replacement
    at(value, path[:-1])[path[-1]] = replacement
    return value


def capture(case, review_type="basic", status="ready", variant="session-free", **kwargs):
    _, (result, state) = case.route(variant, review_type, status, save=False, keyed=False, **kwargs)
    if not state or not state["approved"]:
        raise AssertionError("producer did not approve synthetic metadata")
    return json.loads(state["approved"]["metadata_json"]), result


class NewHistoryContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants = {}
        with access_tests.producer() as case:
            for variant in ("session-free", "session-pro", "review", "dev-session-free", "dev-session-pro"):
                for review_type in ("basic", "advanced"):
                    for status in ("ready", "missing_key"):
                        with patch.dict(os.environ, {"ALPHAMATE_ALLOW_DEV_ACCESS": str(variant.startswith("dev-session")).lower()}):
                            cls.variants[variant, review_type, status] = capture(case, review_type, status, variant)
            cls.charts = {}
            cls.produced_charts = {}
            chart_module = importlib.import_module("core.journal_chart")
            import pandas as pd

            for timeframe, interval, periods in (("daily", "1d", 4), ("weekly", "1wk", 150),
                                                  ("intraday", "1m", 12), ("intraday", "3m", 12), ("unavailable", "1d", 0)):
                trades = copy.deepcopy(case.trades)
                if timeframe == "daily":
                    trades[-1]["trade_date"] = "2026-07-11T10:00"
                elif timeframe == "weekly":
                    trades[0]["trade_date"] = "2026-01-10T09:30"
                elif interval == "3m":
                    trades[-1]["trade_date"] = "2026-07-10T12:30"
                index = pd.date_range("2026-07-10T09:30" if timeframe == "intraday" else "2026-01-10" if timeframe == "weekly" else "2026-07-10",
                                      periods=periods, freq="min" if timeframe == "intraday" else "D")
                frame = pd.DataFrame({"Open": 70000.0, "High": 72000.0, "Low": 69000.0, "Close": 70500.0,
                                      "Volume": 1000.0, "MA5": float("nan"), "MA20": float("nan")}, index=index)
                with ExitStack() as stack:
                    stack.enter_context(patch.object(chart_module, "_try_intraday", return_value=frame if timeframe == "intraday" else pd.DataFrame()))
                    stack.enter_context(patch.object(chart_module, "_daily_data", return_value=frame))
                    # Real journal candle/marker/tooltip/review producers and
                    # actual canonical metadata; only market data is supplied.
                    stack.enter_context(patch.object(case.main, "build_journal_charts", side_effect=chart_module.build_journal_charts))
                    stack.enter_context(patch.object(case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()))
                    for review_type in ("basic", "advanced"):
                        for status in ("ready", "missing_key"):
                            cls.charts[timeframe, interval, review_type, status] = capture(case, review_type, status, trades=trades)
                    produced = chart_module.build_journal_charts(trades)["charts"][0]
                    admitted = case.ai.admit_journal_chart_source(produced)
                    # The actual journal/admission/envelope path also emits
                    # intraday integer times, weekly dates and no-data output.
                    with patch.object(case.ai, "_compact_chart_snapshot", return_value=admitted):
                        for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
                            cls.produced_charts[timeframe, interval, review_type, status] = capture(case, review_type, status, trades=trades)
            cls.base = {review_type: cls.charts["daily", "1d", review_type, "ready"] for review_type in ("basic", "advanced")}

    def accepts(self, metadata, result):
        before = copy.deepcopy((metadata, result))
        self.assertIsNone(contract.validate_new_history_metadata(metadata))
        self.assertIsNone(contract.validate_new_history_structured_review(result["structured_review"], review_type=result["review_type"]))
        self.assertIsNone(contract.validate_new_history_result(result))
        self.assertEqual(before, (metadata, result))

    def rejects(self, validator, value, **kwargs):
        before = copy.deepcopy(value)
        with self.assertRaises(HistoryWriteContractError) as raised:
            validator(value, **kwargs)
        self.assertEqual(before, value)
        self.assertNotIn("synthetic-rejected-secret", str(raised.exception))

    def test_real_producer_twenty_storage_variants(self):
        for coordinates, (metadata, result) in self.variants.items():
            with self.subTest(coordinates=coordinates):
                self.accepts(metadata, result)
                self.assertEqual(META_KEYS, set(metadata))
                self.assertEqual(TRADE_KEYS | {"id"}, set(metadata["trade_snapshot"]))
                self.assertEqual(RESULT_KEYS | {"chart_snapshot" if result["review_type"] == "basic" else "chart_snapshots"}, set(result))
                self.assertEqual(OBJECTIVE_KEYS, set(result["structured_review"]["objective"]["result"]))

    def test_real_journal_and_display_chart_variants(self):
        for coordinates, (metadata, result) in self.charts.items():
            with self.subTest(coordinates=coordinates):
                self.accepts(metadata, result)
                chart = metadata["chart_snapshot"]["charts"][0]
                self.assertEqual("daily" if coordinates[0] == "unavailable" else coordinates[0], chart["timeframe"])
                self.assertEqual(coordinates[0] != "unavailable", "period_label" in chart)
                self.assertNotEqual(chart["candles"], result["chart_display_snapshot"]["charts"][0]["candles"])
                self.assertEqual(2 if chart["candles"] else 0, len(chart["markers"]))
        for coordinates, (metadata, result) in self.produced_charts.items():
            with self.subTest(outbound_coordinates=coordinates):
                self.accepts(metadata, result)
                projection = result["chart_display_snapshot"]
                if coordinates[0] == "unavailable":
                    self.assertEqual({"charts": [], "chart_cards": []}, projection)
                else:
                    chart = projection["charts"][0]
                    self.assertEqual((coordinates[0], coordinates[1]), (chart["timeframe"], chart["interval"]))
                    self.assertIs(type(chart["candles"][0]["time"]), int if coordinates[0] == "intraday" else str)

    def test_real_idless_stale_target_name_only_and_outside_recent_window(self):
        with access_tests.producer() as case:
            for review_type in ("basic", "advanced"):
                for status in ("ready", "missing_key"):
                    for target, idless, name_only in ((None, True, False), (999, False, False), (None, False, True)):
                        trades = copy.deepcopy(case.trades)
                        for trade in trades:
                            if idless:
                                trade.pop("id")
                            if name_only:
                                trade["ticker"] = ""
                        metadata, result = capture(case, review_type, status, target=target, trades=trades)
                        self.accepts(metadata, result)
                        self.assertEqual(not idless, "id" in metadata["trade_snapshot"])
                    trades = [dict(case.trades[index % 2], id=index + 1) for index in range(12)]
                    metadata, result = capture(case, review_type, status, target=1, trades=trades)
                    self.accepts(metadata, result)
                    self.assertNotIn(1, [row["id"] for row in metadata["recent_trades_snapshot"]])
                    self.assertEqual(10, len(metadata["recent_trades_snapshot"]))

    def test_real_objective_partial_fills_multi_symbol_and_unsorted_input(self):
        with access_tests.producer() as case:
            cases = [case.trades[:1], case.trades[1:], list(reversed(case.trades)),
                     [*case.trades, dict(case.trades[0], id=3, ticker="000660", name="합성 두 번째 종목")]]
            for trades in cases:
                for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
                    metadata, result = capture(case, review_type, status, target=999, trades=trades)
                    self.accepts(metadata, result)
                    objective = result["structured_review"]["objective"]["result"]
                    self.assertEqual(objective["trade_count"], objective["buy_fill_count"] + objective["sell_fill_count"])

    def test_real_grouped_fills_sell_only_and_zero_profit(self):
        with access_tests.producer() as case, ExitStack() as stack:
            import pandas as pd

            charts = importlib.import_module("core.journal_chart")
            frame = pd.DataFrame({"Open": 70000.0, "High": 72000.0, "Low": 69000.0, "Close": 70500.0,
                                  "Volume": 1000.0, "MA5": float("nan"), "MA20": float("nan")},
                                 index=pd.date_range("2026-07-10", periods=4))
            stack.enter_context(patch.object(charts, "_try_intraday", return_value=pd.DataFrame()))
            stack.enter_context(patch.object(charts, "_daily_data", return_value=frame))
            stack.enter_context(patch.object(case.main, "build_journal_charts", side_effect=charts.build_journal_charts))
            groups = (
                [case.trades[0], dict(case.trades[0], id=3, quantity=2.0), case.trades[1]],
                [case.trades[1]], [dict(case.trades[1], id=None)],
                [case.trades[0], dict(case.trades[1], price=70000.0)],
            )
            for trades in groups:
                for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
                    metadata, result = capture(case, review_type, status, trades=trades)
                    self.accepts(metadata, result)
                    markers = metadata["chart_snapshot"]["charts"][0]["markers"]
                    if len(trades) == 3:
                        self.assertEqual(("B2", 2), (markers[0]["text"], markers[0]["tooltip"]["count"]))
                    if len(trades) == 1:
                        self.assertIsNone(markers[0]["tooltip"]["profit_amount"])
                        self.assertIsNone(markers[0]["tooltip"]["return_rate"])
                        value = changed(metadata, ("chart_snapshot", "charts", 0, "markers", 0, "tooltip", "return_rate"), 0.0)
                        self.rejects(contract.validate_new_history_metadata, value)
                        value = changed(metadata, ("chart_snapshot", "charts", 0, "markers", 0, "trades", 0, "return_rate"), 0.0)
                        self.rejects(contract.validate_new_history_metadata, value)

    def test_missing_and_extra_keys_at_every_nested_object(self):
        for review_type, (metadata, result) in self.base.items():
            for validator, base in ((contract.validate_new_history_metadata, metadata), (contract.validate_new_history_result, result)):
                for path, original in nodes(base):
                    if path and path[0] == "access" or type(original) is not dict:
                        continue
                    for key in original:
                        # Omitted request IDs are a distinct normal trade variant.
                        if key == "id" and (path == ("trade_snapshot",) or path[:1] == ("recent_trades_snapshot",)):
                            continue
                        with self.subTest(review_type=review_type, path=path, missing=key):
                            value = copy.deepcopy(base)
                            del at(value, path)[key]
                            self.rejects(validator, value)
                    value = copy.deepcopy(base)
                    at(value, path)["synthetic-rejected-secret"] = None
                    self.rejects(validator, value)

    def test_wrong_exact_types_at_every_nested_field(self):
        class DictSubclass(dict):
            pass

        class ListSubclass(list):
            pass

        class StrSubclass(str):
            pass

        class IntSubclass(int):
            pass

        class FloatSubclass(float):
            pass

        alternatives = {
            dict: ([], "{}", DictSubclass()), list: ({}, (), "[]", ListSubclass()),
            str: (True, 1, 1.0, [], {}, StrSubclass("synthetic-rejected-secret")),
            int: (True, False, "1", [], {}, IntSubclass(1)),
            float: (True, False, "1", [], {}, FloatSubclass(1.0)),
            type(None): (True, [], {}),
        }
        for metadata, result in self.base.values():
            for validator, base in ((contract.validate_new_history_metadata, metadata), (contract.validate_new_history_result, result)):
                for path, original in nodes(base):
                    if path and path[0] == "access":
                        continue
                    for wrong in alternatives[type(original)]:
                        with self.subTest(path=path, wrong_type=type(wrong).__name__):
                            self.rejects(validator, changed(base, path, wrong))

    def test_trade_float_count_bool_and_integer_confusion(self):
        metadata, result = self.base["basic"]
        for path, original in nodes(metadata):
            if type(original) is float:
                self.rejects(contract.validate_new_history_metadata, changed(metadata, path, int(original)))
            elif type(original) is int:
                self.rejects(contract.validate_new_history_metadata, changed(metadata, path, float(original)))
        for path, original in nodes(result):
            if path and path[0] == "access" or type(original) is not int:
                continue
            if path[-1] in {"trade_count", "closed_count", "buy_fill_count", "sell_fill_count", "symbol_count", "trade_id"}:
                self.rejects(contract.validate_new_history_result, changed(result, path, float(original)))
        # Objective and approved chart numbers have the exact int|float union
        # established in Step 1. Seal identity is deliberately not checked here.
        value = changed(result, ("chart_display_snapshot", "charts", 0, "candles", 0, "open"), 71234.0)
        contract.validate_new_history_result(value)

    def test_required_nullable_and_id_variants(self):
        metadata, result = self.base["basic"]
        for path in (("target_trade_id",), ("chart_snapshot", "charts", 0, "reviews", 0, "trade_id"),
                     ("chart_snapshot", "charts", 0, "markers", 0, "trades", 0, "id")):
            value = changed(metadata, path, None)
            contract.validate_new_history_metadata(value)
        for parent in (("trade_snapshot",), ("recent_trades_snapshot", 0)):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, parent + ("id",), None))
        for path in (("trade_snapshot", "name"), ("trade_snapshot", "price"), ("trade_snapshot", "memo"),
                     ("chart_snapshot", "charts", 0, "markers", 0, "tooltip"), ("recent_trades_snapshot",)):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, path, None))
        for path in (("chart_display_snapshot", "chart_cards", 0, "trade_id"),
                     ("chart_display_snapshot", "charts", 0, "markers", 0, "label"),
                     ("chart_display_snapshot", "charts", 0, "markers", 0, "tooltip")):
            contract.validate_new_history_result(changed(result, path, None))
        for path in (("structured_review", "summary", "data_confidence"), ("structured_review", "basic", "lesson"),
                     ("chart_display_snapshot", "chart_cards", 0, "metrics"), ("display_snapshot",), ("summary",)):
            self.rejects(contract.validate_new_history_result, changed(result, path, None))

    def test_nonfinite_unsafe_counts_and_negative_trade_values(self):
        metadata, result = self.base["basic"]
        for validator, base in ((contract.validate_new_history_metadata, metadata), (contract.validate_new_history_result, result)):
            for path, original in nodes(base):
                if path and path[0] == "access" or type(original) not in (int, float):
                    continue
                for wrong in (float("inf"), float("-inf"), float("nan")):
                    value = changed(base, path, wrong)
                    with self.assertRaises(HistoryWriteContractError):
                        validator(value)
                    self.assertIs(at(value, path), wrong)
        for path in (("target_trade_id",), ("trade_snapshot", "id"),
                     ("chart_snapshot", "charts", 0, "markers", 0, "tooltip", "count")):
            for wrong in (0, -1, 2**53):
                self.rejects(contract.validate_new_history_metadata, changed(metadata, path, wrong))
        for field in ("price", "quantity", "fee", "tax"):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("trade_snapshot", field), -1.0))
        for field in ("price", "quantity"):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("trade_snapshot", field), 0.0))

    def test_trade_date_symbol_and_metadata_identity(self):
        metadata, _result = self.base["basic"]
        for date_value in ("", "2026-02-30", "2026-07-10T24:00", "2026-07-10T10:00+09:60"):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("trade_snapshot", "trade_date"), date_value))
        for path, wrong in ((("ticker",), "000660"), (("name",), "다른 합성 종목"), (("trade_date",), "2026-07-11"),
                            (("trade_snapshot", "ticker"), "AAPL"), (("trade_snapshot", "side"), "hold"),
                            (("trade_snapshot", "source"), "")):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, path, wrong))
        for path, wrong in ((("trade_snapshot",), "created_at"), (("trade_snapshot",), "user_id")):
            value = copy.deepcopy(metadata)
            at(value, path)[wrong] = "synthetic-rejected-secret"
            self.rejects(contract.validate_new_history_metadata, value)

    def test_structured_partial_and_legacy_shapes_reject(self):
        for review_type, (_metadata, result) in self.base.items():
            base = result["structured_review"]
            candidates = [changed(base, ("objective",), {}), changed(base, ("summary",), {
                key: base["summary"][key] for key in ("decision_quality", "main_issue", "next_action")}),
                changed(base, ("objective", "result"), {"trade_count": 2}), changed(base, (review_type, "lesson"), {"title": "근거"})]
            for value in candidates:
                self.rejects(contract.validate_new_history_structured_review, value, review_type=review_type)
            for wrong in ("basic" if review_type == "advanced" else "advanced", "Basic", None, True):
                self.rejects(contract.validate_new_history_structured_review, base, review_type=wrong)

    def test_structured_bounds_and_enums_do_not_normalize(self):
        for review_type, (_metadata, result) in self.base.items():
            base = result["structured_review"]
            for path, wrong in ((("schema_version",), "trade-review.v0"), (("summary", "decision_quality", "label"), "보통 "),
                                (("summary", "main_issue"), " " * 3), (("summary", "next_action"), "x" * 901),
                                (("summary", "data_confidence", "level"), "medium "), (("summary", "data_confidence", "label"), "높음"),
                                (("summary", "data_confidence", "reasons"), ["근거"] * 6), (("summary", "missing_information"), ["기록"] * 5)):
                self.rejects(contract.validate_new_history_structured_review, changed(base, path, wrong), review_type=review_type)
            arrays = [("good_points", 2, 1), ("next_trade_checks", 3, 1)] if review_type == "basic" else [
                ("detailed_analysis", 5, 0), ("reflection_questions", 2, 0)]
            for key, maximum, minimum in arrays:
                original = base[review_type][key]
                self.rejects(contract.validate_new_history_structured_review, changed(base, (review_type, key), [original[0]] * (maximum + 1)), review_type=review_type)
                if minimum:
                    self.rejects(contract.validate_new_history_structured_review, changed(base, (review_type, key), []), review_type=review_type)
        basic = self.base["basic"][1]["structured_review"]
        self.rejects(contract.validate_new_history_structured_review, changed(basic, ("basic", "next_trade_checks", 0, "phase"), "before_entry "), review_type="basic")
        advanced = self.base["advanced"][1]["structured_review"]
        for path, wrong in ((("advanced", "entry_review", "evidence"), []), (("advanced", "entry_review", "uncertainty"), ["기록"] * 5),
                            (("advanced", "risk_review", "assessment", "label"), "보통"), (("advanced", "next_trade_playbook", "before_entry"), [])):
            self.rejects(contract.validate_new_history_structured_review, changed(advanced, path, wrong), review_type="advanced")

    def test_objective_required_numbers_nulls_and_count_relations(self):
        base = self.base["basic"][1]["structured_review"]
        for field, wrong in (("trade_count", 1), ("closed_count", 3), ("buy_fill_count", 0), ("symbol_count", True),
                             ("weighted_buy_price", 0), ("total_fee", -1), ("total_tax", -1), ("open_quantity", -1)):
            self.rejects(contract.validate_new_history_structured_review, changed(base, ("objective", "result", field), wrong), review_type="basic")
        self.rejects(contract.validate_new_history_structured_review, changed(base, ("objective", "period", "first_trade_date"), "2027-01-01"), review_type="basic")
        for field in ("weighted_buy_price", "weighted_sell_price"):
            contract.validate_new_history_structured_review(changed(base, ("objective", "result", field), None), review_type="basic")
        for field in ("realized_pnl", "realized_return_pct", "win_rate_pct", "total_fee", "total_tax", "open_quantity"):
            self.rejects(contract.validate_new_history_structured_review, changed(base, ("objective", "result", field), None), review_type="basic")

    def test_result_origin_model_type_access_and_placeholder_relations(self):
        for review_type in ("basic", "advanced"):
            base = self.base[review_type][1]
            for path, wrong in ((("status",), "error"), (("source",), "chart-rules"), (("model",), None), (("model",), ""),
                                (("model",), "invalid model"), (("structured_review", "review_type"), "advanced" if review_type == "basic" else "basic"),
                                (("access", "review_type"), "advanced" if review_type == "basic" else "basic"),
                                (("chart_contexts",), [{}]), (("chart_reviews",), [{}])):
                self.rejects(contract.validate_new_history_result, changed(base, path, wrong))
            value = copy.deepcopy(base)
            value["internal_status"] = "invalid_structured_output"
            self.rejects(contract.validate_new_history_result, value)
            value = copy.deepcopy(base)
            value["review_history_id"] = 1
            self.rejects(contract.validate_new_history_result, value)
            value = copy.deepcopy(base)
            value["chart_snapshots" if review_type == "basic" else "chart_snapshot"] = [] if review_type == "basic" else {}
            self.rejects(contract.validate_new_history_result, value)
            missing = self.variants["session-free", review_type, "missing_key"][1]
            for path, wrong in ((("source",), "openai"), (("model",), "synthetic-model"), (("model",), "")):
                self.rejects(contract.validate_new_history_result, changed(missing, path, wrong))

    def test_result_summary_body_and_ready_semantic_rendering(self):
        for _metadata, base in self.base.values():
            self.rejects(contract.validate_new_history_result, changed(base, ("summary",), base["summary"] + " "))
            value = copy.deepcopy(base)
            value["display_snapshot"]["blocks"][0]["runs"][0]["text"] += "추가"
            self.rejects(contract.validate_new_history_result, value)
            value = copy.deepcopy(base)
            value["structured_review"]["summary"]["main_issue"] = "합성 다른 문제"
            self.rejects(contract.validate_new_history_result, value)
            value = copy.deepcopy(base)
            value["display_snapshot"]["surface"] = "chart_card"
            self.rejects(contract.validate_new_history_result, value)
        from tests import test_review_history_producers as producers

        original_output = producers.model_output
        issue = "과거 **체결** 근거 e\u0301 확인"

        def supplied_output(review_type):
            output = original_output(review_type)
            output["main_issue"] = issue
            return output

        with access_tests.producer() as case, patch.object(producers, "model_output", side_effect=supplied_output), \
                patch.object(case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()):
            for review_type in ("basic", "advanced"):
                metadata, result = capture(case, review_type, "ready")
                self.accepts(metadata, result)
                self.assertEqual(issue, result["structured_review"]["summary"]["main_issue"])
                self.assertIn("**체결**", result["summary"])
                self.assertIn("e\u0301", result["summary"])
                self.assertTrue(any(run["type"] == "strong" and run["text"] == "체결"
                                    for block in result["display_snapshot"]["blocks"] for run in block["runs"]))

    def test_chart_candles_timeframe_interval_and_ohlc_relations(self):
        metadata, result = self.base["basic"]
        for field, wrong in (("timeframe", "future"), ("interval", "1wk"), ("source", "weekly OHLCV"),
                             ("period_label", "2026-07-11 ~ 2026-07-10"), ("ticker", "")):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("chart_snapshot", "charts", 0, field), wrong))
        for field, wrong in (("time", 1), ("label", "2026-07-11"), ("open", 0.0), ("high", 1.0), ("low", 80000.0), ("volume", -1.0)):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("chart_snapshot", "charts", 0, "candles", 0, field), wrong))
        for path, wrong in ((("chart_display_snapshot", "charts", 0, "interval"), "1wk"),
                            (("chart_display_snapshot", "charts", 0, "candles", 0, "high"), 1),
                            (("chart_display_snapshot", "charts", 0, "markers", 0, "time"), "2027-01-01"),
                            (("chart_display_snapshot", "charts", 0, "candles"), [])):
            self.rejects(contract.validate_new_history_result, changed(result, path, wrong))
        value = copy.deepcopy(result)
        value["chart_display_snapshot"]["charts"][0].update(timeframe="weekly", interval="1wk")
        self.rejects(contract.validate_new_history_result, value)
        value = copy.deepcopy(result)
        header = value["chart_display_snapshot"]["charts"][0]["header"]
        header["blocks"][0]["runs"][0]["text"] = "일봉 · 1d · 2026-02-30"
        header["canonical_text"] = "일봉 · 1d · 2026-02-30"
        self.rejects(contract.validate_new_history_result, value)

    def test_marker_buy_sell_tooltip_fill_controls_and_relations(self):
        metadata = self.base["basic"][0]
        for field, wrong in (("position", "aboveBar"), ("color", "#ff5252"), ("shape", "arrowDown"),
                             ("size", 1), ("text", "B2"), ("time", "2027-01-01"), ("trades", [])):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("chart_snapshot", "charts", 0, "markers", 0, field), wrong))
        for field, wrong in (("label", "매도"), ("count", 2), ("avg_price", 70001.0), ("total_quantity", 2.0), ("prices", [70001.0])):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("chart_snapshot", "charts", 0, "markers", 0, "tooltip", field), wrong))
        value = copy.deepcopy(metadata)
        value["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"]["profit_amount"] = None
        self.rejects(contract.validate_new_history_metadata, value)
        for key in ("profit_amount", "return_rate"):
            value = copy.deepcopy(metadata)
            del value["chart_snapshot"]["charts"][0]["markers"][1]["tooltip"][key]
            self.rejects(contract.validate_new_history_metadata, value)
        value = copy.deepcopy(metadata)
        value["chart_snapshot"]["charts"][0]["markers"][0]["trades"][0]["matched_cost"] = None
        self.rejects(contract.validate_new_history_metadata, value)
        result = self.base["basic"][1]
        marker_path = ("chart_display_snapshot", "charts", 0, "markers", 0)
        self.rejects(contract.validate_new_history_result, changed(result, marker_path + ("side",), "sell"))
        for suffix, text in ((("label",), "S2"), (("label",), "B1"), (("tooltip",), "매수 3건")):
            value = copy.deepcopy(result)
            document = at(value, marker_path + suffix)
            document["blocks"][0]["runs"][0]["text"] = text
            document["canonical_text"] = "".join("".join(run["text"] for run in block["runs"])
                                                  + block["separator_after"] for block in document["blocks"])
            self.rejects(contract.validate_new_history_result, value)
        value = copy.deepcopy(result)
        tooltip = at(value, marker_path + ("tooltip",))
        tooltip["blocks"].pop()
        tooltip["blocks"][-1]["separator_after"] = ""
        tooltip["canonical_text"] = "".join("".join(run["text"] for run in block["runs"])
                                            + block["separator_after"] for block in tooltip["blocks"])
        self.rejects(contract.validate_new_history_result, value)
        value = copy.deepcopy(result)
        tooltip = at(value, marker_path + ("tooltip",))
        tooltip["blocks"][-1]["separator_after"] = "\n"
        tooltip["blocks"].append({"type": "paragraph", "runs": [{"type": "text", "text": "실현 +1원 · +1%"}], "separator_after": ""})
        tooltip["canonical_text"] += "\n실현 +1원 · +1%"
        self.rejects(contract.validate_new_history_result, value)

    def test_review_card_metadata_and_outbound_shapes(self):
        metadata, result = self.base["basic"]
        card = ("chart_snapshot", "charts", 0, "reviews", 0)
        for path, wrong in ((card + ("metrics",), {}), (card + ("trade_id",), True),
                            (card + ("metrics", "price_vs_close_pct"), None), (card + ("metrics", "ma5"), {"value": 1.0})):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, path, wrong))
        out = ("chart_display_snapshot", "chart_cards", 0)
        for path, wrong in ((out + ("metrics",), {}), (out + ("display", "surface"), "body"),
                            (out + ("metrics", "rsi14"), {"value": None}), (out + ("trade_id",), 0)):
            self.rejects(contract.validate_new_history_result, changed(result, path, wrong))
        self.rejects(contract.validate_new_history_result, changed(result, out + ("display", "blocks", 0, "type"), "heading"))
        unavailable = self.charts["unavailable", "1d", "basic", "ready"][0]
        value = changed(unavailable, ("chart_snapshot", "charts", 0, "reviews", 0, "detail"), "다른 기록")
        self.rejects(contract.validate_new_history_metadata, value)

    def test_metadata_documents_match_unmodified_raw_fields(self):
        base = self.base["basic"][0]
        paths = (("trade_snapshot", "display_snapshot"), ("chart_snapshot", "charts", 0, "display_snapshot"),
                 ("chart_snapshot", "charts", 0, "markers", 0, "display_snapshot"),
                 ("chart_snapshot", "charts", 0, "markers", 0, "tooltip", "display_snapshot"),
                 ("chart_snapshot", "charts", 0, "reviews", 0, "display_snapshot"))
        for path in paths:
            value = copy.deepcopy(base)
            document = at(value, path)
            document["blocks"][0]["runs"][0]["text"] += "추가"
            document["canonical_text"] = "".join("".join(run["text"] for run in block["runs"])
                                                  + block["separator_after"] for block in document["blocks"])
            self.rejects(contract.validate_new_history_metadata, value)

    def test_array_bounds_unknown_legacy_aliases_and_absence(self):
        metadata, result = self.base["basic"]
        for path, maximum in ((("recent_trades_snapshot",), 10), (("chart_snapshot", "charts"), 8),
                              (("chart_snapshot", "charts", 0, "candles"), 500), (("chart_snapshot", "charts", 0, "reviews"), 100)):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, path, [at(metadata, path)[0]] * (maximum + 1)))
        for path, maximum in ((("chart_display_snapshot", "charts"), 8), (("chart_display_snapshot", "chart_cards"), 100),
                              (("chart_display_snapshot", "charts", 0, "markers"), 300)):
            self.rejects(contract.validate_new_history_result, changed(result, path, [at(result, path)[0]] * (maximum + 1)))
        self.rejects(contract.validate_new_history_metadata, changed(metadata, ("recent_trades_snapshot",), []))
        for key in ("chart_contexts", "chart_reviews"):
            value = copy.deepcopy(metadata)
            value["chart_snapshot"][key] = []
            self.rejects(contract.validate_new_history_metadata, value)
        for key in ("trade_markers", "rule_based_observations", "period"):
            value = copy.deepcopy(metadata)
            value["chart_snapshot"]["charts"][0][key] = []
            self.rejects(contract.validate_new_history_metadata, value)

    def test_display_character_bounds_surfaces_and_cycles(self):
        metadata, result = self.base["basic"]
        for wrong in ("\x00", "\r", "\ud800", "x" * 16385):
            self.rejects(contract.validate_new_history_metadata, changed(metadata, ("trade_snapshot", "memo"), wrong))
            self.rejects(contract.validate_new_history_result, changed(result, ("summary",), wrong))
        for path in (("display_snapshot", "blocks"), ("structured_review", "objective")):
            value = copy.deepcopy(result)
            at(value, path[:-1])[path[-1]] = value
            with self.assertRaises(HistoryWriteContractError):
                contract.validate_new_history_result(value)
            self.assertIs(at(value, path), value)
        value = copy.deepcopy(result)
        value["chart_display_snapshot"]["chart_cards"] = [{}] * 100_001
        with self.assertRaises(HistoryWriteContractError):
            contract.validate_new_history_result(value)

    def test_plain_key_and_type_identity_without_custom_callbacks(self):
        class StringSubclass(str):
            pass

        class PretendType(type):
            def __eq__(cls, other):
                raise AssertionError("must not invoke class equality")

            __hash__ = type.__hash__

        class Impostor(metaclass=PretendType):
            pass

        metadata, result = self.base["basic"]
        value = copy.deepcopy(metadata)
        value[StringSubclass("ticker")] = value.pop("ticker")
        self.rejects(contract.validate_new_history_metadata, value)
        for path in (("summary",), ("structured_review", "objective", "result", "trade_count"), ("model",)):
            value = changed(result, path, Impostor())
            with self.assertRaises(HistoryWriteContractError):
                contract.validate_new_history_result(value)

    def test_pure_without_normalizers_legacy_cache_seal_or_io(self):
        tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual({"datetime", "math", "re", "backend.core.review_display_contract", "backend.core.review_history_write_contract"}, imports)
        with access_tests.producer() as case, ExitStack() as stack:
            import builtins
            import sqlite3
            from backend.core import review_source_contract, trade_review_schema, review_history_adapter, review_legacy_compatibility

            def forbidden(*args, **kwargs):
                raise AssertionError("new content contract crossed a forbidden dependency")

            for module, names in ((case.ai, ("_normalized_semantic_review", "safe_legacy_history_snapshot", "admit_ai_review_history_candidate")),
                                  (review_source_contract, ("admit_semantic_source", "admit_objective_source")),
                                  (trade_review_schema, ("normalize_semantic_output",)),
                                  (review_history_adapter, ("adapt_history_record",)),
                                  (review_legacy_compatibility, ("admit_legacy_body", "validate_legacy_body")),
                                  (case.main, ("_validate_ai_review_cached_access",)),
                                  (builtins, ("open",)), (sqlite3, ("connect",)), (os, ("getenv",))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=forbidden))
            stack.enter_context(patch.object(os, "environ", {}))
            for metadata, result in self.base.values():
                self.accepts(metadata, result)
            self.rejects(contract.validate_new_history_metadata, {})

    def test_preserved_step_two_access_exceptions_and_rejection(self):
        for review_type, (metadata, result) in self.base.items():
            for access in access_tests.fixtures():
                if access["review_type"] != review_type:
                    continue
                value = changed(result, ("access",), access)
                self.accepts(metadata, value)
            pro = access_tests.access_fixture(plan="pro", review_type=review_type)
            pro["wallet"]["validity"]["pro_allowance_resets_at"] = "2099-11-02"
            self.rejects(contract.validate_new_history_result, changed(result, ("access",), pro))
            self.rejects(contract.validate_new_history_result, changed(result, ("access", "auth_mode"), "dev"))
