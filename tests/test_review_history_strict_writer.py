"""Step 6 real production writes and invalid history DB side effects under H4."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
import importlib
import json
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.core.review_display_contract import SCHEMA_VERSION
from backend.core.review_envelope_contract import ApprovedReviewSnapshot
from backend.core import review_history_approved_write as approval_contract
from backend.core.review_history_write_contract import HistoryWriteContractError
from tests import test_review_history_write_access as access_tests
from tests import test_review_history_write_content as content_tests
from tests import test_review_history_producers as producers
from tests.history_legacy_fixture import add_legacy_history_fixture
from tests.review_source_fixtures import approved_chart_fixture, history_chart_fixture


@contextmanager
def history_effects(case):
    """Observe only the owned history database, including read connections/DDL."""
    effects = dict.fromkeys(("connection", "INSERT", "DELETE", "DDL"), 0)
    statements = []
    target = case.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].resolve()
    original = case.history.sqlite3.connect

    def observe_sql(sql):
        statements.append(sql)
        operation = sql.lstrip().split(None, 1)[0].upper()
        if operation in ("INSERT", "DELETE"):
            effects[operation] += 1
        elif operation in ("CREATE", "ALTER", "DROP"):
            effects["DDL"] += 1

    def connect(database, *args, **kwargs):
        label = str(database)
        owned_history = label == str(target) or label.split("?", 1)[0] == target.as_uri()
        if owned_history:
            effects["connection"] += 1
        connection = original(database, *args, **kwargs)
        if owned_history:
            connection.set_trace_callback(observe_sql)
        return connection

    with patch.object(case.history.sqlite3, "connect", side_effect=connect):
        yield effects, statements


class StrictHistoryWriterTest(unittest.TestCase):
    def setUp(self):
        self.case = self.enterContext(access_tests.producer())
        self.history_path = self.case.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"]
        self.enterContext(patch.object(self.case.ai, "_compact_chart_snapshot", return_value=approved_chart_fixture()))

    def capture(self, review_type="basic", status="ready", **kwargs):
        _, (result, state) = self.case.route("session-free", review_type, status, save=False, keyed=False, **kwargs)
        return result, state

    def state_copy(self, state):
        # Keep original approval object identities while separating containers.
        return dict(state, approved=dict(state["approved"]), candidate=copy.deepcopy(state["candidate"]))

    def admitted(self, review_type="basic", status="ready"):
        result, state = self.capture(review_type, status)
        metadata = json.loads(state["approved"]["metadata_json"])
        record = dict(metadata, user_id=state["user_id"], review_type=review_type, source=result["source"],
                      model=result["model"] if status == "ready" else "", created_at="2026-10-09T01:02:03+00:00",
                      ai_review=result, access_snapshot=result["access"])
        write = approval_contract.approve_history_write(record=record,
            prepared_content=state["approved"]["prepared_content"], snapshot=state["approved"]["snapshot"])
        return write, record, result, state

    def assert_zero(self, effects):
        self.assertEqual(dict.fromkeys(effects, 0), effects)

    def reject_save(self, result, state, effects):
        before = copy.deepcopy(result)
        with self.assertRaises((HistoryWriteContractError, KeyError, TypeError, ValueError)) as raised:
            self.case.main._save_ai_review_history_if_enabled(result=result, history_state=state)
        self.assertNotIn("synthetic-rejected-secret", str(raised.exception))
        self.assertEqual(before, result)
        self.assert_zero(effects)
        self.assertFalse(self.history_path.exists())

    def test_twenty_producer_variants_save_and_read_exact_approved_parameters(self):
        case = self.case
        original_writer = case.main.add_review_history
        writes = []

        def write(approved):
            self.assertIs(type(approved), approval_contract.ApprovedHistoryWrite)
            writes.append(approved)
            return original_writer(approved)

        with patch.object(case.main, "add_review_history", side_effect=write), history_effects(case) as (effects, sql):
            for variant in ("session-free", "session-pro", "review", "dev-session-free", "dev-session-pro"):
                for review_type in ("basic", "advanced"):
                    for status in ("ready", "missing_key"):
                        with self.subTest(variant=variant, review_type=review_type, status=status), patch.dict(
                                os.environ, {"ALPHAMATE_ALLOW_DEV_ACCESS": str(variant.startswith("dev-session")).lower()}):
                            result, (_, state) = case.route(variant, review_type, status, keyed=False)
                            approved = writes[-1]
                            stored = case.history.get_review_history(result["review_history_id"], user_id=state["user_id"])
                            exact = json.loads(approved.record_bytes)
                            self.assertEqual(stored["id"], result["review_history_id"])
                            for key in exact:
                                if key != "user_id":
                                    self.assertEqual(exact[key], stored[key])
                            self.assertEqual(exact["ai_review"], stored["ai_review"])
                            self.assertEqual(result["summary"], stored["ai_review"]["summary"])
                            self.assertEqual(result["chart_display_snapshot"], stored["ai_review"]["chart_display_snapshot"])
                            self.assertIsNone(approval_contract.validate_approved_history_write(approved))
            self.assertEqual(20, effects["INSERT"])
            self.assertEqual(0, effects["DELETE"])
            self.assertEqual(20, len(writes))
        with case.fixture.connect("ALPHAMATE_REVIEW_HISTORY_DB_PATH") as connection:
            rows = connection.execute("SELECT user_id, trade_snapshot_json, recent_trades_snapshot_json, chart_snapshot_json, ai_review_json, access_snapshot_json FROM review_history ORDER BY id").fetchall()
        for row, approved in zip(rows, writes):
            self.assertEqual(approved.bind_values[0], row[0])
            self.assertEqual(approved.bind_values[6:11], tuple(row[1:]))

    def test_real_target_and_empty_general_chart_variants(self):
        case = self.case
        for review_type in ("basic", "advanced"):
            for target, idless, name_only in ((None, False, False), (999, False, False), (None, True, True)):
                trades = copy.deepcopy(case.trades)
                for trade in trades:
                    if idless:
                        trade.pop("id")
                    if name_only:
                        trade["ticker"] = ""
                result, (_, state) = case.route("session-free", review_type, "missing_key", target=target, trades=trades, keyed=False)
                row = case.history.get_review_history(result["review_history_id"], user_id=state["user_id"])
                self.assertEqual(target, row["target_trade_id"])
                self.assertEqual({"charts": []}, row["chart_snapshot"])
                self.assertEqual(not idless, "id" in row["trade_snapshot"])

        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                for available in (True, False):
                    with self.subTest(review_type=review_type, status=status, available=available), patch.object(
                            case.main, "build_journal_charts",
                            side_effect=lambda trades: history_chart_fixture(trades, available=available)):
                        result, (_, state) = case.route("session-free", review_type, status, keyed=False)
                        row = case.history.get_review_history(result["review_history_id"], user_id=state["user_id"])
                        metadata = json.loads(state["approved"]["metadata_json"])
                        self.assertEqual(metadata["chart_snapshot"], row["chart_snapshot"])
                        chart = row["chart_snapshot"]["charts"][0]
                        self.assertEqual(("daily", "1d", "daily OHLCV"),
                                         (chart["timeframe"], chart["interval"], chart["source"]))
                        self.assertEqual(available, bool(chart["candles"]))
                        self.assertEqual(available, bool(chart["markers"]))

    def test_immediate_history_replay_identity_for_strong_and_missing_key(self):
        case = self.case
        original = producers.model_output
        def strong(review_type):
            output = original(review_type)
            output["main_issue"] = "과거 **체결** 근거 e\u0301 확인"
            return output
        with patch.object(producers, "model_output", side_effect=strong):
            for review_type in ("basic", "advanced"):
                for status in ("ready", "missing_key"):
                    user_id, token = case.identity("session-free")
                    key = "strict-identity-" + review_type + status
                    batch = case.main.JournalAiReviewIn(privacy_consent=True, review_type=review_type, target_trade_id=2,
                        trades=[case.main.JournalTradeIn(**trade) for trade in case.trades])
                    raw = json.dumps(strong(review_type), ensure_ascii=False) if status == "ready" else ""
                    with patch.object(case.ai, "_call_openai_review", return_value=raw):
                        immediate = case.main.get_journal_ai_review_once(batch, authorization=token,
                            x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                    row = case.history.get_review_history(immediate["review_history_id"], user_id=user_id)
                    detail = case.main.get_journal_review_history_detail(row["id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
                    with history_effects(case) as (effects, sql), patch.object(case.main, "verify_ai_review_access", side_effect=AssertionError("replay charge")), \
                            patch.object(case.main, "add_review_history", side_effect=AssertionError("replay write")), \
                            patch.object(case.ai, "_call_openai_review", side_effect=AssertionError("replay model")), \
                            patch.object(case.main, "refund_ai_review_access", side_effect=AssertionError("replay refund")):
                        replay = case.main.get_journal_ai_review_once(batch, authorization=token,
                            x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                        self.assert_zero(effects)
                    self.assertEqual(immediate["review_history_id"], replay["review_history_id"])
                    for field in ("summary", "display_snapshot", "structured_review", "chart_display_snapshot", "status", "source", "model", "review_type"):
                        self.assertEqual(immediate[field], row["ai_review"][field])
                        self.assertEqual(immediate[field], detail["ai_review"][field])
                        self.assertEqual(immediate[field], replay[field])
                    if status == "ready":
                        self.assertIn("**체결**", row["ai_review"]["summary"])
                        self.assertIn("e\u0301", row["ai_review"]["summary"])

    def test_writer_approved_only_raw_kwargs_and_uninitialized_reject_without_db(self):
        write, record, result, state = self.admitted()
        with history_effects(self.case) as (effects, sql), patch.object(self.case.history, "_connect", wraps=self.case.history._connect) as connect:
            for value in (None, record, state["approved"]["prepared_content"], {}, object(), object.__new__(approval_contract.ApprovedHistoryWrite)):
                with self.assertRaises(HistoryWriteContractError):
                    self.case.history.add_review_history(value)
                self.assert_zero(effects)
            with self.assertRaises(TypeError):
                self.case.history.add_review_history(user_id=state["user_id"], review_type="basic")
            self.assertEqual(0, connect.call_count)
        self.assertFalse(self.history_path.exists())

    def test_writer_tampered_approved_values_reject_before_connect(self):
        original, record, result, state = self.admitted()
        with history_effects(self.case) as (effects, sql):
            for name, value in (("_record", b"{}"), ("_snapshots", ()), ("_bind_values", ()), ("_digest", "0" * 64), ("_origin", object())):
                forged = object.__new__(approval_contract.ApprovedHistoryWrite)
                for slot in original.__slots__:
                    object.__setattr__(forged, slot, getattr(original, slot))
                object.__setattr__(forged, name, value)
                with self.assertRaises(HistoryWriteContractError):
                    self.case.history.add_review_history(forged)
                self.assert_zero(effects)
        self.assertFalse(self.history_path.exists())

    def test_access_missing_extra_wrong_nullable_and_naive_expiry_have_zero_db(self):
        result, state = self.capture()
        mutations = [("missing", ("access", "wallet", "products"), None),
                     ("extra", ("access",), None), ("wrong", ("access", "refunded"), True),
                     ("wrong", ("access", "wallet", "basic", "signup_remaining"), True),
                     ("wrong", ("access", "wallet", "validity", "daily_reset_at"), None)]
        with history_effects(self.case) as (effects, sql):
            for operation, path, wrong in mutations:
                changed = copy.deepcopy(result)
                parent = content_tests.at(changed, path[:-1])
                if operation == "missing":
                    del parent[path[-1]]
                elif operation == "extra":
                    parent[path[-1]]["unknown"] = "synthetic-rejected-secret"
                else:
                    parent[path[-1]] = wrong
                self.reject_save(changed, state, effects)
            for expiry in ("2099-11-02T12:34:56", "2099-02-30T00:00:00Z", "not-a-date", None):
                access = access_tests.access_fixture(plan="pro")
                access["wallet"]["validity"]["pro_allowance_resets_at"] = expiry
                self.reject_save(dict(result, access=access), state, effects)

    def test_metadata_missing_extra_and_shape_valid_replacements_have_zero_db(self):
        result, state = self.capture()
        metadata = json.loads(state["approved"]["metadata_json"])
        with history_effects(self.case) as (effects, sql):
            mutations = [dict(metadata, target_trade_id=999), dict(metadata, user_id="synthetic-other-owner"),
                         dict(metadata, chart_snapshot={"charts": []}, unknown="synthetic-rejected-secret")]
            for key in metadata:
                missing = copy.deepcopy(metadata)
                del missing[key]
                mutations.append(missing)
            for changed in mutations:
                replacement = self.state_copy(state)
                replacement["approved"]["metadata_json"] = json.dumps(changed)
                self.reject_save(result, replacement, effects)

    def test_result_missing_extra_wrong_types_and_partial_shapes_have_zero_db(self):
        for review_type in ("basic", "advanced"):
            result, state = self.capture(review_type)
            with history_effects(self.case) as (effects, sql):
                for key in result:
                    changed = copy.deepcopy(result)
                    del changed[key]
                    self.reject_save(changed, state, effects)
                for changed in (dict(result, unknown="synthetic-rejected-secret"), dict(result, internal_status=None),
                                dict(result, review_history_id=1), dict(result, structured_review={"objective": {}}),
                                dict(result, display_snapshot=None), dict(result, chart_display_snapshot={"charts": []})):
                    self.reject_save(changed, state, effects)

    def test_every_nested_required_key_and_wrong_type_have_zero_db_effects(self):
        for review_type in ("basic", "advanced"):
            with patch.object(self.case.main, "build_journal_charts", side_effect=history_chart_fixture):
                result, state = self.capture(review_type)
            metadata = json.loads(state["approved"]["metadata_json"])
            with history_effects(self.case) as (effects, sql):
                for path, node in content_tests.nodes(metadata):
                    mutations = []
                    if type(node) is dict:
                        mutations.append(dict(node, unknown=None))
                        for key in node:
                            missing = dict(node)
                            del missing[key]
                            mutations.append(missing)
                    mutations.append([] if type(node) is dict else {} if type(node) is list else (
                        1 if type(node) is bool else True if type(node) in (int, float) else None if type(node) is str else "wrong"))
                    for mutation in mutations:
                        replacement = self.state_copy(state)
                        replacement["approved"]["metadata_json"] = json.dumps(content_tests.changed(metadata, path, mutation))
                        self.reject_save(result, replacement, effects)
                for path, node in content_tests.nodes(result):
                    if type(node) is dict:
                        self.reject_save(content_tests.changed(result, path, dict(node, unknown=None)), state, effects)
                        for key in node:
                            missing = dict(node)
                            del missing[key]
                            self.reject_save(content_tests.changed(result, path, missing), state, effects)
                    wrong = [] if type(node) is dict else {} if type(node) is list else (
                        1 if type(node) is bool else True if type(node) in (int, float) else None if type(node) is str else "wrong")
                    self.reject_save(content_tests.changed(result, path, wrong), state, effects)

    def test_equal_numeric_value_wrong_type_still_has_zero_db_effects(self):
        result, state = self.capture()
        with history_effects(self.case) as (effects, sql):
            for path in (("chart_display_snapshot", "charts", 0, "candles", 0, "close"),
                         ("structured_review", "objective", "result", "realized_pnl")):
                original = content_tests.at(result, path)
                replacement = float(original) if type(original) is int else int(original)
                self.assertEqual(original, replacement)
                self.reject_save(content_tests.changed(result, path, replacement), state, effects)

    def test_model_source_type_and_access_relations_have_zero_db_effects(self):
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                result, state = self.capture(review_type, status)
                with history_effects(self.case) as (effects, sql):
                    for key, value in (("model", "synthetic-other-model"), ("source", "none"), ("status", "error"),
                                       ("review_type", "advanced" if review_type == "basic" else "basic")):
                        self.reject_save(dict(result, **{key: value}), state, effects)
                    hidden = content_tests.changed(result, ("structured_review", "objective", "result", "weighted_sell_price"), 70901.0)
                    self.reject_save(hidden, state, effects)

    def test_original_seal_prepared_missing_and_crossed_identity_have_zero_db(self):
        result, state = self.capture()
        other_result, other_state = self.capture()
        clone = ApprovedReviewSnapshot(json.loads(state["approved"]["snapshot"].json_text))
        with history_effects(self.case) as (effects, sql):
            for field, value in (("snapshot", clone), ("snapshot", other_state["approved"]["snapshot"]),
                                 ("prepared_content", other_state["approved"]["prepared_content"]),
                                 ("prepared_content", None), ("snapshot", None)):
                changed = self.state_copy(state)
                changed["approved"][field] = value
                self.reject_save(result, changed, effects)
            changed = self.state_copy(state)
            del changed["approved"]["prepared_content"]
            self.reject_save(result, changed, effects)

    def test_admission_serialization_and_bind_failures_have_zero_db(self):
        result, state = self.capture()
        original_encode = approval_contract._encode
        original_bind = approval_contract._prepare_bind_values
        def bad_json(value):
            return b"{}" if type(value) is dict and "user_id" in value else original_encode(value)
        def bad_bind(record, snapshots):
            values = list(original_bind(record, snapshots))
            values[0] = "synthetic-other-owner"
            return tuple(values)
        with history_effects(self.case) as (effects, sql):
            with patch.object(approval_contract, "_encode", side_effect=bad_json):
                self.reject_save(result, state, effects)
            with patch.object(approval_contract, "_prepare_bind_values", side_effect=bad_bind):
                self.reject_save(result, state, effects)
            with patch.object(approval_contract, "_encode", side_effect=HistoryWriteContractError("fixed serialization error")):
                self.reject_save(result, state, effects)

    def test_invalid_raw_finalizer_projection_not_repaired_for_history(self):
        case = self.case
        original = case.ai._finalize_ai_review
        def flip_close(result):
            candle = result["chart_display_snapshot"]["charts"][0]["candles"][0]
            value = candle["close"]
            candle["close"] = float(value) if type(value) is int else int(value)
        for review_type in ("basic", "advanced"):
            user_id, token = case.identity("session-free")
            batch = case.main.JournalAiReviewIn(privacy_consent=True, review_type=review_type,
                trades=[case.main.JournalTradeIn(**trade) for trade in case.trades])
            for mutation in (lambda result: result.pop("chart_display_snapshot"),
                             flip_close):
                def corrupt(*args, **kwargs):
                    result = original(*args, **kwargs)
                    mutation(result)
                    return result
                with patch.object(case.ai, "_call_openai_review", return_value=json.dumps(producers.model_output(review_type))), \
                        patch.object(case.ai, "_finalize_ai_review", side_effect=corrupt), history_effects(case) as (effects, sql):
                    with self.assertRaises(ValueError):
                        case.main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
                    self.assert_zero(effects)
                self.assertFalse(self.history_path.exists())

    def test_metadata_json_duplicate_extra_and_malformed_reject_before_db(self):
        result, state = self.capture()
        original = state["approved"]["metadata_json"]
        with history_effects(self.case) as (effects, sql):
            for text in (None, "{", "[]", '{"ticker":"005930",' + original[1:],
                         json.dumps(dict(json.loads(original), user_id="synthetic-rejected-secret"))):
                changed = self.state_copy(state)
                changed["approved"]["metadata_json"] = text
                self.reject_save(result, changed, effects)

    def test_invalid_route_refunds_once_then_retry_and_replay_once(self):
        case = self.case
        for review_type in ("basic", "advanced"):
            user_id, token = case.identity("session-free")
            batch = case.main.JournalAiReviewIn(privacy_consent=True, review_type=review_type,
                trades=[case.main.JournalTradeIn(**trade) for trade in case.trades])
            key = "strict-refund-retry-" + review_type
            before = case.access.get_user_entitlements(authorization=token, entitlement_token="")[review_type]["signup_remaining"]
            original_save = case.main._save_ai_review_history_if_enabled
            def reject(*, history_state, result):
                result["structured_review"]["objective"]["result"]["weighted_sell_price"] = 70901.0
                return original_save(history_state=history_state, result=result)
            with patch.object(case.ai, "_call_openai_review", return_value=json.dumps(producers.model_output(review_type))) as model, \
                    patch.object(case.main, "refund_ai_review_access", wraps=case.main.refund_ai_review_access) as refund, \
                    patch.object(case.main, "add_review_history", wraps=case.main.add_review_history) as save, \
                    patch.object(case.main, "delete_review_history", wraps=case.main.delete_review_history) as delete, history_effects(case) as (effects, sql):
                with patch.object(case.main, "_save_ai_review_history_if_enabled", side_effect=reject):
                    with self.assertRaises(HistoryWriteContractError):
                        case.main.get_journal_ai_review_once(batch, authorization=token,
                            x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                self.assert_zero(effects)
                self.assertEqual((1, 0, 0), (refund.call_count, save.call_count, delete.call_count))
                self.assertEqual(before, case.access.get_user_entitlements(authorization=token, entitlement_token="")[review_type]["signup_remaining"])
                self.assertNotIn(case.main._ai_review_idempotency_cache_key(token, key), case.main._ai_review_idempotency_cache)
                retry = case.main.get_journal_ai_review_once(batch, authorization=token,
                    x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                counts = effects.copy(), model.call_count, refund.call_count, save.call_count
                replay = case.main.get_journal_ai_review_once(batch, authorization=token,
                    x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                self.assertEqual(counts, (effects, model.call_count, refund.call_count, save.call_count))
                self.assertEqual((2, 1, 1, 0, 1), (model.call_count, refund.call_count, save.call_count, delete.call_count, effects["INSERT"]))
                self.assertEqual(retry["review_history_id"], replay["review_history_id"])
                self.assertTrue(replay["access"]["idempotent_replay"])
            self.assertEqual(before - 1, case.access.get_user_entitlements(authorization=token, entitlement_token="")[review_type]["signup_remaining"])

    def test_finalization_failure_deletes_only_written_row_then_retry_replay(self):
        case = self.case
        user_id, token = case.identity("session-free")
        batch = case.main.JournalAiReviewIn(privacy_consent=True, review_type="basic",
            trades=[case.main.JournalTradeIn(**trade) for trade in case.trades])
        original = case.main._finish_ai_review_idempotency
        attempts = []
        def fail_once(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("synthetic finish failure")
            return original(*args, **kwargs)
        with patch.object(case.main, "_finish_ai_review_idempotency", side_effect=fail_once), \
                patch.object(case.ai, "_call_openai_review", return_value=json.dumps(producers.model_output("basic"))), \
                patch.object(case.main, "refund_ai_review_access", wraps=case.main.refund_ai_review_access) as refund, history_effects(case) as (effects, sql):
            with self.assertRaisesRegex(RuntimeError, "synthetic finish failure"):
                case.main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="strict-finish")
            self.assertEqual((1, 1, 1), (effects["INSERT"], effects["DELETE"], refund.call_count))
            self.assertEqual([], case.history.list_review_history(user_id=user_id))
            retry = case.main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="strict-finish")
            replay = case.main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="strict-finish")
            self.assertEqual((2, 1, 1), (effects["INSERT"], effects["DELETE"], refund.call_count))
            self.assertEqual([retry["review_history_id"]], [row["id"] for row in case.history.list_review_history(user_id=user_id)])
            self.assertEqual(retry["review_history_id"], replay["review_history_id"])

    def test_post_approval_alias_mutation_cannot_change_insert_parameters(self):
        write, record, result, state = self.admitted()
        fixed = write.record_bytes, write.bind_values
        original = self.case.history._connect
        def mutate_then_connect():
            result["structured_review"].clear()
            record["trade_snapshot"].clear()
            record["user_id"] = "synthetic-other-owner"
            state["candidate"].clear()
            return original()
        with patch.object(self.case.history, "_connect", side_effect=mutate_then_connect):
            saved = self.case.history.add_review_history(write)
        self.assertEqual(fixed, (write.record_bytes, write.bind_values))
        self.assertEqual(json.loads(write.record_bytes)["ai_review"], saved["ai_review"])
        self.assertEqual(json.loads(write.record_bytes)["trade_snapshot"], saved["trade_snapshot"])
        self.assertIsNone(self.case.history.get_review_history(saved["id"], user_id=record["user_id"]))

    def test_no_writer_serialization_default_or_coercion_after_connection(self):
        write, record, result, state = self.admitted("advanced", "missing_key")
        original = self.case.history._connect
        with ExitStack() as stack:
            def connect():
                connection = original()
                stack.enter_context(patch.object(approval_contract, "_encode", side_effect=AssertionError("late write serialization")))
                return connection
            stack.enter_context(patch.object(self.case.history, "_connect", side_effect=connect))
            stack.enter_context(patch.object(self.case.history, "_json_dumps", side_effect=AssertionError("writer legacy serialization")))
            stack.enter_context(patch.object(self.case.history, "_now", side_effect=AssertionError("writer default clock")))
            row = self.case.history.add_review_history(write)
        self.assertEqual("", row["model"])
        self.assertIsNone(row["ai_review"]["model"])
        self.assertEqual(record["created_at"], row["created_at"])

    def test_all_admission_preparation_precedes_connection(self):
        result, state = self.capture()
        events = []
        original_approve = self.case.main.approve_history_write
        original_bind = approval_contract._prepare_bind_values
        original_connect = self.case.history._connect
        def bind(*args):
            events.append("bind-ready")
            return original_bind(*args)
        def approve(**kwargs):
            approved = original_approve(**kwargs)
            events.append("issued")
            return approved
        def connect():
            self.assertEqual(["bind-ready", "issued"], events)
            events.append("connection")
            return original_connect()
        with patch.object(approval_contract, "_prepare_bind_values", side_effect=bind), \
                patch.object(self.case.main, "approve_history_write", side_effect=approve), \
                patch.object(self.case.history, "_connect", side_effect=connect):
            identity = self.case.main._save_ai_review_history_if_enabled(result=result, history_state=state)
        self.assertIs(type(identity), int)
        self.assertEqual(["bind-ready", "issued", "connection"], events)

    def test_storage_off_and_terminal_failures_never_open_history_db(self):
        case = self.case
        user_id, token = case.identity("session-free")
        case.accounts.update_journal_storage_setting(authorization=token, enabled=False)
        with history_effects(case) as (effects, sql):
            for review_type in ("basic", "advanced"):
                result, (_, state) = case.route("session-free", review_type, "missing_key", token=token, keyed=False)
                self.assertIsNone(state)
                self.assertNotIn("review_history_id", result)
            case.accounts.update_journal_storage_setting(authorization=token, enabled=True)
            for review_type in ("basic", "advanced"):
                # Fresh identity for a new advanced signup grant.
                user_id, token = case.identity("session-free")
                batch = case.main.JournalAiReviewIn(privacy_consent=True, review_type=review_type,
                    trades=[case.main.JournalTradeIn(**trade) for trade in case.trades])
                with patch.object(case.ai, "_call_openai_review", return_value="invalid JSON"):
                    result = case.main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
                self.assertEqual("error", result["status"])
                self.assertNotIn("review_history_id", result)
                self.assertTrue(result["access"]["refunded"])
            self.assert_zero(effects)
        self.assertFalse(self.history_path.exists())

    def test_owner_scoped_reads_and_fixture_insertion_remain_separate(self):
        case = self.case
        with patch.object(case.history, "add_review_history", side_effect=AssertionError("fixture used strict writer")):
            fixture = add_legacy_history_fixture(case.history, user_id="synthetic-legacy-owner", review_type="basic", ai_review={"summary": "과거 체결 기록"})
        self.assertEqual("과거 체결 기록", case.history.get_review_history(fixture["id"], user_id="synthetic-legacy-owner")["ai_review"]["summary"])
        self.assertIsNone(case.history.get_review_history(fixture["id"], user_id="synthetic-other-owner"))
        write, record, result, state = self.admitted()
        saved = case.history.add_review_history(write)
        self.assertIsNone(case.history.get_review_history(saved["id"], user_id="synthetic-legacy-owner"))
        self.assertEqual(0, case.history.delete_review_history(saved["id"], user_id="synthetic-legacy-owner"))
        self.assertIsNotNone(case.history.get_review_history(saved["id"], user_id=state["user_id"]))

    def test_pure_write_contracts_and_production_cannot_import_legacy_fixture(self):
        tree = ast.parse(Path(self.case.history.__file__).read_text(encoding="utf-8"))
        writer = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "add_review_history")
        self.assertEqual(["approved"], [arg.arg for arg in writer.args.args])
        self.assertFalse(writer.args.defaults)
        calls = {node.func.id for node in ast.walk(writer) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertTrue({"validate_approved_history_write", "_connect", "get_review_history"} <= calls)
        self.assertFalse(calls & {"str", "int", "dict", "_json_dumps", "_now"})
        for path in (Path(self.case.history.__file__), Path(self.case.main.__file__)):
            self.assertNotIn("history_legacy_fixture", path.read_text(encoding="utf-8"))
        result, state = self.capture()
        with patch.object(self.case.ai, "admit_new_ai_review_history_candidate", side_effect=AssertionError("legacy new-write admission")), \
                patch.object(self.case.ai, "admit_ai_review_history_candidate", side_effect=AssertionError("legacy candidate")), \
                patch.object(self.case.ai, "safe_legacy_history_snapshot", side_effect=AssertionError("legacy adapter")), \
                patch.object(self.case.main, "_validate_ai_review_cached_access", side_effect=AssertionError("cache access validator")):
            identity = self.case.main._save_ai_review_history_if_enabled(result=result, history_state=state)
        self.assertIs(type(identity), int)
