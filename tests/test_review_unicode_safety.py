"""Canonical Unicode safety comparisons with exact display bytes under H4."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
import unicodedata
import unittest
from unittest.mock import patch

from core.review_display_contract import SCHEMA_VERSION
from tests import test_review_history_write_access as access_fixture
from tests import test_review_history_strict_writer as write_fixture
from tests.review_source_fixtures import approved_chart_fixture
from tests.test_review_finalizer_compatibility import model_output


PROHIBITED = "70,000원에 매수하세요."


class UnicodeSafetyTest(unittest.TestCase):
    def setUp(self):
        self.case = self.enterContext(access_fixture.producer())
        self.ai = self.case.ai
        self.enterContext(patch.object(self.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()))
        self.trades = [self.case.main.JournalTradeIn(**trade).model_dump() for trade in self.case.trades]

    def build(self, review_type, text, *, escaped=False, trades=None):
        output = model_output(review_type)
        output["main_issue"] = text
        raw = json.dumps(output, ensure_ascii=escaped)
        approval = {}
        builder = self.ai.build_basic_ai_review if review_type == "basic" else self.ai.build_advanced_ai_review
        with patch.object(self.ai, "_call_openai_review", return_value=raw):
            result = builder(self.trades if trades is None else trades, target_trade_id=2, approval_state=approval)
        return result, approval["snapshot"]

    def batch(self, review_type, *, trades=None):
        return self.case.main.JournalAiReviewIn(
            privacy_consent=True, review_type=review_type, target_trade_id=2,
            trades=[self.case.main.JournalTradeIn(**trade) for trade in (self.trades if trades is None else trades)])

    def execute(self, batch, token, key):
        return self.case.main.get_journal_ai_review_once(
            batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)

    def assert_safe(self, value):
        rendered = unicodedata.normalize("NFC", json.dumps(value, ensure_ascii=False))
        self.assertNotIn(PROHIBITED, rendered)
        self.assertFalse(self.ai._contains_prohibited_trade_guidance(rendered))

    def assert_rejected(self, result, snapshot):
        self.assertEqual(("error", "safety_rejected"), (result["status"], result["internal_status"]))
        self.assert_safe(result)
        if snapshot is not None:
            sealed = json.loads(snapshot.json_text)
            self.assertEqual("error", sealed["status"])
            self.assert_safe(sealed)

    def test_all_rule_ids_and_categories_agree_for_nfc_nfd_and_mixed_hangul(self):
        vectors = (
            ("목표가: 80,000원입니다.", "rule_1", "target_price"),
            ("추천 매수가: 70,000원입니다.", "rule_1", "recommended_entry_price"),
            ("추천 매도가: 71,000원입니다.", "rule_1", "recommended_exit_price"),
            ("매수 추천합니다.", "rule_1", "buy_recommendation"),
            ("매도 추천합니다.", "rule_1", "sell_recommendation"),
            ("돌파 시 매수하세요.", "rule_2", "conditional_trade_instruction"),
            (PROHIBITED, "rule_3", "price_or_time_trade_instruction"),
            ("손절가를 65,000원에 두세요.", "rule_4", "explicit_risk_price_instruction"),
            ("-5%면 손절하세요.", "rule_5", "percentage_trade_instruction"),
        )
        for text, rule, category in vectors:
            nfd = unicodedata.normalize("NFD", text)
            self.assertFalse(any(pattern.search(nfd) for _, _, pattern in self.ai._PROHIBITED_TRADE_GUIDANCE_RULES))
            mixed = "".join(unicodedata.normalize("NFD", char) if index % 2 else char
                            for index, char in enumerate(text))
            for variant in (text, nfd, mixed, "A\u0315\u0300 " + nfd):
                with self.subTest(rule=rule, variant=variant):
                    original = variant.encode("utf-8")
                    self.assertEqual([rule], self.ai._matched_prohibited_trade_guidance_rule_ids(variant))
                    self.assertEqual([category], self.ai._matched_prohibited_trade_guidance_rule_categories(variant))
                    self.assertEqual(original, variant.encode("utf-8"))

    def test_pattern_and_target_share_nfc_for_canonical_combining_sequences(self):
        pattern_text = "A\u0315\u0300 " + unicodedata.normalize("NFD", PROHIBITED)
        compiled = self.ai._compile_safety_pattern(pattern_text)
        self.assertEqual(unicodedata.normalize("NFC", pattern_text), compiled.pattern)
        equivalent = "\u00c0\u0315 " + PROHIBITED
        self.assertEqual(unicodedata.normalize("NFC", pattern_text), equivalent)
        with patch.object(self.ai, "_PROHIBITED_TRADE_GUIDANCE_RULES", (("canonical", "combining", compiled),)):
            for text in (pattern_text, equivalent, unicodedata.normalize("NFD", equivalent)):
                self.assertEqual(["canonical"], self.ai._matched_prohibited_trade_guidance_rule_ids(text))
                self.assertEqual(["combining"], self.ai._matched_prohibited_trade_guidance_rule_categories(text))

    def test_safe_filter_returns_original_unicode_object_and_compatibility_forms(self):
        text = self.ai._OpenAiReviewText("과거 e\u0301 A\u0315\u0300 ① Ａ **체결** 기록 👩🏽‍💻", response_status="completed")
        before = text.encode("utf-8")
        with patch.object(self.ai, "record_event", side_effect=AssertionError("safe text telemetry")):
            filtered, rules = self.ai._filter_openai_review_safety(text, payload={}, model="synthetic")
        self.assertIs(text, filtered)
        self.assertEqual([], rules)
        self.assertEqual(before, filtered.encode("utf-8"))
        self.assertEqual("① Ａ", self.ai._safety_comparison_text("① Ａ"))
        self.assertNotEqual("① Ａ", unicodedata.normalize("NFKC", "① Ａ"))

    def test_basic_advanced_nfd_reproduction_has_same_rejection_and_seal_as_nfc(self):
        for review_type in ("basic", "advanced"):
            nfc, nfc_snapshot = self.build(review_type, PROHIBITED)
            nfd, nfd_snapshot = self.build(review_type, unicodedata.normalize("NFD", PROHIBITED))
            self.assert_rejected(nfc, nfc_snapshot)
            self.assert_rejected(nfd, nfd_snapshot)
            self.assertEqual(nfc, nfd)
            self.assertEqual(nfc_snapshot.json_text, nfd_snapshot.json_text)

    def test_json_escaped_nfd_is_checked_after_decoding(self):
        text = unicodedata.normalize("NFD", PROHIBITED)
        raw = json.dumps({"main_issue": text}, ensure_ascii=True)
        self.assertNotIn(text, raw)
        self.assertEqual([], self.ai._matched_prohibited_trade_guidance_rule_ids(raw))
        for review_type in ("basic", "advanced"):
            result, snapshot = self.build(review_type, text, escaped=True)
            self.assert_rejected(result, snapshot)

    def test_nfd_strong_run_join_and_visible_documents_cannot_bypass_safety(self):
        text = unicodedata.normalize("NFD", "70,000원에 매**수**하세요.")
        self.assertEqual([], self.ai._matched_prohibited_trade_guidance_rule_ids(text))
        for review_type in ("basic", "advanced"):
            result, snapshot = self.build(review_type, text)
            self.assert_rejected(result, snapshot)
        document = self.ai.compile_literal_text(unicodedata.normalize("NFD", PROHIBITED))
        original = copy.deepcopy(document)
        issue, rules = self.ai._validate_visible_envelope(
            {"display_snapshot": document}, payload={}, model="synthetic", response_status=None, record_rejection=False)
        self.assertEqual(("safety_rejected", ["rule_3"]), (issue, rules))
        self.assertEqual(original, document)

    def test_nfd_trade_and_chart_sources_are_rejected_before_model(self):
        unsafe = unicodedata.normalize("NFD", PROHIBITED)
        for review_type in ("basic", "advanced"):
            for source in ("memo", "name", "chart"):
                with self.subTest(review_type=review_type, source=source):
                    trades = copy.deepcopy(self.trades)
                    chart = approved_chart_fixture()
                    if source == "chart":
                        chart["rule_based_observations"][0]["detail"] = unsafe
                    else:
                        trades[0][source] = unsafe
                    approval = {}
                    builder = self.ai.build_basic_ai_review if review_type == "basic" else self.ai.build_advanced_ai_review
                    with patch.object(self.ai, "_compact_chart_snapshot", return_value=chart), patch.object(
                            self.ai, "_call_openai_review", side_effect=AssertionError("unsafe source model")) as model:
                        result = builder(trades, target_trade_id=2, approval_state=approval)
                    self.assertEqual(0, model.call_count)
                    self.assert_rejected(result, approval["snapshot"])

    def test_nfc_nfd_routes_refund_once_write_zero_and_replay_only_safe_content(self):
        case = self.case
        for variant in ("session-free", "review"):
            for review_type in ("basic", "advanced"):
                for form in ("NFC", "NFD"):
                    with self.subTest(variant=variant, review_type=review_type, form=form):
                        user_id, token = case.identity(variant)
                        before = case.access.get_user_entitlements(authorization=token, entitlement_token="")
                        output = model_output(review_type)
                        output["main_issue"] = unicodedata.normalize(form, PROHIBITED)
                        key = "unicode-reject-" + variant + review_type + form
                        batch = self.batch(review_type)
                        with write_fixture.history_effects(case) as (effects, sql), patch.object(
                                self.ai, "_call_openai_review", return_value=json.dumps(output, ensure_ascii=False)) as model, patch.object(
                                case.main, "refund_ai_review_access", wraps=case.main.refund_ai_review_access) as refund, patch.object(
                                case.main, "verify_ai_review_access", wraps=case.main.verify_ai_review_access) as charge, patch.object(
                                case.main, "add_review_history", wraps=case.main.add_review_history) as save, patch.object(
                                case.main, "delete_review_history", wraps=case.main.delete_review_history) as delete:
                            result = self.execute(batch, token, key)
                            replay = self.execute(batch, token, key)
                            self.assertEqual((1, 1, 1, 0, 0), (model.call_count, charge.call_count, refund.call_count,
                                                             save.call_count, delete.call_count))
                            self.assertEqual(dict.fromkeys(effects, 0), effects)
                        self.assertEqual(before, case.access.get_user_entitlements(authorization=token, entitlement_token=""))
                        self.assertFalse(case.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].exists())
                        self.assertTrue(result["access"]["refunded"])
                        self.assertTrue(replay["access"]["idempotent_replay"])
                        expected = copy.deepcopy(result)
                        expected["access"]["idempotent_replay"] = True
                        self.assertEqual(expected, replay)
                        self.assertNotIn("review_history_id", result)
                        cached = case.main._ai_review_idempotency_cache[case.main._ai_review_idempotency_cache_key(token, key)]
                        self.assert_rejected(result, cached["snapshot"])
                        self.assert_safe(cached["result"])

    def test_missing_key_unsafe_nfd_source_retains_terminal_refund_contract(self):
        case = self.case
        for review_type in ("basic", "advanced"):
            _, token = case.identity("session-free")
            trades = copy.deepcopy(self.trades)
            trades[0]["memo"] = unicodedata.normalize("NFD", PROHIBITED)
            batch = self.batch(review_type, trades=trades)
            with write_fixture.history_effects(case) as (effects, sql), patch.object(
                    self.ai, "_call_openai_review", side_effect=AssertionError("unsafe no-key model")), patch.object(
                    case.main, "refund_ai_review_access", wraps=case.main.refund_ai_review_access) as refund:
                result = self.execute(batch, token, "unicode-no-key-" + review_type)
                replay = self.execute(batch, token, "unicode-no-key-" + review_type)
                self.assertEqual(1, refund.call_count)
                self.assertEqual(dict.fromkeys(effects, 0), effects)
            self.assertEqual(("error", "safety_rejected", True),
                             (result["status"], result["internal_status"], result["access"]["refunded"]))
            self.assertTrue(replay["access"]["idempotent_replay"])
            self.assert_safe(result)
            self.assert_safe(replay)

    def test_pre_fix_nfd_ready_history_withholds_unsafe_content_without_repair(self):
        case = self.case
        user_id, token = case.identity("session-free")
        output = model_output("advanced")
        output["main_issue"] = unicodedata.normalize("NFD", PROHIBITED)
        key = "unicode-pre-fix-artifact"
        batch = self.batch("advanced")
        # Emulate exactly the former comparison, solely to create an owned old row.
        with patch.object(self.ai, "_safety_comparison_text", side_effect=lambda value: str(value or "")), patch.object(
                self.ai, "_call_openai_review", return_value=json.dumps(output, ensure_ascii=False)):
            result = self.execute(batch, token, key)
        self.assertEqual("ready", result["status"])
        self.assertIn(output["main_issue"], result["summary"])
        path = case.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"]
        before = path.read_bytes()
        raw_before = case.history.get_review_history(result["review_history_id"], user_id=user_id)
        cache_key = case.main._ai_review_idempotency_cache_key(token, key)
        cached = case.main._ai_review_idempotency_cache[cache_key]
        cached_result = copy.deepcopy(cached["result"])
        sealed_bytes = cached["snapshot"].json_text
        detail = case.main.get_journal_review_history_detail(
            result["review_history_id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
        self.assertEqual("unavailable", detail["history_read_status"])
        self.assert_safe(detail)
        self.assertIs(cached, case.main._ai_review_idempotency_cache[cache_key])
        self.assertEqual(cached_result, cached["result"])
        self.assertEqual(sealed_bytes, cached["snapshot"].json_text)
        self.assertEqual(raw_before, case.history.get_review_history(result["review_history_id"], user_id=user_id))
        self.assertEqual(before, path.read_bytes())

    def test_safe_unicode_strong_source_display_history_cache_replay_bytes_stay_exact(self):
        case = self.case
        for review_type in ("basic", "advanced"):
            user_id, token = case.identity("session-free")
            strong = unicodedata.normalize("NFD", "체결")
            text = "과거 **" + strong + "** 기록 e\u0301 A\u0315\u0300 👩🏽‍💻"
            output = model_output(review_type)
            output["main_issue"] = text
            raw = json.dumps(output, ensure_ascii=False)
            trades = copy.deepcopy(self.trades)
            name = unicodedata.normalize("NFD", "합성 종목") + " e\u0301"
            for trade in trades:
                trade["name"] = name
            batch = self.batch(review_type, trades=trades)
            key = "unicode-exact-" + review_type
            with patch.object(self.ai, "_call_openai_review", return_value=raw):
                result = self.execute(batch, token, key)
            self.assertEqual("ready", result["status"])
            self.assertEqual(text, result["structured_review"]["summary"]["main_issue"])
            self.assertIn(text, result["summary"])
            self.assertIn({"type": "strong", "text": strong}, result["display_snapshot"]["blocks"][0]["runs"])
            body = json.dumps(result["display_snapshot"], ensure_ascii=False).encode("utf-8")
            self.assertIn(b"e\xcc\x81", body)
            self.assertIn(b"A\xcc\x95\xcc\x80", body)
            self.assertNotEqual(body, unicodedata.normalize("NFC", body.decode()).encode())
            row = case.history.get_review_history(result["review_history_id"], user_id=user_id)
            detail = case.main.get_journal_review_history_detail(row["id"], authorization=token,
                                                               x_review_display_contract=[SCHEMA_VERSION])
            self.assertEqual(name, row["trade_snapshot"]["name"])
            cached = case.main._ai_review_idempotency_cache[case.main._ai_review_idempotency_cache_key(token, key)]
            self.assertEqual(result["display_snapshot"], json.loads(cached["snapshot"].json_text)["body"])
            self.assertIn(strong.encode("utf-8"), cached["snapshot"].json_text.encode("utf-8"))
            with patch.object(self.ai, "_call_openai_review", side_effect=AssertionError("safe replay model")):
                replay = self.execute(batch, token, key)
            for visible in (row["ai_review"], detail["ai_review"], cached["result"], replay):
                self.assertEqual(body, json.dumps(visible["display_snapshot"], ensure_ascii=False).encode("utf-8"))
                self.assertEqual(text, visible["structured_review"]["summary"]["main_issue"])
                self.assertEqual(result["summary"], visible["summary"])
            self.assertEqual(raw, json.dumps(output, ensure_ascii=False))

    def test_safe_nfc_nfd_missing_key_original_metadata_and_seals_are_preserved(self):
        case = self.case
        for review_type in ("basic", "advanced"):
            for form in ("NFC", "NFD"):
                name = unicodedata.normalize(form, "합성 체결 종목 café")
                trades = copy.deepcopy(self.trades)
                for trade in trades:
                    trade["name"] = name
                result, (_, state) = case.route("session-free", review_type, "missing_key", trades=trades)
                metadata = json.loads(state["approved"]["metadata_json"])
                row = case.history.get_review_history(result["review_history_id"], user_id=state["user_id"])
                self.assertEqual(name, metadata["trade_snapshot"]["name"])
                self.assertEqual(name, row["trade_snapshot"]["name"])
                encoded_name = name.encode("utf-8")
                self.assertIn(encoded_name, state["approved"]["metadata_json"].encode())
                self.assertIn(encoded_name, state["approved"]["snapshot"].json_text.encode())
                self.assertEqual(result["display_snapshot"], row["ai_review"]["display_snapshot"])


if __name__ == "__main__":
    unittest.main()
