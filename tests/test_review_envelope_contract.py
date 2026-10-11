"""Fixed Phase 2A outbound contract cases under the H4 storage boundary."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import hashlib
import json
import pickle
import unittest
from unittest.mock import patch

from backend.core import review_envelope_contract as envelope_contract
from backend.core.review_display_contract import ReviewDisplayContractError, validate_document
from backend.core.review_envelope_contract import (
    ApprovedReviewSnapshot, ReviewEnvelopeContractError, review_envelope_schema,
    validate_envelope,
)


def document(surface, text):
    # Independent literal fixture. No production compiler or validator builds it.
    return {"schema_version": "review-display.v1", "surface": surface,
            "blocks": [{"type": "paragraph", "runs": [{"type": "text", "text": text}],
                        "separator_after": ""}], "canonical_text": text}


def envelope():
    body = {"schema_version": "review-display.v1", "surface": "body",
            "blocks": [{"type": "paragraph", "runs": [
                {"type": "text", "text": "현재는 매"}, {"type": "strong", "text": "수"},
                {"type": "text", "text": " 추천합니다."}], "separator_after": ""}],
            "canonical_text": "현재는 매수 추천합니다."}
    return {
        "schema_version": "review-envelope.v1", "review_type": "basic", "status": "ready",
        "source": "chart-rules", "body": body,
        "objective": {"trade_count": 1, "realized_pnl": 1200.5,
                      "realized_return_pct": 1.25, "win_rate_pct": 100.0,
                      "weighted_buy_price": None, "has_market_data": True},
        "chart_cards": [{"trade_id": 7, "display": document("chart_card", "차트 제목: 세부 내용"),
                         "metrics": {"rsi14": 54.2, "return_10d_before": None,
                                     "volume_ratio_20d": None, "next_5d_return": None,
                                     "next_20d_return": None}}],
        "charts": [{"ticker": "005930", "timeframe": "daily", "interval": "1d",
                    "header": document("chart_header", "일봉 · 2026-07-10"),
                    "tab": document("chart_tab", "삼성전자"),
                    "candles": [{"time": "2026-07-10", "open": 71000, "high": 72000,
                                 "low": 70000, "close": 71500, "volume": 500000,
                                 "ma5": None, "ma20": 70500.0}],
                    "markers": [{"time": "2026-07-10", "side": "buy",
                                 "label": document("marker_label", "B"),
                                 "tooltip": document("marker_tooltip", "매수 1건\n평균 71,000원")}] }],
        "trades": [{"id": 7, "trade_date": "2026-07-10T09:30:00+09:00", "ticker": "005930",
                    "side": "buy", "name": document("trade_name", "삼성전자"),
                    "price": 71000.0, "quantity": 2}],
        "history": {"id": 12, "created_at": "2026-07-10T10:00:00+09:00",
                    "title": document("history_title", "삼성전자 복기")},
        "notice": document("notice", "차트 데이터를 확인했습니다."),
    }


class ReviewEnvelopeContractTest(unittest.TestCase):
    def assert_rejected(self, value):
        with self.assertRaises(ReviewEnvelopeContractError):
            validate_envelope(value)
        with self.assertRaises(ReviewEnvelopeContractError):
            ApprovedReviewSnapshot(value)

    def test_valid_body_document_and_phase1_exact_strong_text(self):
        value = envelope()
        value["chart_cards"] = []
        value["charts"] = []
        value["trades"] = []
        value["history"] = None
        value["notice"] = None
        self.assertIsNone(validate_envelope(value))
        self.assertEqual(value["body"]["canonical_text"], "현재는 매수 추천합니다.")
        self.assertEqual(value["body"]["blocks"][0]["runs"][1], {"type": "strong", "text": "수"})

    def test_valid_chart_card_header_tab_marker_label_and_tooltip(self):
        value = envelope()
        self.assertIsNone(validate_envelope(value))
        self.assertEqual(value["chart_cards"][0]["display"]["surface"], "chart_card")
        self.assertEqual(value["charts"][0]["markers"][0]["tooltip"]["surface"], "marker_tooltip")

    def test_valid_history_title_trade_name_and_notice(self):
        value = envelope()
        self.assertIsNone(validate_envelope(value))
        self.assertEqual(value["history"]["title"]["canonical_text"], "삼성전자 복기")
        self.assertEqual(value["trades"][0]["name"]["canonical_text"], "삼성전자")

    def test_typed_numbers_boolean_null_enums_dates_and_ids(self):
        value = envelope()
        value["review_type"] = "advanced"
        value["status"] = "error"
        value["source"] = "none"
        value["objective"]["weighted_buy_price"] = 71000.25
        value["objective"]["has_market_data"] = False
        value["charts"][0]["candles"][0]["time"] = 1783659600
        value["charts"][0]["markers"][0]["time"] = 1783659600
        self.assertIsNone(validate_envelope(value))
        schema = review_envelope_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], "review-envelope.v1")

    def test_sealed_snapshot_round_trip_is_deterministic(self):
        value = envelope()
        snapshot = ApprovedReviewSnapshot(value)
        self.assertEqual(json.loads(snapshot.json_text), value)
        reordered = dict(reversed(list(value.items())))
        self.assertEqual(ApprovedReviewSnapshot(reordered).json_text, snapshot.json_text)
        self.assertEqual(ApprovedReviewSnapshot(reordered).digest, snapshot.digest)
        self.assertNotIn("NaN", snapshot.json_text)

    def test_snapshot_owns_bytes_and_does_not_expose_mutable_content(self):
        value = envelope()
        snapshot = ApprovedReviewSnapshot(value)
        original_json = snapshot.json_text
        value["body"]["blocks"][0]["runs"][1]["text"] = "위험"
        value["charts"][0]["markers"][0]["tooltip"]["blocks"][0]["runs"][0]["text"] = "변경"
        value["objective"]["trade_count"] = 999
        self.assertEqual(snapshot.json_text, original_json)
        self.assertEqual(json.loads(snapshot.json_text)["objective"]["trade_count"], 1)
        self.assertFalse(hasattr(snapshot, "to_dict"))
        with self.assertRaises(AttributeError):
            snapshot._json = b"unapproved"
        self.assert_rejected(value)

    def test_snapshot_setstate_rejects_direct_restore(self):
        snapshot = ApprovedReviewSnapshot(envelope())
        original = (snapshot.json_text, snapshot.digest)
        with self.assertRaises(TypeError):
            snapshot.__setstate__((b'{}', "0" * 64))
        with self.assertRaises(TypeError):
            snapshot.__init__(envelope())
        self.assertEqual((snapshot.json_text, snapshot.digest), original)

    def test_snapshot_rejects_bytearray_alias_and_source_mutation(self):
        source = envelope()
        snapshot = ApprovedReviewSnapshot(source)
        external_buffer = bytearray(snapshot.json_text.encode("utf-8"))
        with self.assertRaises(ReviewEnvelopeContractError):
            ApprovedReviewSnapshot(external_buffer)
        with self.assertRaises(TypeError):
            snapshot.__setstate__((external_buffer, snapshot.digest))
        external_buffer[0] = ord("!")
        source["body"]["canonical_text"] = "changed"
        self.assertIs(type(snapshot._json), bytes)
        self.assertEqual(json.loads(snapshot.json_text)["body"]["canonical_text"],
                         "현재는 매수 추천합니다.")

    def test_snapshot_digest_cannot_be_injected(self):
        snapshot = ApprovedReviewSnapshot(envelope())
        correct = hashlib.sha256(snapshot._json).hexdigest()
        with self.assertRaises(TypeError):
            snapshot.__setstate__((snapshot._json, "0" * 64))
        with self.assertRaises(AttributeError):
            snapshot._digest = "0" * 64
        self.assertEqual(snapshot.digest, correct)

    def test_snapshot_refuses_unvalidated_json_bytes_and_pickle(self):
        snapshot = ApprovedReviewSnapshot(envelope())
        with self.assertRaises(ReviewEnvelopeContractError):
            ApprovedReviewSnapshot(b'{"schema_version":"review-envelope.v1","summary":"raw"}')
        with self.assertRaises(TypeError):
            snapshot.__setstate__((b'{"summary":"raw"}', "0" * 64))
        with self.assertRaises(TypeError):
            pickle.dumps(snapshot)

    def test_snapshot_json_round_trip_remains_valid(self):
        original = ApprovedReviewSnapshot(envelope())
        restored = ApprovedReviewSnapshot(json.loads(original.json_text))
        self.assertEqual(restored.json_text, original.json_text)
        self.assertEqual(restored.digest, original.digest)

    def test_card_metrics_full_five_keys_with_nullable_values_pass(self):
        value = envelope()
        metrics = value["chart_cards"][0]["metrics"]
        self.assertEqual(set(metrics), {"rsi14", "return_10d_before", "volume_ratio_20d",
                                        "next_5d_return", "next_20d_return"})
        self.assertIsNone(validate_envelope(value))
        self.assertEqual(set(review_envelope_schema()["properties"]["chart_cards"]["items"]
                             ["properties"]["metrics"]["required"]), set(metrics))

    def test_card_metrics_missing_key_rejects(self):
        value = envelope()
        del value["chart_cards"][0]["metrics"]["next_20d_return"]
        self.assert_rejected(value)

    def test_card_metrics_empty_object_rejects(self):
        value = envelope()
        value["chart_cards"][0]["metrics"] = {}
        self.assert_rejected(value)

    def test_card_metrics_unknown_key_rejects(self):
        value = envelope()
        value["chart_cards"][0]["metrics"]["raw_description"] = "free text"
        self.assert_rejected(value)

    def test_datetime_valid_offsets_and_existing_trade_history_pass(self):
        for suffix in ("+09:00", "Z", "+00:00", "-00:00", "+23:59"):
            value = envelope()
            value["history"]["created_at"] = "2026-07-10T10:00:00" + suffix
            value["trades"][0]["trade_date"] = "2026-07-10T09:30:00" + suffix
            with self.subTest(suffix=suffix):
                self.assertIsNone(validate_envelope(value))

    def test_datetime_invalid_offset_minutes_reject(self):
        for suffix in ("+09:99", "+00:99", "-05:60"):
            for field in ("history", "trade"):
                value = envelope()
                if field == "history":
                    value["history"]["created_at"] = "2026-07-10T10:00:00" + suffix
                else:
                    value["trades"][0]["trade_date"] = "2026-07-10T09:30:00" + suffix
                with self.subTest(suffix=suffix, field=field):
                    self.assert_rejected(value)

    def test_datetime_invalid_offset_hours_reject(self):
        for suffix in ("+24:00", "-24:00", "+99:00"):
            for field in ("history", "trade"):
                value = envelope()
                if field == "history":
                    value["history"]["created_at"] = "2026-07-10T10:00:00" + suffix
                else:
                    value["trades"][0]["trade_date"] = "2026-07-10T09:30:00" + suffix
                with self.subTest(suffix=suffix, field=field):
                    self.assert_rejected(value)

    def test_validation_is_not_an_approval_flag(self):
        value = envelope()
        self.assertIsNone(validate_envelope(value))
        value["approved"] = True
        self.assert_rejected(value)
        del value["approved"]
        value["body"]["canonical_text"] = "mutated after validation"
        self.assert_rejected(value)
        value = envelope()
        original_dumps = json.dumps

        def mutate_during_serialization(source, **kwargs):
            source["summary"] = "raw text added after first validation"
            return original_dumps(source, **kwargs)

        with patch.object(envelope_contract.json, "dumps", side_effect=mutate_during_serialization):
            with self.assertRaises(ReviewEnvelopeContractError):
                ApprovedReviewSnapshot(value)

    def test_unknown_top_nested_and_list_strings_fail_closed(self):
        mutations = [
            lambda v: v.update(free_text="arbitrary"),
            lambda v: v["objective"].update(comment="arbitrary"),
            lambda v: v["charts"][0]["candles"][0].update(detail="arbitrary"),
            lambda v: v["charts"][0]["markers"][0].update(raw_text="arbitrary"),
            lambda v: v["trades"].append({"summary": "arbitrary"}),
        ]
        for mutate in mutations:
            value = envelope()
            mutate(value)
            with self.subTest(mutate=mutate):
                self.assert_rejected(value)

    def test_raw_compatibility_strings_have_no_outbound_slot(self):
        mutations = [
            lambda v: v.update(summary="raw summary"),
            lambda v: v.update(body="raw model semantic string"),
            lambda v: v.update(structured_review={"summary": {"main_issue": "raw model semantics"}}),
            lambda v: v["chart_cards"][0].update(title="raw chart title"),
            lambda v: v["chart_cards"][0].update(detail="raw chart detail"),
            lambda v: v["chart_cards"][0].update(display="raw chart title/detail"),
            lambda v: v["charts"][0].update(header="raw chart header"),
            lambda v: v.update(chart_contexts=[{"error": "free context text"}]),
            lambda v: v["objective"].update(symbol={"name": "raw name"}),
            lambda v: v["trades"][0].update(memo="raw trade memo"),
            lambda v: v.update(notice="raw notice"),
        ]
        for mutate in mutations:
            value = envelope()
            mutate(value)
            with self.subTest(mutate=mutate):
                self.assert_rejected(value)

    def test_unknown_surface_and_valid_surface_in_wrong_position_reject(self):
        value = envelope()
        value["body"]["surface"] = "freeform"
        self.assert_rejected(value)
        value = envelope()
        value["body"]["surface"] = "chart_card"
        self.assert_rejected(value)
        value = envelope()
        value["charts"][0]["markers"][0]["tooltip"]["surface"] = "body"
        self.assert_rejected(value)
        with self.assertRaises(ReviewDisplayContractError):
            validate_document(document("chart_card", "card"))
        self.assertEqual(validate_document(document("chart_card", "card"),
                                           expected_surface="chart_card"), "card")

    def test_unknown_fields_types_and_versions_reject(self):
        mutations = [
            lambda v: v.update(schema_version="review-envelope.v2"),
            lambda v: v["body"].update(schema_version="review-display.v2"),
            lambda v: v["body"]["blocks"][0].update(type="html"),
            lambda v: v["body"]["blocks"][0]["runs"][0].update(type="link"),
            lambda v: v["body"]["blocks"][0]["runs"][0].update(style="bold"),
            lambda v: v["charts"][0].update(extra="raw"),
            lambda v: v["chart_cards"][0]["metrics"].update(extra=3),
        ]
        for mutate in mutations:
            value = envelope()
            mutate(value)
            with self.subTest(mutate=mutate):
                self.assert_rejected(value)

    def test_non_finite_numbers_reject_at_all_typed_paths(self):
        for special in (float("nan"), float("inf"), float("-inf")):
            for path in ("objective", "candle", "metric", "trade"):
                value = envelope()
                if path == "objective":
                    value["objective"]["realized_pnl"] = special
                elif path == "candle":
                    value["charts"][0]["candles"][0]["close"] = special
                elif path == "metric":
                    value["chart_cards"][0]["metrics"]["rsi14"] = special
                else:
                    value["trades"][0]["price"] = special
                with self.subTest(special=repr(special), path=path):
                    self.assert_rejected(value)

    def test_canonical_mismatch_and_invalid_ids_dates_codes_enums_reject(self):
        mutations = [
            lambda v: v["body"].update(canonical_text="현재는 매도 추천합니다."),
            lambda v: v["history"].update(id=0),
            lambda v: v["history"].update(created_at="2026-02-30T10:00:00"),
            lambda v: v["trades"][0].update(ticker="raw semantic"),
            lambda v: v["trades"][0].update(side="hold"),
            lambda v: v["objective"].update(has_market_data=1),
        ]
        for mutate in mutations:
            value = envelope()
            mutate(value)
            with self.subTest(mutate=mutate):
                self.assert_rejected(value)

    def test_list_item_shape_and_cycle_reject(self):
        value = envelope()
        value["charts"][0]["markers"].append("raw marker")
        self.assert_rejected(value)
        value = envelope()
        value["chart_cards"].append(value["chart_cards"])
        self.assert_rejected(value)
