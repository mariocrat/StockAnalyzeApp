"""Default-OFF and explicit-ON actual HTTP generation in H4-owned stores."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
import os
import sqlite3
import unittest
from unittest.mock import patch

from backend.core import review_display_activation as activation
from backend.core import review_approval_bundle as bundles
from backend.core import review_durable_storage_approval as durable
from backend.core.review_display_v2_contract import ReviewDisplayV2Error
from tests import test_review_display_negotiation as support
from tests import test_review_history_paired as history_support
from tests.test_review_finalizer_compatibility import model_output


class ReviewDisplayActivationTest(unittest.TestCase):
    def setUp(self):
        self.support = support.ReviewDisplayNegotiationTest()
        self.addCleanup(self.support.doCleanups)
        self.support.setUp()
        self.http, self.case, self.ai, self.main = (self.support.http, self.support.case,
                                                   self.support.ai, self.support.main)
        self.enterContext(patch.dict(os.environ, {activation.PAIRED_GENERATION_SETTING: "false"}))
        self.sequence = 0

    def execute(self, kind="basic", *, headers=support.DUAL, enabled="true", storage=True,
                raw=None, batch=None, key=None, status=200):
        self.case.accounts.update_journal_storage_setting(authorization=self.case.token, enabled=storage)
        self.sequence += 1
        key = key if key is not None else f"slice6-{self.sequence}-{kind}"
        batch = batch if batch is not None else self.case.batch(kind)
        wallet, before = self.case.balance(kind), self.http.history_state()
        captures = []
        original = self.ai._finalize_ai_review

        def finalize(*args, **kwargs):
            result = original(*args, **kwargs)
            history_state = kwargs.get("history_state")
            captures.append((dict(kwargs["approval_state"]),
                             history_state.get("approved") if history_state is not None else None))
            return result

        with patch.dict(os.environ, {activation.PAIRED_GENERATION_SETTING: enabled}), patch.object(
                self.ai, "_call_openai_review", return_value=json.dumps(model_output(kind)) if raw is None else raw) as model, patch.object(
                self.ai, "_finalize_ai_review", side_effect=finalize), patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_paired_review_history", wraps=self.main.add_paired_review_history) as paired_write, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as v1_write:
            response = self.http.request("POST", "/api/journal/ai-review-once", headers, key=key, batch=batch)
        self.assertEqual(response.status_code, status, response.text)
        metrics = dict(ai=model.call_count, charge=charge.call_count, refund=refund.call_count,
                       paired=paired_write.call_count, v1=v1_write.call_count)
        return response, key, batch, metrics, captures, wallet, before

    def entry(self, key):
        return self.main._ai_review_idempotency_cache[self.main._ai_review_idempotency_cache_key(self.case.token, key)]

    def replay(self, key, batch, headers, *, status=200):
        with patch.object(self.main, "add_paired_review_history", side_effect=AssertionError("replay insert")), patch.object(
                bundles, "compile_approval_bundle", side_effect=AssertionError("replay compile")):
            return self.support.replay(key, batch, headers, status=status)

    def test_gate_defaults_off_and_requires_explicit_true(self):
        with patch.dict(os.environ):
            os.environ.pop(activation.PAIRED_GENERATION_SETTING, None)
            self.assertFalse(activation.paired_generation_enabled())
            for value in ("", "false", "0", "1", "TRUE", "on", "unknown"):
                os.environ[activation.PAIRED_GENERATION_SETTING] = value
                self.assertFalse(activation.paired_generation_enabled())
            os.environ[activation.PAIRED_GENERATION_SETTING] = "true"
            self.assertTrue(activation.paired_generation_enabled())

    def test_off_basic_advanced_keep_original_v1_generation_and_effect_counts(self):
        with patch.object(bundles, "compile_approval_bundle", side_effect=AssertionError("OFF compile")), patch.object(
                durable, "capture_live_paired_history", side_effect=AssertionError("OFF capture")):
            for kind in ("basic", "advanced"):
                response, key, batch, counts, captured, wallet, before = self.execute(kind, enabled="false")
                result = response.json()
                self.assertEqual(counts, dict(ai=1, charge=1, refund=0, paired=0, v1=1))
                self.assertEqual(result["display_snapshot"]["schema_version"], support.capability.V1_CAPABILITY)
                self.assertEqual(set(captured[0][0]), {"snapshot"})
                self.assertEqual(set(captured[0][1]), {"snapshot", "metadata_json", "prepared_content"})
                self.assertEqual(self.entry(key)["execution"].bundle.document["kind"], "v1_only")
                self.assertEqual(self.case.balance(kind), wallet - 1)
                self.assertNotEqual(self.http.history_state(), before)
                with patch.dict(os.environ, {activation.PAIRED_GENERATION_SETTING: "true"}):
                    self.assertEqual(self.replay(key, batch, support.DUAL)["display_snapshot"], result["display_snapshot"])

    def test_on_ready_basic_advanced_share_original_bundle_through_sql_and_cache(self):
        for kind in ("basic", "advanced"):
            for headers, version in ((support.V1, "v1"), (support.DUAL, "v2")):
                response, key, batch, counts, captured, wallet, _ = self.execute(kind, headers=headers)
                result, entry = response.json(), self.entry(key)
                approval, history = captured[0]
                self.assertEqual(counts, dict(ai=1, charge=1, refund=0, paired=1, v1=0))
                self.assertEqual(self.case.balance(kind), wallet - 1)
                self.assertIs(entry["execution"].bundle, approval["bundle"])
                self.assertIs(entry["snapshot"], approval["snapshot"])
                self.assertIs(durable._receipt(history["paired_capture"], durable.LivePairedHistoryApproval)[3], approval["bundle"])
                document = approval["bundle"].document
                self.assertEqual(document["kind"], "paired_v1_v2")
                self.assertEqual(result["display_snapshot"], document["representations"][version]["document"])
                row = self.case.history.get_review_history(result["review_history_id"], user_id=self.case.user_id)
                saved = self.ai.safe_legacy_history_snapshot(row, display_capability=support.capability.DUAL_CAPABILITY)
                self.assertEqual(saved["ai_review"]["display_snapshot"], document["representations"]["v2"]["document"])
                self.assertEqual(saved["ai_review"]["chart_display_snapshot"], result["chart_display_snapshot"])
                self.assertNotEqual(saved["chart_snapshot"]["charts"][0]["candles"], result["chart_display_snapshot"]["charts"][0]["candles"])
                for replay_headers, replay_version in ((support.V1, "v1"), (support.DUAL, "v2")):
                    replay = self.replay(key, batch, replay_headers)
                    self.assertEqual(replay["display_snapshot"], document["representations"][replay_version]["document"])

    def test_on_without_storage_or_idempotency_still_projects_one_approved_execution(self):
        for kind in ("basic", "advanced"):
            before = dict(self.main._ai_review_idempotency_cache)
            response, _, _, counts, captured, wallet, history = self.execute(kind, storage=False, key="")
            self.assertEqual(counts, dict(ai=1, charge=1, refund=0, paired=0, v1=0))
            self.assertEqual(response.json()["display_snapshot"]["schema_version"], support.capability.DUAL_CAPABILITY)
            self.assertIsNone(captured[0][1])
            self.assertEqual(self.case.balance(kind), wallet - 1)
            self.assertEqual(self.main._ai_review_idempotency_cache, before)
            self.assertEqual(self.http.history_state(), history)

    def test_on_missing_error_bodyless_and_empty_never_compile_pairs(self):
        for kind in ("basic", "advanced"):
            for raw in ("", "{}", "not-json"):
                with patch.object(bundles, "compile_approval_bundle", side_effect=AssertionError("terminal pair")):
                    response, key, _, counts, _, _, _ = self.execute(kind, raw=raw)
                result = response.json()
                self.assertNotEqual(result["status"], "ready")
                self.assertEqual(counts["paired"], 0)
                if "display_snapshot" in result:
                    self.assertEqual(result["display_snapshot"]["schema_version"], support.capability.V1_CAPABILITY)
                    self.assertEqual(self.entry(key)["execution"].bundle.document["kind"], "v1_only")
                else:
                    self.assertIsNone(self.entry(key)["execution"].bundle)
            with patch.object(bundles, "compile_approval_bundle", side_effect=AssertionError("empty pair")):
                response, _, _, counts, _, _, _ = self.execute(kind, batch=self.case.batch(kind).model_copy(update={"trades": []}))
            self.assertEqual(response.json()["status"], "empty")
            self.assertEqual(counts["ai"], 0)
            self.assertEqual(counts["paired"], 0)

    def test_on_low_confidence_ready_fallback_is_not_pair_eligible(self):
        for kind in ("basic", "advanced"):
            with patch.object(self.ai, "_review_data_quality", return_value=({"level": "low"}, [])), patch.object(
                    bundles, "compile_approval_bundle", side_effect=AssertionError("fallback pair")):
                response, key, _, counts, _, _, _ = self.execute(kind)
            self.assertEqual(response.json()["status"], "ready")
            self.assertEqual(counts["paired"], 0)
            self.assertEqual(self.entry(key)["execution"].bundle.document["kind"], "v1_only")

    def test_switching_off_preserves_existing_pair_replay_and_history_rollback_floor(self):
        response, key, batch, _, _, _, _ = self.execute()
        result = response.json()
        with patch.dict(os.environ, {activation.PAIRED_GENERATION_SETTING: "false"}), self.http.no_effects(lookup=False, reads=False):
            replay = self.replay(key, batch, support.DUAL)
            detail = self.http.request("GET", f'/api/journal/review-history/{result["review_history_id"]}', support.DUAL)
        self.assertEqual(replay["display_snapshot"], result["display_snapshot"])
        self.assertEqual(detail.json()["ai_review"]["display_snapshot"], result["display_snapshot"])
        later, later_key, _, counts, _, _, _ = self.execute(enabled="false")
        self.assertEqual(counts["paired"], 0)
        self.assertEqual(self.entry(later_key)["execution"].bundle.document["kind"], "v1_only")
        self.assertEqual(later.json()["display_snapshot"]["schema_version"], support.capability.V1_CAPABILITY)

    def test_on_corrupt_cache_either_side_rejects_without_retry_charge_or_insert(self):
        _, key, batch, _, _, _, _ = self.execute()
        bundle = self.entry(key)["execution"].bundle
        original = bundle._json
        for version in ("v1", "v2"):
            value = json.loads(original)
            del value["representations"][version]
            object.__setattr__(bundle, "_json", bundles.encode(value))
            try:
                for headers in (support.V1, support.DUAL):
                    self.replay(key, batch, headers, status=500)
            finally:
                object.__setattr__(bundle, "_json", original)

    def test_on_corrupt_sql_pair_unavailable_on_list_detail_export_without_repair(self):
        response, _, _, _, _, _, _ = self.execute()
        identity = response.json()["review_history_id"]
        history = self.support.history
        raw = history.sql("SELECT ai_review_json FROM review_history WHERE id=?", (identity,))[0][0]
        value = json.loads(raw)
        value["payload_digest"] = "0" * 64
        history.replace_review(identity, json.dumps(value))
        before = self.http.history_state()
        with self.http.no_effects(reads=False), patch.object(self.main, "add_paired_review_history", side_effect=AssertionError("read insert")):
            for headers in (support.V1, support.DUAL):
                detail = self.http.request("GET", f"/api/journal/review-history/{identity}", headers)
                listed = self.http.request("GET", "/api/journal/review-history", headers)
                exported = self.http.request("GET", "/api/me/export-data", headers)
                self.assertEqual(detail.json()["history_read_status"], "unavailable")
                self.assertEqual(listed.json()[0]["history_read_status"], "unavailable")
                self.assertEqual(exported.json()["review_history"][0]["history_read_status"], "unavailable")
        self.assertEqual(self.http.history_state(), before)

    def test_on_v2_compiler_failure_never_falls_back_or_persists_partial_v1(self):
        with patch.object(bundles, "compile_body", side_effect=ReviewDisplayV2Error("COMPILER_OUTPUT_MISMATCH")) as compiler:
            _, key, _, counts, captured, wallet, before = self.execute(status=500)
        self.assertEqual(compiler.call_count, 1)
        self.assertEqual(counts, dict(ai=1, charge=1, refund=1, paired=0, v1=0))
        self.assertEqual(captured, [])
        self.assertEqual(self.case.balance("basic"), wallet)
        self.assertEqual(self.http.history_state(), before)
        self.assertNotIn(self.main._ai_review_idempotency_cache_key(self.case.token, key), self.main._ai_review_idempotency_cache)

    def test_on_insert_failure_rolls_back_and_refunds_once_without_retry(self):
        with patch.object(self.case.history, "_insert_paired_review_history", side_effect=sqlite3.OperationalError("synthetic INSERT")) as insert:
            _, _, _, counts, _, wallet, before = self.execute(status=500)
        self.assertEqual(insert.call_count, 1)
        self.assertEqual(counts, dict(ai=1, charge=1, refund=1, paired=1, v1=0))
        self.assertEqual(self.case.balance("basic"), wallet)
        # First storage access may bootstrap the existing schema. The failed
        # transaction must leave zero review rows, including no partial v1 row.
        self.assertEqual(self.support.history.count(), 0)

    def test_on_postcommit_publication_failure_compensates_known_owner_once(self):
        original = self.case.history.add_paired_review_history

        def fail(*args, **kwargs):
            committed = original(*args, **kwargs)
            raise self.main.PairedHistoryPublicationError(committed)

        for stage in ("history_close", "cache"):
            target = "add_paired_review_history" if stage == "history_close" else "_finish_ai_review_idempotency"
            options = {"side_effect": fail if stage == "history_close" else RuntimeError("synthetic publication")}
            with patch.object(self.main, target, **options), patch.object(
                    self.main, "delete_review_history", wraps=self.main.delete_review_history) as delete:
                _, _, _, counts, _, wallet, _ = self.execute(status=500)
            self.assertEqual(counts, dict(ai=1, charge=1, refund=1, paired=1, v1=0))
            self.assertEqual(delete.call_count, 1)
            self.assertEqual(delete.call_args.kwargs["user_id"], self.case.user_id)
            self.assertEqual(self.case.balance("basic"), wallet)
            self.assertEqual(self.support.history.count(), 0)

    def test_on_unknown_commit_keeps_pending_and_blocks_blind_same_key_retry(self):
        original = self.case.history._connect
        with patch.object(self.case.history, "_connect", side_effect=lambda: history_support.ConnectionFault(original(), "commit_after")):
            _, key, batch, counts, _, wallet, _ = self.execute(status=500)
        self.assertEqual(counts, dict(ai=1, charge=1, refund=0, paired=1, v1=0))
        self.assertEqual(self.entry(key)["status"], "pending")
        self.assertEqual(self.support.history.count(), 1)
        self.assertEqual(self.case.balance("basic"), wallet - 1)
        self.assertEqual(self.replay(key, batch, support.DUAL, status=409),
                         {"detail": "AI review request is already running. Please retry shortly."})

    def test_on_display_capability_does_not_change_fingerprint_or_early_gate(self):
        _, key, batch, _, _, _, _ = self.execute()
        fingerprint = self.main._ai_review_payload_fingerprint(batch)
        for headers in (support.V1, support.DUAL):
            self.replay(key, batch, headers)
            changed = batch.model_copy(update={"analysis_focus": "entry"})
            self.assertEqual(self.replay(key, changed, headers, status=409),
                             {"detail": "Idempotency key was reused with a different AI review request."})
        self.assertEqual(self.entry(key)["payload_fingerprint"], fingerprint)
        with patch.dict(os.environ, {activation.PAIRED_GENERATION_SETTING: "true"}), self.http.no_effects(), patch.object(
                self.main, "add_paired_review_history", side_effect=AssertionError("unsupported insert")):
            rejected = self.http.request("POST", "/api/journal/ai-review-once", [(support.gate_support.HEADER, "review-display.v3")])
        self.assertEqual(rejected.status_code, 426)
