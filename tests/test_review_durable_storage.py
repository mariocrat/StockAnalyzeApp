"""Slice 3A pure storage/authority contracts, exclusively under official H4."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
from datetime import datetime, timedelta
import importlib
import json
import math
from pathlib import Path
import pickle
import unittest
from unittest.mock import patch
from weakref import WeakKeyDictionary

from core import review_history_json_codec as codec
from core import review_durable_storage_contract as contract
from core import review_durable_storage_approval as approval
from core import review_history_prepared_content as prepared
from core.review_history_approved_write import approve_history_write
from core.review_approval_bundle import compile_approval_bundle
from core.review_envelope_compiler import compile_review_envelope, seal_review_envelope
from core.review_display_contract import compile_literal_lines
from core.review_legacy_compatibility import admit_legacy_body
from core import review_source_contract as source_contract
from core.review_source_projection import structured_review_payload, trade_payload
from tests.test_review_display_contract import (
    ready_v2_source, _canonical_import_accesses, _has_guarded_review_wildcard_import,
)
from tests.review_source_fixtures import approved_chart_fixture
from tests import test_review_history_write_access as access_tests
from tests.api_test_modules import api_module_state
from tests.test_review_finalizer_compatibility import model_output


def metadata_trade(source):
    row = dict(trade_date=source.trade_date, ticker=source.ticker, name=source.name,
               side=source.side, price=float(source.price), quantity=float(source.quantity),
               fee=float(source.fee), tax=float(source.tax), memo=source.memo, source=source.source)
    labels = (("trade_date", "체결일"), ("ticker", "종목 코드"), ("name", "종목"),
              ("side", "구분"), ("memo", "메모"), ("source", "기록 출처"))
    lines = ["매매 기록", *(label + ": " + row[key] for key, label in labels if row[key]),
             "종목 및 메모: " + row["name"] + " " + row["memo"]]
    row["display_snapshot"] = compile_literal_lines(lines)
    return row


def sql_chart_a():
    name, detail = "합성 SQL 차트", "과거 체결 기록입니다."
    return {"charts": [{"ticker": "005930", "name": name, "timeframe": "daily", "interval": "1d",
        "source": "daily OHLCV", "period_label": "2026-07-10",
        "candles": [{"time": "2026-07-10", "label": "2026-07-10", "open": 70000.0,
                     "high": 72000.0, "low": 69000.0, "close": 70500.0, "volume": 1000.0,
                     "ma5": None, "ma20": None}], "markers": [],
        "reviews": [{"title": name, "detail": detail, "trade_id": None,
                     "metrics": {"price_vs_close_pct": 0.0, "after_5_bars": None,
                                 "after_later_bars": None, "ma5": None, "ma20": None},
                     "display_snapshot": compile_literal_lines([name + ": " + detail,
                                                                "체결가와 봉 종가 차이: 0.0%"])}],
        "display_snapshot": compile_literal_lines(["매매 차트", "종목: " + name, "종목 코드: 005930",
            "차트 주기: daily", "봉 간격: 1d", "기간: 2026-07-10", "차트 출처: daily OHLCV"])}]}


def fixture(review_type="basic", *, empty=False, cards=True, sell_only=False, owner="synthetic-owner"):
    base = ready_v2_source("basic-high" if review_type == "basic" else "advanced-low")
    chart = approved_chart_fixture()
    if not cards:
        chart["rule_based_observations"] = []
    charts = () if empty else (source_contract.admit_chart_source(chart),)
    trades, objective = base.trades, base.objective
    if sell_only:
        trades = tuple(source_contract.admit_trade_source(dict(trade_payload(trade), side="sell")) for trade in trades)
        objective = importlib.import_module("core.ai_review_v2")._objective_review_snapshot(trades)
    source = source_contract.compose_review_source(review_type=review_type, trades=trades,
        objective=objective, charts=charts, analysis_contexts=base.analysis_contexts,
        semantic=source_contract.admit_semantic_source(model_output(review_type), review_type), status="ready", origin="openai")
    envelope = compile_review_envelope(source)
    snapshot = seal_review_envelope(envelope)
    trades = [metadata_trade(trade) for trade in source.trades]
    meta = {**{key: trades[-1][key] for key in ("ticker", "name", "trade_date")},
            "target_trade_id": 999, "trade_snapshot": trades[-1], "recent_trades_snapshot": trades,
            "chart_snapshot": sql_chart_a()}
    result = dict(status="ready", source="openai", review_type=review_type, model="synthetic-model",
        summary=admit_legacy_body(envelope["body"]).summary, display_snapshot=envelope["body"],
        structured_review=structured_review_payload(source), chart_contexts=[], chart_reviews=[],
        chart_display_snapshot={key: envelope[key] for key in ("charts", "chart_cards")})
    result["chart_snapshot" if review_type == "basic" else "chart_snapshots"] = {} if review_type == "basic" else []
    prepared_content = prepared.prepare_history_content(metadata=meta, result=result, snapshot=snapshot,
        finalizer_model=result["model"], _authority=prepared._CAPTURE)
    access = access_tests.access_fixture(review_type=review_type)
    record = dict(meta, user_id=owner, review_type=review_type, model=result["model"],
                  source="openai", created_at="2026-10-13T01:02:03+00:00",
                  ai_review=dict(result, access=access), access_snapshot=copy.deepcopy(access))
    return assemble(source, snapshot, prepared_content, record)


def assemble(source, snapshot, prepared_content, record):
    bundle = compile_approval_bundle(source)
    capture = approval.capture_live_paired_history(source=source, snapshot=snapshot,
        prepared_content=prepared_content, bundle=bundle, _authority=approval._FINALIZER_CAPTURE)
    write = approve_history_write(record=record, prepared_content=prepared_content, snapshot=snapshot)
    durable = approval.issue_durable_history(capture=capture, approved_write=write, row_id=17)
    context = {key: 17 if key == "id" else record[key] for key in contract.CONTEXT_KEYS}
    sql = {key: codec.sql_json(record[key]) for key in contract.SNAPSHOT_KEYS}
    return dict(source=source, snapshot=snapshot, prepared=prepared_content, bundle=bundle,
                capture=capture, write=write, durable=durable, context=context, sql=sql, record=record)


def unsafe_text(text):
    # Existing policy provided by the isolated caller, never imported by 3A.
    return importlib.import_module("core.ai_review_v2")._contains_prohibited_trade_guidance(text)


class DurableStorageTest(unittest.TestCase):
    def reject(self, call, code):
        with self.assertRaises(codec.DurableStorageError) as raised:
            call()
        self.assertEqual(code, raised.exception.code)
        self.assertEqual(code, str(raised.exception))

    def read(self, value, **kwargs):
        return approval.read_durable_history(value["durable"].bytes,
            row_context=kwargs.get("context", value["context"]), sql_snapshots=kwargs.get("sql", value["sql"]),
            unsafe_text=unsafe_text)

    def payload(self, value):
        return json.loads(json.loads(value["durable"].bytes)["payload"])

    def test_deterministic_sorted_unicode_and_numeric_codec_goldens(self):
        value = {"한글": "e\u0301 😀 \" \\", "a": [None, True, 1, 1.0, -0.0, 0.0, 5e-324, 1.7976931348623157e308]}
        encoded = codec.canonical_json(value)
        self.assertEqual(encoded, codec.canonical_json(dict(reversed(list(value.items())))))
        self.assertIn(b'[null,true,1,1.0,-0.0,0.0,5e-324,1.7976931348623157e+308]', encoded)
        decoded = codec.decode_json(encoded, canonical=True)
        self.assertIs(type(decoded["a"][2]), int)
        self.assertIs(type(decoded["a"][3]), float)
        self.assertEqual(-1, math.copysign(1, decoded["a"][4]))
        self.assertEqual(value["한글"], decoded["한글"])

    def test_nonfinite_duplicate_keys_surrogates_and_invalid_utf8_reject(self):
        for number in (float("nan"), float("inf"), -float("inf")):
            self.reject(lambda: codec.canonical_json(number), "NONFINITE")
        for raw in (b'NaN', b'Infinity', b'-Infinity', b'1e9999'):
            self.reject(lambda: codec.decode_json(raw), "NONFINITE")
        self.reject(lambda: codec.decode_json(b'{"a":1,"a":2}'), "DUPLICATE_KEY")
        self.reject(lambda: codec.canonical_json(chr(0xD800)), "SURROGATE")
        self.reject(lambda: codec.decode_json(b'"\\ud800"'), "SURROGATE")
        self.reject(lambda: codec.decode_json(b'"\xff"'), "INVALID_JSON")

    def test_nonplain_keys_subclasses_cycles_and_noncanonical_bytes_reject(self):
        class String(str):
            pass
        class Dictionary(dict):
            pass
        for value in (String("a"), Dictionary(a=1), {1: "a"}, (1,), object()):
            self.reject(lambda: codec.canonical_json(value), "INVALID_JSON_TYPE")
        cycle = []; cycle.append(cycle)
        self.reject(lambda: codec.canonical_json(cycle), "JSON_CYCLE")
        for raw in (b'{ "a":1}', b'{"b":1,"a":2}', b'1e0', b'"\\u0041"', b'{}\n'):
            self.reject(lambda: codec.decode_json(raw, canonical=True), "NONCANONICAL_JSON")

    def test_paired_roundtrip_both_types_and_whole_display_identity(self):
        for kind in ("basic", "advanced"):
            value = fixture(kind)
            before = copy.deepcopy(value["record"])
            reopened = self.read(value)
            self.assertIs(type(reopened), approval.DurableReadAdmission)
            self.assertEqual(kind, reopened.payload["bundle"]["review_type"])
            for field in ("summary", "display_snapshot", "chart_display_snapshot"):
                self.assertEqual(value["record"]["ai_review"][field], reopened.projection[field])
            self.assertEqual(before, value["record"])

    def test_sql_chart_a_is_distinct_and_never_replaces_ai_chart_b_or_cards(self):
        value = fixture()
        read = self.read(value)
        self.assertEqual(70500.0, read.journal_chart_snapshot["charts"][0]["candles"][0]["close"])
        self.assertEqual(71234, read.projection["chart_display_snapshot"]["charts"][0]["candles"][0]["close"])
        self.assertEqual(1, len(read.projection["chart_display_snapshot"]["chart_cards"]))
        self.assertNotEqual(read.journal_chart_snapshot["charts"], read.projection["chart_display_snapshot"]["charts"])

    def test_approved_empty_auxiliary_roundtrip_without_replacement(self):
        for kind in ("basic", "advanced"):
            read = self.read(fixture(kind, empty=True))
            self.assertEqual({"charts": [], "chart_cards": []}, read.projection["chart_display_snapshot"])
            self.assertTrue(read.journal_chart_snapshot["charts"])
        chart_only = self.read(fixture(cards=False)).projection["chart_display_snapshot"]
        self.assertTrue(chart_only["charts"])
        self.assertEqual([], chart_only["chart_cards"])

    def test_digest_domains_match_independent_framing_and_change_with_domains(self):
        import hashlib
        raw = b'{}'
        fields = (b'review-history-paired.v1', b'paired_v1_v2', b'review-history-json.v1', raw)
        framed = b''.join(len(b).to_bytes(8, 'big') + b for b in fields)
        expected = hashlib.sha256(b'StockBoda-review-history-paired-v1\x00' + framed).hexdigest()
        self.assertEqual(expected, contract.payload_digest(raw))
        self.assertNotEqual(expected, contract.payload_digest(raw, codec="future"))
        frames = (b'review-history-json.v1', b'chart_snapshot', raw)
        expected_snapshot = hashlib.sha256(b'StockBoda-review-history-snapshot-v1\x00' +
            b''.join(len(b).to_bytes(8, 'big') + b for b in frames)).hexdigest()
        self.assertEqual(expected_snapshot, contract.snapshot_digest("chart_snapshot", {}))
        self.assertNotEqual(expected_snapshot, contract.snapshot_digest("access_snapshot", {}))

    def test_malformed_markers_versions_kinds_and_unknown_keys_never_fallback(self):
        value = fixture()
        original = json.loads(value["durable"].bytes)
        cases = [(dict(original, storage_schema_version="future"), "INVALID_STORAGE_VERSION"),
                 (dict(original, kind="v1_only"), "INVALID_STORAGE_KIND"),
                 (dict(original, codec_version="future"), "INVALID_CODEC_VERSION"),
                 (dict(original, payload_digest="x" * 64), "INVALID_DIGEST")]
        for field in original:
            cases.append(({key: child for key, child in original.items() if key != field}, "INVALID_KEYS"))
        for bad in ({}, {"summary": "legacy"}, {"representations": {}}, {"kind": None}):
            # An empty nested object has depth one; closed keys reject it.
            cases.append((bad, "INVALID_KEYS"))
        cases.append((dict(original, extra="unknown"), "NODE_LIMIT"))
        for outer, code in cases:
            raw = json.dumps(outer, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            self.reject(lambda: approval.read_durable_history(raw, row_context=value["context"], sql_snapshots=value["sql"]), code)

    def test_noncanonical_outer_inner_duplicate_and_byte_carriers_reject(self):
        value = fixture(); original = json.loads(value["durable"].bytes)
        self.reject(lambda: approval.read_durable_history(value["durable"].bytes + b'\n',
            row_context=value["context"], sql_snapshots=value["sql"]), "NONCANONICAL_JSON")
        for raw, code in ((b'{"a":1,"a":2}', "DUPLICATE_KEY"), (b'{ "a":1}', "NONCANONICAL_JSON")):
            outer = dict(original, payload=raw.decode(), payload_digest=contract.payload_digest(raw))
            self.reject(lambda: approval.read_durable_history(codec.outer_json(outer),
                row_context=value["context"], sql_snapshots=value["sql"]), code)

    def test_payload_mutation_or_digest_mutation_rejects_before_projection(self):
        value = fixture(); outer = json.loads(value["durable"].bytes)
        for changed in (dict(outer, payload=outer["payload"].replace("synthetic-owner", "other-owner")),
                        dict(outer, payload_digest="0" * 64)):
            self.reject(lambda: approval.read_durable_history(codec.outer_json(changed),
                row_context=value["context"], sql_snapshots=value["sql"]), "DIGEST_MISMATCH")

    def test_every_actual_row_context_column_is_bound_with_exact_types(self):
        value = fixture()
        changes = {"id": 18, "user_id": "other-owner", "review_type": "advanced", "ticker": "000660",
            "name": "다른 이름", "trade_date": "2026-02-01", "target_trade_id": None,
            "model": "another-model", "created_at": "2026-10-13T02:02:03+00:00"}
        for field, replacement in changes.items():
            context = dict(value["context"], **{field: replacement})
            self.reject(lambda: self.read(value, context=context), "ROW_CONTEXT_MISMATCH")
        for context in (dict(value["context"], id=True), dict(value["context"], target_trade_id=999.0),
                        dict(value["context"], source="chart-rules")):
            self.reject(lambda: self.read(value, context=context), "INVALID_ROW_CONTEXT")

    def test_all_four_snapshot_columns_are_bound_and_sql_spacing_is_insignificant(self):
        value = fixture()
        changes = {}
        trade = copy.deepcopy(value["record"]["trade_snapshot"]); trade["price"] += 1
        changes["trade_snapshot"] = trade
        recent = copy.deepcopy(value["record"]["recent_trades_snapshot"]); recent[0]["price"] += 1
        changes["recent_trades_snapshot"] = recent
        chart = copy.deepcopy(value["record"]["chart_snapshot"]); chart["charts"][0]["candles"][0]["close"] += 1
        changes["chart_snapshot"] = chart
        access = copy.deepcopy(value["record"]["access_snapshot"])
        for parent in (access["wallet"], access["quota"]):
            parent["basic"]["signup_remaining"] = 3; parent["basic"]["free_available_now"] = 4
        changes["access_snapshot"] = access
        for field, changed in changes.items():
            self.reject(lambda: self.read(value, sql=dict(value["sql"], **{field: codec.sql_json(changed)})),
                        "SNAPSHOT_DIGEST_MISMATCH")
        pretty = {key: json.dumps(json.loads(raw), ensure_ascii=False, indent=2) for key, raw in value["sql"].items()}
        self.assertEqual(self.read(value).payload, self.read(value, sql=pretty).payload)
        self.reject(lambda: self.read(value, sql=dict(value["sql"], chart_snapshot=b'{"charts":[],"charts":[]}')),
                    "DUPLICATE_KEY")

    def test_invalid_sql_with_recomputed_snapshot_checksum_still_rejects(self):
        value = fixture(); payload = self.payload(value)
        bad = copy.deepcopy(value["record"]["chart_snapshot"])
        bad["charts"][0]["candles"][0]["volume"] = -1.0
        payload["snapshot_digests"]["chart_snapshot"] = contract.snapshot_digest("chart_snapshot", bad)
        raw = contract.encode_envelope(payload)
        self.reject(lambda: approval.read_durable_history(raw, row_context=value["context"],
            sql_snapshots=dict(value["sql"], chart_snapshot=codec.sql_json(bad))), "INVALID_SQL_SNAPSHOT")

    def test_auxiliary_missing_malformed_mutated_and_unknown_fields_fail_closed(self):
        value = fixture()
        for replacement, code in ((None, "INVALID_CHART_AUXILIARY"), ({"charts": []}, "INVALID_CHART_AUXILIARY")):
            payload = self.payload(value); payload["chart_display_snapshot"] = replacement
            self.reject(lambda: contract.encode_envelope(payload), code)
        payload = self.payload(value); del payload["chart_display_snapshot"]
        self.reject(lambda: contract.encode_envelope(payload), "INVALID_KEYS")
        outer = json.loads(value["durable"].bytes); payload = json.loads(outer["payload"])
        payload["chart_display_snapshot"]["chart_cards"][0]["metrics"]["rsi14"] = 7.0
        outer["payload"] = codec.canonical_json(payload).decode()
        self.reject(lambda: approval.read_durable_history(codec.outer_json(outer),
            row_context=value["context"], sql_snapshots=value["sql"]), "DIGEST_MISMATCH")
        payload["chart_display_snapshot"]["chart_cards"][0]["unknown"] = "unsafe"
        self.reject(lambda: contract.encode_envelope(payload), "INVALID_CHART_AUXILIARY")

    def test_body_corruption_rejects_whole_pair_even_with_recomputed_digest(self):
        value = fixture()
        def rejected_read(payload, code):
            # Deliberately bypass the semantic encoder: a public checksum can
            # be recomputed by an attacker and must not authorize admission.
            inner = codec.canonical_json(payload)
            outer = json.loads(value["durable"].bytes)
            outer["payload"] = inner.decode("utf-8")
            outer["payload_digest"] = contract.payload_digest(inner)
            self.reject(lambda: approval.read_durable_history(codec.outer_json(outer),
                row_context=value["context"], sql_snapshots=value["sql"], unsafe_text=unsafe_text), code)
        for version in ("v1", "v2"):
            payload = self.payload(value)
            del payload["bundle"]["representations"][version]
            self.reject(lambda: contract.encode_envelope(payload), "BUNDLE_" + version.upper() + "_MISSING")
            rejected_read(payload, "BUNDLE_" + version.upper() + "_MISSING")
            payload = self.payload(value)
            payload["bundle"]["representations"][version]["document"]["canonical_text"] += " changed"
            rejected_read(payload, "BUNDLE_V1_DOCUMENT_INVALID" if version == "v1" else "BUNDLE_CANONICAL_TEXT_MISMATCH")
        payload = self.payload(value); payload["bundle"]["representations"]["v2"]["compiler_version"] = "future"
        self.reject(lambda: contract.encode_envelope(payload), "BUNDLE_COMPILER_VERSION_MISMATCH")
        rejected_read(payload, "BUNDLE_COMPILER_VERSION_MISMATCH")

    def test_complete_objective_hidden_fields_types_and_identity_are_preserved(self):
        value = fixture(); payload = self.payload(value)
        for key in ("weighted_sell_price", "total_tax", "open_quantity", "symbol_count"):
            self.assertIn(key, payload["objective"]["fields"]["result"]["fields"])
        payload["objective"]["fields"]["result"]["fields"]["total_tax"] = -0.0
        self.reject(lambda: contract.encode_envelope(payload), "OBJECTIVE_IDENTITY_MISMATCH")
        payload = self.payload(value); payload["objective"]["fields"]["symbol"]["fields"]["symbol_kind"] = "name_only"
        self.reject(lambda: contract.encode_envelope(payload), "INVALID_OBJECTIVE")
        payload = self.payload(value); payload["objective"]["extra"] = 1
        self.reject(lambda: contract.encode_envelope(payload), "INVALID_KEYS")
        sell_only = fixture(sell_only=True)
        nullable = self.read(sell_only).payload["objective"]["fields"]["result"]["fields"]
        self.assertIsNone(nullable["weighted_buy_price"])
        # The existing backend determines SELL-only accounting; storage neither
        # replaces it with zero nor changes its type/meaning in this slice.
        self.assertEqual(sell_only["source"].objective.result.realized_pnl, nullable["realized_pnl"])
        self.assertIs(type(sell_only["source"].objective.result.realized_pnl), type(nullable["realized_pnl"]))
        self.assertIs(type(nullable["trade_count"]), int)

    def test_restart_equivalent_read_needs_no_live_issuance_receipt_or_compiler(self):
        value = fixture(); raw = bytes(value["durable"].bytes)
        with patch.object(approval, "_ISSUED", WeakKeyDictionary()), patch(
                "core.review_approval_bundle.compile_approval_bundle", side_effect=AssertionError("compile")), patch(
                "core.review_display_v2_compiler.compile_body", side_effect=AssertionError("compile")), patch(
                "core.review_approval_bundle.compile_review_body", side_effect=AssertionError("compile")), patch.object(
                approval, "compile_review_envelope", side_effect=AssertionError("compile")):
            restored = approval.read_durable_history(raw, row_context=value["context"], sql_snapshots=value["sql"],
                                                     unsafe_text=unsafe_text)
            self.assertEqual(value["record"]["ai_review"]["summary"], restored.projection["summary"])
            self.reject(lambda: approval.validate_durable_write(value["durable"]), "INVALID_AUTHORITY")

    def test_raw_dict_equal_byte_clones_and_nonfinalizer_capture_cannot_issue(self):
        value = fixture()
        self.reject(lambda: approval.capture_live_paired_history(source=value["source"], snapshot=value["snapshot"],
            prepared_content=value["prepared"], bundle=value["bundle"]), "FINALIZER_AUTHORITY_REQUIRED")
        for capture in ({}, self.payload(value), value["bundle"]):
            self.reject(lambda: approval.issue_durable_history(capture=capture, approved_write=value["write"], row_id=17),
                        "INVALID_AUTHORITY")
        self.reject(lambda: approval.issue_durable_history(capture=value["capture"], approved_write=value["record"], row_id=17),
                    "INVALID_WRITE_AUTHORITY")
        clone = seal_review_envelope(json.loads(value["snapshot"].json_text))
        self.reject(lambda: approval.capture_live_paired_history(source=value["source"], snapshot=clone,
            prepared_content=value["prepared"], bundle=value["bundle"], _authority=approval._FINALIZER_CAPTURE),
            "ORIGINAL_SNAPSHOT_REQUIRED")

    def test_durable_read_cannot_issue_write_capture_or_live_authority(self):
        value = fixture(); read = self.read(value)
        self.reject(lambda: approval.issue_durable_history(capture=read, approved_write=value["write"], row_id=17),
                    "INVALID_AUTHORITY")
        self.reject(lambda: approval.validate_durable_write(read), "INVALID_AUTHORITY")
        self.assertFalse(hasattr(read, "source")); self.assertFalse(hasattr(read, "write"))
        for kind in (approval.DurableReadAdmission, approval.ApprovedDurableHistoryEnvelope, approval.LivePairedHistoryApproval):
            with self.assertRaises(TypeError):
                kind(read)

    def test_immutable_aliases_pickle_forgery_and_recomputed_receipt_reject(self):
        value = fixture(); read = self.read(value)
        returned = read.payload; returned["chart_display_snapshot"]["charts"] = []
        self.assertTrue(read.payload["chart_display_snapshot"]["charts"])
        for obj in (value["capture"], value["durable"], read):
            with self.assertRaises(AttributeError):
                obj._receipt = ()
            with self.assertRaises(TypeError):
                pickle.dumps(obj)
        forged = object.__new__(approval.ApprovedDurableHistoryEnvelope)
        object.__setattr__(forged, "_receipt", value["durable"]._receipt)
        self.reject(lambda: approval.validate_durable_write(forged), "INVALID_AUTHORITY")
        original = value["durable"]._receipt
        object.__setattr__(value["durable"], "_receipt", (original[0] + b' ', *original[1:]))
        self.reject(lambda: approval.validate_durable_write(value["durable"]), "AUTHORITY_MUTATION")

    def test_original_source_owner_and_late_snapshot_write_mutations_reject(self):
        value = fixture(); other = fixture()
        self.reject(lambda: approval.capture_live_paired_history(source=other["source"], snapshot=value["snapshot"],
            prepared_content=value["prepared"], bundle=value["bundle"], _authority=approval._FINALIZER_CAPTURE),
            "SOURCE_OWNER_MISMATCH")
        empty = fixture(empty=True)
        self.assertEqual(self.payload(value)["bundle"]["representations"]["v1"]["document"],
                         self.payload(empty)["bundle"]["representations"]["v1"]["document"])
        self.reject(lambda: approval.capture_live_paired_history(source=empty["source"], snapshot=value["snapshot"],
            prepared_content=value["prepared"], bundle=empty["bundle"], _authority=approval._FINALIZER_CAPTURE),
            "SOURCE_SNAPSHOT_MISMATCH")
        original = value["snapshot"]._json
        try:
            object.__setattr__(value["snapshot"], "_json", original + b' ')
            self.reject(lambda: approval.validate_durable_write(value["durable"]), "SNAPSHOT_MUTATION")
        finally:
            object.__setattr__(value["snapshot"], "_json", original)
        original = value["write"]._record
        object.__setattr__(value["write"], "_record", original + b' ')
        self.reject(lambda: approval.validate_durable_write(value["durable"]), "INVALID_WRITE_AUTHORITY")

    def test_payload_exact_byte_limit_and_limit_plus_one_preflight(self):
        parts = ["q" * codec.MAX_STRING] * 79 + [""]
        remaining = codec.MAX_PAYLOAD_BYTES - len(codec.canonical_json(parts))
        parts[-1] = "q" * remaining
        raw = codec.canonical_json(parts)
        self.assertEqual(1_310_720, len(raw))
        self.assertEqual(parts, codec.decode_json(raw, canonical=True))
        parts[-1] += "q"
        self.reject(lambda: codec.canonical_json(parts), "BYTE_LIMIT")
        self.reject(lambda: codec.decode_json(raw + b' '), "BYTE_LIMIT")

    def test_outer_exact_byte_limit_and_limit_plus_one_preflight(self):
        raw = b'"' + b'q' * (codec.MAX_OUTER_BYTES - 2) + b'"'
        self.assertEqual(2_622_464, len(raw))
        self.assertEqual(codec.MAX_OUTER_BYTES - 2, len(codec.decode_outer(raw)))
        self.reject(lambda: codec.decode_outer(raw + b' '), "BYTE_LIMIT")

    def test_nodes_exact_limit_and_limit_plus_one_without_semantic_callbacks(self):
        value = [None] * (codec.MAX_NODES - 1)
        self.assertEqual(32_768, codec.validate_json_tree(value))
        self.assertEqual(value, codec.decode_json(codec.canonical_json(value)))
        value.append(None)
        self.reject(lambda: codec.validate_json_tree(value), "NODE_LIMIT")

    def test_depth_exact_limit_and_limit_plus_one_scanned_before_json_decode(self):
        value = 0
        for _ in range(16):
            value = [value]
        raw = codec.canonical_json(value)
        self.assertEqual(value, codec.decode_json(raw))
        self.reject(lambda: codec.canonical_json([value]), "DEPTH_LIMIT")
        self.reject(lambda: codec.decode_json(b'[' * 17 + b'0' + b']' * 17), "DEPTH_LIMIT")
        self.reject(lambda: codec.decode_json(b'[' * 18 + b'0' + b']' * 18), "DEPTH_LIMIT")
        self.assertEqual("[[[", codec.decode_json(b'"[[["'))

    def test_whole_row_safety_is_required_without_repair_or_swallowed_callback_bugs(self):
        value = fixture(); raw = value["durable"].bytes

        def read(predicate=None):
            return approval.read_durable_history(raw, row_context=value["context"], sql_snapshots=value["sql"],
                                                 unsafe_text=predicate)

        self.reject(lambda: read(), "INVALID_SAFETY_PREDICATE")
        self.reject(lambda: read(lambda text: 0), "INVALID_SAFETY_PREDICATE")
        self.reject(lambda: read(lambda text: "합성 SQL 차트" in text), "UNSAFE_CONTENT")
        self.reject(lambda: read(lambda text: "승인된 과거 차트" in text), "UNSAFE_CONTENT")

        def broken(_text):
            raise ValueError("synthetic predicate bug")

        with self.assertRaisesRegex(ValueError, "synthetic predicate bug"):
            read(broken)
        payload = self.payload(value)
        display = payload["chart_display_snapshot"]["chart_cards"][0]["display"]
        display["blocks"][0]["runs"] = [{"type": "text", "text": "[데이터 확인]"}]
        display["canonical_text"] = "[데이터 확인]"
        raw = contract.encode_envelope(payload)
        self.reject(lambda: read(unsafe_text), "UNSAFE_CONTENT")

    def test_production_shaped_maximum_request_chart_window_and_cards_through_real_finalizer(self):
        # Current real request/builder/chart producer/finalizer; model and market
        # I/O are mocked, accounts exist only in H4-owned temp stores, save=False.
        with api_module_state():
            compact = importlib.import_module("core.ai_review_v2")._compact_chart_snapshot
        for kind in ("basic", "advanced"):
            with access_tests.producer() as case:
                import pandas as pd
                charts = importlib.import_module("core.journal_chart")
                start = datetime(2026, 1, 1)
                fills = [dict(id=index + 1, trade_date="2026-01-26T09:30", ticker="005930", name="합성 종목",
                              side="buy", price=70000.0, quantity=1.0, fee=0.0, tax=0.0, memo="", source="manual")
                         for index in range(180)]
                for index in range(20):
                    day = start + timedelta(days=25 + round(index * 94 / 19))
                    fills.append(dict(fills[0], id=181 + index, side="sell", price=70900.0,
                                      trade_date=day.strftime("%Y-%m-%dT10:00")))
                frame = pd.DataFrame({"Open": 70000.0, "High": 72000.0, "Low": 69000.0,
                    "Close": 70500.0, "Volume": 1000.0, "MA5": float("nan"), "MA20": float("nan")},
                    index=pd.date_range(start, periods=140))
                owners = []; finish = case.ai.finish_review_source

                def capture(*args, **kwargs):
                    source = finish(*args, **kwargs); owners.append(source); return source

                def sql_producer(trades):
                    # Independent SQL A legitimately lacks market data. The real
                    # producer returns its approved unavailable chart (one card),
                    # rather than 200 reviews that its metadata gate cannot admit.
                    with patch.object(charts, "_daily_data", return_value=pd.DataFrame()):
                        return charts.build_journal_charts(trades)

                with patch.object(case.ai, "finish_review_source", side_effect=capture), patch.object(
                        case.main, "_ai_review_max_trades", return_value=200), patch.object(
                        charts, "_try_intraday", return_value=pd.DataFrame()), patch.object(
                        charts, "_daily_data", return_value=frame), patch.object(
                        case.ai, "build_journal_charts", side_effect=charts.build_journal_charts), patch.object(
                        case.main, "build_journal_charts", side_effect=sql_producer), patch.object(
                        case.ai, "_compact_chart_snapshot", side_effect=compact):
                    _, (result, state) = case.route("session-free", kind, "ready", trades=fills, target=200,
                                                   save=False, keyed=False)
                saved = state["approved"]
                source = next(owner for owner in reversed(owners) if owner.status == "ready")
                meta = json.loads(saved["metadata_json"])
                record = dict(meta, user_id=state["user_id"], review_type=kind, model=result["model"], source="openai",
                    created_at="2026-10-13T01:02:03+00:00", ai_review=result, access_snapshot=result["access"])
                value = assemble(source, saved["snapshot"], saved["prepared_content"], record)
                read = self.read(value)
                auxiliary = read.projection["chart_display_snapshot"]
                self.assertEqual(200, source.objective.result.trade_count)
                self.assertEqual(140, len(auxiliary["charts"][0]["candles"]))
                self.assertEqual(20, len(auxiliary["charts"][0]["markers"]))
                self.assertEqual(20, len(auxiliary["chart_cards"]))
                self.assertEqual(result["chart_display_snapshot"], auxiliary)
                self.assertLess(len(codec.canonical_json(read.payload)), 1_064_696)
                self.assertLess(codec.validate_json_tree(read.payload), 20_898)
                # Slice 3B: persist the actual producer maxima in the same
                # H4-owned temp DB and check the whole reopened display identity.
                committed = case.history.add_paired_review_history(
                    value["capture"], value["write"], unsafe_text=unsafe_text)
                reopened = case.ai.safe_legacy_history_snapshot(
                    case.history.get_review_history(committed.id, user_id=state["user_id"]))
                self.assertEqual(reopened, committed.record)
                self.assertEqual(reopened["ai_review"]["display_snapshot"], result["display_snapshot"])
                self.assertEqual(reopened["ai_review"]["chart_display_snapshot"], auxiliary)
                self.assertEqual(reopened["chart_snapshot"], meta["chart_snapshot"])
                print("DURABLE_MAX_VALID_RESULT " + json.dumps({"review_type": kind, "trades": 200,
                    "candles": 140, "markers": 20, "cards": 20,
                    "payload_bytes": len(codec.canonical_json(read.payload)),
                    "nodes": codec.validate_json_tree(read.payload)}, sort_keys=True))

    def test_pure_modules_are_disconnected_from_runtime_and_have_no_io_imports(self):
        from collections import Counter
        root = Path(__file__).resolve().parents[1]
        modules = {"review_history_json_codec", "review_durable_storage_contract", "review_durable_storage_approval"}
        approved_relative = "backend/core/ai_review_v2.py"
        approved_import = ("core", ("review_display_activation", "review_approval_bundle",
                                             "review_durable_storage_approval"))

        def approved_edge(relative, node):
            return (relative, node.module or "", tuple(alias.name for alias in node.names)) == (
                approved_relative, *approved_import)

        expected_accesses = {
            ("core.review_durable_storage_approval.capture_live_paired_history", "call"): 1,
            ("core.review_durable_storage_approval._FINALIZER_CAPTURE", "access"): 1,
        }

        def check_accesses(relative, tree, exact=False):
            self.assertFalse(_has_guarded_review_wildcard_import(tree, relative),
                             (relative, "guarded review wildcard import"))
            observed = Counter((target, kind) for target, kind in _canonical_import_accesses(tree)
                               if modules.intersection(target.split(".")))
            if relative == approved_relative:
                self.assertFalse(set(observed) - set(expected_accesses), (relative, observed))
                if exact:
                    self.assertEqual(expected_accesses, dict(observed))
            else:
                self.assertFalse(observed, (relative, observed))

        for relative, source in (
            ("backend/main.py", "import core as core\ncore.review_durable_storage_approval"),
            ("backend/main.py", "import core as renamed\nrenamed.review_durable_storage_approval.capture_live_paired_history()"),
            (approved_relative, "import core as core\ncore.review_durable_storage_approval.unknown()"),
            (approved_relative, "import core as renamed\nrenamed.review_durable_storage_approval._FINALIZER_CAPTURE()"),
            (approved_relative, "from backend import core as renamed\nrenamed.review_history_json_codec.canonical_json(None)"),
            ("backend/core/unrelated.py", "from core import *"),
            ("backend/core/unrelated.py", "from core import *\nreview_approval_bundle.compile_approval_bundle()"),
            ("backend/core/unrelated.py", "from core import *\nreview_durable_storage_approval.capture_live_paired_history()"),
            ("backend/core/unrelated.py", "from core.review_approval_bundle import *"),
            ("backend/core/unrelated.py", "from core.review_durable_storage_approval import *"),
            ("backend/core/unrelated.py", "from . import *"),
            ("backend/core/unrelated.py", "from ..core import *\nreview_approval_bundle.compile_approval_bundle()"),
            ("backend/core/unrelated.py", "from .review_durable_storage_approval import *\ncapture_live_paired_history()"),
        ):
            with self.subTest(alias_source=source), self.assertRaises(AssertionError):
                check_accesses(relative, ast.parse(source))

        for relative, source in (
            ("backend/main.py", "from core import review_durable_storage_approval"),
            (approved_relative, "from core import review_durable_storage_approval"),
            (approved_relative, "from core.review_durable_storage_approval import capture_live_paired_history"),
        ):
            self.assertFalse(approved_edge(relative, ast.parse(source).body[0]))

        observed_approved_edges = set()
        for path in (root / "backend").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            relative = path.relative_to(root).as_posix()
            imports = [name for node in ast.walk(tree) for name in (
                [node.module or "", *((node.module or "") + "." + item.name for item in node.names)] if isinstance(node, ast.ImportFrom) else
                [item.name for item in node.names] if isinstance(node, ast.Import) else [])]
            if path.stem not in modules | {"review_history", "review_history_adapter", "review_history_paired"}:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        imported = [node.module or "", *((node.module or "") + "." + item.name for item in node.names)]
                        if any(name.split(".")[-1] in modules for name in imported):
                            self.assertTrue(approved_edge(relative, node), (relative, ast.unparse(node)))
                            observed_approved_edges.add((relative, node.module or "", tuple(item.name for item in node.names)))
                    elif isinstance(node, ast.Import):
                        self.assertFalse(any(item.name.split(".")[-1] in modules for item in node.names), str(path))
                if relative == approved_relative:
                    check_accesses(relative, tree, exact=True)
                else:
                    check_accesses(relative, tree)
            elif path.stem in modules:
                self.assertFalse(any(name.split(".")[-1] in {"main", "review_history", "sqlite3", "os", "env",
                    "socket", "requests", "urllib", "ai_review_v2", "idempotency_cache", "hmac"} for name in imports))
                self.assertFalse(any(name.split(".")[0] in {"socket", "sqlite3", "urllib", "requests", "os", "hmac"}
                                     for name in imports))
        self.assertEqual({(approved_relative, *approved_import)}, observed_approved_edges)
