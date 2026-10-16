"""Step 5 complete records, serialization/binds and immutable approval under H4."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
import importlib
import json
import os
import pickle
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from core import review_history_approved_write as contract
from core import review_history_content_contract as content
from core import review_history_prepared_content as prepared_contract
from core.review_envelope_contract import ApprovedReviewSnapshot
from core.review_history_write_contract import HistoryWriteContractError
from tests import test_review_history_write_access as access_tests
from tests import test_review_history_write_content as content_tests
from tests import test_review_history_producers as producers
from tests.review_source_fixtures import approved_chart_fixture


# Actual INSERT order, independently transcribed from review_history.py.
EXPECTED_COLUMNS = (
    "user_id", "review_type", "ticker", "name", "trade_date", "target_trade_id",
    "trade_snapshot_json", "recent_trades_snapshot_json", "chart_snapshot_json",
    "ai_review_json", "access_snapshot_json", "model", "source", "created_at",
)
SNAPSHOT_FIELDS = ("trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot")
ROW_KEYS = {
    "user_id", "review_type", "ticker", "name", "trade_date", "target_trade_id", "trade_snapshot",
    "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot", "model", "source", "created_at",
}
_ORIGINAL = object()


def captured(case, review_type="basic", status="ready", variant="session-free", **kwargs):
    _, (result, state) = case.route(variant, review_type, status, save=False, keyed=False, **kwargs)
    approved = state["approved"]
    metadata = json.loads(approved["metadata_json"])
    record = dict(metadata, user_id=state["user_id"], review_type=result["review_type"],
                  model=result["model"] if status == "ready" else "", source=result["source"],
                  created_at="2026-10-09T01:02:03+00:00", ai_review=copy.deepcopy(result),
                  access_snapshot=copy.deepcopy(result["access"]))
    return record, approved["snapshot"], approved["prepared_content"]


def set_access(record, access):
    record["access_snapshot"] = copy.deepcopy(access)
    record["ai_review"]["access"] = copy.deepcopy(access)


class ApprovedHistoryWriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants = {}
        with access_tests.producer() as case, ExitStack() as stack:
            import pandas as pd

            charts = importlib.import_module("core.journal_chart")
            frame = pd.DataFrame({"Open": 70000.0, "High": 72000.0, "Low": 69000.0, "Close": 70500.0,
                                  "Volume": 1000.0, "MA5": float("nan"), "MA20": float("nan")},
                                 index=pd.date_range("2026-07-10", periods=4))
            stack.enter_context(patch.object(charts, "_try_intraday", return_value=pd.DataFrame()))
            stack.enter_context(patch.object(charts, "_daily_data", return_value=frame))
            stack.enter_context(patch.object(case.main, "build_journal_charts", side_effect=charts.build_journal_charts))
            stack.enter_context(patch.object(case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()))
            for variant in ("session-free", "session-pro", "review", "dev-session-free", "dev-session-pro"):
                for review_type in ("basic", "advanced"):
                    for status in ("ready", "missing_key"):
                        with patch.dict(os.environ, {"ALPHAMATE_ALLOW_DEV_ACCESS": str(variant.startswith("dev-session")).lower()}):
                            cls.variants[variant, review_type, status] = captured(case, review_type, status, variant)

    def base(self, review_type="basic", status="ready", variant="session-free"):
        record, snapshot, prepared = self.variants[variant, review_type, status]
        return copy.deepcopy(record), snapshot, prepared

    def approve(self, fixture, *, record=_ORIGINAL, snapshot=_ORIGINAL, prepared=_ORIGINAL):
        row, seal, content_value = fixture
        return contract.approve_history_write(
            record=row if record is _ORIGINAL else record,
            snapshot=seal if snapshot is _ORIGINAL else snapshot,
            prepared_content=content_value if prepared is _ORIGINAL else prepared)

    def rejected(self, fixture, **kwargs):
        with self.assertRaises(HistoryWriteContractError) as raised:
            self.approve(fixture, **kwargs)
        self.assertNotIn("synthetic-rejected-secret", str(raised.exception))

    def test_twenty_actual_producer_variants_and_exact_bind_columns(self):
        self.assertEqual(EXPECTED_COLUMNS, contract.SQL_BIND_COLUMNS)
        self.assertEqual(SNAPSHOT_FIELDS, contract.JSON_SNAPSHOT_FIELDS)
        self.assertEqual(20, len(self.variants))
        for coordinates in self.variants:
            with self.subTest(coordinates=coordinates):
                fixture = self.base(coordinates[1], coordinates[2], coordinates[0])
                record, snapshot, prepared = fixture
                before = copy.deepcopy(record)
                approval = self.approve(fixture)
                self.assertIs(type(approval), contract.ApprovedHistoryWrite)
                self.assertEqual(ROW_KEYS, set(json.loads(approval.record_bytes)))
                self.assertEqual(before, record)
                self.assertEqual(prepared.digest, approval.prepared_content_digest)
                self.assertEqual(14, len(approval.bind_values))
                self.assertIs(type(approval.bind_values), tuple)
                self.assertIs(type(approval.record_bytes), bytes)
                self.assertEqual(record, json.loads(approval.record_bytes))
                for column, value in zip(EXPECTED_COLUMNS, approval.bind_values):
                    if column.endswith("_json"):
                        field = column[:-5]
                        self.assertEqual(record[field], json.loads(value))
                        self.assertEqual(value.encode("utf-8"), approval.json_snapshot_bytes[SNAPSHOT_FIELDS.index(field)])
                    else:
                        self.assertIs(type(record[column]), type(value))
                        self.assertEqual(record[column], value)
                self.assertNotEqual(record["chart_snapshot"]["charts"][0]["candles"],
                                    record["ai_review"]["chart_display_snapshot"]["charts"][0]["candles"])
                self.assertIsNone(contract.validate_approved_history_write(approval))

    def test_missing_key_none_and_empty_row_model_are_explicit(self):
        for review_type in ("basic", "advanced"):
            fixture = self.base(review_type, "missing_key")
            record = fixture[0]
            approval = self.approve(fixture)
            self.assertIsNone(json.loads(approval.bind_values[9])["model"])
            self.assertEqual("", approval.bind_values[11])
            for row_model in (None, "synthetic-model", False):
                self.rejected(fixture, record=dict(record, model=row_model))
            missing = copy.deepcopy(record)
            del missing["model"]
            self.rejected(fixture, record=missing)
            for result_model in ("", "synthetic-model", False):
                self.rejected(fixture, record=content_tests.changed(record, ("ai_review", "model"), result_model))

    def test_required_row_keys_and_extra_fields_reject(self):
        fixture = self.base()
        self.assertEqual(ROW_KEYS, set(fixture[0]))
        for key in ROW_KEYS:
            value = copy.deepcopy(fixture[0])
            del value[key]
            self.rejected(fixture, record=value)
        for key in ("id", "status", "prepared_content", "snapshot", "internal_status", "trade_snapshot_json", "unknown"):
            self.rejected(fixture, record=dict(fixture[0], **{key: None}))
        for value in (None, [], "synthetic-rejected-secret", {True: "wrong"}):
            self.rejected(fixture, record=value)

    def test_row_scalar_types_nullability_and_datetime(self):
        fixture = self.base()
        string_subclass = type("StringSubclass", (str,), {})
        for key in ("user_id", "review_type", "ticker", "name", "trade_date", "model", "source", "created_at"):
            for wrong in (None, True, 1, 1.0, [], {}, string_subclass(fixture[0][key])):
                self.rejected(fixture, record=content_tests.changed(fixture[0], (key,), wrong))
        for wrong in (True, 1.0, "2", 0, -1, 2**53, [], {}):
            self.rejected(fixture, record=content_tests.changed(fixture[0], ("target_trade_id",), wrong))
        for wrong in ("", " \t", "x" * 121, "synthetic-rejected-secret\x00", "\ud800"):
            self.rejected(fixture, record=dict(fixture[0], user_id=wrong))
        for wrong in ("", "2026-10-09", "2026-10-09T01:02:03", "2026-10-09T01:02:03Z",
                      "2026-10-09T10:02:03+09:00", "2026-10-09T01:02:03.1+00:00", "2026-10-09 01:02:03+00:00",
                      "2026-02-30T01:02:03+00:00", "2026-10-09T24:00:00+00:00", "2026-10-09T01:60:00+00:00"):
            self.rejected(fixture, record=dict(fixture[0], created_at=wrong))
        self.approve(fixture, record=dict(fixture[0], created_at="2028-02-29T23:59:59+00:00"))

    def test_row_and_result_origin_relations_reject(self):
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                fixture = self.base(review_type, status)
                record = fixture[0]
                for key, wrong in (("review_type", "advanced" if review_type == "basic" else "basic"),
                                   ("source", "chart-rules" if status == "ready" else "openai"),
                                   ("model", "synthetic-other-model")):
                    self.rejected(fixture, record=dict(record, **{key: wrong}))
                for key, wrong in (("status", "error"), ("status", "empty"), ("source", "none"),
                                   ("review_type", "Basic"), ("model", "")):
                    self.rejected(fixture, record=content_tests.changed(record, ("ai_review", key), wrong))

    def test_access_variants_and_producer_exceptions_preserved(self):
        for review_type in ("basic", "advanced"):
            fixture = self.base(review_type)
            accesses = [access_tests.access_fixture(auth_mode="review", plan="pro", review_type=review_type),
                        access_tests.access_fixture(auth_mode="review", plan="pro", wallet_plan="free", review_type=review_type),
                        access_tests.access_fixture(plan="pro", review_type=review_type)]
            if review_type == "advanced":
                accesses.extend(access_tests.access_fixture(plan="pro", review_type=review_type, source=source)
                                for source in ("signup_advanced", "weekly_ad_advanced", "purchased_advanced"))
            for access in accesses:
                record = copy.deepcopy(fixture[0])
                set_access(record, access)
                approval = self.approve(fixture, record=record)
                self.assertEqual(access, json.loads(approval.bind_values[10]))
                self.assertIsNone(contract.validate_approved_history_write(approval))

    def test_access_mutations_and_naive_expiry_reject(self):
        fixture = self.base(variant="session-pro")
        original = copy.deepcopy(fixture[0]["access_snapshot"])
        # The actual producer aliases quota to wallet balances. Separate the
        # two copies before testing a quota-only mismatch.
        original["quota"] = copy.deepcopy(original["quota"])
        mutations = [(("auth_mode",), "dev"), (("source",), "free_daily_basic"),
                     (("refunded",), True), (("idempotent_replay",), True),
                     (("wallet", "basic", "signup_remaining"), True),
                     (("quota", "basic", "purchased_remaining"), 999),
                     (("wallet", "validity", "pro_allowance_resets_at"), "2099-01-01T00:00:00"),
                     (("wallet", "validity", "pro_allowance_resets_at"), "2099-02-30T00:00:00Z"),
                     (("wallet", "validity", "pro_allowance_resets_at"), "2099-01-01T00:00+09:60"),
                     (("wallet", "validity", "pro_allowance_resets_at"), None)]
        for path, wrong in mutations:
            record = copy.deepcopy(fixture[0])
            set_access(record, content_tests.changed(original, path, wrong))
            with self.subTest(path=path):
                self.rejected(fixture, record=record)

    def test_independent_access_snapshots_must_match_exactly(self):
        fixture = self.base()
        access = access_tests.access_fixture(source="purchased_basic")
        access_tests.contract.validate_new_history_access(access, review_type="basic", status="ready")
        for key in ("access_snapshot", "ai_review"):
            record = copy.deepcopy(fixture[0])
            if key == "access_snapshot":
                record[key] = access
            else:
                record[key]["access"] = access
            self.rejected(fixture, record=record)
        record = copy.deepcopy(fixture[0])
        record["access_snapshot"] = record["ai_review"]["access"]
        self.approve(fixture, record=record)

    def test_nested_content_keys_types_and_bool_int_reject(self):
        for review_type in ("basic", "advanced"):
            fixture = self.base(review_type)
            record = fixture[0]
            for path, node in content_tests.nodes(record):
                if type(node) is dict:
                    extra = dict(node, unknown="synthetic-rejected-secret")
                    self.rejected(fixture, record=content_tests.changed(record, path, extra))
                    for key in node:
                        missing = dict(node)
                        del missing[key]
                        self.rejected(fixture, record=content_tests.changed(record, path, missing))
                wrong = [] if type(node) is dict else {} if type(node) is list else (
                    1 if type(node) is bool else True if type(node) in (int, float) else None if type(node) is str else "wrong")
                self.rejected(fixture, record=content_tests.changed(record, path, wrong))

    def test_original_prepared_and_seal_identity_required(self):
        fixture = self.base()
        record, snapshot, prepared = fixture
        clone = ApprovedReviewSnapshot(json.loads(snapshot.json_text))
        self.assertEqual(snapshot.json_text, clone.json_text)
        self.rejected(fixture, snapshot=clone)
        other = self.base(variant="session-pro")
        self.rejected(fixture, prepared=other[2])
        self.rejected(fixture, prepared=prepared, snapshot=other[1])
        for wrong in (None, {}, object(), object.__new__(prepared_contract.PreparedHistoryContent)):
            self.rejected(fixture, prepared=wrong)
        for wrong in (None, {}, object(), object.__new__(ApprovedReviewSnapshot)):
            self.rejected(fixture, snapshot=wrong)
        self.approve(fixture)

    def test_shape_valid_metadata_and_hidden_structured_replacements_reject(self):
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                fixture = self.base(review_type, status)
                changed = content_tests.changed(fixture[0], ("target_trade_id",), 999)
                metadata = {key: changed[key] for key in content_tests.META_KEYS}
                content.validate_new_history_metadata(metadata)
                self.rejected(fixture, record=changed)
                changed = content_tests.changed(fixture[0], ("ai_review", "structured_review", "objective", "result", "weighted_sell_price"), 70901.0)
                content.validate_new_history_result(changed["ai_review"])
                self.rejected(fixture, record=changed)
                if status == "missing_key":
                    changed = content_tests.changed(fixture[0], ("ai_review", "structured_review", "summary", "main_issue"), "합성 대체 이슈")
                    content.validate_new_history_result(changed["ai_review"])
                    self.rejected(fixture, record=changed)
                else:
                    changed = content_tests.changed(fixture[0], ("ai_review", "model"), "synthetic-other-model")
                    changed["model"] = "synthetic-other-model"
                    content.validate_new_history_result(changed["ai_review"])
                    self.rejected(fixture, record=changed)

    def test_target_absent_unmatched_outside_recent_and_name_only_variants(self):
        with access_tests.producer() as case:
            for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
                for target, idless, name_only in ((None, False, False), (999, False, False), (None, True, False), (None, True, True)):
                    trades = copy.deepcopy(case.trades)
                    for trade in trades:
                        if idless:
                            trade.pop("id")
                        if name_only:
                            trade["ticker"] = ""
                    fixture = captured(case, review_type, status, target=target, trades=trades)
                    approval = self.approve(fixture)
                    self.assertEqual(target, approval.bind_values[5])
                    if name_only:
                        self.assertEqual("", approval.bind_values[2])
                        self.assertEqual([], json.loads(approval.bind_values[8])["charts"])
                trades = [dict(case.trades[index % 2], id=index + 1) for index in range(12)]
                fixture = captured(case, review_type, status, target=1, trades=trades)
                approval = self.approve(fixture)
                self.assertNotIn(1, [row["id"] for row in json.loads(approval.bind_values[7])])
                self.assertEqual(1, approval.bind_values[5])

    def test_immutable_bytes_and_bind_values_survive_all_alias_mutations(self):
        for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
            fixture = self.base(review_type, status)
            record = fixture[0]
            record["access_snapshot"] = record["ai_review"]["access"]
            trade, recent, chart, structured, access = (record["trade_snapshot"], record["recent_trades_snapshot"],
                record["chart_snapshot"], record["ai_review"]["structured_review"], record["access_snapshot"])
            approval = self.approve(fixture)
            fixed = approval.record_bytes, approval.json_snapshot_bytes, approval.bind_values, approval.digest
            trade["price"] = 1.0
            recent.clear()
            chart["charts"].clear()
            structured["summary"]["main_issue"] = "합성 변경"
            access["quota"].clear()
            record["user_id"] = "synthetic-other-owner"
            record.clear()
            decoded = json.loads(approval.record_json)
            decoded["ai_review"].clear()
            for text in approval.bind_values[6:11]:
                decoded = json.loads(text)
                decoded.clear()
            self.assertEqual(fixed, (approval.record_bytes, approval.json_snapshot_bytes, approval.bind_values, approval.digest))
            self.assertIsNone(contract.validate_approved_history_write(approval))

    def test_no_mutable_references_or_public_construction_copy_restore(self):
        approval = self.approve(self.base())
        self.assertFalse(hasattr(approval, "__dict__"))
        for slot in approval.__slots__:
            value = getattr(approval, slot)
            self.assertNotIsInstance(value, (dict, list, prepared_contract.PreparedHistoryContent, ApprovedReviewSnapshot))
            if type(value) is tuple:
                self.assertTrue(all(type(child) in (str, bytes, int, type(None)) for child in value))
            with self.assertRaises(AttributeError):
                setattr(approval, slot, value)
            with self.assertRaises(AttributeError):
                delattr(approval, slot)
        for name in ("record_bytes", "bind_values", "json_snapshot_bytes", "digest"):
            with self.assertRaises(AttributeError):
                setattr(approval, name, None)
        for action in (lambda: contract.ApprovedHistoryWrite(), lambda: contract.ApprovedHistoryWrite(b"{}"),
                       lambda: type("Unsupported", (contract.ApprovedHistoryWrite,), {}),
                       lambda: copy.copy(approval), lambda: copy.deepcopy(approval), lambda: pickle.dumps(approval),
                       lambda: approval.__setstate__({})):
            with self.assertRaises(TypeError):
                action()
        with self.assertRaises(TypeError):
            approval.bind_values[0] = "other"
        with self.assertRaises(TypeError):
            approval.record_bytes[0] = 0

    def test_invalid_records_never_allocate_approval(self):
        fixture = self.base()
        denied = Mock(side_effect=AssertionError("invalid record reached issuance"))
        allocation_guard = type("AllocationGuard", (), {"__new__": staticmethod(denied)})
        with patch.object(contract, "object", allocation_guard, create=True):
            for record in (None, {}, dict(fixture[0], source="none"), dict(fixture[0], user_id=""),
                           content_tests.changed(fixture[0], ("ai_review", "display_snapshot"), None)):
                self.rejected(fixture, record=record)
            with self.assertRaisesRegex(AssertionError, "reached issuance"):
                self.approve(fixture)
        self.assertEqual(1, denied.call_count)

    def test_json_encode_errors_prevent_issuance(self):
        fixture = self.base()
        original_encode = contract._encode
        for error in (TypeError("synthetic-rejected-secret"), ValueError("synthetic-rejected-secret"),
                      UnicodeError("synthetic-rejected-secret"), OverflowError("synthetic-rejected-secret"),
                      RecursionError("synthetic-rejected-secret")):
            def fail(value):
                if value is fixture[0]:
                    with patch.object(contract.json, "dumps", side_effect=error):
                        return original_encode(value)
                return original_encode(value)
            with patch.object(contract, "_encode", side_effect=fail):
                self.rejected(fixture)
        self.approve(fixture)

    def test_serialized_partial_extra_wrong_type_and_duplicate_json_reject(self):
        fixture = self.base()
        original_encode = contract._encode
        encoded = original_encode(fixture[0])
        extra = original_encode(dict(fixture[0], unknown=None))
        wrong = original_encode(dict(fixture[0], target_trade_id=True))
        for buffer in (b"{", b"null", b"[]", b'{"user_id":"partial"}', extra, wrong,
                       b'{"user_id":"discarded",' + encoded[1:], b"\xff", encoded + b" ", b"NaN"):
            def broken(value):
                return buffer if value is fixture[0] else original_encode(value)
            with patch.object(contract, "_encode", side_effect=broken):
                self.rejected(fixture)

    def test_valid_shape_serialization_replacements_reject(self):
        fixture = self.base()
        original_encode = contract._encode
        for row in (dict(fixture[0], user_id="synthetic-other-owner"),
                    dict(fixture[0], created_at="2026-10-10T01:02:03+00:00")):
            # All content/seal checks still pass: the independent source/JSON
            # comparison must catch otherwise valid scalar substitutions.
            contract._validate_candidate(row, fixture[2], fixture[1])
            buffer = original_encode(row)
            with patch.object(contract, "_encode", side_effect=lambda value: buffer if value is fixture[0] else original_encode(value)):
                self.rejected(fixture)

    def test_each_snapshot_serialization_is_rechecked(self):
        fixture = self.base()
        original_encode = contract._encode
        for field in SNAPSHOT_FIELDS:
            expected = fixture[0][field]
            def wrong_snapshot(value):
                return b"null" if type(value) is type(expected) and value == expected else original_encode(value)
            with self.subTest(field=field), patch.object(contract, "_encode", side_effect=wrong_snapshot):
                self.rejected(fixture)

    def test_sql_bind_types_order_values_and_json_are_rechecked(self):
        fixture = self.base()
        original_bind = contract._prepare_bind_values
        good = self.approve(fixture).bind_values
        wrong_binds = [list(good), good[:-1], good + ("extra",)]
        for index in range(14):
            values = list(good)
            values[index] = True if index == 5 else None
            wrong_binds.append(tuple(values))
        for index, wrong in ((0, "synthetic-other-owner"), (2, "000660"), (5, 1.0),
                             (5, 2**53), (6, b"{}"), (7, "{}"), (8, "null"),
                             (9, good[10]), (10, good[9]), (10, "\ud800"),
                             (13, "2026-10-10T01:02:03+00:00")):
            values = list(good)
            values[index] = wrong
            wrong_binds.append(tuple(values))
        for values in wrong_binds:
            with patch.object(contract, "_prepare_bind_values", return_value=values):
                self.rejected(fixture)
        with patch.object(contract, "_prepare_bind_values", wraps=original_bind) as prepared:
            self.approve(fixture)
            self.assertEqual(1, prepared.call_count)

    def test_mutation_during_admission_rejects(self):
        original_bind = contract._prepare_bind_values
        for mutation in (lambda row: row.update(user_id="synthetic-other-owner"),
                         lambda row: row.update(created_at="2026-10-10T01:02:03+00:00"),
                         lambda row: set_access(row, access_tests.access_fixture(source="purchased_basic")),
                         lambda row: row["trade_snapshot"].update(price=1.0)):
            fixture = self.base()
            def mutated(row, snapshots):
                mutation(fixture[0])
                return original_bind(row, snapshots)
            with patch.object(contract, "_prepare_bind_values", side_effect=mutated):
                self.rejected(fixture)
        fixture = self.base()
        snapshot = fixture[1]
        original_seal = snapshot._json
        def swap_seal(row, snapshots):
            object.__setattr__(snapshot, "_json", original_seal + b" ")
            return original_bind(row, snapshots)
        try:
            with patch.object(contract, "_prepare_bind_values", side_effect=swap_seal):
                self.rejected(fixture)
        finally:
            object.__setattr__(snapshot, "_json", original_seal)
        self.approve(fixture)

    def test_strong_unicode_and_exact_numbers_survive_serialization(self):
        original_output = producers.model_output
        def strong_output(review_type):
            output = original_output(review_type)
            output["main_issue"] = "과거 **체결** 근거 e\u0301 확인"
            return output
        with access_tests.producer() as case, patch.object(producers, "model_output", side_effect=strong_output), \
                patch.object(case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()):
            for review_type in ("basic", "advanced"):
                fixture = captured(case, review_type)
                approval = self.approve(fixture)
                self.assertIn("**체결**", json.loads(approval.bind_values[9])["summary"])
                self.assertIn("e\u0301", approval.record_json)
                self.assertIn("e\u0301".encode("utf-8"), approval.json_snapshot_bytes[3])
                self.assertIs(type(json.loads(approval.bind_values[6])["price"]), float)
                self.assertIs(type(json.loads(approval.bind_values[9])["structured_review"]["objective"]["result"]["trade_count"]), int)
                chart = fixture[0]["ai_review"]["chart_display_snapshot"]["charts"][0]
                value = chart["candles"][0]["close"]
                wrong = int(value) if type(value) is float else float(value)
                self.rejected(fixture, record=content_tests.changed(fixture[0],
                    ("ai_review", "chart_display_snapshot", "charts", 0, "candles", 0, "close"), wrong))

    def test_forged_uninitialized_and_tampered_approval_rejects(self):
        fixture = self.base()
        for value in (None, {}, fixture[2], object(), object.__new__(contract.ApprovedHistoryWrite)):
            with self.assertRaises(HistoryWriteContractError):
                contract.validate_approved_history_write(value)
        for slot, wrong in (("_origin", object()), ("_record", b"{}"), ("_snapshots", []),
                            ("_bind_values", ()), ("_content_digest", "0" * 64), ("_digest", "0" * 64)):
            value = self.approve(fixture)
            object.__setattr__(value, slot, wrong)
            with self.assertRaises(HistoryWriteContractError):
                contract.validate_approved_history_write(value)
        value = self.approve(fixture)
        wrong = list(value.bind_values)
        wrong[0] = "synthetic-other-owner"
        object.__setattr__(value, "_bind_values", tuple(wrong))
        with self.assertRaises(HistoryWriteContractError):
            contract.validate_approved_history_write(value)
        self.approve(fixture)

    def test_pure_without_io_reseal_normalizers_legacy_or_cache(self):
        tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual({"datetime", "hashlib", "json", "re", "core",
                          "core.review_history_prepared_content", "core.review_history_write_contract"}, imports)
        with access_tests.producer() as case, ExitStack() as stack:
            import builtins
            import sqlite3
            from core import review_history_adapter, review_legacy_compatibility, trade_review_schema

            def forbidden(*args, **kwargs):
                raise AssertionError("approved write crossed a forbidden dependency")

            for module, names in ((case.ai, ("seal_review_envelope", "prepare_history_content", "_normalized_semantic_review", "safe_legacy_history_snapshot", "admit_ai_review_history_candidate", "admit_new_ai_review_history_candidate")),
                                  (prepared_contract, ("prepare_history_content",)), (ApprovedReviewSnapshot, ("__init__",)),
                                  (trade_review_schema, ("normalize_semantic_output",)),
                                  (review_history_adapter, ("adapt_history_record",)),
                                  (review_legacy_compatibility, ("admit_legacy_body", "validate_legacy_body")),
                                  (case.main, ("_save_ai_review_history_if_enabled", "add_review_history", "_normalize_ai_review_result", "_validate_ai_review_cached_access")),
                                  (builtins, ("open",)), (sqlite3, ("connect",)), (os, ("getenv",))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=forbidden))
            stack.enter_context(patch.object(os, "environ", {}))
            for fixture in self.variants.values():
                approval = self.approve(fixture)
                self.assertIsNone(contract.validate_approved_history_write(approval))
