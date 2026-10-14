"""Slice 4 actual HTTP/cache/temp-SQL negotiation under the H4 boundary."""
from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
import unittest
from unittest.mock import patch

from backend.core import review_display_capability as capability
from backend.core import review_execution_cache as execution
from backend.core import review_history_paired as paired
from backend.core import review_approval_bundle as bundles
from backend.core.review_source_projection import trade_payload
from backend.core.review_history_json_codec import canonical_json, outer_json
from backend.core.review_durable_storage_contract import payload_digest
from tests import test_review_execution_cache as cache_support
from tests import test_review_history_paired as history_support
from tests import test_review_display_client_gate as gate_support
from tests import test_review_durable_storage as durable_support
from tests.test_review_history_adapter import canonical_record, legacy_record
from tests.test_review_finalizer_compatibility import model_output

V1 = [(gate_support.HEADER, capability.V1_CAPABILITY)]
DUAL = [(gate_support.HEADER, capability.DUAL_CAPABILITY)]


class ReviewDisplayNegotiationTest(unittest.TestCase):
    def setUp(self):
        self.cache = cache_support.WholeExecutionCacheTest()
        self.addCleanup(self.cache.doCleanups)
        self.cache.setUp()
        self.http, self.main, self.case, self.ai = self.cache.http, self.cache.main, self.cache.case, self.cache.ai
        # Reuse the same owned SQL/route setup; imported TestCases are not exposed.
        self.history = history_support.PairedHistoryIntegrationTest()
        self.history.gate, self.history.history, self.history.ai = self.http, self.case.history, self.ai
        self.history.owner = self.case.user_id

    def replay(self, key, batch, headers, *, status=200):
        before, wallet = self.http.history_state(), self.case.balance(batch.review_type)
        with self.http.no_effects(lookup=False) as effects:
            response = self.http.request("POST", "/api/journal/ai-review-once", headers, key=key, batch=batch)
        self.assertEqual(response.status_code, status, response.text)
        self.assertTrue(all(spy.call_count == 0 for spy in effects.values()))
        self.assertEqual(before, self.http.history_state())
        self.assertEqual(wallet, self.case.balance(batch.review_type))
        if status == 500:
            self.assertEqual(response.text, "Internal Server Error")
            return response.text
        return response.json()

    def test_exact_capabilities_and_early_malformed_rejection_on_every_surface(self):
        from backend.core.review_display_client import require_review_display_client
        for value in (capability.V1_CAPABILITY, capability.DUAL_CAPABILITY):
            self.assertEqual(require_review_display_client([value]), value)
        malformed = list(gate_support.UNSUPPORTED.values()) + [
            [(gate_support.HEADER, " " + capability.DUAL_CAPABILITY)],
            [(gate_support.HEADER, capability.DUAL_CAPABILITY + " ")],
            [(gate_support.HEADER, "REVIEW-DISPLAY.V2")],
            [(gate_support.HEADER, capability.V1_CAPABILITY + "," + capability.DUAL_CAPABILITY)],
            [(gate_support.HEADER, capability.DUAL_CAPABILITY + ";version=2")],
            DUAL + DUAL, V1 + DUAL,
        ]
        before = self.http.history_state()
        with self.http.no_effects() as effects:
            for headers in malformed:
                for method, path in (("POST", "/api/journal/ai-review-once"),
                    ("GET", "/api/journal/review-history"), ("GET", "/api/journal/review-history/1"),
                    ("GET", "/api/me/export-data")):
                    response = self.http.request(method, path, headers)
                    self.assertEqual((response.status_code, response.json()), (426, gate_support.FIXED_ERROR))
        self.assertTrue(all(spy.call_count == 0 for spy in effects.values()))
        self.assertEqual(before, self.http.history_state())
        self.assertEqual(self.main._ai_review_idempotency_cache, {})

    def test_same_paired_execution_switches_v1_v2_v1_without_effects_or_aliases(self):
        for kind in ("basic", "advanced"):
            key, entry, batch, value = self.cache.paired(kind)
            original = copy.deepcopy(entry["result"])
            for headers, version in ((V1, "v1"), (DUAL, "v2"), (V1, "v1"), (DUAL, "v2")):
                response = self.replay(key, batch, headers)
                expected = copy.deepcopy(original)
                expected["display_snapshot"] = value["bundle"].document["representations"][version]["document"]
                expected["access"]["idempotent_replay"] = True
                self.assertEqual(response, expected)
                response["display_snapshot"]["canonical_text"] = "consumer mutation"
            self.assertEqual(entry["result"], original)
            self.assertEqual(entry["execution"].bundle.document["kind"], "paired_v1_v2")

    def test_v1_only_ready_and_fallback_remain_v1_without_missing_side_regeneration(self):
        for kind in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                self.case.run_route(kind, raw="" if status == "missing_key" else None, status=status, storage=True)
                batch, key, entry, _ = self.case.last
                before = copy.deepcopy(entry["result"])
                with patch.object(bundles, "compile_approval_bundle", side_effect=AssertionError("upgrade")):
                    response = self.replay(key, batch, DUAL)
                before["access"]["idempotent_replay"] = True
                self.assertEqual(response, before)
                self.assertEqual(response["display_snapshot"]["schema_version"], capability.V1_CAPABILITY)
                self.assertEqual(entry["execution"].bundle.document["kind"], "v1_only")

    def test_fresh_dual_requests_generate_only_v1_then_replay_without_more_execution(self):
        for kind in ("basic", "advanced"):
            before, wallet = len(self.case.history.list_review_history(user_id=self.case.user_id)), self.case.balance(kind)
            batch, key = self.case.batch(kind), "slice4-fresh-dual-" + kind
            with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(model_output(kind))) as model, patch.object(
                    bundles, "compile_approval_bundle", side_effect=AssertionError("paired generation")), patch.object(
                    self.case.history, "add_paired_review_history", side_effect=AssertionError("paired SQL")):
                response = self.http.request("POST", "/api/journal/ai-review-once", DUAL, key=key, batch=batch)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(self.case.balance(kind), wallet - 1)
            self.assertEqual(len(self.case.history.list_review_history(user_id=self.case.user_id)), before + 1)
            entry = self.main._ai_review_idempotency_cache[self.main._ai_review_idempotency_cache_key(self.case.token, key)]
            self.assertEqual(entry["execution"].bundle.document["kind"], "v1_only")
            saved = self.case.history.get_review_history(response.json()["review_history_id"], user_id=self.case.user_id)
            self.assertFalse(paired.paired_marker(saved["ai_review"]))
            for headers in (V1, DUAL):
                self.assertEqual(self.replay(key, batch, headers)["display_snapshot"], response.json()["display_snapshot"])

    def test_bodyless_terminal_and_empty_execution_do_not_acquire_a_v2_body(self):
        _, seed = self.cache.seed()
        batch, key = self.case.batch("advanced"), "slice4-bodyless"
        result = dict(status="error", source="none", summary="", review_type="advanced",
                      internal_status="safety_rejected", access=copy.deepcopy(seed["result"]["access"]))
        result["access"]["refunded"] = True
        cache_key, _ = self.main._begin_ai_review_idempotency(self.case.token, key, self.main._ai_review_payload_fingerprint(batch))
        self.main._finish_ai_review_idempotency(cache_key, result)
        self.assertNotIn("display_snapshot", self.replay(key, batch, DUAL))
        empty = batch.model_copy(update={"trades": []})
        with patch.object(self.ai, "_call_openai_review", side_effect=AssertionError("empty model")):
            response = self.http.request("POST", "/api/journal/ai-review-once", DUAL, key="slice4-empty", batch=empty)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.replay("slice4-empty", empty, DUAL)["display_snapshot"]["schema_version"], capability.V1_CAPABILITY)

    def test_corrupt_unrequested_cache_side_fails_closed_for_both_capabilities(self):
        key, entry, batch, value = self.cache.paired()
        bundle, original = value["bundle"], value["bundle"]._json
        for version in ("v1", "v2"):
            damaged = json.loads(original)
            del damaged["representations"][version]
            object.__setattr__(bundle, "_json", bundles.encode(damaged))
            try:
                for headers in (V1, DUAL):
                    self.replay(key, batch, headers, status=500)
            finally:
                object.__setattr__(bundle, "_json", original)
        self.assertEqual(entry["result"]["display_snapshot"]["schema_version"], capability.V1_CAPABILITY)

    def test_whole_cache_admission_precedes_selection_and_uses_no_compilers(self):
        key, entry, batch, value = self.cache.paired()
        events = []
        original_check, original_select = execution._check_content, execution.select_admitted_body
        def check(*args):
            result = original_check(*args)
            events.append("whole_admitted")
            return result
        def select(*args, **kwargs):
            self.assertTrue(events and events[-1] == "whole_admitted")
            events.append("select")
            return original_select(*args, **kwargs)
        with patch.object(execution, "_check_content", side_effect=check), patch.object(
                execution, "select_admitted_body", side_effect=select), patch.object(
                execution, "compile_review_envelope", side_effect=AssertionError("compile")), patch.object(
                bundles, "compile_body", side_effect=AssertionError("v2 compile")), patch.object(
                bundles, "compile_review_body", side_effect=AssertionError("v1 compile")):
            response = self.replay(key, batch, DUAL)
        self.assertEqual(response["display_snapshot"], value["bundle"].document["representations"]["v2"]["document"])
        self.assertIn("select", events)

    def test_display_capability_preserves_fingerprint_and_changed_body_conflict(self):
        key, entry, batch, _ = self.cache.paired()
        fingerprint = self.main._ai_review_payload_fingerprint(batch)
        changed = batch.model_copy(update={"analysis_focus": "entry"})
        for headers in (V1, DUAL):
            self.assertEqual(self.replay(key, changed, headers, status=409),
                             {"detail": "Idempotency key was reused with a different AI review request."})
            self.replay(key, batch, headers)
        self.assertEqual(fingerprint, entry["payload_fingerprint"])
        self.assertEqual(fingerprint, self.main._ai_review_payload_fingerprint(batch))

    def test_dual_after_ttl_or_restart_is_ordinary_new_execution_not_history_post_replay(self):
        for lost in ("expiry", "restart"):
            key, entry = self.cache.seed("basic")
            batch = self.case.batch("basic")
            before, wallet = len(self.case.history.list_review_history(user_id=self.case.user_id)), self.case.balance("basic")
            target = "_ai_review_idempotency_now" if lost == "expiry" else "_ai_review_idempotency_cache"
            options = {"return_value": entry["expires_at"] + self.main.datetime.timedelta(seconds=1)} if lost == "expiry" else {"new": {}}
            with patch.object(self.main, target, **options), patch.object(self.main, "get_review_history",
                    side_effect=AssertionError("POST history ledger")), patch.object(self.ai, "_call_openai_review",
                    return_value=json.dumps(model_output("basic"))) as model:
                response = self.http.request("POST", "/api/journal/ai-review-once", DUAL, key=key, batch=batch)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(self.case.balance("basic"), wallet - 1)
            self.assertEqual(len(self.case.history.list_review_history(user_id=self.case.user_id)), before + 1)
            self.assertEqual(response.json()["display_snapshot"]["schema_version"], capability.V1_CAPABILITY)

    def test_paired_history_list_detail_reopen_export_project_same_admission_and_chart_sources(self):
        for kind in ("basic", "advanced"):
            _, seed = self.cache.seed(kind)
            value = self.history.value(kind)
            access = copy.deepcopy(seed["result"]["access"])
            value["record"]["ai_review"]["access"] = access
            value["record"]["access_snapshot"] = copy.deepcopy(access)
            value = durable_support.assemble(value["source"], value["snapshot"], value["prepared"], value["record"])
            committed = self.history.save(value)
            batch = self.main.JournalAiReviewIn(privacy_consent=True, review_type=kind,
                trades=[self.main.JournalTradeIn(**trade_payload(trade)) for trade in value["source"].trades])
            key = "slice4-shared-cache-history-" + kind
            cache_key, _ = self.main._begin_ai_review_idempotency(self.case.token, key,
                self.main._ai_review_payload_fingerprint(batch))
            result = copy.deepcopy(value["record"]["ai_review"])
            result["review_history_id"] = committed.id
            self.main._finish_ai_review_idempotency(cache_key, result, snapshot=value["snapshot"], bundle=value["bundle"])
            before, wallet = self.http.history_state(), self.case.balance(kind)
            for headers, version in ((V1, "v1"), (DUAL, "v2"), (V1, "v1")):
                with self.http.no_effects(lookup=False, reads=False), patch.object(
                        bundles, "compile_body", side_effect=AssertionError("history recompile")):
                    detail = self.http.request("GET", f"/api/journal/review-history/{committed.id}", headers)
                    reopened = self.http.request("GET", f"/api/journal/review-history/{committed.id}", headers)
                    exported = self.http.request("GET", "/api/me/export-data", headers)
                    listed = self.http.request("GET", "/api/journal/review-history", headers)
                for response in (detail, reopened, exported, listed):
                    self.assertEqual(response.status_code, 200, response.text)
                record = detail.json()
                self.assertEqual(record, reopened.json())
                self.assertEqual(record, next(r for r in exported.json()["review_history"] if r["id"] == committed.id))
                for field, data in next(r for r in listed.json() if r["id"] == committed.id).items():
                    self.assertEqual(record[field], data)
                self.assertEqual(record["ai_review"]["display_snapshot"], value["bundle"].document["representations"][version]["document"])
                self.assertEqual(record["ai_review"]["summary"], value["record"]["ai_review"]["summary"])
                self.assertEqual(record["ai_review"]["chart_display_snapshot"], value["record"]["ai_review"]["chart_display_snapshot"])
                self.assertEqual(record["chart_snapshot"], value["record"]["chart_snapshot"])
                self.assertNotEqual(record["chart_snapshot"]["charts"][0]["candles"],
                                    record["ai_review"]["chart_display_snapshot"]["charts"][0]["candles"])
                cached_view = self.replay(key, batch, headers)
                for field in ("display_snapshot", "summary", "chart_display_snapshot"):
                    self.assertEqual(cached_view[field], record["ai_review"][field])
                self.assertEqual(cached_view["review_history_id"], committed.id)
                self.assertEqual(cached_view["access"]["wallet"], record["ai_review"]["access"]["wallet"])
            self.assertEqual(before, self.http.history_state())
            self.assertEqual(wallet, self.case.balance(kind))

    def test_dual_history_preserves_approved_empty_ai_auxiliary(self):
        value = self.history.value("advanced", empty=True)
        committed = self.history.save(value)
        with self.http.no_effects(lookup=False, reads=False):
            response = self.http.request("GET", f"/api/journal/review-history/{committed.id}", DUAL)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["ai_review"]["chart_display_snapshot"], {"charts": [], "chart_cards": []})
        self.assertTrue(response.json()["chart_snapshot"]["charts"])
        self.assertEqual(response.json()["ai_review"]["display_snapshot"], value["bundle"].document["representations"]["v2"]["document"])

    def test_legacy_and_canonical_v1_history_dual_projection_is_unchanged(self):
        identities = [self.http.save(record) for record in (legacy_record(), canonical_record())]
        before = self.http.history_state()
        for identity in identities:
            with self.http.no_effects(lookup=False, reads=False):
                responses = [self.http.request("GET", f"/api/journal/review-history/{identity}", headers) for headers in (V1, DUAL)]
            self.assertEqual(responses[0].json(), responses[1].json())
            self.assertEqual(responses[1].json()["ai_review"]["display_snapshot"]["schema_version"], capability.V1_CAPABILITY)
        self.assertEqual(before, self.http.history_state())

    def test_corrupt_paired_history_never_selects_good_side_or_legacy_fallback(self):
        committed = self.history.save(self.history.value())
        original = self.history.sql("SELECT ai_review_json FROM review_history WHERE id=?", (committed.id,))[0][0]
        mutations = ['{"payload":"bad", "summary":"legacy looking"}']
        for side in ("v1", "v2", "chart_display_snapshot", "row_context"):
            outer = json.loads(original)
            payload = json.loads(outer["payload"])
            if side in ("v1", "v2"):
                del payload["bundle"]["representations"][side]
            else:
                payload.pop(side)
            # Reach whole-record admission with valid carrier encoding/checksum;
            # neither representation selection nor legacy fallback may bypass it.
            raw = canonical_json(payload)
            outer.update(payload=raw.decode("utf-8"), payload_digest=payload_digest(raw))
            mutations.append(outer_json(outer).decode("utf-8"))
        for raw in mutations:
            self.history.replace_review(committed.id, raw)
            before = self.http.history_state()
            with self.http.no_effects(lookup=False, reads=False):
                for headers in (V1, DUAL):
                    detail = self.http.request("GET", f"/api/journal/review-history/{committed.id}", headers)
                    self.assertEqual(detail.status_code, 200)
                    self.history.unavailable(detail.json())
                    self.assertEqual(self.http.request("GET", "/api/journal/review-history", headers).json()[0]["history_read_status"], "unavailable")
                    self.history.unavailable(self.http.request("GET", "/api/me/export-data", headers).json()["review_history"][0])
            self.assertEqual(before, self.http.history_state())

    def test_dual_history_retains_ownership_and_storage_gates_before_admission(self):
        committed = self.history.save(self.history.value())
        with patch.object(paired, "admit_stored_paired_history", side_effect=AssertionError("unauthorized admission")):
            response = self.http.request("GET", f"/api/journal/review-history/{committed.id}", DUAL, token="Bearer invalid")
            self.assertEqual(response.status_code, 401)
            other = self.case.accounts.login_dev_provider(provider="naver", provider_user_id="slice4-other-synthetic", display_name="합성 다른 계정")
            token = "Bearer " + other["session_token"]
            self.case.accounts.update_journal_storage_setting(authorization=token, enabled=True)
            response = self.http.request("GET", f"/api/journal/review-history/{committed.id}", DUAL, token=token)
            self.assertEqual(response.status_code, 404)
            self.case.accounts.update_journal_storage_setting(authorization=self.case.token, enabled=False)
            self.assertEqual(self.http.request("GET", "/api/journal/review-history", DUAL).json(), [])
            self.assertEqual(self.http.request("GET", f"/api/journal/review-history/{committed.id}", DUAL).status_code, 403)
            self.history.unavailable(self.http.request("GET", "/api/me/export-data", DUAL).json()["review_history"][0])
