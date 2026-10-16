"""Whole-record history reads: synthetic records/SQLite only, under H4."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.history_legacy_fixture import add_legacy_history_fixture

from core.review_display_contract import SCHEMA_VERSION

import copy
import importlib
import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi import HTTPException
from tests.api_test_modules import api_module_state
from tests.module_isolation import current_boundary
from core.review_legacy_compatibility import admit_legacy_body
from core.review_source_contract import UNAVAILABLE_REVIEW_TEXT
from core.review_history_adapter import history_list_projection
from core.review_envelope_compiler import compile_review_envelope, seal_review_envelope
from core.review_envelope_contract import approved_chart_display_snapshot
from core.review_source_contract import finish_review_source
from tests.review_source_fixtures import approved_chart_fixture, review_input_fixture


SAFE_BODY = "과거 체결 기록과 당시 근거를 확인했습니다."
UNSAFE = "현재는 매수 추천합니다."


def body():
    return {"schema_version": "review-display.v1", "surface": "body",
            "blocks": [{"type": "paragraph", "runs": [
                {"type": "strong", "text": "체결 기록"},
                {"type": "text", "text": "과 당시 근거를 확인했습니다."}], "separator_after": ""}],
            "canonical_text": "체결 기록과 당시 근거를 확인했습니다."}


def legacy_record():
    trade = {"id": 7, "trade_date": "2026-07-10T09:30", "ticker": "005930",
             "name": "합성종목", "side": "buy", "price": 70000, "quantity": 2,
             "fee": 10, "tax": 0, "memo": "당시 체결 근거를 기록했습니다.", "source": "manual"}
    card = {"trade_id": 7, "title": "과거 체결", "detail": "체결 당시 기록을 비교했습니다.",
            "metrics": {"price_vs_close_pct": 1, "ma5": None}}
    chart = {"ticker": "005930", "name": "합성종목", "timeframe": "daily", "interval": "1d",
             "source": "daily OHLCV", "period_label": "2026-07-10",
             "candles": [{"time": "2026-07-10", "label": "2026-07-10", "open": 70000,
                          "high": 71000, "low": 69000, "close": 70500, "volume": 1000,
                          "ma5": None, "ma20": 70000}],
             "markers": [{"time": "2026-07-10", "side": "buy", "text": "B",
                          "position": "belowBar", "color": "#2962ff", "shape": "arrowUp", "size": 2,
                          "trades": [{"id": 7, "date": "2026-07-10T09:30", "price": 70000, "quantity": 2}],
                          "tooltip": {"label": "매수", "count": 1, "avg_price": 70000,
                                      "total_quantity": 2, "prices": [70000]}}],
             "reviews": [card]}
    return {"id": 17, "review_type": "basic", "ticker": "005930", "name": "합성종목",
            "trade_date": "2026-07-10T09:30", "target_trade_id": 7,
            "model": "synthetic-model", "source": "openai", "created_at": "2026-07-10T01:00:00+00:00",
            "trade_snapshot": trade, "recent_trades_snapshot": [copy.deepcopy(trade)],
            "chart_snapshot": {"charts": [chart], "chart_contexts": [], "chart_reviews": [copy.deepcopy(card)]},
            "ai_review": {"status": "ready", "source": "openai", "review_type": "basic",
                          "model": "synthetic-model", "summary": SAFE_BODY, "chart_reviews": [],
                          "chart_contexts": [], "chart_snapshot": {}}, "access_snapshot": {}}


def canonical_record():
    record = legacy_record()
    record["ai_review"].update(display_snapshot=body(), summary="**체결 기록**과 당시 근거를 확인했습니다.")
    return record


def structured_record():
    record = legacy_record()
    record["ai_review"]["summary"] = "별도의 오래된 summary는 표시하지 않습니다."
    record["ai_review"]["structured_review"] = {
        "schema_version": "trade-review.v1", "review_type": "basic", "objective": {},
        "summary": {"decision_quality": {"label": "보통", "explanation": "과거 기록을 확인했습니다."},
                    "main_issue": "당시 근거를 비교했습니다.", "next_action": "복기 기록을 점검합니다."},
        "basic": {"good_points": [{"title": "기록", "detail": "체결 근거가 기록되었습니다."}],
                  "main_improvement": {"title": "복기", "detail": "당시 기록을 비교했습니다."},
                  "next_trade_checks": [{"phase": "before_entry", "text": "판단 근거를 기록합니다."}],
                  "lesson": {"title": "체결 기록", "concept": "과거 근거 확인", "applied_to_this_trade": "당시 기록 비교"}},
    }
    return record


def semantic_record(review_type, canonical):
    record = structured_record()
    if review_type == "advanced":
        from tests.test_review_source_contract import advanced_semantic
        semantic = advanced_semantic()
        common = {"decision_quality", "main_issue", "next_action"}
        structured = record["ai_review"]["structured_review"]
        structured.pop("basic")
        structured.update(review_type=review_type,
                          summary={key: semantic[key] for key in common},
                          advanced={key: value for key, value in semantic.items() if key not in common})
        record["review_type"] = record["ai_review"]["review_type"] = review_type
    if canonical:
        record["ai_review"].update(display_snapshot=body(), summary=admit_legacy_body(body()).summary)
    return record


class HistoryReadAdapterTest(unittest.TestCase):
    def setUp(self):
        self.fixture = self.enterContext(storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"))
        self.modules = self.enterContext(api_module_state())
        self.ai = importlib.import_module("core.ai_review_v2")
        self.main, self.history = self.modules.main, self.modules.review_history
        session = self.modules.account_store.login_dev_provider(
            provider="kakao", provider_user_id="synthetic-history-reader", display_name="합성 이력 사용자")
        self.user_id = session["user"]["id"]
        self.token = f"Bearer {session['session_token']}"
        self.modules.account_store.update_journal_storage_setting(authorization=self.token, enabled=True)

    def adapt(self, record):
        return self.ai.safe_legacy_history_snapshot(record)

    def assert_unavailable(self, record):
        original = copy.deepcopy(record)
        result = self.adapt(record)
        self.assertEqual("unavailable", result["history_read_status"])
        self.assertEqual(UNAVAILABLE_REVIEW_TEXT, result["ai_review"]["display_snapshot"]["canonical_text"])
        self.assertEqual(UNAVAILABLE_REVIEW_TEXT, result["ai_review"]["summary"])
        self.assertEqual((None, [], {}, {}, None, False), (
            result["trade_snapshot"], result["recent_trades_snapshot"], result["chart_snapshot"],
            result["access_snapshot"], result["target_trade_id"], result["trade_restore_allowed"]))
        self.assertEqual("", result["ticker"])
        self.assertEqual("", result["name"])
        self.assertNotIn(UNSAFE, json.dumps(result, ensure_ascii=False))
        self.assertEqual(original, record)
        self.assertEqual(result, self.adapt(record))
        return result

    def save(self, record):
        fields = {key: record[key] for key in (
            "review_type", "ticker", "name", "trade_date", "target_trade_id", "model", "source",
            "trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot")}
        return add_legacy_history_fixture(self.history, user_id=self.user_id, **fields)["id"]

    def db_state(self):
        connection = self.fixture.connect("ALPHAMATE_REVIEW_HISTORY_DB_PATH")
        rows = connection.execute("SELECT * FROM review_history ORDER BY id").fetchall()
        connection.close()
        return (rows, self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes())

    def assert_semantic_routes(self, raw, expected):
        original = copy.deepcopy(raw)
        identity = self.save(raw)  # Synthetic fixture setup precedes read guards.
        before = self.db_state()
        forbidden = [(self.ai, name) for name in ("_call_openai_review", "get_review_stock_ohlcv",
                     "build_journal_charts", "_contexts_for_trades", "_compact_chart_snapshot", "record_event")]
        forbidden += [(self.main, name) for name in ("build_journal_charts", "verify_ai_review_access", "refund_ai_review_access")]
        forbidden += [(self.history, name) for name in ("_connect", "add_review_history", "delete_review_history", "clear_review_history")]
        if expected == "unavailable":
            forbidden.append((importlib.import_module("core.review_history_adapter"), "admit_semantic_source"))
        first = None
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name))) for module, name in forbidden]
            boundary = stack.enter_context(patch.object(self.main, "safe_legacy_history_snapshot", wraps=self.ai.safe_legacy_history_snapshot))
            for _ in range(3):
                rows = self.main.get_journal_review_history(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                detail = self.main.get_journal_review_history_detail(identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                exported = self.main.export_me_data(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
                listed = next(row for row in rows if row["id"] == identity)
                export = next(row for row in exported if row["id"] == identity)
                self.assertEqual(expected, listed["history_read_status"])
                self.assertEqual(history_list_projection(detail), listed)
                self.assertEqual(detail, export)
                current = (listed, detail, export)
                if first is None:
                    first = copy.deepcopy(current)
                self.assertEqual(first, current)
                if expected == "unavailable":
                    self.assertEqual((None, [], {}, False), (detail["trade_snapshot"], detail["recent_trades_snapshot"],
                                                            detail["chart_snapshot"], detail["trade_restore_allowed"]))
                    self.assertEqual(UNAVAILABLE_REVIEW_TEXT, detail["ai_review"]["summary"])
                    self.assertNotIn("합성 unknown semantic 원문", json.dumps(current, ensure_ascii=False))
                elif expected == "canonical":
                    self.assertEqual(raw["ai_review"]["display_snapshot"], detail["ai_review"]["display_snapshot"])
                    self.assertEqual(raw["ai_review"]["summary"], detail["ai_review"]["summary"])
            calls = [call for call in boundary.call_args_list if call.args[0]["id"] == identity]
            self.assertEqual(9, len(calls))
            self.assertTrue(all({"ai_review", "chart_snapshot", "trade_snapshot", "access_snapshot"} <= set(call.args[0]) for call in calls))
            self.assertEqual([0] * len(spies), [spy.call_count for spy in spies])
        self.assertEqual(before, self.db_state())
        self.assertEqual(original, raw)

    def test_summary_unknown_nested_field_with_valid_duplicate_fails_all_read_routes(self):
        for review_type in ("basic", "advanced"):
            for canonical in (False, True):
                with self.subTest(review_type=review_type, canonical=canonical):
                    raw = semantic_record(review_type, canonical)
                    semantic = raw["ai_review"]["structured_review"]
                    semantic[review_type]["decision_quality"] = copy.deepcopy(semantic["summary"]["decision_quality"])
                    semantic["summary"]["decision_quality"]["unknown"] = "합성 unknown semantic 원문"
                    self.assert_semantic_routes(raw, "unavailable")

    def test_summary_object_main_issue_with_valid_duplicate_fails_all_read_routes(self):
        for review_type in ("basic", "advanced"):
            for canonical in (False, True):
                with self.subTest(review_type=review_type, canonical=canonical):
                    raw = semantic_record(review_type, canonical)
                    semantic = raw["ai_review"]["structured_review"]
                    semantic[review_type]["main_issue"] = semantic["summary"]["main_issue"]
                    semantic["summary"]["main_issue"] = {"unknown": "합성 unknown semantic 원문"}
                    self.assert_semantic_routes(raw, "unavailable")

    def test_all_cross_section_duplicates_are_rejected_even_when_equal_and_valid(self):
        for review_type in ("basic", "advanced"):
            for canonical in (False, True):
                for key in ("decision_quality", "main_issue", "next_action"):
                    with self.subTest(review_type=review_type, canonical=canonical, key=key):
                        raw = semantic_record(review_type, canonical)
                        semantic = raw["ai_review"]["structured_review"]
                        semantic[review_type][key] = copy.deepcopy(semantic["summary"][key])
                        self.assert_unavailable(raw)

    def test_original_sections_require_exact_keys_nested_shapes_and_types(self):
        mutations = (
            lambda s, t: s.update(summary=[]),
            lambda s, t: s["summary"].pop("main_issue"),
            lambda s, t: s["summary"].update(main_issue={"unknown": "합성 unknown semantic 원문"}),
            lambda s, t: s["summary"].update(decision_quality=[]),
            lambda s, t: s["summary"]["decision_quality"].update(unknown="合成"),
            lambda s, t: s["summary"]["decision_quality"].pop("explanation"),
            lambda s, t: s["summary"].update(next_action=[]),
            lambda s, t: s["summary"].update(unknown="합성 unknown semantic 원문"),
            lambda s, t: s["summary"].update(data_confidence={"level": "low", "label": "기록", "reasons": [],
                                                          "unknown": "합성 unknown semantic 원문"}, missing_information=[]),
            lambda s, t: s["summary"].update(data_confidence={"level": "low", "label": "기록", "reasons": []},
                                            missing_information={}),
            lambda s, t: s.update({t: []}),
            lambda s, t: s[t].pop("lesson"),
            lambda s, t: s[t]["lesson"].update(unknown="합성 unknown semantic 원문"),
            lambda s, t: s[t]["lesson"].update(title={}),
            lambda s, t: s[t].update({"good_points" if t == "basic" else "detailed_analysis": {}}),
            lambda s, t: s[t]["good_points" if t == "basic" else "detailed_analysis"][0].update(detail=[]),
        )
        for review_type in ("basic", "advanced"):
            for canonical in (False, True):
                for index, mutate in enumerate(mutations):
                    with self.subTest(review_type=review_type, canonical=canonical, mutation=index):
                        raw = semantic_record(review_type, canonical)
                        mutate(raw["ai_review"]["structured_review"], review_type)
                        with patch("core.review_history_adapter.admit_semantic_source", side_effect=AssertionError("unvalidated semantic")) as admission:
                            self.assert_unavailable(raw)
                            self.assertEqual(0, admission.call_count)

    def test_normal_canonical_with_valid_separate_semantics_stays_canonical(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type), patch.object(self.ai, "compile_structured_review", side_effect=AssertionError("semantic rebuild")):
                self.assert_semantic_routes(semantic_record(review_type, True), "canonical")

    def test_normal_supported_semantic_legacy_stays_deterministically_adapted(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                self.assert_semantic_routes(semantic_record(review_type, False), "adapted")

    def chart_record(self):
        record = canonical_record()
        source = review_input_fixture(record["recent_trades_snapshot"], approved_chart_fixture())
        selected = finish_review_source(source, semantic=self.ai._default_basic_semantics(source),
                                        status="ready", origin="chart-rules", notice=None)
        snapshot = seal_review_envelope(compile_review_envelope(selected))
        record["ai_review"]["status"] = "ready"
        record["ai_review"]["chart_display_snapshot"] = approved_chart_display_snapshot(snapshot)
        return record

    def test_closed_chart_projection_is_preserved_without_recompiling_its_documents(self):
        record = self.chart_record()
        expected = copy.deepcopy(record["ai_review"]["chart_display_snapshot"])
        original = copy.deepcopy(record)
        result = self.adapt(record)
        self.assertEqual("canonical", result["history_read_status"])
        self.assertEqual(expected, result["ai_review"]["chart_display_snapshot"])
        self.assertEqual(original, record)
        result["ai_review"]["chart_display_snapshot"]["charts"].clear()
        self.assertEqual(expected, self.adapt(record)["ai_review"]["chart_display_snapshot"])

    def test_unsafe_unknown_and_corrupt_chart_projection_has_no_legacy_fallback(self):
        paths = (("charts", 0, "tab"), ("charts", 0, "header"),
                 ("charts", 0, "markers", 0, "label"), ("charts", 0, "markers", 0, "tooltip"),
                 ("chart_cards", 0, "display"))
        for path in paths:
            record = self.chart_record()
            document = record["ai_review"]["chart_display_snapshot"]
            for key in path:
                document = document[key]
            document["blocks"] = [{"type": "paragraph", "runs": [{"type": "text", "text": UNSAFE}], "separator_after": ""}]
            document["canonical_text"] = UNSAFE
            with self.subTest(path=path):
                self.assert_unavailable(record)
        for mode in ("version", "unknown", "corrupt", "null"):
            record = self.chart_record()
            charts = record["ai_review"]["chart_display_snapshot"]
            if mode == "version": charts["charts"][0]["header"]["schema_version"] = "review-display.v99"
            elif mode == "unknown": charts["charts"][0]["safe_but_unknown"] = "당시 기록"
            elif mode == "corrupt": charts["charts"][0]["tab"]["canonical_text"] = "불일치"
            else: record["ai_review"]["chart_display_snapshot"] = None
            with self.subTest(mode=mode):
                self.assert_unavailable(record)

    def test_new_chart_projection_does_not_bypass_whole_record_legacy_checks(self):
        for surface in ("chart", "tooltip", "trade", "body"):
            record = self.chart_record()
            if surface == "chart": record["chart_snapshot"]["charts"][0]["name"] = UNSAFE
            elif surface == "tooltip": record["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"]["label"] = UNSAFE
            elif surface == "trade": record["trade_snapshot"]["memo"] = UNSAFE
            else: record["ai_review"]["display_snapshot"]["schema_version"] = "review-display.v99"
            with self.subTest(surface=surface):
                self.assert_unavailable(record)

    def test_error_or_bodyless_chart_projection_cannot_admit_a_chart(self):
        for mode in ("error", "empty", "bodyless"):
            record = self.chart_record()
            if mode == "bodyless": record["ai_review"].pop("display_snapshot")
            else: record["ai_review"]["status"] = mode
            with self.subTest(mode=mode):
                self.assert_unavailable(record)

    def test_chart_projection_all_history_routes_keep_snapshot_and_db_bytes(self):
        self.assert_semantic_routes(self.chart_record(), "canonical")

    def test_safe_legacy_whole_record_gets_canonical_body_chart_tooltip_and_trade(self):
        raw = legacy_record()
        raw["access_snapshot"] = {"source": "weekly_ad_advanced"}
        for trade in (raw["trade_snapshot"], raw["recent_trades_snapshot"][0]):
            trade.update(user_id="synthetic-owner", created_at="2026-07-10T01:00:00+00:00")
        original = copy.deepcopy(raw)
        result = self.adapt(raw)
        self.assertEqual("adapted", result["history_read_status"])
        self.assertEqual(SAFE_BODY, result["ai_review"]["summary"])
        self.assertEqual(result["ai_review"]["summary"], admit_legacy_body(result["ai_review"]["display_snapshot"]).summary)
        self.assertIn("display_snapshot", result["trade_snapshot"])
        self.assertIn("display_snapshot", result["chart_snapshot"]["charts"][0])
        self.assertIn("display_snapshot", result["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"])
        self.assertIn("display_snapshot", result["chart_snapshot"]["chart_reviews"][0])
        self.assertTrue(result["trade_restore_allowed"])
        self.assertEqual("synthetic-owner", result["trade_snapshot"]["user_id"])
        self.assertEqual(raw["trade_snapshot"]["created_at"], result["trade_snapshot"]["created_at"])
        self.assertEqual(original, raw)

    def test_supported_structured_legacy_has_one_canonical_display_authority(self):
        raw = structured_record()
        result = self.adapt(raw)
        self.assertEqual("adapted", result["history_read_status"])
        self.assertNotIn("structured_review", result["ai_review"])
        self.assertNotIn(raw["ai_review"]["summary"], json.dumps(result, ensure_ascii=False))
        self.assertEqual(result["ai_review"]["summary"], admit_legacy_body(result["ai_review"]["display_snapshot"]).summary)
        self.assertIn("과거 기록을 확인했습니다.", result["ai_review"]["display_snapshot"]["canonical_text"])

    def test_safe_canonical_preserves_exact_body_strong_wire_without_semantic_rebuild(self):
        raw = canonical_record()
        with patch.object(self.ai, "compile_structured_review", side_effect=AssertionError("semantic rebuild")):
            result = self.adapt(raw)
        self.assertEqual("canonical", result["history_read_status"])
        self.assertEqual(raw["ai_review"], result["ai_review"])
        self.assertIsNot(raw["ai_review"]["display_snapshot"], result["ai_review"]["display_snapshot"])
        self.assertEqual("strong", result["ai_review"]["display_snapshot"]["blocks"][0]["runs"][0]["type"])

    def test_current_persisted_metadata_documents_are_validated_and_preserved(self):
        raw = canonical_record()
        projected = self.adapt(raw)
        for key in ("trade_snapshot", "recent_trades_snapshot", "chart_snapshot"):
            raw[key] = projected[key]
        result = self.adapt(raw)
        self.assertEqual("canonical", result["history_read_status"])
        for key in ("trade_snapshot", "recent_trades_snapshot", "chart_snapshot"):
            self.assertEqual(raw[key], result[key])

    def test_body_safe_chart_unsafe_withholds_whole_record(self):
        raw = legacy_record()
        raw["chart_snapshot"]["charts"][0]["reviews"][0]["detail"] = UNSAFE
        self.assert_unavailable(raw)

    def test_body_unsafe_chart_safe_withholds_whole_record(self):
        raw = legacy_record()
        raw["ai_review"]["summary"] = UNSAFE
        self.assert_unavailable(raw)

    def test_tooltip_unsafe_withholds_whole_record(self):
        raw = legacy_record()
        raw["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"]["label"] = UNSAFE
        self.assert_unavailable(raw)

    def test_trade_name_unsafe_in_target_and_recent_restore_snapshots(self):
        for target in ("target", "recent"):
            with self.subTest(target=target):
                raw = legacy_record()
                trade = raw["trade_snapshot"] if target == "target" else raw["recent_trades_snapshot"][0]
                trade["name"] = UNSAFE
                self.assert_unavailable(raw)

    def test_trade_memo_unsafe_in_target_and_recent_restore_snapshots(self):
        for target in ("target", "recent"):
            with self.subTest(target=target):
                raw = legacy_record()
                trade = raw["trade_snapshot"] if target == "target" else raw["recent_trades_snapshot"][0]
                trade["memo"] = UNSAFE
                self.assert_unavailable(raw)

    def test_split_chart_title_detail_cannot_bypass_whole_record_checks(self):
        raw = legacy_record()
        raw["chart_snapshot"]["chart_reviews"][0].update(title="현재는 매수", detail="추천합니다.")
        self.assert_unavailable(raw)

    def test_split_trade_name_memo_cannot_be_restored(self):
        raw = legacy_record()
        raw["trade_snapshot"].update(name="현재는 매수", memo="추천합니다.")
        self.assert_unavailable(raw)

    def test_unknown_nested_free_form_fields_reject_even_safe_text(self):
        paths = [(), ("ai_review",), ("trade_snapshot",), ("recent_trades_snapshot", 0),
                 ("chart_snapshot",), ("chart_snapshot", "charts", 0),
                 ("chart_snapshot", "charts", 0, "candles", 0),
                 ("chart_snapshot", "charts", 0, "markers", 0),
                 ("chart_snapshot", "charts", 0, "markers", 0, "tooltip"),
                 ("chart_snapshot", "chart_reviews", 0, "metrics"), ("access_snapshot",)]
        for path in paths:
            for text in ("알 수 없는 안전한 필드", UNSAFE):
                with self.subTest(path=path, text=text):
                    raw = legacy_record()
                    parent = raw
                    for key in path:
                        parent = parent[key]
                    parent["unknown"] = {"nested": [{"free_form": text}]}
                    self.assert_unavailable(raw)

    def test_canonical_body_does_not_excuse_separate_unsafe_legacy_chart(self):
        for location in ("stored", "review"):
            with self.subTest(location=location):
                raw = canonical_record()
                if location == "stored":
                    raw["chart_snapshot"]["charts"][0]["name"] = UNSAFE
                else:
                    raw["ai_review"]["chart_reviews"] = [{"title": "과거 체결", "detail": UNSAFE}]
                self.assert_unavailable(raw)

    def test_unknown_canonical_version_never_falls_back_to_safe_raw_summary(self):
        raw = canonical_record()
        raw["ai_review"]["display_snapshot"]["schema_version"] = "review-display.v999"
        raw["ai_review"]["summary"] = SAFE_BODY
        self.assert_unavailable(raw)

    def test_malformed_canonical_documents_never_fall_back_to_legacy(self):
        mutations = [lambda d: d.update(canonical_text=SAFE_BODY), lambda d: d.update(blocks=[]),
                     lambda d: d.update(surface="chart_card"), lambda d: d.update(unknown="safe"),
                     lambda d: d["blocks"][0]["runs"][0].update(type="unknown"),
                     lambda d: d["blocks"][0].update(separator_after="<br>")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                raw = canonical_record()
                mutate(raw["ai_review"]["display_snapshot"])
                self.assert_unavailable(raw)

    def test_invalid_supplied_chart_or_trade_document_is_not_repaired(self):
        for target in ("chart", "trade", "tooltip"):
            with self.subTest(target=target):
                raw = canonical_record()
                original = self.adapt(raw)
                key = "chart_snapshot" if target in ("chart", "tooltip") else "trade_snapshot"
                raw[key] = original[key]
                item = raw["chart_snapshot"]["charts"][0] if target == "chart" else raw["trade_snapshot"]
                if target == "tooltip":
                    item = raw["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"]
                item["display_snapshot"] = body()
                self.assert_unavailable(raw)

    def test_unknown_or_malformed_structured_legacy_has_no_raw_summary_fallback(self):
        for change in ("version", "shape", "objective"):
            with self.subTest(change=change):
                raw = structured_record()
                structured = raw["ai_review"]["structured_review"]
                if change == "version":
                    structured["schema_version"] = "trade-review.v999"
                elif change == "shape":
                    structured["basic"]["good_points"] = {"nested": "safe"}
                else:
                    structured["objective"] = {"unknown": {"nested": "safe"}}
                self.assert_unavailable(raw)

    def test_unknown_canonical_semantic_fields_are_closed_without_rebuilding_body(self):
        raw = structured_record()
        raw["ai_review"].update(display_snapshot=body(), summary="**체결 기록**과 당시 근거를 확인했습니다.")
        raw["ai_review"]["structured_review"]["basic"]["lesson"]["unknown"] = "safe"
        self.assert_unavailable(raw)

    def test_wrong_canonical_compatibility_wire_is_withheld(self):
        raw = canonical_record()
        raw["ai_review"]["summary"] = raw["ai_review"]["display_snapshot"]["canonical_text"]
        self.assert_unavailable(raw)

    def test_midword_strong_and_unsupported_annotations_are_unsafe(self):
        for summary in ("현재는 매**수** 추천합니다.", "목표[데이터 확인]가: 80,000원입니다."):
            with self.subTest(summary=summary):
                raw = legacy_record()
                raw["ai_review"]["summary"] = summary
                self.assert_unavailable(raw)

    def test_invalid_scalar_shapes_and_nonfinite_numbers_fail_closed(self):
        for path, value in [(("target_trade_id",), True), (("review_type",), "future"),
                            (("created_at",), "bad date"), (("name",), [SAFE_BODY]),
                            (("trade_snapshot", "price"), float("inf")),
                            (("chart_snapshot", "charts", 0, "markers", 0, "tooltip", "count"), "1"),
                            (("trade_snapshot", "price"), -1), (("trade_snapshot", "quantity"), 0),
                            (("trade_snapshot", "fee"), -1), (("created_at",), "2026-07-10T01:00:00+00:99"),
                            (("chart_snapshot", "charts", 0, "timeframe"), "weekly"),
                            (("chart_snapshot", "charts", 0, "source"), "weekly OHLCV"),
                            (("chart_snapshot", "charts", 0, "candles", 0, "label"), "unknown label"),
                            (("chart_snapshot", "charts", 0, "markers", 0, "position"), "aboveBar"),
                            (("chart_snapshot", "charts", 0, "markers", 0, "size"), 999),
                            (("chart_snapshot", "charts", 0, "markers", 0, "tooltip", "count"), 2)]:
            with self.subTest(path=path):
                raw = legacy_record()
                parent = raw
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                self.assert_unavailable(raw)

    def test_cyclic_or_non_json_records_return_only_fixed_content(self):
        raw = legacy_record()
        raw["unknown"] = raw
        result = self.adapt(raw)
        self.assertEqual("unavailable", result["history_read_status"])
        self.assertEqual(UNAVAILABLE_REVIEW_TEXT, result["ai_review"]["summary"])
        self.assertEqual("unavailable", self.adapt([legacy_record()])["history_read_status"])
        self.assertEqual("unavailable", self.adapt({"id": UNSAFE, "review_type": []})["history_read_status"])

    def test_repeat_reads_are_deterministic_and_return_independent_copies(self):
        for raw in (legacy_record(), canonical_record(), structured_record()):
            with self.subTest(canonical="display_snapshot" in raw["ai_review"]):
                original = copy.deepcopy(raw)
                first, second = self.adapt(raw), self.adapt(raw)
                self.assertNotEqual("unavailable", first["history_read_status"])
                self.assertEqual(json.dumps(first, ensure_ascii=False, sort_keys=True), json.dumps(second, ensure_ascii=False, sort_keys=True))
                first["ai_review"]["display_snapshot"]["blocks"][0]["runs"][0]["text"] = "changed copy"
                first["trade_snapshot"]["name"] = "changed trade"
                self.assertEqual(original, raw)
                self.assertEqual(second, self.adapt(raw))

    def test_adapter_calls_no_model_provider_chart_billing_or_storage_operations(self):
        forbidden = [(self.ai, name) for name in ("_call_openai_review", "get_review_stock_ohlcv",
                     "build_journal_charts", "_contexts_for_trades", "_compact_chart_snapshot", "record_event")]
        forbidden += [(self.main, name) for name in ("build_journal_charts", "verify_ai_review_access", "refund_ai_review_access")]
        forbidden += [(self.history, name) for name in ("_connect", "_read_connect", "add_review_history", "delete_review_history", "clear_review_history")]
        unsafe = legacy_record()
        unsafe["trade_snapshot"]["memo"] = UNSAFE
        unknown = canonical_record()
        unknown["ai_review"]["display_snapshot"]["schema_version"] = "unknown"
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name))) for module, name in forbidden]
            for raw in (legacy_record(), structured_record(), canonical_record(), unsafe, unknown):
                self.adapt(raw)
            self.assertEqual([0] * len(spies), [spy.call_count for spy in spies])

    def test_list_detail_export_all_admit_full_rows_through_the_same_boundary(self):
        raw = canonical_record()
        raw["chart_snapshot"]["charts"][0]["reviews"][0]["detail"] = UNSAFE
        identity = self.save(raw)
        with patch.object(self.main, "safe_legacy_history_snapshot", wraps=self.ai.safe_legacy_history_snapshot) as boundary:
            rows = self.main.get_journal_review_history(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
            detail = self.main.get_journal_review_history_detail(identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
            exported = self.main.export_me_data(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
        self.assertEqual(3, boundary.call_count)
        for call in boundary.call_args_list:
            self.assertTrue({"ai_review", "chart_snapshot", "trade_snapshot", "access_snapshot"} <= set(call.args[0]))
            self.assertEqual(UNSAFE, call.args[0]["chart_snapshot"]["charts"][0]["reviews"][0]["detail"])
        self.assertEqual([history_list_projection(detail)], rows)
        self.assertEqual([detail], exported)
        self.assertEqual("unavailable", detail["history_read_status"])

    def test_synthetic_db_values_and_bytes_do_not_change_for_safe_unsafe_unknown_reads(self):
        unsafe, unknown = legacy_record(), canonical_record()
        unsafe["trade_snapshot"]["memo"] = UNSAFE
        unknown["ai_review"]["display_snapshot"]["schema_version"] = "future"
        identities = [self.save(raw) for raw in (legacy_record(), canonical_record(), structured_record(), unsafe, unknown)]
        before = self.db_state()
        first = None
        for _ in range(3):
            rows = self.main.get_journal_review_history(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
            details = [self.main.get_journal_review_history_detail(identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION]) for identity in identities]
            exported = self.main.export_me_data(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
            current = (rows, details, exported)
            if first is None:
                first = copy.deepcopy(current)
            self.assertEqual(first, current)
        self.assertEqual(["adapted", "canonical", "adapted", "unavailable", "unavailable"], [item["history_read_status"] for item in first[1]])
        self.assertEqual(before, self.db_state())

    def test_history_store_reads_are_select_only_and_use_read_only_connections(self):
        identity = self.save(legacy_record())
        before = self.db_state()
        original = self.history.sqlite3.connect
        calls, statements = [], []

        def connect(database, *args, **kwargs):
            calls.append((database, kwargs))
            connection = original(database, *args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection

        with patch.object(self.history, "_connect", side_effect=AssertionError("schema initialization")), patch.object(
                self.history.sqlite3, "connect", side_effect=connect):
            self.history.list_review_history(user_id=self.user_id)
            self.history.get_review_history(identity, user_id=self.user_id)
        self.assertEqual(2, len(calls))
        self.assertTrue(all(database.endswith("?mode=ro") and kwargs.get("uri") is True for database, kwargs in calls))
        self.assertEqual(2, len(statements))
        self.assertTrue(all(statement.lstrip().startswith("SELECT ") for statement in statements))
        self.assertEqual(before, self.db_state())

    def test_missing_history_db_reads_do_not_create_file_or_parent(self):
        path = self.fixture.root / "never-created" / "history.sqlite3"
        with patch.object(self.history, "_db_path", return_value=path):
            self.assertEqual([], self.history.list_review_history(user_id=self.user_id))
            self.assertIsNone(self.history.get_review_history(1, user_id=self.user_id))
        self.assertFalse(path.parent.exists())

    def test_read_only_uri_outside_h4_root_is_blocked_before_connect(self):
        boundary = current_boundary()
        outside = boundary.root.parent / "never-open-history.sqlite3"
        with boundary.expect_violation("write"):
            self.history.sqlite3.connect(outside.as_uri() + "?mode=ro", uri=True)
        self.assertFalse(outside.exists())

    def test_unapproved_sqlite_uri_variants_are_blocked_before_connect(self):
        boundary = current_boundary()
        path = self.fixture.root / "never-open-uri.sqlite3"
        variants = [(path.as_uri() + "?mode=ro", False),
                    (path.as_uri() + "?mode=rw", True),
                    (path.as_uri() + "?mode=rwc", True),
                    (path.as_uri() + "?mode=ro&cache=shared", True),
                    (path.as_uri() + "?mode=ro#fragment", True),
                    ("file://remote-host/history.sqlite3?mode=ro", True),
                    ("file:relative.sqlite3?mode=ro", True)]
        for uri, enabled in variants:
            with self.subTest(uri=uri), boundary.expect_violation("sqlite-uri"):
                self.history.sqlite3.connect(uri, uri=enabled)
        self.assertFalse(path.exists())

    def test_corrupt_and_duplicate_stored_json_fail_closed_without_db_repair(self):
        for column in ("trade_snapshot_json", "recent_trades_snapshot_json", "chart_snapshot_json", "ai_review_json", "access_snapshot_json"):
            for payload in ("{broken", '{"summary":"safe","summary":"duplicate"}'):
                with self.subTest(column=column, payload=payload):
                    identity = self.save(canonical_record())
                    connection = self.fixture.connect("ALPHAMATE_REVIEW_HISTORY_DB_PATH")
                    # Synthetic fixture corruption is setup, never read adaptation.
                    connection.execute(f"UPDATE review_history SET {column} = ? WHERE id = ?", (payload, identity))
                    connection.commit()
                    connection.close()
                    before = self.db_state()
                    detail = self.main.get_journal_review_history_detail(identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                    self.assertEqual("unavailable", detail["history_read_status"])
                    self.assertEqual(before, self.db_state())

    def test_partial_trade_metadata_is_not_offered_as_restoration_input(self):
        raw = legacy_record()
        raw["trade_snapshot"] = {"id": 7, "ticker": "005930", "name": "합성종목"}
        raw["recent_trades_snapshot"] = [{"id": 7}]
        result = self.adapt(raw)
        self.assertEqual("adapted", result["history_read_status"])
        self.assertFalse(result["trade_restore_allowed"])
        self.assertIsNone(result["trade_snapshot"])
        self.assertEqual([], result["recent_trades_snapshot"])

    def test_history_ownership_and_storage_opt_in_still_apply(self):
        identity = self.save(legacy_record())
        self.assertIsNone(self.history.get_review_history(identity, user_id="synthetic-other-user"))
        self.assertEqual([], self.history.list_review_history(user_id="synthetic-other-user"))
        self.modules.account_store.update_journal_storage_setting(authorization=self.token, enabled=False)
        self.assertEqual([], self.main.get_journal_review_history(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION]))
        with self.assertRaises(HTTPException) as error:
            self.main.get_journal_review_history_detail(identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
        self.assertEqual(403, error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
