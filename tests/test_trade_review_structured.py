from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.history_legacy_fixture import add_legacy_history_fixture

from tests.review_source_fixtures import compact_chart_fixture, fallback_model_fixture, review_input_fixture, history_chart_fixture

from tests.api_test_modules import _import_state, api_module_state

import copy
import importlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


class TradeReviewStructuredTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai_review_v2 = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai_review_v2.__dict__))
        importlib.reload(self.ai_review_v2)
        self.schema = importlib.import_module("core.trade_review_schema")
        self.display_contract = importlib.import_module("core.review_display_contract")
        self.compatibility = importlib.import_module("core.review_legacy_compatibility")
        self.real_compact_chart_snapshot = self.ai_review_v2._compact_chart_snapshot
        self.trades = [
            {
                "id": 1,
                "trade_date": "2026-07-10T09:30",
                "ticker": "005930",
                "name": "삼성전자",
                "side": "buy",
                "price": 70000,
                "quantity": 10,
                "fee": 105,
                "tax": 0,
                "memo": "거래량 증가를 보고 진입",
             'source': 'manual'},
            {
                "id": 2,
                "trade_date": "2026-07-10T10:00",
                "ticker": "005930",
                "name": "삼성전자",
                "side": "sell",
                "price": 70900,
                "quantity": 10,
                "fee": 106,
                "tax": 0,
                "memo": "수익 확정으로 매도",
             'source': 'manual'},
        ]
        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: compact_chart_fixture({
            "candles": [{"time": "2026-07-10", "close": 70400}],
            "rule_based_observations": [],
        })))

    def _model_output(self, review_type):
        output = {
            "decision_quality": {
                "label": "보통 이상",
                "explanation": "체결 결과와 당시 확인 가능한 근거를 분리해 평가합니다.",
            },
            "main_issue": "사전 기준과 실제 행동의 연결을 더 분명히 남길 필요가 있습니다.",
            "next_action": "다음 주문 전에 핵심 판단 기준을 한 문장으로 기록합니다.",
        }
        if review_type == "basic":
            output.update({
                "good_points": [
                    {"title": "수익을 확정함", "detail": "매수 평균보다 높은 가격에 매도했습니다."},
                    {"title": "체결을 확인함", "detail": "매수·매도 체결을 같은 거래로 비교할 수 있습니다."},
                ],
                "main_improvement": {
                    "title": "사전 매도 기준",
                    "detail": "매도 후 상승보다 주문 전에 정한 수익 확정·추세 종료 기준을 먼저 확인합니다.",
                },
                "next_trade_checks": [
                    {"phase": "before_entry", "text": "진입 이유와 무효화 기준을 기록합니다."},
                    {"phase": "while_holding", "text": "처음 가설과 실제 흐름을 비교합니다."},
                    {"phase": "before_exit", "text": "수익 확정과 추세 종료를 구분합니다."},
                ],
                "lesson": {
                    "title": "좋은 매도는 최고가 매도가 아닙니다",
                    "concept": "사후 가격과 당시 판단 품질은 분리해 평가합니다.",
                    "applied_to_this_trade": "이번 거래의 핵심은 사전 매도 기준을 기록했는지입니다.",
                },
            })
        else:
            output.update({
                "entry_review": {
                    "evidence": ["매수 가격과 체결 시각을 확인합니다."],
                    "uncertainty": ["실제 매수 이유 기록은 제한적입니다."],
                    "invalidation": "기록 없음",
                    "assessment": {"label": "근거 일부", "explanation": "확인 가능한 근거만 평가합니다."},
                },
                "risk_review": {
                    "planned_rule": "기록 없음",
                    "actual_response": "실제 매도 대응과 사전 기준을 비교합니다.",
                    "assessment": {"label": "근거 부족", "explanation": "사전 위험 기준 기록이 부족합니다."},
                },
                "exit_review": {
                    "profit_taking_assessment": "합리적일 가능성",
                    "trend_exit_assessment": "추가 확인 필요",
                    "explanation": "매도 후 가격 상승만으로 매도 실패라고 판단하지 않습니다.",
                },
                "detailed_analysis": [{"title": "체결 흐름", "detail": "체결 전후의 확인 가능한 흐름입니다."}],
                "next_trade_playbook": {
                    "before_entry": ["진입 근거를 한 가지 기록합니다."],
                    "while_holding": ["가설과 실제 흐름을 점검합니다."],
                    "before_exit": ["매도 관점을 나눠 기록합니다."],
                },
                "lesson": {
                    "title": "사전 기준과 사후 결과를 분리하기",
                    "concept": "판단의 질은 당시 알 수 있었던 정보와 기준으로 평가합니다.",
                    "applied_to_this_trade": "이번 거래의 사전 기준 존재 여부를 확인합니다.",
                    "next_trade_application": "다음 주문 전에 진입·위험·매도 기준을 기록합니다.",
                },
                "reflection_questions": ["매수 직전 어떤 조건이 깨지면 판단이 틀렸다고 보려 했나요?"],
            })
        return json.dumps(output, ensure_ascii=False)

    def _review_from_output(self, review_type, output, *, approval_state=None):
        raw_output = json.dumps(output, ensure_ascii=False)
        with patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: raw_output):
            builder = (self.ai_review_v2.build_advanced_ai_review if review_type == "advanced"
                       else self.ai_review_v2.build_basic_ai_review)
            return builder(self.trades, approval_state=approval_state)

    def _assert_final_text_safe(self, result):
        structured = result["structured_review"]
        leaves = self.ai_review_v2._model_text_leaves(structured)
        compiled, covered = self.display_contract.compile_structured_review(structured)
        self.assertEqual({path for path, _value in leaves}, covered)
        # Semantic coverage is checked before display selection. Fallback has
        # its own canonical legacy template, approved by the same finalizer.
        if result["status"] == "ready" or result["source"] == "none":
            self.assertEqual(compiled, result["display_snapshot"])
        self.assertEqual(self.compatibility.admit_legacy_body(result["display_snapshot"]).summary, result["summary"])
        for text in [*(value for _path, value in leaves), result["summary"]]:
            self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(text), text)

    def test_strict_model_decoder_rejects_duplicate_keys_in_every_object(self):
        cases = (
            '{"arbitrary": 1, "arbitrary": 2}',
            '{"outer": {"arbitrary": null, "arbitrary": false}}',
            '{"items": [{"arbitrary": [], "arbitrary": {}}]}',
            '{"outer": [{"deeper": [{"arbitrary": 1, "arbitrary": 1}]}]}',
            r'{"key": 1, "\u006bey": 2}',
            r'{"outer": {"\u006bey": 1, "key": 2}}',
            r'{"items": [{"\u006bey": 1, "\u006b\u0065\u0079": 2}]}',
            r'{"\ud83d\ude00": 1, "😀": 2}',
            '```json\n{"arbitrary": 1, "arbitrary": 2}\n```',
        )
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.ai_review_v2._decode_structured_model_output(raw)

    def test_strict_model_decoder_preserves_unique_keys_and_normal_json(self):
        siblings = {"left": {"key": 1}, "items": [{"key": 2}, {"key": 3}],
                    "text": '{"key": 1, "key": 2}'}
        cases = [siblings, *(json.loads(self._model_output(kind)) for kind in ("basic", "advanced"))]
        for value in cases:
            for escaped in (False, True):
                raw = json.dumps(value, ensure_ascii=escaped)
                for encoded in (raw, f"```json\n{raw}\n```"):
                    with self.subTest(escaped=escaped, encoded=encoded):
                        self.assertEqual(value, self.ai_review_v2._decode_structured_model_output(encoded))
        for raw in ('[]', '"text"'):
            with self.subTest(raw=raw):
                self.assertIsNone(self.ai_review_v2._decode_structured_model_output(raw))

    def test_model_decoder_integer_digit_boundary_and_duplicate_order(self):
        self.addCleanup(sys.set_int_max_str_digits, sys.get_int_max_str_digits())
        sys.set_int_max_str_digits(4300)
        for digits in (4300, 4301):
            number = "9" * digits
            cases = {
                "unique": '{"number": ' + number + '}',
                "number-first": '{"key": ' + number + ', "key": "safe"}',
                "number-second": '{"key": "safe", "key": ' + number + '}',
                "duplicate-before-number": '{"key": 1, "key": 2, "number": ' + number + '}',
                "duplicate-after-number": '{"number": ' + number + ', "key": 1, "key": 2}',
            }
            for case, raw in cases.items():
                with self.subTest(digits=digits, case=case):
                    if digits == 4300 and case == "unique":
                        decoded = self.ai_review_v2._decode_structured_model_output(raw)
                        self.assertEqual(10 ** 4300 - 1, decoded["number"])
                    else:
                        with self.assertRaises(ValueError):
                            self.ai_review_v2._decode_structured_model_output(raw)

    def test_model_decoder_wraps_only_json_parsing_and_conversion_errors(self):
        errors = (json.JSONDecodeError("synthetic", "{", 1), ValueError("synthetic int limit"),
                  TypeError("synthetic type"), RecursionError("synthetic depth"), OverflowError("synthetic conversion"))
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(
                    self.ai_review_v2.json, "loads", side_effect=error):
                with self.assertRaises(ValueError) as raised:
                    self.ai_review_v2._decode_structured_model_output('{"key": "safe"}')
                self.assertEqual("_StructuredModelDecodeError", type(raised.exception).__name__)
                self.assertIs(error, raised.exception.__cause__)

    def test_both_builders_return_the_exact_common_finalizer_snapshot(self):
        original = self.ai_review_v2._finalize_ai_review
        finalized = []

        def track(*args, **kwargs):
            result = original(*args, **kwargs)
            finalized.append(result)
            return result

        with patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: self._model_output(payload["review_type"])), patch.object(
            self.ai_review_v2, "_finalize_ai_review", track,
        ):
            basic = self.ai_review_v2.build_basic_ai_review(self.trades)
            advanced = self.ai_review_v2.build_advanced_ai_review(self.trades)

        self.assertIs(basic, finalized[0])
        self.assertIs(advanced, finalized[1])
        self.assertEqual(["ready", "ready"], [basic["status"], advanced["status"]])
        self._assert_final_text_safe(basic)
        self._assert_final_text_safe(advanced)

    def test_current_schema_text_paths_are_all_in_final_leaf_and_display_checks(self):
        def schema_paths(spec, path):
            if spec["type"] == "string":
                return {path}
            if spec["type"] == "array":
                return schema_paths(spec["items"], path + ("*",))
            return set().union(*(schema_paths(child, path + (key,))
                                 for key, child in spec["properties"].items()))

        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                result = self._review_from_output(review_type, json.loads(self._model_output(review_type)))
                self.assertEqual("ready", result["status"])
                structured = result["structured_review"]
                actual = {tuple("*" if isinstance(part, int) else part for part in path)
                          for path, _value in self.ai_review_v2._model_text_leaves(structured)}
                expected = set()
                for key, child in self.schema.structured_output_schema(review_type)["properties"].items():
                    owner = "summary" if key in {"decision_quality", "main_issue", "next_action"} else review_type
                    expected.update(schema_paths(child, (owner, key)))
                self.assertEqual(expected, actual)
                compiled, covered = self.display_contract.compile_structured_review(structured)
                self.assertEqual(actual, {tuple("*" if isinstance(part, int) else part for part in path)
                                          for path in covered})
                self.assertEqual(result["summary"], compiled["canonical_text"])
                self._assert_final_text_safe(result)

    def test_basic_and_advanced_keep_objective_numbers_outside_model_semantics(self):
        def fake_call(payload, *, model, instructions):
            return self._model_output(payload["review_type"])

        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        from core.journal import build_review

        expected = build_review(self.trades)["summary"]
        basic = self.ai_review_v2.build_basic_ai_review(self.trades)
        advanced = self.ai_review_v2.build_advanced_ai_review(self.trades)

        for result, review_type in ((basic, "basic"), (advanced, "advanced")):
            structured = result["structured_review"]
            self.assertEqual("trade-review.v1", structured["schema_version"])
            self.assertEqual(review_type, structured["review_type"])
            self.assertEqual(float(expected["realized_pnl"]), structured["objective"]["result"]["realized_pnl"])
            self.assertNotIn("objective", structured[review_type])
            self.assertIn("decision_quality", structured["summary"])
            self.assertIn("data_confidence", structured["summary"])

        self.assertLessEqual(len(basic["structured_review"]["basic"]["good_points"]), 2)
        self.assertIn("entry_review", advanced["structured_review"]["advanced"])
        self.assertIn("next_trade_playbook", advanced["structured_review"]["advanced"])

    def test_malformed_model_output_is_terminal_without_fallback(self):
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: "not-json"))

        approval = {"snapshot": "old"}
        with patch.object(self.ai_review_v2, "seal_review_envelope", wraps=self.ai_review_v2.seal_review_envelope) as seal:
            result = self.ai_review_v2.build_basic_ai_review(self.trades, approval_state=approval)

        self.assertEqual("error", result["status"])
        self.assertEqual("invalid_structured_output", result["internal_status"])
        self.assertEqual(("none", "", None, 0), (result["source"], result["summary"], approval["snapshot"], seal.call_count))
        self.assertNotIn("structured_review", result)
        self.assertNotIn("display_snapshot", result)

    def test_large_trade_chart_gap_is_low_confidence_and_explicit(self):
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: compact_chart_fixture({
            "candles": [{"time": "2026-07-10", "close": 59000}],
            "rule_based_observations": [
                {
                    "title": "매수 시점",
                    "detail": "체결가와 차트 기준 가격을 비교해야 합니다.",
                    "metrics": {"price_vs_close_pct": 18.5},
                },
            ],
        })))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: self._model_output("advanced")))

        result = self.ai_review_v2.build_advanced_ai_review(self.trades)
        summary = result["structured_review"]["summary"]

        self.assertEqual("low", summary["data_confidence"]["level"])
        self.assertTrue(any("18.50%" in reason for reason in summary["data_confidence"]["reasons"]))
        self.assertEqual("판단 보류", summary["decision_quality"]["label"])

    def test_responses_request_contains_strict_json_schema_format(self):
        captured = {}
        os.environ["OPENAI_API_KEY"] = "sk-test"

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return Response(json.dumps({"output_text": "{}"}).encode("utf-8"))

        self.enterContext(patch.object(self.ai_review_v2.urllib.request, "urlopen", fake_urlopen))
        self.ai_review_v2._call_openai_review(
            {
                "review_type": "basic",
                "output_contract": {
                    "response_format": self.schema.structured_output_format("basic"),
                },
            },
            model="gpt-test",
            instructions="test",
        )

        response_format = captured["body"]["text"]["format"]
        self.assertEqual("json_schema", response_format["type"])
        self.assertTrue(response_format["strict"])
        self.assertEqual("trade_review_basic", response_format["name"])
        self.assertFalse(response_format["schema"]["additionalProperties"])

    def test_semantic_normalizer_rejects_missing_required_fields(self):
        valid = json.loads(self._model_output("basic"))
        invalid = copy.deepcopy(valid)
        invalid.pop("lesson")

        self.assertIsNone(self.schema.normalize_semantic_output(invalid, "basic"))
        self.assertIsNotNone(self.schema.normalize_semantic_output(valid, "basic"))
        valid["decision_quality"]["label"] = "허용되지 않은 판단"
        valid["main_issue"] = "x" * (self.schema.MAX_REVIEW_TEXT_CHARS + 1)
        normalized = self.schema.normalize_semantic_output(valid, "basic")
        self.assertEqual("판단 보류", normalized["decision_quality"]["label"])
        self.assertEqual(self.schema.MAX_REVIEW_TEXT_CHARS, len(normalized["main_issue"]))

    def test_required_content_arrays_reject_empty_but_optional_advanced_arrays_remain_valid(self):
        basic = json.loads(self._model_output("basic"))
        empty_good_points = copy.deepcopy(basic)
        empty_good_points["good_points"] = []
        empty_checks = copy.deepcopy(basic)
        empty_checks["next_trade_checks"] = []

        self.assertIsNone(self.schema.normalize_semantic_output(empty_good_points, "basic"))
        self.assertIsNone(self.schema.normalize_semantic_output(empty_checks, "basic"))
        self.assertEqual(1, self.schema.structured_output_schema("basic")["properties"]["good_points"]["minItems"])
        self.assertEqual(1, self.schema.structured_output_schema("basic")["properties"]["next_trade_checks"]["minItems"])

        advanced = json.loads(self._model_output("advanced"))
        advanced["entry_review"]["uncertainty"] = []
        advanced["detailed_analysis"] = []
        advanced["reflection_questions"] = []
        self.assertIsNotNone(self.schema.normalize_semantic_output(advanced, "advanced"))

        empty_evidence = copy.deepcopy(advanced)
        empty_evidence["entry_review"]["evidence"] = []
        self.assertIsNone(self.schema.normalize_semantic_output(empty_evidence, "advanced"))
        empty_playbook = copy.deepcopy(advanced)
        empty_playbook["next_trade_playbook"]["before_entry"] = []
        self.assertIsNone(self.schema.normalize_semantic_output(empty_playbook, "advanced"))
        advanced_schema = self.schema.structured_output_schema("advanced")["properties"]
        self.assertEqual(1, advanced_schema["entry_review"]["properties"]["evidence"]["minItems"])
        self.assertEqual(1, advanced_schema["next_trade_playbook"]["properties"]["before_entry"]["minItems"])
        self.assertNotIn("minItems", advanced_schema["entry_review"]["properties"]["uncertainty"])
        self.assertNotIn("minItems", advanced_schema["reflection_questions"])

    def test_empty_required_arrays_use_deterministic_structured_fallback(self):
        for review_type, field_path in (("basic", ("good_points",)), ("basic", ("next_trade_checks",)), ("advanced", ("entry_review", "evidence"))):
            invalid = json.loads(self._model_output(review_type))
            target = invalid
            for key in field_path[:-1]:
                target = target[key]
            target[field_path[-1]] = []
            with patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: json.dumps(invalid, ensure_ascii=False)):
                result = (
                    self.ai_review_v2.build_basic_ai_review(self.trades)
                    if review_type == "basic"
                    else self.ai_review_v2.build_advanced_ai_review(self.trades)
                )

            self.assertEqual("error", result["status"])
            self.assertEqual("invalid_structured_output", result["internal_status"])
            self.assertEqual("chart-rules", result["source"])
            fallback_body = result["structured_review"][review_type]
            target = fallback_body
            for key in field_path[:-1]:
                target = target[key]
            self.assertTrue(target[field_path[-1]])

    def test_basic_legacy_summary_uses_basic_fields_and_advanced_summary_regresses(self):
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: self._model_output(payload["review_type"])))

        basic = self.ai_review_v2.build_basic_ai_review(self.trades)
        advanced = self.ai_review_v2.build_advanced_ai_review(self.trades)

        self.assertIn("매수 평균보다 높은 가격에 매도했습니다.", basic["summary"])
        self.assertIn("주문 전에 정한 수익 확정·추세 종료 기준을 먼저 확인합니다.", basic["summary"])
        self.assertIn("진입 가설 검토: 확인 가능한 근거만 평가합니다.", advanced["summary"])
        self.assertIn("상세 분석: 체결 흐름: 체결 전후의 확인 가능한 흐름입니다.", advanced["summary"])
        self.assertIn("진입 전: 진입 근거를 한 가지 기록합니다.", advanced["summary"])
        self.assertIn("보유 중: 가설과 실제 흐름을 점검합니다.", advanced["summary"])
        self.assertIn("매도 전: 매도 관점을 나눠 기록합니다.", advanced["summary"])
        self.assertIn("이번에 배울 점: 사전 기준과 사후 결과를 분리하기", advanced["summary"])
        self.assertIn("다음 거래 적용: 다음 주문 전에 진입·위험·매도 기준을 기록합니다.", advanced["summary"])
        self.assertIn("다음 복기 질문: 매수 직전 어떤 조건이 깨지면 판단이 틀렸다고 보려 했나요?", advanced["summary"])

    def _assert_unsafe_model_output_falls_back(self, raw_output, unsafe_text):
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: raw_output))
        result = self.ai_review_v2.build_basic_ai_review(self.trades)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertEqual("chart-rules", result["source"])
        self.assertEqual(result["display_snapshot"]["canonical_text"], result["summary"])
        self.assertNotIn(unsafe_text, result["summary"])
        self.assertNotIn(unsafe_text, json.dumps(result["structured_review"], ensure_ascii=False))

    def test_plain_prohibited_structured_text_still_falls_back(self):
        unsafe_text = "현재는 매수 추천합니다."
        output = json.loads(self._model_output("basic"))
        output["main_issue"] = unsafe_text
        self._assert_unsafe_model_output_falls_back(json.dumps(output, ensure_ascii=False), unsafe_text)

    def test_unicode_escaped_prohibited_structured_text_falls_back(self):
        unsafe_text = "현재는 매수 추천합니다."
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = unsafe_text
        raw_output = json.dumps(output, ensure_ascii=True)
        self.assertNotIn(unsafe_text, raw_output)
        self._assert_unsafe_model_output_falls_back(raw_output, unsafe_text)

    def test_mixed_escaped_prohibited_structured_text_falls_back(self):
        unsafe_text = "현재는 매수 추천합니다."
        output = json.loads(self._model_output("basic"))
        output["next_trade_checks"][0]["text"] = unsafe_text
        raw_output = json.dumps(output, ensure_ascii=False).replace("매수 추천합니다.", r"매\uC218 추천합니다.")
        self.assertNotIn(unsafe_text, raw_output)
        self._assert_unsafe_model_output_falls_back(raw_output, unsafe_text)

    def test_safe_decoded_structured_text_remains_accepted(self):
        raw_output = json.dumps(json.loads(self._model_output("basic")), ensure_ascii=True)
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: raw_output))

        result = self.ai_review_v2.build_basic_ai_review(self.trades)

        self.assertEqual("ready", result["status"])
        self.assertEqual("openai", result["source"])
        self.assertIn("확인된 강점:", result["summary"])

    def test_split_fields_become_unsafe_only_after_legacy_summary_composition(self):
        output = json.loads(self._model_output("advanced"))
        output["detailed_analysis"] = [{"title": "목표가", "detail": "80,000원입니다."}]
        raw_output = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw_output))
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance("목표가"))
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance("80,000원입니다."))
        semantic, rule_ids, rejected = self.ai_review_v2._prepare_structured_model_output(
            raw_output, payload={"review_type": "advanced"}, model="test-model",
        )
        self.assertIsNotNone(semantic)
        self.assertEqual([], rule_ids)
        self.assertFalse(rejected)
        composed = self.display_contract.compile_structured_review(
            self.ai_review_v2._normalized_semantic_review(semantic, "advanced"))[0]["canonical_text"]
        self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(composed))

        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: raw_output))
        result = self.ai_review_v2.build_advanced_ai_review(self.trades)

        self.assertEqual("error", result["status"])
        self.assertEqual("chart-rules", result["source"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertEqual(result["display_snapshot"]["canonical_text"], result["summary"])
        self.assertNotIn("목표가: 80,000원입니다.", result["summary"])
        self.assertNotIn("목표가: 80,000원입니다.", json.dumps(result["structured_review"], ensure_ascii=False))
        self.assertNotEqual(output["detailed_analysis"], result["structured_review"]["advanced"]["detailed_analysis"])

    def test_safe_split_title_and_detail_remain_visible_in_legacy_summary(self):
        output = json.loads(self._model_output("advanced"))
        output["detailed_analysis"] = [{"title": "체결가", "detail": "80,000원에서 체결됐습니다."}]
        raw_output = json.dumps(output, ensure_ascii=False)
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: raw_output))

        result = self.ai_review_v2.build_advanced_ai_review(self.trades)

        self.assertEqual("ready", result["status"])
        self.assertEqual("openai", result["source"])
        self.assertIn("상세 분석: 체결가: 80,000원에서 체결됐습니다.", result["summary"])

    def test_basic_good_point_split_fields_reject_and_discard_all_model_text(self):
        output = json.loads(self._model_output("basic"))
        output["good_points"][0] = {"title": "목표가", "detail": "80,000원입니다."}
        output["lesson"]["concept"] = "UNIQUE_SAFE_MODEL_MARKER_741"
        raw_output = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw_output))

        result = self._review_from_output("basic", output)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertEqual("chart-rules", result["source"])
        self.assertNotIn("UNIQUE_SAFE_MODEL_MARKER_741", json.dumps(result, ensure_ascii=False))
        self._assert_final_text_safe(result)

    def test_basic_main_improvement_split_fields_reject(self):
        output = json.loads(self._model_output("basic"))
        output["main_improvement"] = {"title": "목표가", "detail": "80,000원입니다."}
        result = self._review_from_output("basic", output)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self._assert_final_text_safe(result)

    def test_list_items_split_into_prohibited_display_text_reject(self):
        output = json.loads(self._model_output("advanced"))
        output["next_trade_playbook"]["before_entry"] = ["현재는 매수", "추천합니다."]
        raw_output = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw_output))
        semantic, rule_ids, rejected = self.ai_review_v2._prepare_structured_model_output(
            raw_output, payload={"review_type": "advanced"}, model="test-model",
        )
        self.assertIsNotNone(semantic)
        self.assertEqual([], rule_ids)
        self.assertFalse(rejected)

        result = self._review_from_output("advanced", output)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self._assert_final_text_safe(result)

    def test_normalization_900_character_suffix_rejects_after_truncation(self):
        output = json.loads(self._model_output("basic"))
        suffix = "목표가: 80,000원"
        output["lesson"]["concept"] = "A" * (900 - len(suffix)) + suffix + "이라는 표현을 과거 기록에서 확인했습니다."
        raw_output = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw_output))
        normalized = self.schema.normalize_semantic_output(output, "basic")
        self.assertEqual(900, len(normalized["lesson"]["concept"]))
        self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(normalized["lesson"]["concept"]))

        result = self._review_from_output("basic", output)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self._assert_final_text_safe(result)

    def test_normalization_160_character_card_title_rejects_after_truncation(self):
        output = json.loads(self._model_output("basic"))
        suffix = "목표가: 80,000원"
        output["good_points"][0]["title"] = "A" * (160 - len(suffix)) + suffix + "이라는 과거 표현"
        raw_output = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw_output))
        normalized = self.schema.normalize_semantic_output(output, "basic")
        self.assertEqual(160, len(normalized["good_points"][0]["title"]))
        self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(normalized["good_points"][0]["title"]))

        result = self._review_from_output("basic", output)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self._assert_final_text_safe(result)

    def test_40_character_label_normalization_preserves_safe_result(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                output = json.loads(self._model_output(review_type))
                output["decision_quality"]["label"] = "X" * 40 + "Y"
                result = self._review_from_output(review_type, output)

                self.assertEqual("ready", result["status"])
                self.assertEqual("판단 보류", result["structured_review"]["summary"]["decision_quality"]["label"])
                self._assert_final_text_safe(result)

    def test_nested_list_middle_and_last_unsafe_values_reject(self):
        for position in (1, 2):
            with self.subTest(position=position):
                output = json.loads(self._model_output("advanced"))
                output["entry_review"]["evidence"] = ["과거 체결 확인", "추가 기록 확인", "당시 흐름 확인"]
                output["entry_review"]["evidence"][position] = "현재는 매수 추천합니다."
                result = self._review_from_output("advanced", output)

                self.assertEqual("error", result["status"])
                self.assertEqual("safety_rejected", result["internal_status"])
                self._assert_final_text_safe(result)

    def test_final_structured_nested_future_field_is_checked(self):
        original = self.ai_review_v2._build_structured_review

        def inject(*args, **kwargs):
            structured = original(*args, **kwargs)
            if args[0].status == "ready":
                structured["advanced"]["future_notes"] = {"items": ["현재는 매수 추천합니다."]}
            return structured

        with patch.object(self.ai_review_v2, "_build_structured_review", inject):
            result = self._review_from_output("advanced", json.loads(self._model_output("advanced")))

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self._assert_final_text_safe(result)

    def test_unsupported_or_excessive_final_tree_never_becomes_ready(self):
        original = self.ai_review_v2._build_structured_review
        for bad_value in (object(), ["safe"] * (self.ai_review_v2._FINAL_REVIEW_MAX_NODES + 1)):
            with self.subTest(value_type=type(bad_value).__name__):
                def inject(*args, **kwargs):
                    structured = original(*args, **kwargs)
                    if args[0].status == "ready":
                        structured["advanced"]["future_notes"] = bad_value
                    return structured

                with patch.object(self.ai_review_v2, "_build_structured_review", inject):
                    result = self._review_from_output("advanced", json.loads(self._model_output("advanced")))

                self.assertEqual("error", result["status"])
                self.assertEqual("invalid_structured_output", result["internal_status"])
                self._assert_final_text_safe(result)

    def test_unsafe_chart_fallback_uses_fixed_safe_result_for_both_types(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                chart = {
                    "candles": [{"time": "2026-07-10", "close": 70400}],
                    "rule_based_observations": [{
                        "trade_id": 1, "title": "매수 시점: 아쉬움" if review_type == "advanced" else "매수 시점: 좋음",
                        "detail": "현재는 매수 추천합니다.", "metrics": {},
                    }],
                }
                with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)), patch.object(
                    self.ai_review_v2, "_call_openai_review", return_value="not-json",
                ):
                    builder = (self.ai_review_v2.build_advanced_ai_review if review_type == "advanced"
                               else self.ai_review_v2.build_basic_ai_review)
                    result = builder(self.trades)

                self.assertEqual("error", result["status"])
                self.assertEqual("safety_rejected", result["internal_status"])
                self.assertIn("복기 내용을 안전하게 표시할 수 없습니다.", result["summary"])
                self.assertEqual([], result["chart_reviews"])
                self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))
                self._assert_final_text_safe(result)

    def test_unsafe_fallback_confidence_reason_uses_fixed_safe_result(self):
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})), patch.object(
            self.ai_review_v2, "_contexts_for_trades", return_value=[{"error": "현재는 매수 추천합니다."}],
        ), patch.object(self.ai_review_v2, "_call_openai_review", return_value="not-json"):
            result = self.ai_review_v2.build_basic_ai_review(self.trades)

        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertIn("복기 내용을 안전하게 표시할 수 없습니다.", result["summary"])
        self.assertEqual([], result["chart_contexts"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))
        self._assert_final_text_safe(result)

    def test_twenty_trade_episode_keeps_objective_and_prompt_aligned(self):
        trades = [dict(self.trades[0], id=index, trade_date="2026-07-10T09:30", price=100, quantity=1) for index in range(1, 21)]
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured.update(payload)
            return self._model_output("basic")

        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        result = self.ai_review_v2.build_basic_ai_review(trades, target_trade_id=20)

        self.assertEqual(20, len(captured["trade_episode"]))
        self.assertEqual(20, result["structured_review"]["objective"]["result"]["trade_count"])
        self.assertEqual(20, result["structured_review"]["objective"]["result"]["open_quantity"])

    def test_twenty_one_buys_use_full_episode_for_objective(self):
        trades = [dict(self.trades[0], id=index, trade_date="2026-07-10T09:30", price=100 + index, quantity=1) for index in range(1, 22)]
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured.update(payload)
            return self._model_output(payload["review_type"])

        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        for review_type, builder in (("basic", self.ai_review_v2.build_basic_ai_review), ("advanced", self.ai_review_v2.build_advanced_ai_review)):
            result = builder(trades, target_trade_id=21)
            objective = result["structured_review"]["objective"]["result"]
            self.assertEqual(21, objective["trade_count"])
            self.assertEqual(21, objective["buy_fill_count"])
            self.assertEqual(21, objective["open_quantity"])
            prompt_rows = captured["trade_episode" if review_type == "basic" else "recent_trades"]
            self.assertEqual(list(range(2, 22)), [row["id"] for row in prompt_rows])

    def test_twenty_first_sell_changes_full_episode_pnl_and_balance(self):
        trades = [dict(self.trades[0], id=index, trade_date="2026-07-10T09:30", price=50 if index == 1 else 100, quantity=1, fee=0) for index in range(1, 21)]
        trades.append(dict(self.trades[1], id=21, trade_date="2026-07-10T10:00", price=200, quantity=1, fee=0, tax=0))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: self._model_output(payload["review_type"])))
        from core.journal import build_review

        expected_pnl = float(build_review(trades)["summary"]["realized_pnl"])
        truncated_pnl = float(build_review(trades[-20:])["summary"]["realized_pnl"])
        self.assertEqual(102.0, expected_pnl)
        self.assertEqual(100.0, truncated_pnl)
        self.assertNotEqual(expected_pnl, truncated_pnl)
        for builder in (self.ai_review_v2.build_basic_ai_review, self.ai_review_v2.build_advanced_ai_review):
            result = builder(trades, target_trade_id=21)
            objective = result["structured_review"]["objective"]["result"]
            self.assertEqual(21, objective["trade_count"])
            self.assertEqual(19, objective["open_quantity"])
            self.assertEqual(expected_pnl, objective["realized_pnl"])

    def test_two_hundred_trade_episode_keeps_prompt_window_at_twenty(self):
        trades = [dict(self.trades[0], id=index, trade_date="2026-07-10T09:30", price=100, quantity=1) for index in range(1, 201)]
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured[payload["review_type"]] = payload
            return self._model_output(payload["review_type"])

        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        for review_type, builder in (("basic", self.ai_review_v2.build_basic_ai_review), ("advanced", self.ai_review_v2.build_advanced_ai_review)):
            result = builder(trades, target_trade_id=200)
            objective = result["structured_review"]["objective"]["result"]
            self.assertEqual(200, objective["trade_count"])
            self.assertEqual(200, objective["open_quantity"])
            prompt_rows = captured[review_type]["trade_episode" if review_type == "basic" else "recent_trades"]
            self.assertEqual(list(range(181, 201)), [row["id"] for row in prompt_rows])

    def test_advanced_malformed_response_is_terminal_without_fallback(self):
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: "not-json"))
        approval = {"snapshot": "old"}
        with patch.object(self.ai_review_v2, "seal_review_envelope", wraps=self.ai_review_v2.seal_review_envelope) as seal:
            result = self.ai_review_v2.build_advanced_ai_review(self.trades, approval_state=approval)

        self.assertEqual("error", result["status"])
        self.assertEqual("invalid_structured_output", result["internal_status"])
        self.assertEqual(("none", "", None, 0), (result["source"], result["summary"], approval["snapshot"], seal.call_count))
        self.assertNotIn("structured_review", result)
        self.assertNotIn("display_snapshot", result)

    def test_versioned_structured_review_survives_existing_history_json_storage(self):
        # storage_fixture owns this testcase's DB path and its cleanup.
        history = importlib.import_module("core.review_history")
        self.enterContext(patch.dict(history.__dict__))
        importlib.reload(history)
        structured = {
            "schema_version": "trade-review.v1",
            "review_type": "basic",
            "objective": {"result": {"realized_pnl": 29967}},
            "summary": {"data_confidence": {"level": "high"}},
            "basic": {"good_points": []},
        }

        saved = add_legacy_history_fixture(history,
            user_id="structured-user",
            review_type="basic",
            ticker="005930",
            name="삼성전자",
            ai_review={"summary": "legacy summary", "structured_review": structured},
        )
        detail = history.get_review_history(saved["id"], user_id="structured-user")

        self.assertEqual("legacy summary", detail["ai_review"]["summary"])
        self.assertEqual("trade-review.v1", detail["ai_review"]["structured_review"]["schema_version"])
        self.assertEqual(29967, detail["ai_review"]["structured_review"]["objective"]["result"]["realized_pnl"])

    def test_low_confidence_basic_checks_normalized_semantics_before_default(self):
        output = json.loads(self._model_output("basic"))
        suffix = "목표가: 80,000원"
        output["lesson"]["concept"] = "A" * (900 - len(suffix)) + suffix + "이라는 과거 기록입니다."
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            result = self._review_from_output("basic", output)
        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertNotIn(suffix, json.dumps(result, ensure_ascii=False))

    def test_low_confidence_advanced_checks_normalized_semantics_before_default(self):
        output = json.loads(self._model_output("advanced"))
        suffix = "목표가: 80,000원"
        output["lesson"]["concept"] = "A" * (900 - len(suffix)) + suffix + "이라는 과거 기록입니다."
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            result = self._review_from_output("advanced", output)
        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertNotIn(suffix, json.dumps(result, ensure_ascii=False))

    def test_safe_low_confidence_still_uses_default_semantics(self):
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            result = self._review_from_output("basic", json.loads(self._model_output("basic")))
        self.assertEqual("ready", result["status"])
        self.assertEqual("low", result["structured_review"]["summary"]["data_confidence"]["level"])
        self.assertNotIn("매수 평균보다 높은 가격", result["summary"])

    def _review_with_observations(self, observations, raw_output=None, *, approval_state=None):
        chart = {"candles": [{"time": "2026-07-10", "close": 70400}],
                 "rule_based_observations": [
                     {"trade_id": index, "title": "매수 시점", "detail": detail, "metrics": {}}
                     for index, detail in enumerate(observations, start=1)
                 ]}
        if raw_output is None:
            raw_output = self._model_output("advanced")
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)), patch.object(
            self.ai_review_v2, "_call_openai_review", return_value=raw_output,
        ):
            return self.ai_review_v2.build_advanced_ai_review(self.trades, approval_state=approval_state)

    def test_earlier_unsafe_chart_review_rejects_even_when_last_is_safe(self):
        result = self._review_with_observations(["현재는 매수 추천합니다.", "과거 체결을 확인합니다."])
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual([], result["chart_reviews"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_middle_unsafe_chart_review_rejects_whole_envelope(self):
        result = self._review_with_observations(["과거 확인", "현재는 매수 추천합니다.", "마지막 확인"])
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual([], result["chart_snapshots"])

    def test_last_unsafe_chart_review_rejects_whole_envelope(self):
        result = self._review_with_observations(["과거 확인", "현재는 매수 추천합니다."])
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual([], result["chart_reviews"])

    def test_malformed_model_and_unsafe_chart_keep_safety_rejection(self):
        result = self._review_with_observations(["현재는 매수 추천합니다.", "과거 확인"], "not-json")
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertIn("복기 내용을 안전하게 표시할 수 없습니다.", result["summary"])

    def test_safe_chart_reviews_remain_in_ready_envelope(self):
        approval = {}
        result = self._review_with_observations(
            ["과거 체결을 확인합니다.", "차트 근거가 부족합니다."], approval_state=approval)
        self.assertEqual("ready", result["status"])
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual(2, len(envelope["chart_cards"]))
        self.assertEqual([], result["chart_reviews"])

    def test_nested_chart_context_trade_text_rejects_whole_envelope(self):
        context = [{"trade": {"memo": "현재는 매수 추천합니다."}, "error": "차트 없음"}]
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})), patch.object(
            self.ai_review_v2, "_contexts_for_trades", return_value=context,
        ):
            result = self._review_from_output("basic", json.loads(self._model_output("basic")))
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual([], result["chart_contexts"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_unsupported_annotation_rejects_canonical_body(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = "목표[데이터 확인]가: 80,000원입니다."
        raw = json.dumps(output, ensure_ascii=False)
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(raw))
        result = self._review_from_output("basic", output)
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertNotIn("목표[데이터 확인]가", json.dumps(result, ensure_ascii=False))

    def test_finalized_snapshot_owns_bytes_after_source_mutation(self):
        chart = {"candles": [{"time": "2026-07-10", "close": 70400}],
                 "rule_based_observations": [{"title": "체결 관찰", "detail": "과거 체결입니다."}]}
        with api_module_state() as modules:
            history_trades = [modules.main.JournalTradeIn(**trade).model_dump() for trade in self.trades]
        state = {"candidate": {"ticker": "005930", "name": "삼성전자", "trade_date": history_trades[1]["trade_date"],
                               "target_trade_id": 2, "trade_snapshot": copy.deepcopy(history_trades[1]),
                               "recent_trades_snapshot": copy.deepcopy(history_trades),
                               "charts": history_chart_fixture(history_trades)["charts"]}}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)), patch.object(
            self.ai_review_v2, "_call_openai_review", return_value=self._model_output("basic"),
        ):
            approval = {}
            result = self.ai_review_v2.build_basic_ai_review(
                history_trades, history_state=state, approval_state=approval)
        self.assertEqual("ready", result["status"])
        expected_result = copy.deepcopy(result)
        sealed_text = approval["snapshot"].json_text
        chart["rule_based_observations"][0]["detail"] = "현재는 매수 추천합니다."
        state["candidate"]["charts"][0]["name"] = "현재는 매수 추천합니다."
        history_trades[1]["memo"] = "현재는 매수 추천합니다."
        self.assertEqual(expected_result, result)
        self.assertEqual(sealed_text, approval["snapshot"].json_text)
        self.assertIs(approval["snapshot"], state["approved"]["snapshot"])
        self.assertEqual("삼성전자", json.loads(state["approved"]["metadata_json"])["chart_snapshot"]["charts"][0]["name"])

    def test_history_candidate_is_not_approved_in_phase2b(self):
        state = {"candidate": {"ticker": "005930", "name": "삼성전자", "trade_date": "2026-07-10",
                               "target_trade_id": 2, "trade_snapshot": {"memo": "현재는 매수 추천합니다."},
                               "recent_trades_snapshot": [], "charts": []}}
        approval = {}
        with patch.object(self.ai_review_v2, "_call_openai_review", return_value=self._model_output("basic")):
            result = self.ai_review_v2.build_basic_ai_review(
                self.trades, history_state=state, approval_state=approval)
        self.assertEqual(("error", "safety_rejected"),
                         (result["status"], result["internal_status"]))
        self.assertIsNone(state["approved"])
        self.assertIsNone(json.loads(approval["snapshot"].json_text)["history"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_summary_only_final_sink_rejects_after_safe_normalized_semantics(self):
        original = self.ai_review_v2.compile_structured_review

        def final_summary(structured):
            if structured.get("objective") and structured["summary"]["main_issue"] == json.loads(self._model_output("basic"))["main_issue"]:
                _document, paths = original(structured)
                return self.display_contract.compile_literal_text("목표가: 80,000원입니다."), paths
            return original(structured)

        with patch.object(self.ai_review_v2, "compile_structured_review", final_summary):
            result = self._review_from_output("basic", json.loads(self._model_output("basic")))
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertNotIn("목표가: 80,000원입니다.", json.dumps(result, ensure_ascii=False))

    def test_extra_chart_reviews_are_inside_finalizer_even_without_chart_snapshot(self):
        output = self._model_output("basic")
        source = review_input_fixture(self.trades, compact_chart_fixture({
            "rule_based_observations": [{"title": "매수 시점", "detail": "현재는 매수 추천합니다."}],
        }))
        result = self.ai_review_v2._finalize_ai_review(
            output, source=source, review_type="basic", payload={"review_type": "basic"}, model="test-model",
        )
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual([], result["chart_reviews"])

    def test_user_supplied_symbol_name_cannot_survive_fixed_fallback_objective(self):
        trades = copy.deepcopy(self.trades)
        for trade in trades:
            trade["name"] = "현재는 매수 추천합니다."
        with patch.object(self.ai_review_v2, "_call_openai_review", return_value=self._model_output("basic")):
            result = self.ai_review_v2.build_basic_ai_review(trades)
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertEqual("", result["structured_review"]["objective"]["symbol"]["name"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_midword_strong_canonical_text_rejects_production_review(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = "현재는 매**수** 추천합니다."
        self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(json.dumps(output, ensure_ascii=False)))
        result = self._review_from_output("basic", output)
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertNotIn("현재는 매수 추천합니다.", result["summary"])
        self.assertEqual(result["summary"], self.display_contract.flatten_document(result["display_snapshot"]))

    def test_normal_strong_survives_production_body_and_summary_is_a1_wire(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = "**체결 기록**을 확인합니다."
        result = self._review_from_output("basic", output)
        self.assertEqual("ready", result["status"])
        self.assertIn("**체결 기록**을 확인합니다.", result["summary"])
        self.assertIn("체결 기록을 확인합니다.", result["display_snapshot"]["canonical_text"])
        self.assertEqual(result["summary"], self.compatibility.admit_legacy_body(result["display_snapshot"]).summary)
        self.assertTrue(any(run == {"type": "strong", "text": "체결 기록"}
                            for block in result["display_snapshot"]["blocks"] for run in block["runs"]))

    def test_unknown_model_field_fails_closed_before_ready(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["future_note"] = "UNMAPPED_SAFE_NOTE"
        result = self._review_from_output("basic", output)
        self.assertEqual(("error", "invalid_structured_output"), (result["status"], result["internal_status"]))
        self.assertNotIn("UNMAPPED_SAFE_NOTE", json.dumps(result, ensure_ascii=False))

    def test_unknown_final_semantic_field_fails_closed(self):
        original = self.ai_review_v2._build_structured_review

        def inject(*args, **kwargs):
            structured = original(*args, **kwargs)
            if args[0].status == "ready":
                structured["basic"]["future_note"] = "UNMAPPED_SAFE_NOTE"
            return structured

        with patch.object(self.ai_review_v2, "_build_structured_review", inject):
            result = self._review_from_output("basic", json.loads(self._model_output("basic")))
        self.assertEqual(("error", "invalid_structured_output"), (result["status"], result["internal_status"]))
        self.assertNotIn("UNMAPPED_SAFE_NOTE", json.dumps(result, ensure_ascii=False))

    def test_chart_review_header_metric_and_marker_tooltip_have_canonical_surfaces(self):
        chart = {
            "ticker": "005930", "name": "**삼성전자**", "timeframe": "daily", "period": "2026-07-10",
            "candles": [{"time": "2026-07-10", "close": 70400}],
            "trade_markers": [{"time": "2026-07-10", "side": "buy", "text": "B", "tooltip": {
                "label": "매수", "count": 1, "avg_price": 70000, "total_quantity": 10,
                "prices": [70000],
            }}],
            "rule_based_observations": [{"title": "체결 기록", "detail": "과거 체결입니다.",
                                         "metrics": {"price_vs_close_pct": 1.5}}],
        }
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            approval = {}
            result = self._review_from_output(
                "basic", json.loads(self._model_output("basic")), approval_state=approval)
        self.assertEqual("ready", result["status"])
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual("chart_header", envelope["charts"][0]["header"]["surface"])
        tab = envelope["charts"][0]["tab"]
        self.assertEqual("삼성전자", tab["canonical_text"])
        self.assertEqual("strong", tab["blocks"][0]["runs"][0]["type"])
        review = envelope["chart_cards"][0]["display"]
        self.assertEqual("체결 기록: 과거 체결입니다.", review["canonical_text"])
        self.assertEqual(set(envelope["chart_cards"][0]["metrics"]),
                         {"rsi14", "return_10d_before", "volume_ratio_20d", "next_5d_return", "next_20d_return"})
        marker = envelope["charts"][0]["markers"][0]
        self.assertEqual("B", marker["label"]["canonical_text"])
        self.assertIn("평균 70,000원 · 수량 10", marker["tooltip"]["canonical_text"])

    def test_internal_context_and_memo_have_no_outbound_surface(self):
        context = {"trade_id": 1, "date": "2026-07-10T09:30", "market_date": "2026-07-10",
                   "ticker": "005930", "name": "**삼성전자**", "memo": "**체결 기록**", "side": "buy",
                   "price": 70000, "quantity": 10, "close": 70400, "price_vs_close_pct": None,
                   "ma5": None, "ma20": None, "ma60": None, "rsi14": None, "volume_ratio_20d": None,
                   "return_10d_before": None, "position_in_20d_range": None,
                   "next_5d_return": None, "next_20d_return": None}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})), patch.object(
            self.ai_review_v2, "_contexts_for_trades", return_value=[context],
        ):
            approval = {}
            result = self._review_from_output(
                "basic", json.loads(self._model_output("basic")), approval_state=approval)
        self.assertEqual("ready", result["status"])
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertNotIn("chart_contexts", envelope)
        self.assertNotIn("memo", approval["snapshot"].json_text)
        self.assertEqual([], result["chart_contexts"])

    def test_split_user_name_and_memo_reject_before_approval(self):
        trades = copy.deepcopy(self.trades)
        trades[0]["name"] = "현재는 매수"
        trades[0]["memo"] = "추천합니다."
        with patch.object(self.ai_review_v2, "_call_openai_review", return_value=self._model_output("basic")):
            result = self.ai_review_v2.build_basic_ai_review(trades)
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_corrupt_chart_document_fails_full_envelope_validation(self):
        chart = {"candles": [{"time": "2026-07-10", "close": 70400}],
                 "rule_based_observations": [{"title": "체결", "detail": "과거 체결입니다.", "metrics": {}}]}
        compiler = importlib.import_module("core.review_envelope_compiler")
        original = compiler._surface

        def corrupt(surface, lines):
            rendered = original(surface, lines)
            if surface == "chart_card":
                rendered["canonical_text"] += "x"
            return rendered

        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)), patch.object(
            compiler, "_surface", corrupt,
        ):
            result = self._review_from_output("basic", json.loads(self._model_output("basic")))
        self.assertEqual(("error", "invalid_structured_output"), (result["status"], result["internal_status"]))
        self.assertEqual(result["summary"], self.display_contract.flatten_document(result["display_snapshot"]))

    def test_production_builders_seal_valid_closed_envelopes(self):
        contract = importlib.import_module("core.review_envelope_contract")
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                approval = {}
                result = self._review_from_output(
                    review_type, json.loads(self._model_output(review_type)), approval_state=approval)
                snapshot = approval["snapshot"]
                self.assertIsInstance(snapshot, contract.ApprovedReviewSnapshot)
                envelope = json.loads(snapshot.json_text)
                self.assertIsNone(contract.validate_envelope(envelope))
                self.assertEqual(("ready", "openai", review_type),
                                 (envelope["status"], envelope["source"], envelope["review_type"]))
                self.assertEqual(result["summary"], envelope["body"]["canonical_text"])
                self.assertEqual(len(self.trades), envelope["objective"]["trade_count"])
                self.assertEqual(len(self.trades), len(envelope["trades"]))
                self.assertIsNone(envelope["history"])
                if review_type == "advanced":
                    body = envelope["body"]["canonical_text"]
                    labels = ("이번 매매 판단:", "진입 가설 검토:", "위험 관리 검토:",
                              "매수·매도 대응:", "상세 분석:", "다음 매매 체크:",
                              "이번에 배울 점:", "다음 복기 질문:")
                    positions = [body.index(label) for label in labels]
                    self.assertEqual(sorted(positions), positions)

    def test_empty_missing_key_and_model_failure_seal_status_contract(self):
        for review_type in ("basic", "advanced"):
            builder = (self.ai_review_v2.build_basic_ai_review if review_type == "basic"
                       else self.ai_review_v2.build_advanced_ai_review)
            approval = {}
            empty = builder([], approval_state=approval)
            envelope = json.loads(approval["snapshot"].json_text)
            self.assertEqual(("empty", "none"), (empty["status"], envelope["source"]))
            self.assertEqual("empty", envelope["status"])
            approval = {}
            with patch.object(self.ai_review_v2, "_call_openai_review", return_value=""):
                missing = builder(self.trades, approval_state=approval)
            self.assertEqual("missing_key", missing["status"])
            self.assertEqual("missing_key", json.loads(approval["snapshot"].json_text)["status"])
            approval = {}
            with patch.object(self.ai_review_v2, "_call_openai_review", side_effect=RuntimeError("synthetic")):
                failed = builder(self.trades, approval_state=approval)
            self.assertEqual("error", failed["status"])
            self.assertEqual("error", json.loads(approval["snapshot"].json_text)["status"])

    def test_decode_failures_are_terminal_and_schema_invalid_output_keeps_fallback(self):
        for raw in ("not-json", "{", " ", '```json\n\n```', '{"key": 1,}', '{"key": 1} trailing'):
            with self.subTest(raw=raw), patch.object(self.ai_review_v2, "_call_openai_review", return_value=raw), patch.object(
                    self.ai_review_v2, "seal_review_envelope", wraps=self.ai_review_v2.seal_review_envelope) as seal:
                approval = {"snapshot": "old"}
                result = self.ai_review_v2.build_basic_ai_review(self.trades, approval_state=approval)
                self.assertEqual(("error", "invalid_structured_output", "none", ""),
                                 (result["status"], result["internal_status"], result["source"], result["summary"]))
                self.assertEqual(0, seal.call_count)
                self.assertIsNone(approval["snapshot"])
                self.assertNotIn("structured_review", result)
                self.assertNotIn("display_snapshot", result)
        for output in ({}, {"decision_quality": {"label": "보통", "explanation": "기록 확인"}}):
            approval = {}
            raw = output if type(output) is str else json.dumps(output, ensure_ascii=False)
            with patch.object(self.ai_review_v2, "_call_openai_review", return_value=raw):
                result = self.ai_review_v2.build_basic_ai_review(self.trades, approval_state=approval)
            envelope = json.loads(approval["snapshot"].json_text)
            self.assertEqual(("error", "invalid_structured_output"),
                             (result["status"], result["internal_status"]))
            self.assertEqual(("error", "chart-rules"), (envelope["status"], envelope["source"]))
            self.assertEqual(result["summary"], envelope["body"]["canonical_text"])
            self.assertEqual("notice", envelope["notice"]["surface"])

    def test_midword_and_normal_strong_are_decided_on_sealed_body(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = "현재는 매**수** 추천합니다."
        approval = {}
        rejected = self._review_from_output("basic", output, approval_state=approval)
        self.assertEqual(("error", "safety_rejected"),
                         (rejected["status"], rejected["internal_status"]))
        self.assertEqual("error", json.loads(approval["snapshot"].json_text)["status"])
        output["lesson"]["concept"] = "**체결 기록**을 확인합니다."
        approval = {}
        ready = self._review_from_output("basic", output, approval_state=approval)
        body = json.loads(approval["snapshot"].json_text)["body"]
        self.assertEqual("ready", ready["status"])
        self.assertIn("체결 기록을 확인합니다.", body["canonical_text"])
        self.assertTrue(any(run == {"type": "strong", "text": "체결 기록"}
                            for block in body["blocks"] for run in block["runs"]))

    def test_unknown_chart_string_fails_closed_without_raw_leak(self):
        chart = {"ticker": "005930", "name": "삼성전자", "timeframe": "daily",
                 "interval": "1d", "future_display": "UNMAPPED_SAFE_STRING",
                 "candles": [], "rule_based_observations": []}
        approval = {}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._review_from_output(
                "basic", json.loads(self._model_output("basic")), approval_state=approval)
        self.assertEqual(("error", "invalid_structured_output"),
                         (result["status"], result["internal_status"]))
        self.assertNotIn("UNMAPPED_SAFE_STRING", approval["snapshot"].json_text)
        self.assertEqual([], json.loads(approval["snapshot"].json_text)["charts"])

    def test_raw_semantic_and_chart_strings_only_enter_display_surfaces(self):
        output = json.loads(self._model_output("basic"))
        output["lesson"]["concept"] = "MODEL SEMANTIC TOKEN"
        chart = {"ticker": "005930", "name": "삼성전자", "timeframe": "daily",
                 "interval": "1d", "candles": [{"time": "2026-07-10", "close": 70400}],
                 "trade_markers": [],
                 "rule_based_observations": [
                     {"trade_id": 1, "title": "RAW_CHART_TITLE", "detail": "RAW_CHART_DETAIL"}]}
        approval = {}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._review_from_output("basic", output, approval_state=approval)
        self.assertEqual("ready", result["status"])
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual({"body", "chart_cards", "charts", "history", "notice", "objective",
                          "review_type", "schema_version", "source", "status", "trades"}, set(envelope))
        self.assertEqual("RAW_CHART_TITLE: RAW_CHART_DETAIL",
                         envelope["chart_cards"][0]["display"]["canonical_text"])
        self.assertIn("MODEL SEMANTIC TOKEN", envelope["body"]["canonical_text"])
        for forbidden in ("structured_review", "summary", "title", "detail", "chart_contexts"):
            self.assertNotIn(f'"{forbidden}"', approval["snapshot"].json_text)

    def test_sealed_objective_uses_full_20_21_200_episode_and_prompt_20(self):
        for count in (20, 21, 200):
            with self.subTest(count=count):
                trades = [dict(self.trades[0], id=index, trade_date="2026-07-10T09:30",
                               price=100, quantity=1, fee=0) for index in range(1, count + 1)]
                seen = []

                def fake_call(payload, *, model, instructions):
                    seen.append(len(payload["trade_episode"]))
                    return self._model_output("basic")

                approval = {}
                with patch.object(self.ai_review_v2, "_call_openai_review", fake_call):
                    result = self.ai_review_v2.build_basic_ai_review(
                        trades, target_trade_id=count, approval_state=approval)
                envelope = json.loads(approval["snapshot"].json_text)
                self.assertEqual("ready", result["status"])
                self.assertEqual(min(count, 20), seen[0])
                self.assertEqual(count, envelope["objective"]["trade_count"])
                self.assertEqual(min(count, 20), len(envelope["trades"]))

    def test_actual_compact_chart_source_projects_typed_candle_and_marker(self):
        provider = {"charts": [{
            "ticker": "005930", "name": "삼성전자", "timeframe": "daily", "interval": "1d",
            "source": "daily OHLCV", "period_label": "2026-07-10", "candles": [{
                "time": "2026-07-10", "label": "2026-07-10", "open": 70000,
                "high": 71000, "low": 69000, "close": 70400, "volume": 1000,
                "ma5": 70200, "ma20": None,
            }], "markers": [{
                "time": "2026-07-10", "side": "buy", "position": "belowBar", "color": "#2962ff",
                "shape": "arrowUp", "text": "B", "size": 2,
                "trades": [{"id": 1, "date": "2026-07-10T09:30", "price": 70000, "quantity": 10}],
                "tooltip": {
                    "label": "매수", "count": 1, "avg_price": 70000,
                    "total_quantity": 10, "prices": [70000],
                },
            }], "reviews": [{"trade_id": 1, "title": "과거 체결", "detail": "근거 확인",
                            "metrics": {"price_vs_close_pct": 0, "after_5_bars": None,
                                        "after_later_bars": None, "ma5": None, "ma20": None}}],
        }]}
        approval = {}
        with patch.object(self.ai_review_v2, "build_journal_charts", return_value=provider), patch.object(
            self.ai_review_v2, "_compact_chart_snapshot", self.real_compact_chart_snapshot,
        ):
            result = self._review_from_output(
                "basic", json.loads(self._model_output("basic")), approval_state=approval)
        self.assertEqual("ready", result["status"])
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual("2026-07-10", envelope["charts"][0]["candles"][0]["time"])
        self.assertEqual(70400, envelope["charts"][0]["candles"][0]["close"])
        self.assertEqual("B", envelope["charts"][0]["markers"][0]["label"]["canonical_text"])
        self.assertIsNone(envelope["chart_cards"][0]["metrics"]["rsi14"])

    def test_model_objective_injection_cannot_change_sealed_objective(self):
        output = json.loads(self._model_output("basic"))
        output["objective"] = {"trade_count": 999999, "realized_pnl": 999999999}
        approval = {}
        result = self._review_from_output("basic", output, approval_state=approval)
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual(("error", "invalid_structured_output"),
                         (result["status"], result["internal_status"]))
        self.assertEqual(2, envelope["objective"]["trade_count"])
        self.assertNotEqual(999999999, envelope["objective"]["realized_pnl"])

    def test_low_confidence_unsafe_semantic_keeps_rejection_in_sealed_fallback(self):
        output = json.loads(self._model_output("basic"))
        suffix = "목표가: 80,000원"
        output["lesson"]["concept"] = "A" * (900 - len(suffix)) + suffix + "이라는 기록"
        approval = {}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            result = self._review_from_output("basic", output, approval_state=approval)
        envelope = json.loads(approval["snapshot"].json_text)
        self.assertEqual(("error", "safety_rejected"),
                         (result["status"], result["internal_status"]))
        self.assertEqual("error", envelope["status"])
        self.assertNotIn(suffix, approval["snapshot"].json_text)

    def test_phase2c_normal_body_section_separators_and_sealed_summary(self):
        for review_type, count, separator in (("basic", 4, "\n\n"), ("advanced", 8, "\n\n")):
            approval = {}
            result = self._review_from_output(review_type, json.loads(self._model_output(review_type)), approval_state=approval)
            sealed = json.loads(approval["snapshot"].json_text)["body"]
            self.assertEqual("ready", result["status"])
            self.assertEqual(count, len(sealed["blocks"]))
            self.assertEqual([separator] * (count - 1) + [""], [block["separator_after"] for block in sealed["blocks"]])
            self.assertEqual(result["display_snapshot"], sealed)
            self.assertEqual(result["summary"], self.compatibility.admit_legacy_body(sealed).summary)
            self._assert_final_text_safe(result)

    def test_phase2c_basic_fallback_legacy_exact_string(self):
        expected = (
            "이번 매매 판단: 삼성전자 매매는 평균 70,000원 매수, 70,900원 매도로 실현손익 +8,789원(+1.26%)입니다.\n\n"
            "확인된 강점: 손실 포지션을 남기지 않고 수익을 실현한 점은 대응 측면에서 유효했습니다.\n\n"
            "개선할 점: 수익 여부와 별개로 매수 직후 불리한 움직임을 견딜 가격 기준이 숫자로 정해져 있었는지 확인해야 합니다.\n\n"
            "다음 매매 점검: 이번 매수 전에 진입 이유와 가설이 틀렸다고 판단할 기준을 기록했는지 확인하기 / "
            "이번 1회 매수 체결마다 분할 진입의 목적이 서로 달랐는지 확인하기 / "
            "이번 매도 이유가 매매 중의 불안감인지 사전에 정한 기준인지 구분해 기록하기"
        )
        self._phase2c_assert_fallback("basic", expected)

    def test_phase2c_advanced_fallback_legacy_exact_string(self):
        expected = (
            "최근 패턴: 2건, 실현손익 +8,789원, 승률 100.0%입니다.\n\n"
            "반복 문제: 체결 전후 봉에서 반복되는 명확한 약점은 아직 표본이 부족합니다.\n\n"
            "손실 관리: 확정 손실 종목 없음. 미청산 종목은 0개입니다.\n\n"
            "다음 복기 질문: 매수 이유가 체결 전에 기록됐는지, 당시 위험 허용 범위를 정했는지, 매도 이유가 그 기준과 일치했는지 확인하세요."
        )
        self._phase2c_assert_fallback("advanced", expected)

    def _phase2c_assert_fallback(self, review_type, expected):
        builder = self.ai_review_v2.build_basic_ai_review if review_type == "basic" else self.ai_review_v2.build_advanced_ai_review
        for raw, missing_key in (("{}", False), ("", True)):
            approval = {}
            with patch.dict(os.environ, {"OPENAI_API_KEY": "" if missing_key else "synthetic", "ALPHAMATE_OPENAI_API_KEY": ""}), patch.object(self.ai_review_v2, "_call_openai_review", return_value=raw):
                result = builder(self.trades, approval_state=approval)
            self.assertEqual("missing_key" if missing_key else "error", result["status"])
            body = json.loads(approval["snapshot"].json_text)["body"]
            self.assertEqual(expected, result["summary"])
            self.assertEqual(expected, body["canonical_text"])
            self.assertEqual(body, result["display_snapshot"])
            separator = "\n\n"
            self.assertEqual([separator] * 3 + [""], [block["separator_after"] for block in body["blocks"]])
            if review_type == "advanced":
                fixture = json.loads((Path(__file__).resolve().parents[1] / "frontend/scripts/fixtures/review-compatibility-v1.json").read_text(encoding="utf-8"))["cases"][1]
                self.assertEqual("closed-profit-trade", fixture["id"])
                self.assertEqual(expected, fixture["summary"])
                self.assertEqual(fixture["sections"], ["".join(run["text"] for run in block["runs"]) for block in body["blocks"]])
                self.assertEqual(fixture["legacy_summary"].split("\n"), fixture["sections"])
                self.assertEqual(fixture["summary"].split("\n\n"), fixture["sections"])
            self.assertEqual(expected, self.compatibility.admit_legacy_body(body).summary)
            self._assert_final_text_safe(result)

    def test_phase2c_advanced_fallback_preserves_repeated_loss_and_open_facts(self):
        self.trades[1]["price"] = 69000
        # A partial exit keeps the selected episode open; a later fresh buy
        # would select a different episode under the unchanged 2B policy.
        self.trades[1]["quantity"] = 5
        chart = compact_chart_fixture({"rule_based_observations": [{"trade_id": 1, "title": "매수 시점: 아쉬움", "detail": "체결 전후 흐름을 확인합니다.", "metrics": {}}]})
        approval = {}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=chart), patch.object(self.ai_review_v2, "_call_openai_review", return_value="{}"):
            result = self.ai_review_v2.build_advanced_ai_review(self.trades, approval_state=approval)
        self.assertEqual("반복 문제: 체결 전후 흐름을 확인합니다.", result["summary"].split("\n\n")[1])
        self.assertEqual("손실 관리: 삼성전자 -5,158원. 미청산 종목은 1개입니다.", result["summary"].split("\n\n")[2])
        self.assertEqual(result["summary"], json.loads(approval["snapshot"].json_text)["body"]["canonical_text"])

    def test_phase2c_strong_sentence_has_same_approved_wire_summary(self):
        for review_type in ("basic", "advanced"):
            output = json.loads(self._model_output(review_type))
            output["main_issue"] = "**체결 기록**을 확인합니다."
            approval = {}
            result = self._review_from_output(review_type, output, approval_state=approval)
            body = json.loads(approval["snapshot"].json_text)["body"]
            self.assertEqual("ready", result["status"])
            self.assertIn({"type": "strong", "text": "체결 기록"}, body["blocks"][0]["runs"])
            self.assertIn("**체결 기록**을 확인합니다.", result["summary"])
            self.assertIn("체결 기록을 확인합니다.", body["canonical_text"])
            self.assertEqual(self.compatibility.admit_legacy_body(body).summary, result["summary"])

    def test_phase2c_midword_strong_safety_cannot_reappear_in_compatibility(self):
        for review_type in ("basic", "advanced"):
            output = json.loads(self._model_output(review_type))
            output["main_issue"] = "현재는 매**수** 추천합니다."
            approval = {}
            result = self._review_from_output(review_type, output, approval_state=approval)
            self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
            self.assertNotIn("매**수** 추천", result["summary"])
            self.assertNotIn("매수 추천", result["summary"])
            self.assertEqual(result["summary"], self.compatibility.admit_legacy_body(json.loads(approval["snapshot"].json_text)["body"]).summary)

    def test_phase2c_candidate_and_source_mutation_cannot_change_approved_summary(self):
        original_seal = self.ai_review_v2.seal_review_envelope
        candidates = []
        def seal(candidate):
            candidates.append(candidate)
            return original_seal(candidate)
        for review_type in ("basic", "advanced"):
            for output in (json.loads(self._model_output(review_type)), {}):
                approval = {}
                with patch.object(self.ai_review_v2, "seal_review_envelope", side_effect=seal):
                    result = self._review_from_output(review_type, output, approval_state=approval)
                summary = result["summary"]
                sealed_bytes = approval["snapshot"].json_text
                candidates[-1]["body"]["blocks"][0]["runs"][0]["text"] = "candidate mutation"
                candidates[-1]["body"]["canonical_text"] = "candidate mutation"
                original_trades = copy.deepcopy(self.trades)
                self.trades[0]["name"] = "source mutation"
                output.clear()
                result["structured_review"].clear()
                result["display_snapshot"]["blocks"].clear()
                self.assertEqual(sealed_bytes, approval["snapshot"].json_text)
                self.trades = original_trades
                self.assertEqual(summary, self.compatibility.admit_legacy_body(json.loads(sealed_bytes)["body"]).summary)

    def test_phase2c_fallback_strong_source_uses_same_canonical_runs(self):
        chart = compact_chart_fixture({"rule_based_observations": [{"trade_id": 1, "title": "매수 시점: 아쉬움", "detail": "**체결 기록**을 확인합니다.", "metrics": {}}]})
        for review_type in ("basic", "advanced"):
            approval = {}
            builder = self.ai_review_v2.build_basic_ai_review if review_type == "basic" else self.ai_review_v2.build_advanced_ai_review
            with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=chart), patch.object(self.ai_review_v2, "_call_openai_review", return_value="{}"):
                result = builder(self.trades, approval_state=approval)
            body = json.loads(approval["snapshot"].json_text)["body"]
            self.assertEqual("error", result["status"])
            self.assertEqual("chart-rules", result["source"])
            self.assertTrue(any(run == {"type": "strong", "text": "체결 기록"} for block in body["blocks"] for run in block["runs"]))
            self.assertIn("**체결 기록**을 확인합니다.", result["summary"])
            self.assertIn("체결 기록을 확인합니다.", body["canonical_text"])
            self.assertEqual(self.compatibility.admit_legacy_body(body).summary, result["summary"])

    def test_phase2c_compatibility_never_uses_legacy_summary_producers(self):
        with patch.object(self.ai_review_v2, "_fallback_basic_text", side_effect=AssertionError("legacy summary producer")), patch.object(self.ai_review_v2, "_fallback_advanced_text", side_effect=AssertionError("legacy summary producer")):
            for review_type in ("basic", "advanced"):
                for output in (json.loads(self._model_output(review_type)), {}):
                    approval = {}
                    result = self._review_from_output(review_type, output, approval_state=approval)
                    self.assertEqual(result["summary"], self.compatibility.admit_legacy_body(json.loads(approval["snapshot"].json_text)["body"]).summary)


if __name__ == "__main__":
    unittest.main()
