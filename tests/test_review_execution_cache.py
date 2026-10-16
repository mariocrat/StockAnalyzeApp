"""Slice 3C process-local whole bundle and real HTTP replay under H4."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import ast
import copy
import json
import pickle
from pathlib import Path
import unittest
from unittest.mock import patch

from core import review_execution_cache as execution
from core import review_approval_bundle as bundles
from tests import test_review_display_client_gate as http_fixture
from tests.test_review_durable_storage import fixture
from core.review_source_projection import trade_payload


class WholeExecutionCacheTest(unittest.TestCase):
    def setUp(self):
        self.http = http_fixture.ReviewDisplayClientGateTest()
        self.addCleanup(self.http.doCleanups)
        self.http.setUp()
        self.main, self.case, self.ai = self.http.main, self.http.case, self.http.ai

    def seed(self, kind="advanced"):
        self.case.strong_route(kind)
        _, key, entry, _ = self.case.last
        return key, entry

    def paired(self, kind="advanced"):
        _, seed = self.seed(kind)
        value = fixture(kind, owner=self.case.user_id)
        result = copy.deepcopy(value["record"]["ai_review"])
        result["access"] = copy.deepcopy(seed["result"]["access"])
        batch = self.main.JournalAiReviewIn(privacy_consent=True, review_type=kind,
            trades=[self.main.JournalTradeIn(**trade_payload(trade)) for trade in value["source"].trades])
        key = "slice3c-paired-" + kind
        cache_key, _ = self.main._begin_ai_review_idempotency(
            self.case.token, key, self.main._ai_review_payload_fingerprint(batch))
        self.main._finish_ai_review_idempotency(cache_key, result,
            snapshot=value["snapshot"], bundle=value["bundle"])
        return key, self.main._ai_review_idempotency_cache[cache_key], batch, value

    def replay(self, key, entry, batch, *, status=200):
        return self.http.assert_cached_request_has_no_effects(
            batch.review_type, key, entry, status=status, batch=batch)

    def test_paired_basic_and_advanced_hit_project_v1_without_any_execution_effects(self):
        for kind in ("basic", "advanced"):
            key, entry, batch, value = self.paired(kind)
            response = self.replay(key, entry, batch).json()
            expected = copy.deepcopy(entry["result"])
            expected["access"]["idempotent_replay"] = True
            self.assertEqual(response, expected)
            self.assertEqual(response["display_snapshot"], value["bundle"].document["representations"]["v1"]["document"])
            self.assertEqual(response["chart_display_snapshot"], value["record"]["ai_review"]["chart_display_snapshot"])
            self.assertNotIn("representations", response)
            self.assertEqual(entry["execution"].bundle.document["kind"], "paired_v1_v2")

    def test_each_representation_and_provenance_corruption_is_fail_closed_not_a_miss(self):
        key, entry, batch, value = self.paired()
        bundle = value["bundle"]
        original = bundle._json, bundle._digest
        for target in ("v1", "v2", "missing_v1", "missing_v2", "kind", "source", "objective", "compiler"):
            with self.subTest(target=target):
                candidate = json.loads(original[0])
                if target in ("v1", "v2"):
                    candidate["representations"][target]["document"]["canonical_text"] += " changed"
                elif target.startswith("missing_"):
                    del candidate["representations"][target[8:]]
                elif target == "kind":
                    candidate["kind"] = "v1_only"
                elif target in ("source", "objective"):
                    candidate[target + "_identity"] = "0" * 64
                else:
                    candidate["representations"]["v2"]["compiler_version"] = "future"
                raw = bundles.encode(candidate)
                object.__setattr__(bundle, "_json", raw)
                object.__setattr__(bundle, "_digest", bundles._digest(raw, bundle._source, bundle._objective))
                try:
                    self.replay(key, entry, batch, status=500)
                finally:
                    object.__setattr__(bundle, "_json", original[0])
                    object.__setattr__(bundle, "_digest", original[1])

    def test_source_and_snapshot_mutation_reject_without_read_time_repair(self):
        key, entry, batch, value = self.paired()
        for obj, attr, changed in ((value["source"], "notice", "changed source"),
                                   (value["snapshot"], "_json", b"{}")):
            original = getattr(obj, attr)
            object.__setattr__(obj, attr, changed)
            try:
                self.replay(key, entry, batch, status=500)
            finally:
                object.__setattr__(obj, attr, original)

    def test_response_access_history_and_execution_metadata_are_bound_exactly(self):
        key, entry = self.seed()
        batch = self.case.batch("advanced")
        mutations = []
        for field, replacement in (("review_history_id", entry["result"]["review_history_id"] + 1),
                                   ("model", "other-model"), ("summary", "different summary")):
            result = copy.deepcopy(entry["result"]); result[field] = replacement
            mutations.append({**entry, "result": result})
        result = json.loads(json.dumps(entry["result"]))
        # Still valid wallet/quota shape and values; original issued access differs.
        result["access"]["wallet"]["advanced"]["purchased_remaining"] += 1
        result["access"]["quota"]["advanced"]["purchased_remaining"] += 1
        mutations += [{**entry, "result": result}, {**entry, "payload_fingerprint": "0" * 64},
                      {**entry, "expires_at": entry["expires_at"] + self.main.datetime.timedelta(seconds=1)}]
        class DerivedDateTime(self.main.datetime.datetime):
            pass
        derived = DerivedDateTime.fromtimestamp(entry["expires_at"].timestamp(), self.main.datetime.timezone.utc)
        self.assertEqual(derived, entry["expires_at"])
        with self.assertRaises(ValueError):
            execution.approve_cached_execution(cache_key=key, fingerprint=entry["payload_fingerprint"],
                expires_at=derived, result=entry["result"], snapshot=entry["snapshot"])
        mutations.append({**entry, "expires_at": derived})
        auxiliary = copy.deepcopy(entry["result"])
        auxiliary["chart_display_snapshot"] = {"charts": [], "chart_cards": []}
        mutations.append({**entry, "result": auxiliary})
        for changed in mutations:
            self.replay(key, changed, batch, status=500)

    def test_cross_key_copy_is_corruption_even_before_expiry_or_capacity_pruning(self):
        key, entry, batch, _ = self.paired()
        for changed in (entry, {**entry, "expires_at": entry["expires_at"] - self.main.datetime.timedelta(days=1)}):
            self.replay("slice3c-foreign-key", changed, batch, status=500)
        self.replay(key, entry, batch)

    def test_same_key_changed_body_conflicts_and_token_exclusions_preserve_replay(self):
        key, entry, batch, _ = self.paired()
        changed = batch.model_copy(update={"analysis_focus": "entry"})
        response = self.replay(key, entry, changed, status=409)
        self.assertEqual(response.json()["detail"], "Idempotency key was reused with a different AI review request.")
        excluded = batch.model_copy(update={"ad_reward_token": "unused-synthetic", "entitlement_token": "unused-synthetic"})
        self.assertEqual(self.main._ai_review_payload_fingerprint(batch), self.main._ai_review_payload_fingerprint(excluded))
        self.replay(key, entry, excluded)

    def test_ttl_expiry_keeps_new_execution_semantics_without_receipt_mutation(self):
        key, entry = self.seed()
        with patch.object(self.main, "_ai_review_idempotency_now",
                          return_value=entry["expires_at"] + self.main.datetime.timedelta(seconds=1)):
            self.http.assert_fresh_idempotent_execution("advanced", key)

    def test_restart_equivalent_cache_loss_executes_again_without_history_post_ledger(self):
        key, entry = self.seed()
        old_history_id = entry["result"]["review_history_id"]
        with patch.object(self.main, "_ai_review_idempotency_cache", {}), patch.object(
                self.main, "get_review_history", side_effect=AssertionError("history POST replay lookup")):
            cache = self.http.assert_fresh_idempotent_execution("advanced", key)
        cache_key = self.main._ai_review_idempotency_cache_key(self.case.token, key)
        self.assertNotEqual(old_history_id, cache[cache_key]["result"]["review_history_id"])

    def test_display_capability_is_not_execution_fingerprint_or_paired_activation(self):
        key, entry, batch, _ = self.paired()
        fingerprint = self.main._ai_review_payload_fingerprint(batch)
        with self.http.no_effects(lookup=False):
            response = self.http.request("POST", "/api/journal/ai-review-once",
                [(http_fixture.HEADER, "review-display.v2")], key=key, batch=batch)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_snapshot"],
                         entry["execution"].bundle.document["representations"]["v2"]["document"])
        self.assertEqual(entry["execution"].bundle.document["kind"], "paired_v1_v2")
        self.assertEqual(self.main._ai_review_payload_fingerprint(batch), fingerprint)
        self.replay(key, entry, batch)

    def test_live_basic_advanced_generation_and_existing_history_stay_v1_only(self):
        for kind in ("basic", "advanced"):
            key, entry = self.seed(kind)
            self.assertEqual(entry["execution"].bundle.document["kind"], "v1_only")
            self.http.assert_cached_request_has_no_effects(kind, key, entry, status=200)
            stored = self.case.history.get_review_history(entry["result"]["review_history_id"], user_id=self.case.user_id)
            self.assertIs(type(stored), dict)
            self.assertNotIn("storage_schema_version", stored["ai_review"])
            empty = self.case.batch(kind).model_copy(update={"trades": []})
            empty_key = "slice3c-empty-" + kind
            with patch.object(self.ai, "_call_openai_review", side_effect=AssertionError("empty model call")):
                response = self.http.request("POST", "/api/journal/ai-review-once", http_fixture.SUPPORTED,
                                             review_type=kind, key=empty_key, batch=empty)
            self.assertEqual(response.status_code, 200, response.text)
            empty_entry = self.main._ai_review_idempotency_cache[
                self.main._ai_review_idempotency_cache_key(self.case.token, empty_key)]
            self.assertEqual(empty_entry["execution"].bundle.document["kind"], "v1_only")
            self.assertEqual(empty_entry["execution"].bundle.document["status"], "empty")
            self.replay(empty_key, empty_entry, empty)

    def test_hit_checks_receipts_without_body_compilers_and_owns_projection_copies(self):
        key, entry, batch, _ = self.paired()
        with patch.object(execution, "compile_review_envelope", side_effect=AssertionError("recompile")), patch.object(
                bundles, "compile_body", side_effect=AssertionError("v2 recompile")), patch.object(
                bundles, "compile_review_body", side_effect=AssertionError("v1 recompile")):
            first = self.replay(key, entry, batch).json()
            first["access"]["wallet"]["advanced"]["purchased_remaining"] = 999
            self.assertNotEqual(first, self.replay(key, entry, batch).json())
        tree = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(any("durable" in name or "history_json_codec" in name for name in imported if name))

    def test_raw_or_restored_execution_authority_and_receipt_substitution_reject(self):
        key, entry, batch, _ = self.paired()
        with self.assertRaises(TypeError):
            execution.ApprovedCachedExecution()
        with self.assertRaises(TypeError):
            pickle.dumps(entry["execution"])
        fake = object.__new__(execution.ApprovedCachedExecution)
        object.__setattr__(fake, "_receipt", entry["execution"]._receipt)
        for receipt in ({}, fake, None):
            self.replay(key, {**entry, "execution": receipt}, batch, status=500)
        other_key, other = self.seed("basic")
        self.replay(key, {**entry, "execution": other["execution"]}, batch, status=500)
        self.assertNotEqual(key, other_key)
        receipt = entry["execution"]._receipt
        object.__setattr__(entry["execution"], "_receipt", tuple(list(receipt)))
        try:
            self.replay(key, entry, batch, status=500)
        finally:
            object.__setattr__(entry["execution"], "_receipt", receipt)

    def test_invalid_publication_leaves_only_pending_and_never_replaces_with_partial_pair(self):
        _, seed = self.seed()
        key, _ = self.main._begin_ai_review_idempotency(self.case.token, "slice3c-invalid-publication", "a" * 64)
        original = self.main._ai_review_idempotency_cache[key]
        with self.assertRaises(ValueError):
            self.main._finish_ai_review_idempotency(key, seed["result"], snapshot=seed["snapshot"], bundle={})
        self.assertIs(self.main._ai_review_idempotency_cache[key], original)
        self.assertEqual(original["status"], "pending")

    def test_bodyless_terminal_remains_bundleless_but_whole_response_is_protected(self):
        _, seed = self.seed()
        result = dict(status="error", source="none", summary="", review_type="advanced",
                      internal_status="safety_rejected", access=copy.deepcopy(seed["result"]["access"]))
        result["access"]["refunded"] = True
        batch = self.case.batch("advanced")
        key = "slice3c-terminal"
        cache_key, _ = self.main._begin_ai_review_idempotency(self.case.token, key, self.main._ai_review_payload_fingerprint(batch))
        self.main._finish_ai_review_idempotency(cache_key, result)
        entry = self.main._ai_review_idempotency_cache[cache_key]
        self.assertIsNone(entry["execution"].bundle)
        self.replay(key, entry, batch)
        self.replay(key, {**entry, "result": {**entry["result"], "summary": "injected"}}, batch, status=500)
