"""Slice 3B real SQLite boundaries and whole paired history reads under H4."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from backend.core import review_durable_storage_approval as durable
from backend.core import review_history_paired as paired
from backend.core.review_history_json_codec import DurableStorageError, canonical_json, outer_json
from backend.core.review_durable_storage_contract import payload_digest
from tests.test_review_durable_storage import fixture, unsafe_text
import tests.test_review_display_client_gate as _gate_support
from tests.test_review_history_adapter import legacy_record, canonical_record
from tests.history_legacy_fixture import add_legacy_history_fixture
from tests.test_review_finalizer_compatibility import model_output


class ConnectionFault:
    def __init__(self, connection, fault):
        self.connection, self.fault = connection, fault

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, statement, *args):
        if self.fault == "insert" and statement.strip().upper().startswith("INSERT"):
            raise sqlite3.OperationalError("synthetic insert failure")
        return self.connection.execute(statement, *args)

    def commit(self):
        if self.fault == "commit_before":
            raise sqlite3.OperationalError("synthetic commit before acknowledgement")
        if self.fault == "commit_rolled_back":
            self.connection.rollback()
            raise sqlite3.OperationalError("synthetic commit outcome with automatic rollback")
        self.connection.commit()
        if self.fault.startswith("commit_after"):
            raise sqlite3.OperationalError("synthetic commit acknowledgement lost")

    def close(self):
        self.connection.close()
        if self.fault.endswith("close"):
            raise sqlite3.OperationalError("synthetic post-commit close failure")


class PairedHistoryIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.gate = _gate_support.ReviewDisplayClientGateTest()
        self.addCleanup(self.gate.doCleanups)
        self.gate.setUp()
        self.history, self.ai = self.gate.case.history, self.gate.ai
        self.owner = self.gate.case.user_id

    def value(self, kind="basic", **kwargs):
        return fixture(kind, owner=self.owner, **kwargs)

    def save(self, value):
        return self.history.add_paired_review_history(value["capture"], value["write"], unsafe_text=unsafe_text)

    def view(self, identity, *, owner=None):
        return self.ai.safe_legacy_history_snapshot(
            self.history.get_review_history(identity, user_id=self.owner if owner is None else owner))

    def sql(self, statement, parameters=(), *, write=False):
        connection = self.history._connect() if write else self.history._read_connect()
        if connection is None:
            return []
        try:
            rows = connection.execute(statement, parameters).fetchall()
            if write:
                connection.commit()
            return rows
        finally:
            connection.close()

    def count(self):
        return len(self.sql("SELECT id FROM review_history"))

    def replace_review(self, identity, text):
        self.sql("UPDATE review_history SET ai_review_json=? WHERE id=?", (text, identity), write=True)

    def unavailable(self, record):
        self.assertEqual(record["history_read_status"], "unavailable")
        self.assertFalse(record["trade_restore_allowed"])
        self.assertIsNone(record["trade_snapshot"])
        self.assertEqual(record["recent_trades_snapshot"], [])
        self.assertEqual(record["chart_snapshot"], {})
        self.assertNotIn("chart_display_snapshot", record["ai_review"])
        self.assertNotIn("user_id", record)

    def test_basic_advanced_atomic_save_reopen_keeps_body_and_distinct_chart_sources(self):
        for kind in ("basic", "advanced"):
            value = self.value(kind)
            with self.gate.no_effects(lookup=False, reads=False):
                committed = self.save(value)
                record = self.view(committed.id)
            self.assertTrue(committed.committed)
            self.assertEqual(committed.user_id, self.owner)
            self.assertEqual(record, committed.record)
            self.assertEqual(record["history_read_status"], "canonical")
            self.assertEqual(record["ai_review"]["display_snapshot"], value["record"]["ai_review"]["display_snapshot"])
            self.assertEqual(record["ai_review"]["chart_display_snapshot"], value["record"]["ai_review"]["chart_display_snapshot"])
            self.assertEqual(record["chart_snapshot"], value["record"]["chart_snapshot"])
            self.assertNotEqual(record["chart_snapshot"]["charts"][0]["candles"],
                                record["ai_review"]["chart_display_snapshot"]["charts"][0]["candles"])
            self.assertTrue(record["ai_review"]["chart_display_snapshot"]["chart_cards"])
            self.assertNotIn("structured_review", record["ai_review"])
            self.assertEqual(record["access_snapshot"], value["record"]["access_snapshot"])
            raw = self.sql("SELECT ai_review_json FROM review_history WHERE id=?", (committed.id,))[0][0]
            self.assertEqual(json.loads(raw)["kind"], "paired_v1_v2")
            self.assertEqual(set(json.loads(raw)), {"storage_schema_version", "kind", "codec_version", "payload", "payload_digest"})

    def test_empty_and_chart_only_approved_auxiliary_remain_exact(self):
        for kind in ("basic", "advanced"):
            for options in ({"empty": True}, {"cards": False}):
                value = self.value(kind, **options)
                committed = self.save(value)
                self.assertEqual(self.view(committed.id)["ai_review"]["chart_display_snapshot"],
                                 value["record"]["ai_review"]["chart_display_snapshot"])
                self.assertTrue(self.view(committed.id)["chart_snapshot"]["charts"])

    def test_list_detail_reopen_export_use_one_admission_without_history_writes(self):
        committed = self.save(self.value("advanced"))
        before = self.gate.history_state()
        original = paired.admit_stored_paired_history
        with patch.object(paired, "admit_stored_paired_history", wraps=original) as admit, self.gate.no_effects(lookup=False, reads=False):
            listed = self.gate.request("GET", "/api/journal/review-history", _gate_support.SUPPORTED)
            detail = self.gate.request("GET", f"/api/journal/review-history/{committed.id}", _gate_support.SUPPORTED)
            reopened = self.gate.request("GET", f"/api/journal/review-history/{committed.id}", _gate_support.SUPPORTED)
            exported = self.gate.request("GET", "/api/me/export-data", _gate_support.SUPPORTED)
        self.assertEqual([200] * 4, [r.status_code for r in (listed, detail, reopened, exported)])
        self.assertEqual(admit.call_count, 4)
        self.assertEqual(detail.json(), reopened.json())
        self.assertEqual(detail.json(), exported.json()["review_history"][0])
        for key, value in listed.json()[0].items():
            self.assertEqual(value, detail.json()[key])
        self.assertEqual(before, self.gate.history_state())
        encoded = json.dumps(exported.json()["review_history"])
        for internal in ("payload_digest", "source_identity", "objective_identity", "representations", "codec_version"):
            self.assertNotIn(internal, encoded)

    def test_ownership_and_storage_opt_in_precede_paired_admission(self):
        committed = self.save(self.value())
        self.assertIsNone(self.history.get_review_history(committed.id, user_id="other-owner"))
        with patch.object(paired, "admit_stored_paired_history", side_effect=AssertionError("must not admit")):
            denied = self.gate.request("GET", f"/api/journal/review-history/{committed.id}", _gate_support.SUPPORTED,
                                       token="Bearer invalid-synthetic")
            self.assertEqual(denied.status_code, 401)
            self.gate.case.accounts.update_journal_storage_setting(authorization=self.gate.case.token, enabled=False)
            self.assertEqual(self.gate.request("GET", "/api/journal/review-history", _gate_support.SUPPORTED).json(), [])
            self.assertEqual(self.gate.request("GET", f"/api/journal/review-history/{committed.id}", _gate_support.SUPPORTED).status_code, 403)
            exported = self.gate.request("GET", "/api/me/export-data", _gate_support.SUPPORTED)
            self.unavailable(exported.json()["review_history"][0])

    def test_markerless_legacy_and_v1_rows_keep_existing_read_and_write_path(self):
        for record in (legacy_record(), canonical_record()):
            fields = {key: record[key] for key in ("review_type", "ticker", "name", "trade_date", "target_trade_id",
                "trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot", "model", "source")}
            saved = add_legacy_history_fixture(self.history, user_id=self.owner, **fields)
            self.assertEqual(self.view(saved["id"])["history_read_status"],
                             "canonical" if "display_snapshot" in record["ai_review"] else "adapted")
        value = self.value()
        saved = self.history.add_review_history(value["write"])
        self.assertIs(type(saved), dict)
        self.assertFalse(paired.paired_marker(saved["ai_review"]))
        self.assertEqual(self.view(saved["id"])["ai_review"]["structured_review"],
                         value["record"]["ai_review"]["structured_review"])
        self.gate.case.accounts.update_journal_storage_setting(authorization=self.gate.case.token, enabled=False)
        exported = self.gate.request("GET", "/api/me/export-data", _gate_support.SUPPORTED)
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(all(row["history_read_status"] in {"adapted", "canonical"}
                            for row in exported.json()["review_history"]))

    def test_raw_dict_and_read_authority_cannot_open_writer_or_issue_pair(self):
        value = self.value()
        admission = durable.read_durable_history(value["durable"].bytes, row_context=value["context"],
                                                sql_snapshots=value["sql"], unsafe_text=unsafe_text)
        with patch.object(self.history, "_connect", side_effect=AssertionError("SQL opened")):
            for capture, write in (({}, value["write"]), (admission, value["write"]), (value["capture"], {})):
                with self.subTest(capture=type(capture).__name__), self.assertRaises(DurableStorageError):
                    self.history.add_paired_review_history(capture, write, unsafe_text=unsafe_text)
            with self.assertRaises(DurableStorageError):
                self.history._insert_paired_review_history(None, {})
        self.assertEqual(self.count(), 0)

    def test_actual_id_reservation_obeys_deleted_autoincrement_sequence(self):
        first = self.save(self.value())
        self.history.delete_review_history(first.id, user_id=self.owner)
        self.sql("UPDATE sqlite_sequence SET seq=41 WHERE name='review_history'", write=True)
        second = self.save(self.value())
        self.assertEqual(second.id, 42)
        self.assertEqual(self.sql("SELECT seq FROM sqlite_sequence WHERE name='review_history'")[0][0], 42)
        self.assertEqual(self.view(second.id), second.record)

    def test_absent_null_sequence_and_safe_id_overflow(self):
        self.sql("SELECT id FROM review_history", write=True)
        self.assertEqual(self.save(self.value()).id, 1)
        self.sql("UPDATE sqlite_sequence SET seq=NULL WHERE name='review_history'", write=True)
        self.assertEqual(self.save(self.value()).id, 2)
        self.sql("UPDATE sqlite_sequence SET seq=? WHERE name='review_history'", (2**53 - 1,), write=True)
        with self.assertRaises(DurableStorageError) as error:
            self.save(self.value())
        self.assertEqual(str(error.exception), "INVALID_ROW_ID")
        self.assertEqual(self.count(), 2)

    def test_single_complete_insert_no_placeholder_update_or_post_commit_select(self):
        value = self.value()
        connection = self.history._connect()
        statements = []
        connection.set_trace_callback(statements.append)
        with patch.object(self.history, "_connect", return_value=connection), patch.object(
                self.history, "get_review_history", side_effect=AssertionError("post-commit select")):
            committed = self.save(value)
        normalized = [statement.strip().upper() for statement in statements]
        self.assertEqual(sum(statement.startswith("INSERT INTO REVIEW_HISTORY") for statement in normalized), 1)
        self.assertEqual(sum(statement.startswith("UPDATE") for statement in normalized), 0)
        self.assertLess(next(i for i, s in enumerate(normalized) if s == "BEGIN IMMEDIATE"),
                        next(i for i, s in enumerate(normalized) if s.startswith("SELECT MAX")))
        self.assertEqual(normalized[-1], "COMMIT")
        self.assertEqual(committed.record, self.view(committed.id))

    def test_insert_failure_rolls_back_without_partial_row_or_retry(self):
        value = self.value()
        with patch.object(self.history, "_connect", return_value=ConnectionFault(self.history._connect(), "insert")):
            with self.assertRaises(sqlite3.OperationalError):
                self.save(value)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.save(value).id, 1)

    def test_precommit_failure_rolls_back_and_never_reports_committed(self):
        with patch.object(self.history, "_connect", return_value=ConnectionFault(self.history._connect(), "commit_before")):
            with self.assertRaises(sqlite3.OperationalError):
                self.save(self.value())
        self.assertEqual(self.count(), 0)
        with patch.object(self.history, "CommittedPairedHistoryWrite", side_effect=RuntimeError("synthetic result allocation")):
            with self.assertRaises(RuntimeError):
                self.save(self.value())
        self.assertEqual(self.count(), 0)

    def test_unknown_commit_outcome_retains_identity_and_never_retries_insert(self):
        for expected_id, fault in enumerate(("commit_after", "commit_after_close"), start=1):
            with self.subTest(fault=fault), patch.object(self.history, "_connect",
                    return_value=ConnectionFault(self.history._connect(), fault)):
                with self.assertRaises(self.history.PairedHistoryCommitUnknown) as error:
                    self.save(self.value())
            self.assertEqual(error.exception.user_id, self.owner)
            self.assertEqual(error.exception.row_id, expected_id)
            self.assertEqual(self.count(), expected_id)
            self.assertEqual(self.view(error.exception.row_id)["history_read_status"], "canonical")
        with patch.object(self.history, "_connect", return_value=ConnectionFault(self.history._connect(), "commit_rolled_back")):
            with self.assertRaises(self.history.PairedHistoryCommitUnknown) as error:
                self.save(self.value())
        self.assertEqual(error.exception.row_id, 3)
        self.assertEqual(self.count(), 2)
        self.assertIsNone(self.view(3))

    def test_committed_close_failure_preserves_result_for_owner_scoped_compensation(self):
        with patch.object(self.history, "_connect", return_value=ConnectionFault(self.history._connect(), "close")):
            with self.assertRaises(self.history.PairedHistoryPublicationError) as error:
                self.save(self.value())
        committed = error.exception.committed_result
        self.assertEqual(self.count(), 1)
        self.assertEqual(committed.record, self.view(committed.id))
        self.assertEqual(self.history.delete_review_history(committed.id, user_id="other-owner"), 0)
        self.assertEqual(self.history.delete_review_history(committed.id, user_id=committed.user_id), 1)

    def test_post_commit_reread_failure_keeps_immutable_result_without_retry(self):
        committed = self.save(self.value())
        before = self.gate.history_state()
        with patch.object(self.history, "get_review_history", side_effect=sqlite3.OperationalError("synthetic reread")) as read:
            with self.assertRaises(self.history.PairedHistoryPublicationError) as error:
                self.history.reread_paired_review_history(committed)
        self.assertIs(error.exception.committed_result, committed)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(self.count(), 1)
        self.assertEqual(before, self.gate.history_state())
        copy_view = committed.record
        copy_view["ai_review"]["summary"] = "different consumer view"
        self.assertNotEqual(copy_view, committed.record)
        with self.assertRaises(AttributeError):
            committed.id = 999

    def test_row_scalar_context_corruption_including_owner_fails_closed(self):
        committed = self.save(self.value())
        fields = {"ticker": "000660", "name": "다른 합성 종목", "trade_date": "2026-07-11",
            "target_trade_id": 123, "model": "other-model", "source": "chart-rules",
            "review_type": "advanced", "created_at": "2026-10-14T00:00:00+00:00"}
        originals = self.sql("SELECT * FROM review_history WHERE id=?", (committed.id,))[0]
        for field, replacement in fields.items():
            with self.subTest(field=field):
                self.sql("UPDATE review_history SET " + field + "=? WHERE id=?", (replacement, committed.id), write=True)
                self.unavailable(self.view(committed.id))
                self.sql("UPDATE review_history SET " + field + "=? WHERE id=?", (originals[field], committed.id), write=True)
        self.sql("UPDATE review_history SET user_id='other-owner' WHERE id=?", (committed.id,), write=True)
        self.assertIsNone(self.view(committed.id))
        self.unavailable(self.view(committed.id, owner="other-owner"))

    def test_copying_wrapper_to_another_actual_row_id_is_rejected(self):
        first, second = self.save(self.value()), self.save(self.value())
        raw = self.sql("SELECT ai_review_json FROM review_history WHERE id=?", (first.id,))[0][0]
        self.replace_review(second.id, raw)
        self.unavailable(self.view(second.id))
        self.assertEqual(self.view(first.id)["history_read_status"], "canonical")

    def test_all_sql_snapshot_mutations_and_duplicate_keys_are_rejected(self):
        committed = self.save(self.value())
        original = self.sql("SELECT * FROM review_history WHERE id=?", (committed.id,))[0]
        for column, mutate in (
            ("trade_snapshot_json", lambda v: v.update(price=v["price"] + 1)),
            ("recent_trades_snapshot_json", lambda v: v[0].update(price=v[0]["price"] + 1)),
            ("chart_snapshot_json", lambda v: v["charts"][0]["candles"][0].update(close=1.0)),
            ("access_snapshot_json", lambda v: v.update(source="purchased_advanced"))):
            with self.subTest(column=column):
                value = json.loads(original[column]); mutate(value)
                self.sql("UPDATE review_history SET " + column + "=? WHERE id=?",
                         (json.dumps(value, ensure_ascii=False), committed.id), write=True)
                self.unavailable(self.view(committed.id))
                self.sql("UPDATE review_history SET " + column + "=? WHERE id=?", (original[column], committed.id), write=True)
        self.sql("UPDATE review_history SET trade_snapshot_json=? WHERE id=?",
                 ('{"price":1,"price":2}', committed.id), write=True)
        self.unavailable(self.view(committed.id))

    def test_whole_pair_corruption_rejects_both_sides_auxiliary_and_digest(self):
        committed = self.save(self.value())
        original = json.loads(self.sql("SELECT ai_review_json FROM review_history WHERE id=?", (committed.id,))[0][0])
        for field in ("v1", "v2", "chart_display_snapshot", "objective", "row_context", "snapshot_digests"):
            with self.subTest(field=field):
                outer = copy.deepcopy(original); payload = json.loads(outer["payload"])
                if field in ("v1", "v2"):
                    payload["bundle"]["representations"][field]["document"]["canonical_text"] += " changed"
                elif field == "chart_display_snapshot":
                    payload[field]["chart_cards"][0]["metrics"]["rsi14"] = 7.0
                elif field == "objective":
                    payload[field]["fields"]["result"]["fields"]["total_tax"] += 1
                elif field == "row_context":
                    payload[field]["name"] = "다른 합성"
                else:
                    payload[field]["trade_snapshot"] = "0" * 64
                outer["payload"] = canonical_json(payload).decode("utf-8")
                self.replace_review(committed.id, outer_json(outer).decode("utf-8"))
                self.unavailable(self.view(committed.id))
        outer = copy.deepcopy(original); outer["payload_digest"] = "0" * 64
        self.replace_review(committed.id, outer_json(outer).decode("utf-8"))
        self.unavailable(self.view(committed.id))

    def test_recomputed_digest_invalid_body_or_auxiliary_still_rejects_on_read(self):
        committed = self.save(self.value())
        original = json.loads(self.sql("SELECT ai_review_json FROM review_history WHERE id=?", (committed.id,))[0][0])
        for target in ("v1", "v2", "missing_auxiliary", "malformed_auxiliary"):
            with self.subTest(target=target):
                outer = copy.deepcopy(original); payload = json.loads(outer["payload"])
                if target in ("v1", "v2"):
                    del payload["bundle"]["representations"][target]
                elif target == "missing_auxiliary":
                    del payload["chart_display_snapshot"]
                else:
                    payload["chart_display_snapshot"] = {"charts": [], "chart_cards": None}
                raw = canonical_json(payload)
                outer.update(payload=raw.decode("utf-8"), payload_digest=payload_digest(raw))
                self.replace_review(committed.id, outer_json(outer).decode("utf-8"))
                self.unavailable(self.view(committed.id))

    def test_reserved_partial_unknown_duplicate_or_malformed_markers_never_fallback(self):
        committed = self.save(self.value())
        original = json.loads(self.sql("SELECT ai_review_json FROM review_history WHERE id=?", (committed.id,))[0][0])
        mutations = [json.dumps({"summary": "legacy looking", key: "unknown"}) for key in paired.RESERVED_KEYS]
        mutations += [json.dumps(dict(original, storage_schema_version="future")), json.dumps(dict(original, kind="v1_only")),
            json.dumps(dict(original, codec_version="future")), '{"payload":', '{"payload":"x","payload":"y"}',
            json.dumps({"schema_version": "review-approval-bundle.v1", "summary": "legacy looking"})]
        for text in mutations:
            with self.subTest(marker=text[:40]):
                self.replace_review(committed.id, text)
                before = self.gate.history_state()
                self.unavailable(self.view(committed.id))
                self.assertEqual(before, self.gate.history_state())

    def test_paired_dispatch_is_bounded_and_does_not_decode_legacy_or_compile_body(self):
        committed = self.save(self.value())
        row = self.sql("SELECT * FROM review_history WHERE id=?", (committed.id,))[0]
        with patch.object(self.history, "_json_loads", side_effect=AssertionError("legacy parser")):
            stored = self.history._row_to_detail(row)
        self.assertIs(type(stored), paired.StoredPairedHistoryRow)
        with patch("backend.core.review_body_compiler.compile_review_body", side_effect=AssertionError("v1 compile")), patch(
                "backend.core.review_display_v2_compiler.compile_body", side_effect=AssertionError("v2 compile")), patch(
                "backend.core.review_envelope_compiler.compile_review_envelope", side_effect=AssertionError("envelope compile")):
            self.assertEqual(self.ai.safe_legacy_history_snapshot(stored), committed.record)
        self.assertTrue(paired.paired_marker_in_text('{"p\\u0061yload":"x"}'))
        self.assertFalse(paired.paired_marker_in_text('{"summary":"payload", "chart_snapshot":{"payload":"nested"}}'))
        self.replace_review(committed.id, '{"payload":"' + "x" * 2_622_465 + '"}')
        self.unavailable(self.view(committed.id))

    def test_corrupt_pair_is_unavailable_on_all_public_history_surfaces(self):
        committed = self.save(self.value("advanced"))
        self.replace_review(committed.id, '{"payload":"not a complete wrapper", "summary":"must not display"}')
        before = self.gate.history_state()
        with self.gate.no_effects(lookup=False, reads=False):
            listed = self.gate.request("GET", "/api/journal/review-history", _gate_support.SUPPORTED)
            detail = self.gate.request("GET", f"/api/journal/review-history/{committed.id}", _gate_support.SUPPORTED)
            exported = self.gate.request("GET", "/api/me/export-data", _gate_support.SUPPORTED)
        self.assertEqual(listed.json()[0]["history_read_status"], "unavailable")
        self.unavailable(detail.json())
        self.assertEqual(detail.json(), exported.json()["review_history"][0])
        self.assertEqual(before, self.gate.history_state())

    def test_live_generation_remains_v1_only_even_with_paired_history_support(self):
        from backend.core import review_display_activation, review_approval_bundle
        self.assertFalse(review_display_activation.paired_generation_enabled())
        for kind in ("basic", "advanced"):
            with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(model_output(kind))), patch.object(
                    durable, "capture_live_paired_history", side_effect=AssertionError("paired generation")), patch.object(
                    review_approval_bundle, "compile_approval_bundle", side_effect=AssertionError("paired compiler")), patch.object(
                    self.gate.main, "add_paired_review_history", side_effect=AssertionError("OFF route paired writer")), patch.object(
                    self.history, "add_paired_review_history", side_effect=AssertionError("paired writer")):
                response = self.gate.request("POST", "/api/journal/ai-review-once", _gate_support.SUPPORTED,
                                             review_type=kind, key="slice3b-generation-off-" + kind)
            self.assertEqual(response.status_code, 200, response.text)
            saved = self.history.get_review_history(response.json()["review_history_id"], user_id=self.owner)
            self.assertIs(type(saved), dict)
            self.assertFalse(paired.paired_marker(saved["ai_review"]))
        root = Path(__file__).resolve().parents[1]
        # Slice 6 adds the typed writer path, but all factories remain outside
        # main. Above runtime traps prove default OFF cannot call that path.
        tree = ast.parse((root / "backend/main.py").read_text(encoding="utf-8-sig"))
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertFalse(calls & {"compile_approval_bundle", "capture_live_paired_history", "issue_durable_history"})
