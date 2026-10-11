"""Step 4 original-seal/content identity and alias mutations under H4."""

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
from unittest.mock import patch

from backend.core import review_history_prepared_content as prepared_contract
from backend.core import review_history_content_contract as content
from backend.core.review_envelope_contract import ApprovedReviewSnapshot
from backend.core.review_history_write_contract import HistoryWriteContractError
from tests import test_review_history_write_access as access_tests
from tests import test_review_history_producers as producers
from tests.review_source_fixtures import approved_chart_fixture


def finalized(result):
    return {key: value for key, value in result.items() if key != "access"}


def replaced(value, path, replacement):
    value = copy.deepcopy(value)
    owner = value
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = replacement
    return value


def capture_as_finalizer(**kwargs):
    return prepared_contract.prepare_history_content(**kwargs, _authority=prepared_contract._CAPTURE)


class PreparedHistoryContentTest(unittest.TestCase):
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
                            _, (result, state) = case.route(variant, review_type, status, save=False, keyed=False)
                        approved = state["approved"]
                        cls.variants[variant, review_type, status] = (
                            json.loads(approved["metadata_json"]), result, approved["snapshot"], approved["prepared_content"])

    def verify(self, fixture, *, metadata=None, result=None, snapshot=None, prepared=None):
        original_metadata, original_result, original_snapshot, original_prepared = fixture
        prepared_contract.validate_prepared_history_content(
            original_prepared if prepared is None else prepared,
            metadata=original_metadata if metadata is None else metadata,
            result=original_result if result is None else result,
            snapshot=original_snapshot if snapshot is None else snapshot)

    def rejected(self, fixture, **kwargs):
        with self.assertRaises(HistoryWriteContractError) as raised:
            self.verify(fixture, **kwargs)
        self.assertNotIn("synthetic-rejected-secret", str(raised.exception))

    def base(self, review_type="basic", status="ready"):
        return self.variants["session-free", review_type, status]

    def test_actual_twenty_storage_variants_capture_before_access(self):
        for coordinates, fixture in self.variants.items():
            with self.subTest(coordinates=coordinates):
                metadata, result, snapshot, prepared = fixture
                before = copy.deepcopy((metadata, result))
                self.assertIs(type(prepared), prepared_contract.PreparedHistoryContent)
                self.assertIs(prepared.snapshot, snapshot)
                self.assertIs(type(prepared.metadata_bytes), bytes)
                self.assertIs(type(prepared.result_bytes), bytes)
                self.assertIs(type(prepared.structured_review_bytes), bytes)
                self.assertNotIn("access", json.loads(prepared.result_bytes))
                self.assertEqual(json.loads(prepared.result_bytes)["structured_review"], json.loads(prepared.structured_review_bytes))
                self.assertNotEqual(metadata["chart_snapshot"]["charts"][0]["candles"],
                                    result["chart_display_snapshot"]["charts"][0]["candles"])
                self.verify(fixture)
                self.assertEqual(before, (metadata, result))

    def test_finalizer_publishes_one_existing_seal_and_prepared_bytes(self):
        with access_tests.producer() as case:
            original_seal = case.ai.seal_review_envelope
            original_prepare = case.ai.prepare_history_content
            events, inputs = [], []

            def seal(candidate):
                snapshot = original_seal(candidate)
                events.append(("seal", snapshot))
                return snapshot

            def prepare(**kwargs):
                self.assertEqual("seal", events[-1][0])
                self.assertIs(kwargs["snapshot"], events[-1][1])
                self.assertIn("chart_display_snapshot", kwargs["result"])
                self.assertNotIn("access", kwargs["result"])
                inputs.append((kwargs["metadata"], kwargs["result"]))
                value = original_prepare(**kwargs)
                events.append(("prepare", value))
                return value

            for review_type, status in (("basic", "ready"), ("advanced", "missing_key")):
                events.clear()
                with patch.object(case.ai, "seal_review_envelope", side_effect=seal), patch.object(case.ai, "prepare_history_content", side_effect=prepare):
                    _, (result, state) = case.route("session-free", review_type, status, save=False, keyed=False)
                self.assertEqual(["seal", "prepare"], [event[0] for event in events])
                self.assertIs(state["approved"]["snapshot"], events[0][1])
                self.assertIs(state["approved"]["prepared_content"], events[1][1])
                fixture = (json.loads(state["approved"]["metadata_json"]), result, *[event[1] for event in events])
                self.verify(fixture)
                captured_metadata, captured_result = inputs[-1]
                fixed = fixture[3].metadata_bytes, fixture[3].result_bytes
                captured_metadata["target_trade_id"] = 999
                captured_result["structured_review"]["objective"]["result"]["weighted_sell_price"] = 70901.0
                state["candidate"]["name"] = "합성 변경 후보"
                self.assertEqual(fixed, (fixture[3].metadata_bytes, fixture[3].result_bytes))
                self.verify(fixture)
                self.rejected(fixture, metadata=captured_metadata)
                self.rejected(fixture, result=dict(captured_result, access=result["access"]))
            original_output = producers.model_output

            def strong_output(review_type):
                output = original_output(review_type)
                output["main_issue"] = "과거 **체결** 근거 e\u0301 확인"
                return output

            with patch.object(producers, "model_output", side_effect=strong_output), \
                    patch.object(case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()):
                for review_type in ("basic", "advanced"):
                    _, (result, state) = case.route("session-free", review_type, "ready", save=False, keyed=False)
                    approved = state["approved"]
                    fixture = (json.loads(approved["metadata_json"]), result, approved["snapshot"], approved["prepared_content"])
                    self.verify(fixture)
                    self.assertIn("**체결**", result["summary"])
                    self.assertIn("e\u0301", result["summary"])
                    self.assertIn("e\u0301", approved["prepared_content"].result_json)

    def test_original_snapshot_identity_rejects_equal_bytes_clone(self):
        for status in ("ready", "missing_key"):
            fixture = self.base(status=status)
            snapshot = fixture[2]
            clone = ApprovedReviewSnapshot(json.loads(snapshot.json_text))
            self.assertEqual(snapshot.digest, clone.digest)
            self.assertEqual(snapshot.json_text, clone.json_text)
            self.rejected(fixture, snapshot=clone)

    def test_other_seal_with_same_history_projection_rejects(self):
        fixture = self.base()
        envelope = json.loads(fixture[2].json_text)
        envelope["notice"] = copy.deepcopy(envelope["body"])
        envelope["notice"]["surface"] = "notice"
        other = ApprovedReviewSnapshot(envelope)
        self.assertEqual(json.loads(fixture[2].json_text)["body"], json.loads(other.json_text)["body"])
        self.rejected(fixture, snapshot=other)

    def test_body_summary_chart_replacements_cannot_reapprove(self):
        fixture = self.base(status="missing_key")
        metadata, result, snapshot, _prepared = fixture
        value = copy.deepcopy(result)
        body = value["display_snapshot"]
        body["blocks"][0]["runs"][0]["text"] += " 합성 변경"
        body["canonical_text"] = "".join("".join(run["text"] for run in block["runs"])
                                          + block["separator_after"] for block in body["blocks"])
        value["summary"] = "".join("".join("**" + run["text"] + "**" if run["type"] == "strong" else run["text"]
                                          for run in block["runs"]) + block["separator_after"] for block in body["blocks"])
        content.validate_new_history_result(value)
        self.rejected(fixture, result=value)
        with self.assertRaises(HistoryWriteContractError):
            capture_as_finalizer(metadata=metadata, result=finalized(value), snapshot=snapshot, finalizer_model=None)
        value = replaced(result, ("chart_display_snapshot", "charts", 0, "candles", 0, "open"), 71235)
        # Other OHLC values retain their own valid range.
        value["chart_display_snapshot"]["charts"][0]["candles"][0]["high"] = 71236
        content.validate_new_history_result(value)
        self.rejected(fixture, result=value)

    def test_origin_type_and_model_are_bound_at_capture(self):
        for review_type in ("basic", "advanced"):
            fixture = self.base(review_type)
            value = replaced(fixture[1], ("model",), "synthetic-other-model")
            content.validate_new_history_result(value)
            self.rejected(fixture, result=value)
            value = copy.deepcopy(fixture[1])
            value.update(status="missing_key", source="chart-rules", model=None)
            content.validate_new_history_result(value)
            self.rejected(fixture, result=value)
            other = self.base("advanced" if review_type == "basic" else "basic")
            self.rejected(fixture, result=other[1])

    def test_shape_valid_metadata_replacement_rejects(self):
        fixture = self.base()
        for value in (replaced(fixture[0], ("target_trade_id",), 999), replaced(fixture[0], ("chart_snapshot",), {"charts": []})):
            content.validate_new_history_metadata(value)
            self.rejected(fixture, metadata=value)
        for field in ("price", "quantity", "fee", "tax"):
            value = replaced(fixture[0], ("trade_snapshot", field), fixture[0]["trade_snapshot"][field] + 1.0)
            content.validate_new_history_metadata(value)
            self.rejected(fixture, metadata=value)

    def test_unrendered_structured_fields_and_missing_key_semantics_reject(self):
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                fixture = self.base(review_type, status)
                value = replaced(fixture[1], ("structured_review", "objective", "result", "weighted_sell_price"), 70901.0)
                content.validate_new_history_result(value)
                self.rejected(fixture, result=value)
                if status == "missing_key":
                    value = replaced(fixture[1], ("structured_review", "summary", "main_issue"), "합성 다른 과거 기록")
                    content.validate_new_history_result(value)
                    self.rejected(fixture, result=value)

    def test_equal_numeric_value_with_changed_type_rejects(self):
        for status in ("ready", "missing_key"):
            fixture = self.base(status=status)
            for path in (("chart_display_snapshot", "charts", 0, "candles", 0, "open"),
                         ("structured_review", "objective", "result", "total_fee"),
                         ("structured_review", "objective", "result", "realized_pnl")):
                original = fixture[1]
                for key in path:
                    original = original[key]
                replacement = float(original) if type(original) is int else int(original)
                value = replaced(fixture[1], path, replacement)
                content.validate_new_history_result(value)
                self.rejected(fixture, result=value)

    def test_input_and_decoded_alias_mutations_leave_bytes_fixed(self):
        fixture = self.base()
        metadata, result, snapshot, prepared = fixture
        frozen = prepared.metadata_bytes, prepared.result_bytes, prepared.structured_review_bytes, prepared.digest
        changed_metadata, changed_result = copy.deepcopy((metadata, result))
        changed_metadata["target_trade_id"] = 999
        changed_result["model"] = "synthetic-rejected-secret"
        self.rejected(fixture, metadata=changed_metadata, result=changed_result)
        for buffer in frozen[:3]:
            decoded = json.loads(buffer)
            decoded.clear()
        self.assertEqual(frozen, (prepared.metadata_bytes, prepared.result_bytes, prepared.structured_review_bytes, prepared.digest))
        self.verify(fixture)
        with self.assertRaises(HistoryWriteContractError):
            prepared_contract.prepare_history_content(metadata=changed_metadata, result=finalized(result), snapshot=snapshot, finalizer_model=result["model"])

    def test_immutable_slots_constructor_copy_pickle_and_subclass(self):
        prepared = self.base()[3]
        self.assertFalse(hasattr(prepared, "__dict__"))
        for name in ("_metadata", "_result", "_structured", "_snapshot", "_seal", "digest", "approved"):
            with self.assertRaises(AttributeError):
                setattr(prepared, name, b"synthetic-rejected-secret")
            with self.assertRaises(AttributeError):
                delattr(prepared, name)
        for create in (lambda: prepared_contract.PreparedHistoryContent(), lambda: copy.copy(prepared),
                       lambda: copy.deepcopy(prepared), lambda: pickle.dumps(prepared), lambda: prepared.__setstate__({})):
            with self.assertRaises(TypeError):
                create()
        with self.assertRaises(TypeError):
            type("Unapproved", (prepared_contract.PreparedHistoryContent,), {})
        self.assertNotIn(self.base()[0]["name"], repr(prepared))

    def test_missing_body_projection_and_partial_shapes_never_rebuild(self):
        fixture = self.base()
        metadata, result, snapshot, _prepared = fixture
        for key in ("display_snapshot", "summary", "structured_review", "chart_display_snapshot", "model"):
            value = copy.deepcopy(result)
            del value[key]
            self.rejected(fixture, result=value)
            with self.assertRaises(HistoryWriteContractError):
                capture_as_finalizer(metadata=metadata, result=finalized(value), snapshot=snapshot, finalizer_model=result["model"])
        for value in ({"charts": []}, {"charts": [], "chart_cards": []}, None):
            self.rejected(fixture, result=replaced(result, ("chart_display_snapshot",), value))
        for key in ("prepared_content", "internal_status", "review_history_id"):
            value = dict(result, **{key: None})
            self.rejected(fixture, result=value)

    def test_capture_model_and_partial_sealed_objective_exactness(self):
        metadata, result, snapshot, _prepared = self.base()
        with self.assertRaises(HistoryWriteContractError):
            capture_as_finalizer(metadata=metadata, result=finalized(result), snapshot=snapshot, finalizer_model="synthetic-other-model")
        value = replaced(finalized(result), ("structured_review", "objective", "result", "realized_pnl"), int(result["structured_review"]["objective"]["result"]["realized_pnl"]))
        self.assertEqual(value["structured_review"]["objective"]["result"]["realized_pnl"], result["structured_review"]["objective"]["result"]["realized_pnl"])
        with self.assertRaises(HistoryWriteContractError):
            capture_as_finalizer(metadata=metadata, result=value, snapshot=snapshot, finalizer_model=result["model"])

    def test_serialized_values_and_capture_mutation_are_rechecked(self):
        metadata, result, snapshot, _prepared = self.base()
        original_encode = prepared_contract._encode
        finalized_value = finalized(copy.deepcopy(result))

        def corrupted(value):
            if value is finalized_value:
                return b'{"status":"ready"}'
            return original_encode(value)

        with patch.object(prepared_contract, "_encode", side_effect=corrupted), self.assertRaises(HistoryWriteContractError):
            capture_as_finalizer(metadata=metadata, result=finalized_value, snapshot=snapshot, finalizer_model=result["model"])

        def mutated(value):
            if value is finalized_value:
                value["model"] = "synthetic-other-model"
            return original_encode(value)

        with patch.object(prepared_contract, "_encode", side_effect=mutated), self.assertRaises(HistoryWriteContractError):
            capture_as_finalizer(metadata=metadata, result=finalized_value, snapshot=snapshot, finalizer_model=result["model"])
        self.verify(self.base())

    def test_forged_types_uninitialized_objects_and_slot_tampering_reject(self):
        fixture = self.base()
        for value in (object(), {}, object.__new__(prepared_contract.PreparedHistoryContent)):
            self.rejected(fixture, prepared=value)
        for value in (object(), {}, object.__new__(ApprovedReviewSnapshot)):
            self.rejected(fixture, snapshot=value)
        metadata, result, snapshot, _prepared = fixture
        forged = capture_as_finalizer(metadata=metadata, result=finalized(result), snapshot=snapshot, finalizer_model=result["model"])
        object.__setattr__(forged, "_metadata", forged.metadata_bytes + b" ")
        self.rejected(fixture, prepared=forged)
        self.verify(fixture)

    def test_pure_without_reseal_normalizers_legacy_cache_or_io(self):
        tree = ast.parse(Path(prepared_contract.__file__).read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual({"hashlib", "json", "re", "backend.core", "backend.core.review_envelope_contract", "backend.core.review_history_write_contract"}, imports)
        with access_tests.producer() as case, ExitStack() as stack:
            import builtins
            import sqlite3
            from backend.core import review_history_adapter, review_legacy_compatibility, trade_review_schema

            def forbidden(*args, **kwargs):
                raise AssertionError("prepared content crossed a forbidden dependency")

            for module, names in ((case.ai, ("seal_review_envelope", "_normalized_semantic_review", "safe_legacy_history_snapshot", "admit_ai_review_history_candidate")),
                                  (ApprovedReviewSnapshot, ("__init__",)), (trade_review_schema, ("normalize_semantic_output",)),
                                  (review_history_adapter, ("adapt_history_record",)),
                                  (review_legacy_compatibility, ("admit_legacy_body", "validate_legacy_body")),
                                  (case.main, ("_normalize_ai_review_result", "_validate_ai_review_cached_access")),
                                  (builtins, ("open",)), (sqlite3, ("connect",)), (os, ("getenv",))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=forbidden))
            stack.enter_context(patch.object(os, "environ", {}))
            for fixture in self.variants.values():
                self.verify(fixture)
            metadata, result, snapshot, _prepared = self.base()
            capture_as_finalizer(metadata=metadata, result=finalized(result), snapshot=snapshot, finalizer_model=result["model"])

    def test_empty_failed_and_no_storage_do_not_publish_prepared_content(self):
        with access_tests.producer() as case:
            with patch.object(case.ai, "prepare_history_content", side_effect=AssertionError("not a history approval")):
                for review_type in ("basic", "advanced"):
                    build = case.ai.build_basic_ai_review if review_type == "basic" else case.ai.build_advanced_ai_review
                    state, approval = {"approved": "old"}, {}
                    result = build([], history_state=state, approval_state=approval)
                    self.assertEqual("empty", result["status"])
                    self.assertIsNone(state["approved"])
                    result = build(case.trades, approval_state={})
                    self.assertEqual("missing_key", result["status"])
                    with patch.object(case.ai, "_call_openai_review", return_value="invalid JSON"):
                        state = {"approved": "old"}
                        result = build(case.trades, history_state=state, approval_state={})
                    self.assertEqual("error", result["status"])
                    self.assertIsNone(state["approved"])

    def test_access_is_validated_later_without_granting_write_approval(self):
        for review_type in ("basic", "advanced"):
            fixture = self.base(review_type)
            for access in access_tests.fixtures():
                if access["review_type"] == review_type:
                    self.verify(fixture, result=replaced(fixture[1], ("access",), access))
            invalid = access_tests.access_fixture(plan="pro", review_type=review_type)
            invalid["wallet"]["validity"]["pro_allowance_resets_at"] = "2099-11-02"
            self.rejected(fixture, result=replaced(fixture[1], ("access",), invalid))
