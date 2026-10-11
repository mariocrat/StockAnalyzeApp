"""A2 production builder/finalizer admission, under H4 before target imports."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import copy
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.api_test_modules import _import_state
from tests.review_source_fixtures import compact_chart_fixture
from backend.core.review_legacy_compatibility import admit_legacy_body, validate_legacy_body


VECTORS = json.loads((Path(__file__).resolve().parents[1]
                     / "frontend/scripts/fixtures/review-legacy-compatibility-v1.json")
                    .read_text(encoding="utf-8"))


def model_output(review_type):
    """Independent synthetic semantic values; never derived from a result."""
    value = {
        "decision_quality": {"label": "보통", "explanation": "결과와 당시 판단을 구분합니다."},
        "main_issue": "사전 기록을 대조합니다.",
        "next_action": "주문 전에 판단 근거를 기록합니다.",
        "lesson": {"title": "기준과 결과 구분", "concept": "당시 확인 가능한 사실로 평가합니다.",
                   "applied_to_this_trade": "체결 시점의 기록을 확인합니다."},
    }
    if review_type == "basic":
        value.update(
            good_points=[{"title": "체결 확인", "detail": "매수와 매도 체결을 비교합니다."},
                         {"title": "기록 확인", "detail": "사전 메모를 함께 대조합니다."}],
            main_improvement={"title": "사전 기준", "detail": "위험 허용 범위의 기록을 확인합니다."},
            next_trade_checks=[{"phase": "before_entry", "text": "진입 이유를 기록합니다."},
                               {"phase": "while_holding", "text": "가설과 실제 흐름을 비교합니다."},
                               {"phase": "before_exit", "text": "매도 이유를 대조합니다."}],
        )
    else:
        quality = {"label": "근거 일부", "explanation": "당시 근거만 비교합니다."}
        value.update(
            entry_review={"evidence": ["체결 가격 확인", "체결 시각 확인"],
                          "uncertainty": ["매수 이유 확인 필요", "가설 기록 확인 필요"],
                          "invalidation": "무효화 기준 기록 확인", "assessment": quality},
            risk_review={"planned_rule": "사전 위험 기록 확인", "actual_response": "실제 대응 기록 확인",
                         "assessment": {"label": "근거 부족", "explanation": "계획과 행동을 대조합니다."}},
            exit_review={"profit_taking_assessment": "수익 확정 근거 확인",
                         "trend_exit_assessment": "추세 종료 근거 확인", "explanation": "당시 매도 근거를 확인합니다."},
            detailed_analysis=[{"title": "진입 흐름", "detail": "진입 전후 사실 확인"},
                               {"title": "매도 흐름", "detail": "매도 전후 사실 확인"}],
            next_trade_playbook={"before_entry": ["진입 가설 기록", "위험 기준 기록"],
                                 "while_holding": ["실제 흐름 점검"], "before_exit": ["매도 관점 구분"]},
            reflection_questions=["당시 근거는 무엇이었나요?", "계획과 행동은 일치했나요?"],
        )
        value["lesson"]["next_trade_application"] = "주문 전에 판단 기준을 기록합니다."
    return value


class ProductionFinalizerCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai.__dict__))
        importlib.reload(self.ai)
        self.trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "005930", "name": "삼성전자",
             "side": "buy", "price": 70000, "quantity": 10, "fee": 105, "tax": 0,
             "memo": "거래량 증가를 보고 진입", "source": "manual"},
            {"id": 2, "trade_date": "2026-07-10T10:00", "ticker": "005930", "name": "삼성전자",
             "side": "sell", "price": 70900, "quantity": 10, "fee": 106, "tax": 0,
             "memo": "수익 확정으로 매도", "source": "manual"},
        ]
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic", "ALPHAMATE_OPENAI_API_KEY": ""}))
        self.enterContext(patch.object(self.ai, "_contexts_for_trades", return_value=[]))
        self.enterContext(patch.object(self.ai, "_compact_chart_snapshot", return_value=compact_chart_fixture({
            "candles": [{"time": "2026-07-10", "close": 70400}], "rule_based_observations": [],
        })))

    def build(self, review_type, *, output=None, raw=None, trades=None, approval=None, history=None):
        builder = self.ai.build_basic_ai_review if review_type == "basic" else self.ai.build_advanced_ai_review
        if raw is None:
            raw = json.dumps(model_output(review_type) if output is None else output, ensure_ascii=False)
        with patch.object(self.ai, "_call_openai_review", return_value=raw):
            return builder(self.trades if trades is None else trades,
                           approval_state=approval, history_state=history)

    def assert_approved(self, result, approval, status, blocks=None):
        snapshot = approval["snapshot"]
        self.assertIsNotNone(snapshot)
        sealed = json.loads(snapshot.json_text)
        self.assertEqual((status, status), (result["status"], sealed["status"]))
        body = sealed["body"]
        self.assertIsNone(validate_legacy_body(body))
        self.assertEqual(result["display_snapshot"], body)
        self.assertEqual(result["summary"], admit_legacy_body(body).summary)
        if blocks is not None:
            self.assertEqual(len(body["blocks"]), blocks)
        self.assertEqual(["\n\n"] * (len(body["blocks"]) - 1) + [""],
                         [block["separator_after"] for block in body["blocks"]])
        return body

    def assert_terminal(self, result, approval, history=None, internal="invalid_structured_output"):
        self.assertEqual(("error", internal, "", None),
                         (result["status"], result["internal_status"], result["summary"], approval["snapshot"]))
        self.assertNotIn("display_snapshot", result)
        self.assertNotIn("structured_review", result)
        if history is not None:
            self.assertIsNone(history["approved"])

    @contextmanager
    def inject_body(self, document, *, only_ready=False):
        # Only the candidate body is supplied by an independent fixture. The
        # builder/source, finalizer, safety, admission, seal and serializer stay
        # real. Both compiler references receive the same canonical candidate.
        original = self.ai.compile_review_envelope
        original_body = self.ai.compile_review_body

        def body(source):
            return (original_body(source) if only_ready and source.status != "ready"
                    else copy.deepcopy(document))

        def compile_envelope(source):
            candidate = original(source)
            candidate["body"] = body(source)
            return candidate

        with patch.object(self.ai, "compile_review_body", side_effect=body), patch.object(
            self.ai, "compile_review_envelope", side_effect=compile_envelope,
        ):
            yield

    def test_normal_basic_preserves_all_semantic_content_in_four_safe_paragraphs(self):
        approval = {}
        result = self.build("basic", approval=approval)
        body = self.assert_approved(result, approval, "ready", 4)
        for path, text in self.ai._model_text_leaves(result["structured_review"]):
            expected = {"before_entry": "진입 전", "while_holding": "보유 중", "before_exit": "매도 전"}.get(text, text)
            with self.subTest(path=path):
                self.assertIn(expected, body["canonical_text"])
        self.assertTrue(body["canonical_text"].startswith("이번 매매 판단:"))
        self.assertEqual(2, result["structured_review"]["objective"]["result"]["trade_count"])
        self.assertEqual(8789, result["structured_review"]["objective"]["result"]["realized_pnl"])

    def test_normal_advanced_preserves_all_semantic_content_in_eight_safe_paragraphs(self):
        approval = {}
        result = self.build("advanced", approval=approval)
        body = self.assert_approved(result, approval, "ready", 8)
        for path, text in self.ai._model_text_leaves(result["structured_review"]):
            with self.subTest(path=path):
                self.assertIn(text, body["canonical_text"])

    def test_basic_fallback_missing_key_and_semantic_failure_share_admission(self):
        for raw, key, status in (("", "", "missing_key"), ("{}", "synthetic", "error")):
            with self.subTest(status=status), patch.dict(os.environ, {"OPENAI_API_KEY": key}):
                approval = {}
                body = self.assert_approved(self.build("basic", raw=raw, approval=approval), approval, status, 4)
                self.assertIn("실현손익 +8,789원(+1.26%)", body["canonical_text"])
                self.assertIn("이번 1회 매수 체결마다 분할 진입의 목적", body["canonical_text"])
                self.assertIn("이번 매도 이유가 매매 중의 불안감인지", body["canonical_text"])

    def test_advanced_fallback_matches_both_independent_four_paragraph_fixtures(self):
        for vector in VECTORS["pass"]:
            if not vector["id"].startswith("advanced_fallback_"):
                continue
            with self.subTest(vector=vector["id"]):
                approval = {}
                trades = self.trades[:1] if "open" in vector["id"] else self.trades
                result = self.build("advanced", raw="{}", trades=trades, approval=approval)
                body = self.assert_approved(result, approval, "error", 4)
                self.assertEqual(body, vector["document"])
                self.assertEqual(result["summary"], vector["expected_summary"])

    def test_low_confidence_selection_still_admits_the_selected_body(self):
        with patch.object(self.ai, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            for review_type in ("basic", "advanced"):
                with self.subTest(review_type=review_type):
                    approval = {}
                    result = self.build(review_type, approval=approval)
                    self.assert_approved(result, approval, "ready", 4 if review_type == "basic" else 8)
                    self.assertNotEqual(model_output(review_type)["main_issue"], result["structured_review"]["summary"]["main_issue"])

    def test_fixed_unavailable_and_empty_bodies_use_the_same_admission(self):
        for review_type in ("basic", "advanced"):
            for trades, status in (([], "empty"), ([dict(self.trades[0], unexpected="synthetic")], "error")):
                with self.subTest(review_type=review_type, status=status):
                    approval = {}
                    result = self.build(review_type, trades=trades, approval=approval)
                    self.assert_approved(result, approval, status)
                    self.assertEqual("none", result["source"])

    def test_empty_optional_advanced_sections_have_no_owned_edge_or_double_space(self):
        output = model_output("advanced")
        output["entry_review"]["uncertainty"] = []
        output["detailed_analysis"] = []
        output["reflection_questions"] = []
        approval = {}
        body = self.assert_approved(self.build("advanced", output=output, approval=approval), approval, "ready", 8)
        self.assertEqual(body["blocks"][4]["runs"], [{"type": "text", "text": "상세 분석:"}])
        self.assertEqual(body["blocks"][7]["runs"], [{"type": "text", "text": "다음 복기 질문:"}])
        self.assertIn(" / 불확실성: / 무효화 기준:", body["canonical_text"])

    def test_normal_strong_uses_a1_wire_from_sealed_body(self):
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output["main_issue"] = "**체결 기록**을 확인합니다."
            approval = {}
            result = self.build(review_type, output=output, approval=approval)
            body = self.assert_approved(result, approval, "ready")
            self.assertIn("**체결 기록**을 확인합니다.", result["summary"])
            self.assertIn("체결 기록을 확인합니다.", body["canonical_text"])
            self.assertIn({"type": "strong", "text": "체결 기록"}, body["blocks"][0]["runs"])

    def test_p1_literal_counterexamples_are_terminal_in_actual_builders(self):
        for text in ("현재는 매**수** 추천합니다. *", "현재는 매**수** 추천합니다. [참고](url)"):
            for review_type in ("basic", "advanced"):
                with self.subTest(text=text, review_type=review_type):
                    output = model_output(review_type)
                    output["main_issue"] = text
                    approval, history = {"snapshot": "old"}, {"approved": "old"}
                    with patch.object(self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope) as seal, patch.object(
                        self.ai, "admit_legacy_body", wraps=admit_legacy_body,
                    ) as serializer, patch.object(self.ai, "_default_basic_semantics", side_effect=AssertionError("fallback bypass")), patch.object(
                        self.ai, "_default_advanced_semantics", side_effect=AssertionError("fallback bypass"),
                    ):
                        result = self.build(review_type, output=output, approval=approval, history=history)
                    self.assert_terminal(result, approval, history)
                    self.assertEqual((0, 0), (seal.call_count, serializer.call_count))
                    self.assertNotIn(text, json.dumps(result, ensure_ascii=False))

    def test_literal_markup_internal_whitespace_and_reserved_tokens_reject_model_body(self):
        for text in ("# 기록", "기록 [참고](url)", "*강조* 기록", "기록 `code`", "기록 _강조_",
                     "기록\n확인", "기록\t확인", "기록\u00a0확인", "기록  확인",
                     "MA20 확인", "ma 5 확인", "mA 20 확인", "M**A**20 확인", "잘한**점** 확인",
                     "[데이터 확인] 기록", "[합리적 추론] 기록"):
            for review_type in ("basic", "advanced"):
                with self.subTest(text=text, review_type=review_type):
                    output = model_output(review_type)
                    output["main_issue"] = text
                    approval = {}
                    result = self.build(review_type, output=output, approval=approval)
                    self.assertNotEqual("ready", result["status"])
                    self.assertNotIn(text, result["summary"])
                    if "[데이터 확인]" not in text and "[합리적 추론]" not in text:
                        self.assert_terminal(result, approval)

    def test_incompatible_model_is_not_hidden_by_low_confidence_selection(self):
        with patch.object(self.ai, "_compact_chart_snapshot", return_value=compact_chart_fixture({})):
            for review_type in ("basic", "advanced"):
                output = model_output(review_type)
                output["main_issue"] = "MA20 확인"
                approval = {}
                self.assert_terminal(self.build(review_type, output=output, approval=approval), approval)

    def test_fallback_incompatibility_is_error_even_without_key_and_never_repairs(self):
        for text in ("MA20 확인", "기록\n확인", "기록\t확인", "기록\u00a0확인", "기록  확인", " 기록 "):
            chart = compact_chart_fixture({"rule_based_observations": [
                {"trade_id": 1, "title": "매수 시점: 아쉬움", "detail": text, "metrics": {}}]})
            for review_type in ("basic", "advanced"):
                with self.subTest(text=text, review_type=review_type), patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch.object(
                    self.ai, "_compact_chart_snapshot", return_value=chart,
                ), patch.object(self.ai, "_fixed_safe_structured_review", side_effect=AssertionError("template repair")), patch.object(
                    self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope,
                ) as seal:
                    approval, history = {"snapshot": "old"}, {"approved": "old"}
                    result = self.build(review_type, raw="", approval=approval, history=history)
                    self.assert_terminal(result, approval, history)
                    self.assertEqual(seal.call_count, 0)

    def test_a1_fixture_admission_agrees_and_production_safety_remains_stricter(self):
        for accepted, vectors in ((True, VECTORS["pass"]), (False, VECTORS["fail"])):
            for vector in vectors:
                for review_type in ("basic", "advanced"):
                    with self.subTest(vector=vector["id"], review_type=review_type):
                        # This A1 PASS proves display compatibility for a future
                        # recommendation. Production safety must still reject it.
                        safety_only = accepted and vector["id"] == "mid_word_strong"
                        approval = {"snapshot": "old"}
                        with self.inject_body(vector["document"], only_ready=safety_only), patch.object(
                            self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope,
                        ) as seal, patch.object(self.ai, "admit_legacy_body", wraps=admit_legacy_body) as serializer:
                            try:
                                result = self.build(review_type, approval=approval)
                            except self.ai.ReviewDisplayContractError:
                                self.assertFalse(accepted)
                                result = None
                        if accepted:
                            if safety_only:
                                self.assertIsNone(validate_legacy_body(vector["document"]))
                                self.assert_approved(result, approval, "error")
                                self.assertEqual(result["internal_status"], "safety_rejected")
                                self.assertNotIn(vector["expected_summary"], result["summary"])
                            else:
                                body = self.assert_approved(result, approval, "ready")
                                self.assertEqual(body, vector["document"])
                                self.assertEqual(result["summary"], vector["expected_summary"])
                            self.assertEqual((1, 1), (seal.call_count, serializer.call_count))
                        else:
                            self.assertIsNone(approval["snapshot"])
                            self.assertEqual((0, 0), (seal.call_count, serializer.call_count))
                            if result is not None:
                                self.assertEqual(("error", ""), (result["status"], result["summary"]))

    def test_lexical_failures_cannot_bypass_production_by_splitting_runs(self):
        codes = {"literal_markdown", "reserved_basic_section", "reserved_ma_token",
                 "unsupported_whitespace", "consecutive_whitespace", "paragraph_edge_whitespace"}
        for vector in VECTORS["fail"]:
            document = vector["document"]
            if vector["expected_rejection"] not in codes or len(document["blocks"]) != 1:
                continue
            text = document["canonical_text"]
            for cut in range(1, len(text)):
                for kind in ("text", "strong"):
                    value = copy.deepcopy(document)
                    value["blocks"][0]["runs"] = [{"type": "text", "text": text[:cut]},
                                                  {"type": kind, "text": text[cut:]}]
                    with self.subTest(vector=vector["id"], cut=cut, kind=kind), self.inject_body(value):
                        approval = {}
                        try:
                            result = self.build("basic", approval=approval)
                        except self.ai.ReviewDisplayContractError:
                            result = None
                        self.assertIsNone(approval["snapshot"])
                        if result is not None:
                            self.assertEqual(("error", ""), (result["status"], result["summary"]))

    def test_fixed_and_empty_body_compatibility_failure_never_seals(self):
        vector = next(v for v in VECTORS["fail"] if v["id"] == "leading_space")
        for review_type in ("basic", "advanced"):
            for trades in ([], [dict(self.trades[0], unexpected="synthetic")]):
                with self.subTest(review_type=review_type, empty=not trades), self.inject_body(vector["document"]), patch.object(
                    self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope,
                ) as seal:
                    approval = {}
                    self.assert_terminal(self.build(review_type, trades=trades, approval=approval), approval)
                    self.assertEqual(seal.call_count, 0)

    def test_safety_then_admission_then_seal_then_only_sealed_serialization(self):
        events, snapshots, serializer_inputs = [], [], []
        original_safety, original_seal = self.ai._filter_openai_review_safety, self.ai.seal_review_envelope

        def safety(*args, **kwargs):
            events.append("safety")
            return original_safety(*args, **kwargs)

        def admit(body):
            events.append("admission")
            return validate_legacy_body(body)

        def seal(candidate):
            events.append("seal")
            snapshot = original_seal(candidate)
            snapshots.append(snapshot)
            candidate["body"]["blocks"].clear()  # Post-seal caller mutation.
            candidate["body"]["canonical_text"] = "candidate mutation"
            return snapshot

        def serialize(body):
            events.append("serializer")
            serializer_inputs.append(copy.deepcopy(body))
            self.assertEqual(body, json.loads(snapshots[-1].json_text)["body"])
            return admit_legacy_body(body)

        with patch.object(self.ai, "_filter_openai_review_safety", side_effect=safety), patch.object(
            self.ai, "validate_legacy_body", side_effect=admit,
        ), patch.object(self.ai, "seal_review_envelope", side_effect=seal), patch.object(
            self.ai, "admit_legacy_body", side_effect=serialize,
        ), patch.object(self.ai, "serialize_compatibility_summary", side_effect=AssertionError("old serializer")), patch.object(
            self.ai, "_fallback_basic_text", side_effect=AssertionError("legacy builder"),
        ), patch.object(self.ai, "_fallback_advanced_text", side_effect=AssertionError("legacy builder")):
            for review_type in ("basic", "advanced"):
                for raw, trades in ((None, self.trades), ("{}", self.trades), (None, []), (None, [dict(self.trades[0], extra="bad")])):
                    events.clear()
                    approval = {}
                    result = self.build(review_type, raw=raw, trades=trades, approval=approval)
                    self.assert_approved(result, approval, "empty" if not trades else "error" if raw or "extra" in trades[0] else "ready")
                    seal_index = events.index("seal")
                    self.assertEqual(events[seal_index - 1], "admission")
                    self.assertIn("safety", events[:seal_index - 1])
                    self.assertEqual(events[seal_index + 1:], ["serializer"])
        self.assertEqual(len(serializer_inputs), 8)

    def test_actual_safety_rejection_retains_its_meaning(self):
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output["main_issue"] = "현재는 매**수** 추천합니다."
            approval = {}
            result = self.build(review_type, output=output, approval=approval)
            self.assert_approved(result, approval, "error")
            self.assertEqual(result["internal_status"], "safety_rejected")
            self.assertNotIn("매수 추천", result["summary"])

    def test_compatibility_rejection_does_not_overwrite_prior_safety_rejection(self):
        document = next(v["document"] for v in VECTORS["fail"] if v["id"] == "ma_uppercase")
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output["main_issue"] = "현재는 매**수** 추천합니다."
            with self.inject_body(document):
                approval = {}
                result = self.build(review_type, output=output, approval=approval)
                self.assert_terminal(result, approval, internal="safety_rejected")
