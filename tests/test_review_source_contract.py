"""Phase 2B-1 source admission regressions under the H4 boundary."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
from dataclasses import FrozenInstanceError, fields, is_dataclass
import math
import pickle
from pathlib import Path
import unittest

from core import review_source_contract as source


def _source_dto_classes(namespace=None):
    """Find factory-base subclasses before checking their dataclass decoration."""
    namespace = vars(source) if namespace is None else namespace
    return tuple(sorted(
        {value for value in namespace.values()
         if isinstance(value, type) and value is not source._FactoryOnly
         and issubclass(value, source._FactoryOnly)},
        key=lambda value: value.__name__,
    ))


def _ast_source_dto_names():
    tree = ast.parse(Path(source.__file__).read_text(encoding="utf-8"))
    return tuple(sorted(
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "_FactoryOnly" for base in node.bases)
    ))


def _normal_context():
    return {"trade_id": 1, "date": "2026-07-10T09:30", "market_date": "2026-07-10",
            "ticker": "005930", "name": "삼성전자", "side": "buy", "price": 70000,
            "quantity": 2, "memo": "기록", "close": 70400,
            "price_vs_close_pct": -0.5, "ma5": None, "ma20": None, "ma60": None,
            "rsi14": None, "volume_ratio_20d": None, "return_10d_before": None,
            "position_in_20d_range": None, "next_5d_return": None,
            "next_20d_return": None}


def _factory_source_roots():
    basic = review_source()
    basic["trades"] = [trade(), {**trade(), "id": 7, "created_at": "2026-07-10T10:00:00",
                                 "user_id": "owner-1"}]
    basic["objective"]["result"].update(trade_count=2, buy_fill_count=2, open_quantity=4)
    basic["charts"][0]["rule_based_observations"].append(
        {"title": "데이터 없음", "detail": "지표 없음"})
    basic["charts"].append({"kind": "unavailable", "reason": "no_market_data"})
    basic["analysis_contexts"] = [
        _normal_context(),
        {"error": "매매일 이전 차트 데이터가 없습니다.", "trade": trade()},
    ]

    advanced = review_source()
    advanced.update(review_type="advanced", semantic=advanced_semantic())

    empty = review_source()
    empty.update(status="empty", origin="none", trades=[],
                 objective={"kind": "unavailable", "reason": "no_trades"},
                 charts=[{"kind": "unavailable", "reason": "no_market_data"}],
                 semantic=None, has_market_data=False)
    return (source.admit_review_source(basic), source.admit_review_source(advanced),
            source.admit_review_source(empty))


def _factory_dto_types(roots):
    found = set()
    pending = list(roots)
    while pending:
        value = pending.pop()
        if isinstance(value, source._FactoryOnly):
            found.add(type(value))
            pending.extend(getattr(value, field.name) for field in fields(type(value)))
        elif type(value) is tuple:
            pending.extend(value)
    return found


def _assert_dto_class_protected(testcase, dto_class):
    testcase.assertTrue(is_dataclass(dto_class), f"{dto_class.__name__} must be a dataclass")
    testcase.assertTrue(dto_class.__dataclass_params__.frozen,
                        f"{dto_class.__name__} must remain frozen")
    testcase.assertIn("__slots__", dto_class.__dict__,
                      f"{dto_class.__name__} must declare slots")
    testcase.assertIs(dto_class.__dict__.get("__setstate__"),
                      source._reject_source_state_restore,
                      f"{dto_class.__name__} must use the restore guard")
    testcase.assertIs(dto_class.__reduce_ex__, source._FactoryOnly.__dict__["__reduce_ex__"],
                      f"{dto_class.__name__} must keep pickle restoration disabled")


def _pickle_with_mutable_state(dto_class):
    dto_fields = fields(dto_class)
    state_index = next((index for index, field in enumerate(dto_fields) if field.name == "price"), 0)
    state_values = b"N" * state_index + b"]" + b"N" * (len(dto_fields) - state_index - 1)
    return (b"\x80\x04c" + dto_class.__module__.encode("ascii") + b"\n"
            + dto_class.__name__.encode("ascii") + b"\n)\x81(" + state_values + b"tb.")


def trade():
    return {"trade_date": "2026-07-10T09:30", "ticker": "005930", "name": "삼성전자",
            "side": "buy", "price": 70000, "quantity": 2, "fee": 100, "tax": 0,
            "memo": "기록", "source": "manual"}


def objective():
    return {"symbol": {"ticker": "005930", "name": "삼성전자"},
            "period": {"first_trade_date": "2026-07-10T09:30",
                       "last_trade_date": "2026-07-10T09:30"},
            "result": {"trade_count": 1, "closed_count": 0, "realized_pnl": 0,
                       "realized_return_pct": 0, "win_rate_pct": 0,
                       "weighted_buy_price": 70000, "weighted_sell_price": None,
                       "total_fee": 100, "total_tax": 0, "buy_fill_count": 1,
                       "sell_fill_count": 0, "open_quantity": 2, "symbol_count": 1}}


def candle():
    return {"time": "2026-07-10", "t": "2026-07-10", "o": 70000,
            "h": 71000, "l": 69000, "c": 70400, "v": 1000,
            "ma5": 70100, "ma20": None}


def marker(side="buy"):
    tooltip = {"label": "매수" if side == "buy" else "매도", "count": 1,
               "avg_price": 70000, "total_quantity": 2, "prices": [70000]}
    if side == "sell":
        tooltip.update(profit_amount=None, return_rate=None)
    return {"time": "2026-07-10", "side": side, "tooltip": tooltip}


def observation():
    return {"trade_id": 1, "title": "과거 체결", "detail": "근거 확인",
            "metrics": {"price_vs_close_pct": 0.5, "after_5_bars": None,
                        "after_later_bars": -1.5, "ma5": 70100, "ma20": None}}


def chart():
    return {"ticker": "005930", "name": "삼성전자", "timeframe": "daily",
            "interval": "1d", "period": "2026-07-10", "candles": [candle()],
            "trade_markers": [marker("buy"), marker("sell")],
            "rule_based_observations": [observation()]}


def basic_semantic():
    return {"decision_quality": {"label": "보통", "explanation": "근거 확인"},
            "main_issue": "사전 기준 기록", "next_action": "다음 거래 전 기록",
            "good_points": [{"title": "체결 확인", "detail": "매수 체결을 확인했습니다."}],
            "main_improvement": {"title": "기준 기록", "detail": "판단 근거를 기록합니다."},
            "next_trade_checks": [{"phase": "before_entry", "text": "기준을 확인합니다."}],
            "lesson": {"title": "사전 기준", "concept": "사후 결과와 구분합니다.",
                       "applied_to_this_trade": "이번 거래를 기록합니다."}}


def advanced_semantic():
    value = basic_semantic()
    for key in ("good_points", "main_improvement", "next_trade_checks", "lesson"):
        value.pop(key)
    value.update({
        "entry_review": {"evidence": ["체결가 확인"], "uncertainty": [],
                         "invalidation": "기록 없음",
                         "assessment": {"label": "근거 일부", "explanation": "확인 가능한 사실"}},
        "risk_review": {"planned_rule": "기록 없음", "actual_response": "매도 기록 확인",
                        "assessment": {"label": "근거 부족", "explanation": "기록 부족"}},
        "exit_review": {"profit_taking_assessment": "확인 필요",
                        "trend_exit_assessment": "확인 필요", "explanation": "결과 분리"},
        "detailed_analysis": [{"title": "체결 흐름", "detail": "가격을 비교했습니다."}],
        "next_trade_playbook": {"before_entry": ["진입 근거 기록"],
                                "while_holding": ["가설 확인"],
                                "before_exit": ["매도 기준 확인"]},
        "lesson": {"title": "사전 기준", "concept": "사후 결과와 구분합니다.",
                   "applied_to_this_trade": "이번 거래를 기록합니다.",
                   "next_trade_application": "다음 거래 전 기준을 기록합니다."},
        "reflection_questions": ["어떤 근거였나요?"],
    })
    return value


def review_source():
    return {"review_type": "basic", "status": "ready", "origin": "openai",
            "trades": [trade()], "objective": objective(), "charts": [chart()],
            "analysis_contexts": [], "semantic": basic_semantic(),
            "has_market_data": True, "notice": None}


class ReviewSourceContractTest(unittest.TestCase):
    def assert_rejected(self, factory, raw, **kwargs):
        with self.assertRaises(source.SourceAdmissionError):
            factory(raw, **kwargs)

    def test_every_factory_only_subclass_has_dataclass_and_restore_guard(self):
        dto_classes = _source_dto_classes()
        ast_names = _ast_source_dto_names()
        factory_types = _factory_dto_types(_factory_source_roots())
        runtime_names = tuple(dto_class.__name__ for dto_class in dto_classes)
        factory_names = tuple(sorted(dto_class.__name__ for dto_class in factory_types))
        self.assertEqual((28, 28, 28), (len(ast_names), len(dto_classes), len(factory_types)))
        self.assertEqual(ast_names, runtime_names)
        self.assertEqual(ast_names, factory_names)
        for dto_class in dto_classes:
            with self.subTest(dto=dto_class.__name__):
                _assert_dto_class_protected(self, dto_class)
                self.assertTrue(issubclass(dto_class, source._FactoryOnly))
                with self.assertRaises(TypeError):
                    dto_class()

                uninitialized = dto_class.__new__(dto_class)
                mutable_state = tuple([] for _field in fields(dto_class))
                with self.assertRaises(TypeError):
                    uninitialized.__setstate__(mutable_state)
                self.assertFalse(any(hasattr(uninitialized, field.name)
                                     for field in fields(dto_class)))
                with self.assertRaises(TypeError):
                    pickle.loads(_pickle_with_mutable_state(dto_class))

    def test_factory_only_subclass_without_dataclass_cannot_escape_enumeration(self):
        class MissingDataclass(source._FactoryOnly):
            __slots__ = ()

        namespace = dict(vars(source))
        namespace["MissingDataclass"] = MissingDataclass
        dto_classes = _source_dto_classes(namespace)
        self.assertIn(MissingDataclass, dto_classes)
        with self.assertRaisesRegex(AssertionError, "must be a dataclass"):
            _assert_dto_class_protected(self, MissingDataclass)

    def test_trade_state_restore_cannot_replace_price_or_pickle_factory_result(self):
        admitted = source.admit_trade_source(trade())
        self.assertEqual(70000, admitted.price)
        fields_in_order = fields(source.TradeSource)
        price_index = next(index for index, field in enumerate(fields_in_order)
                           if field.name == "price")
        for invalid in ({"mutable": []}, [], bytearray(b"70000")):
            state = [getattr(admitted, field.name) for field in fields_in_order]
            state[price_index] = invalid
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises(TypeError):
                    admitted.__setstate__(tuple(state))
                self.assertEqual(70000, admitted.price)
        with self.assertRaises(TypeError):
            pickle.dumps(admitted)

        uninitialized = source.TradeSource.__new__(source.TradeSource)
        with self.assertRaises(TypeError):
            uninitialized.__setstate__((None, None, None, None, None, None, {"bad": []}))
        self.assertFalse(hasattr(uninitialized, "price"))

    def test_trade_exact_basic_identified_and_stored_variants(self):
        raw = trade()
        self.assertEqual("basic", source.admit_trade_source(raw).variant)
        raw["id"] = 7
        self.assertEqual("identified", source.admit_trade_source(raw).variant)
        raw.update(created_at="2026-07-10T10:00:00", user_id="owner-1")
        admitted = source.admit_trade_source(raw)
        self.assertEqual(("stored", 7, "krx"), (admitted.variant, admitted.id, admitted.symbol_kind))
        raw["ticker"] = ""
        self.assertEqual("name_only", source.admit_trade_source(raw).symbol_kind)
        for fee, tax in ((69, None), (None, 1500), (None, None), (0, 0)):
            broker = {**trade(), "source": "broker_import", "fee": fee, "tax": tax}
            admitted = source.admit_trade_source(broker)
            self.assertEqual((fee, tax), (admitted.fee, admitted.tax))
            if fee is None or tax is None:
                with self.assertRaises(source.SourceAdmissionError):
                    source.admit_trade_source({**broker, "source": "manual"})

    def test_trade_required_unknown_and_partial_variant_reject(self):
        for mutation in (lambda v: v.pop("fee"), lambda v: v.update(extra=1),
                         lambda v: v.update(created_at="2026-07-10T10:00:00"),
                         lambda v: v.update(id=None)):
            with self.subTest(mutation=mutation):
                raw = trade()
                mutation(raw)
                self.assert_rejected(source.admit_trade_source, raw)

    def test_trade_numeric_types_and_nonfinite_reject(self):
        for key, value in (("price", True), ("price", "70000"), ("quantity", False),
                           ("fee", "0"), ("tax", math.nan), ("price", math.inf),
                           ("quantity", -math.inf), ("price", 0), ("quantity", -1)):
            with self.subTest(key=key, value=value):
                raw = trade()
                raw[key] = value
                self.assert_rejected(source.admit_trade_source, raw)

    def test_trade_invalid_date_side_code_name_and_lengths_reject(self):
        for key, value in (("trade_date", "2026-02-30"), ("trade_date", "2026-07-10T25:00"),
                           ("side", "hold"), ("ticker", "AAPL"), ("name", "  "),
                           ("name", "N" * 121), ("source", "s" * 41),
                           ("memo", "m" * 2001)):
            with self.subTest(key=key):
                raw = trade()
                raw[key] = value
                self.assert_rejected(source.admit_trade_source, raw)
        self.assertEqual(3000, len(source.admit_trade_source({**trade(), "memo": "m" * 3000},
                                                           memo_max_chars=3000).memo))

    def test_invalid_unidentified_trade_cannot_be_skipped_after_window(self):
        raw = review_source()
        raw["trades"] = [trade() for _ in range(20)] + [{**trade(), "side": "hold"}]
        raw["objective"]["result"].update(trade_count=21, buy_fill_count=21)
        self.assert_rejected(source.admit_review_source, raw)

    def test_objective_exact_nested_full_result_passes(self):
        dto = source.admit_objective_source(objective())
        self.assertEqual(1, dto.result.trade_count)
        self.assertIsNone(dto.result.weighted_sell_price)
        self.assertEqual("krx", dto.symbol.symbol_kind)

    def test_objective_missing_unknown_invalid_counts_numbers_dates_reject(self):
        changes = (
            lambda v: v["result"].pop("weighted_sell_price"),
            lambda v: v["result"].update(extra=1),
            lambda v: v["symbol"].update(extra=1),
            lambda v: v["result"].update(trade_count=True),
            lambda v: v["result"].update(closed_count="0"),
            lambda v: v["result"].update(realized_pnl=math.nan),
            lambda v: v["result"].update(weighted_buy_price=math.inf),
            lambda v: v["period"].update(first_trade_date="2026-02-30"),
            lambda v: v["result"].update(sell_fill_count=1),
        )
        for change in changes:
            with self.subTest(change=change):
                raw = objective()
                change(raw)
                self.assert_rejected(source.admit_objective_source, raw)

    def test_chart_compact_candle_buy_sell_tooltip_and_observation_pass(self):
        dto = source.admit_chart_source(chart())
        self.assertEqual(70400, dto.candles[0].c)
        self.assertEqual("매수", dto.trade_markers[0].tooltip.label)
        self.assertIsNone(dto.trade_markers[1].tooltip.profit_amount)
        self.assertIsNone(dto.trade_markers[1].tooltip.return_rate)
        self.assertEqual(0.5, dto.rule_based_observations[0].metrics.price_vs_close_pct)

    def test_chart_unavailable_is_distinct_from_malformed(self):
        dto = source.admit_chart_source({"kind": "unavailable", "reason": "no_market_data"})
        self.assertIsInstance(dto, source.UnavailableChartSource)
        for raw in ({}, {"kind": "unavailable", "reason": "bad_shape"},
                    {"kind": "unavailable", "reason": "no_market_data", "candles": []}):
            self.assert_rejected(source.admit_chart_source, raw)

    def test_chart_candles_wrong_container_or_malformed_item_reject(self):
        for candles in ("", {}, None, [None]):
            with self.subTest(candles=candles):
                raw = chart()
                raw["candles"] = candles
                self.assert_rejected(source.admit_chart_source, raw)

    def test_candle_missing_unknown_numeric_string_bool_nan_and_infinity_reject(self):
        changes = (lambda v: v.pop("o"), lambda v: v.update(extra=1),
                   lambda v: v.update(o="70000"), lambda v: v.update(v=True),
                   lambda v: v.update(c=math.nan), lambda v: v.update(ma5=math.inf))
        for change in changes:
            raw = chart()
            change(raw["candles"][0])
            self.assert_rejected(source.admit_chart_source, raw)

    def test_candle_ohlc_volume_and_label_relationship_reject(self):
        for key, value in (("h", 69999), ("l", 70500), ("v", -1),
                           ("t", "2026-07-11"), ("time", "2026-02-30")):
            raw = chart()
            raw["candles"][0][key] = value
            self.assert_rejected(source.admit_chart_source, raw)

    def test_intraday_candle_and_marker_time_pass(self):
        raw = chart()
        raw.update(timeframe="intraday", interval="1m")
        raw["candles"][0].update(time=1783659600, t="2026-07-10 09:00")
        for item in raw["trade_markers"]:
            item["time"] = 1783659600
        self.assertEqual(1783659600, source.admit_chart_source(raw).candles[0].time)

    def test_timeframe_interval_pair_and_period_reject(self):
        for key, value in (("interval", "3m"), ("timeframe", "monthly"),
                           ("period", "2026-02-30"), ("period", None)):
            raw = chart()
            raw[key] = value
            self.assert_rejected(source.admit_chart_source, raw)

    def test_marker_buy_sell_text_and_label_consistency(self):
        raw = chart()
        raw["trade_markers"][0]["text"] = "B"
        raw["trade_markers"][1]["text"] = "S"
        self.assertEqual("S", source.admit_chart_source(raw).trade_markers[1].text)
        for change in (lambda v: v.update(text="S"),
                       lambda v: v["tooltip"].update(label="매도"),
                       lambda v: v.update(side="hold")):
            invalid = chart()
            change(invalid["trade_markers"][0])
            self.assert_rejected(source.admit_chart_source, invalid)

    def test_marker_count_bool_numeric_string_and_nested_unknown_reject(self):
        for key, value in (("count", True), ("count", "1"), ("avg_price", math.nan),
                           ("prices", ""), ("prices", ["70000"]), ("extra", 1)):
            raw = chart()
            raw["trade_markers"][0]["tooltip"][key] = value
            self.assert_rejected(source.admit_chart_source, raw)

    def test_sell_nullable_result_is_preserved_and_required(self):
        raw = chart()
        self.assertIsNone(source.admit_chart_source(raw).trade_markers[1].tooltip.profit_amount)
        raw["trade_markers"][1]["tooltip"].pop("profit_amount")
        self.assert_rejected(source.admit_chart_source, raw)

    def test_technical_metrics_subset_missing_unknown_and_nonfinite_reject(self):
        for change in (lambda v: v.pop("ma20"), lambda v: v.update(other=1),
                       lambda v: v.update(after_5_bars=math.inf)):
            raw = chart()
            change(raw["rule_based_observations"][0]["metrics"])
            self.assert_rejected(source.admit_chart_source, raw)
        raw = chart()
        raw["rule_based_observations"][0]["metrics"] = {}
        self.assert_rejected(source.admit_chart_source, raw)

    def test_observation_unavailable_variant_and_numeric_title_detail(self):
        raw = chart()
        raw["rule_based_observations"] = [{"title": "데이터 없음", "detail": "지표 없음"}]
        self.assertIsInstance(source.admit_chart_source(raw).rule_based_observations[0],
                              source.UnavailableObservationSource)
        for key in ("title", "detail"):
            invalid = chart()
            invalid["rule_based_observations"][0][key] = 123
            self.assert_rejected(source.admit_chart_source, invalid)

    def test_analysis_context_ready_and_error_variants_pass(self):
        normal = {"trade_id": 1, "date": "2026-07-10T09:30", "market_date": "2026-07-10",
                  "ticker": "005930", "name": "삼성전자", "side": "buy", "price": 70000,
                  "quantity": 2, "memo": "기록", "close": 70400,
                  "price_vs_close_pct": -0.5, "ma5": None, "ma20": None, "ma60": None,
                  "rsi14": None, "volume_ratio_20d": None, "return_10d_before": None,
                  "position_in_20d_range": None, "next_5d_return": None,
                  "next_20d_return": None}
        self.assertEqual(70400, source.admit_analysis_context_source(normal).close)
        error = {"error": "매매일 이전 차트 데이터가 없습니다.", "trade": trade()}
        self.assertIsInstance(source.admit_analysis_context_source(error),
                              source.AnalysisContextErrorSource)

    def test_analysis_context_missing_unknown_bad_metric_and_bad_error_reject(self):
        raw = {"error": "매매일 이전 차트 데이터가 없습니다.", "trade": trade()}
        for change in (lambda v: v.update(extra=1),
                       lambda v: v.update(error="unknown"),
                       lambda v: v["trade"].update(price=True)):
            invalid = copy.deepcopy(raw)
            change(invalid)
            self.assert_rejected(source.admit_analysis_context_source, invalid)

    def test_basic_semantic_existing_trim_length_and_label_mapping_pass(self):
        raw = basic_semantic()
        raw["main_issue"] = "  사전 기준  "
        raw["good_points"][0]["title"] = "t" * 170
        raw["decision_quality"]["label"] = "알 수 없는 등급"
        dto = source.admit_semantic_source(raw, "basic")
        self.assertEqual("사전 기준", dto.main_issue)
        self.assertEqual(160, len(dto.good_points[0].title))
        self.assertEqual("판단 보류", dto.decision_quality.label)

    def test_advanced_semantic_exact_source_passes(self):
        dto = source.admit_semantic_source(advanced_semantic(), "advanced")
        self.assertEqual("근거 일부", dto.entry_review.assessment.label)
        self.assertEqual(("진입 근거 기록",), dto.next_trade_playbook.before_entry)

    def test_semantic_numeric_title_detail_unknown_and_missing_reject(self):
        changes = (lambda v: v["good_points"][0].update(title=123),
                   lambda v: v["good_points"][0].update(detail=123),
                   lambda v: v["lesson"].update(concept=True),
                   lambda v: v["main_improvement"].update(extra="x"),
                   lambda v: v.pop("next_action"),
                   lambda v: v.update(objective={"trade_count": 999}))
        for change in changes:
            invalid = basic_semantic()
            change(invalid)
            self.assert_rejected(source.admit_semantic_source, invalid, review_type="basic")

    def test_semantic_full_list_shape_checked_before_truncation(self):
        raw = basic_semantic()
        raw["good_points"].extend([
            {"title": "두 번째", "detail": "정상"},
            {"title": 7, "detail": "잘리기 전 검증되어야 함"},
        ])
        self.assert_rejected(source.admit_semantic_source, raw, review_type="basic")
        raw["good_points"][2]["title"] = "세 번째"
        self.assertEqual(2, len(source.admit_semantic_source(raw, "basic").good_points))
        raw["good_points"][2]["detail"] = "  "
        self.assert_rejected(source.admit_semantic_source, raw, review_type="basic")
        raw = basic_semantic()
        raw["next_trade_checks"].extend([
            {"phase": "while_holding", "text": "두 번째"},
            {"phase": "before_exit", "text": "세 번째"},
            {"phase": "unknown", "text": "잘리기 전 검증"},
        ])
        self.assert_rejected(source.admit_semantic_source, raw, review_type="basic")

    def test_semantic_malformed_array_does_not_become_empty(self):
        for value in ("", {}, None, [None]):
            raw = basic_semantic()
            raw["good_points"] = value
            self.assert_rejected(source.admit_semantic_source, raw, review_type="basic")

    def test_review_source_full_episode_and_nested_tuple_ownership(self):
        raw = review_source()
        dto = source.admit_review_source(raw)
        raw["trades"][0]["name"] = "변경"
        raw["charts"][0]["candles"][0]["c"] = 1
        raw["charts"][0]["trade_markers"][0]["tooltip"]["prices"].append(1)
        raw["semantic"]["good_points"][0]["title"] = "변경"
        raw["objective"]["result"]["trade_count"] = 999
        self.assertEqual("삼성전자", dto.trades[0].name)
        self.assertEqual(70400, dto.charts[0].candles[0].c)
        self.assertEqual((70000,), dto.charts[0].trade_markers[0].tooltip.prices)
        self.assertEqual("체결 확인", dto.semantic.good_points[0].title)
        self.assertEqual(1, dto.objective.result.trade_count)
        self.assertIsInstance(dto.trades, tuple)
        with self.assertRaises(FrozenInstanceError):
            dto.trades[0].price = 1
        with self.assertRaises(TypeError):
            source.ValidatedReviewSource()

    def test_review_source_top_and_late_trade_shape_reject(self):
        for change in (lambda v: v.update(extra=1), lambda v: v.pop("notice"),
                       lambda v: v.update(has_market_data=1),
                       lambda v: v["charts"][0]["candles"].append(None),
                       lambda v: v["trades"].append({**trade(), "price": True})):
            invalid = review_source()
            change(invalid)
            self.assert_rejected(source.admit_review_source, invalid)

    def test_empty_episode_uses_explicit_objective_variant(self):
        raw = review_source()
        raw.update(status="empty", origin="none", trades=[],
                   objective={"kind": "unavailable", "reason": "no_trades"},
                   charts=[{"kind": "unavailable", "reason": "no_market_data"}],
                   semantic=None, has_market_data=False)
        dto = source.admit_review_source(raw)
        self.assertIsInstance(dto.objective, source.UnavailableObjectiveSource)
        raw["objective"] = {}
        self.assert_rejected(source.admit_review_source, raw)
