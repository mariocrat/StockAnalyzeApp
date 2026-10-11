"""F1 production HTTP/cache regressions inside the existing H4 boundary."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
import os
import sys
import unittest
from unittest.mock import patch

from tests import test_review_display_client_gate as http_fixture


class IdempotencyCacheContractTest(unittest.TestCase):
    def setUp(self):
        self.zero_effect_requests = 0
        self.effect_totals = {}
        self.http = http_fixture.ReviewDisplayClientGateTest()
        self.addCleanup(self.http.doCleanups)
        self.http.setUp()
        self.main, self.case, self.ai = self.http.main, self.http.case, self.http.ai
        self.case.strong_route("advanced")
        _, self.key, self.done, _ = self.case.last
        self.cache_key = self.main._ai_review_idempotency_cache_key(self.case.token, self.key)
        self.now = self.main.datetime.datetime.now(self.main.datetime.timezone.utc)

    def tearDown(self):
        if self.zero_effect_requests:
            print("F1_CACHE_EFFECTS " + json.dumps({"case": self._testMethodName,
                "requests": self.zero_effect_requests, "effects": self.effect_totals}), file=sys.stderr)

    def entry_copy(self):
        return {**self.done, "result": copy.deepcopy(self.done["result"])}

    def pending(self, *, expired=False):
        return {"status": "pending", "payload_fingerprint": "a" * 64,
                "expires_at": self.now + self.main.datetime.timedelta(seconds=-1 if expired else 300)}

    def assert_blocked(self, cache, keys, *, capacity=1000):
        expected = {key: ({name: value if name == "snapshot" else copy.deepcopy(value)
                           for name, value in entry.items()} if type(entry) is dict else copy.deepcopy(entry))
                    for key, entry in cache.items()}
        identities = {key: id(entry) for key, entry in cache.items()}
        before, history = self.case.balance("advanced"), self.http.history_state()
        with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                self.main, "AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE", capacity), self.http.no_effects(lookup=False) as spies:
            for key in keys:
                response = self.http.request("POST", "/api/journal/ai-review-once", http_fixture.SUPPORTED,
                                             review_type="advanced", key=key)
                self.assertEqual((500, "Internal Server Error"), (response.status_code, response.text))
                self.assertEqual((0, 0, 0), (cache.writes, cache.overwrites, cache.removals))
                self.assertEqual(expected, dict(cache))
                self.assertEqual(identities, {name: id(entry) for name, entry in cache.items()})
        effects = {"model": spies["_call_openai_review"].call_count,
                   "provider": sum(spies[name].call_count for name in (
                       "_contexts_for_trades", "_compact_chart_snapshot", "get_review_stock_ohlcv",
                       "build_journal_charts", "get_journal_charts_once")),
                   "charge": spies["verify_ai_review_access"].call_count,
                   "refund": spies["refund_ai_review_access"].call_count,
                   "history": spies["add_review_history"].call_count,
                   "cached_content": 0,  # Every response was asserted to be the fixed 500 above.
                   "write": cache.writes, "overwrite": cache.overwrites, "delete": cache.removals}
        self.assertEqual(dict.fromkeys(effects, 0), effects)
        self.assertEqual(before, self.case.balance("advanced"))
        self.assertEqual(history, self.http.history_state())
        self.zero_effect_requests += len(keys)
        for name, count in effects.items():
            self.effect_totals[name] = self.effect_totals.get(name, 0) + count

    def corrupt_cache(self, entry, *, valid_first=False, expired_valid=False):
        entries = {self.cache_key: entry}
        if valid_first:
            entries = {"f1-valid-before-corruption": self.pending(expired=expired_valid), **entries}
        return http_fixture.ObservedIdempotencyCache(entries)

    def test_cross_key_corrupt_entry_blocks_fresh_and_original_key(self):
        for valid_first in (False, True):
            with self.subTest(valid_first=valid_first):
                cache = self.corrupt_cache({**self.done, "status": "corrupt-status"}, valid_first=valid_first)
                self.assert_blocked(cache, ("f1-fresh-other-key", self.key))

    def test_cross_key_expired_corrupt_entry_blocks_all_pruning(self):
        for valid_first in (False, True):
            with self.subTest(valid_first=valid_first):
                bad = {**self.done, "status": "corrupt-status", "expires_at": self.now - self.main.datetime.timedelta(seconds=1)}
                cache = self.corrupt_cache(bad, valid_first=valid_first, expired_valid=True)
                self.assert_blocked(cache, ("f1-fresh-expiry-key", self.key))

    def test_cross_key_capacity_corrupt_entry_blocks_all_trimming(self):
        for valid_first in (False, True):
            with self.subTest(valid_first=valid_first):
                cache = self.corrupt_cache({**self.done, "status": "corrupt-status"}, valid_first=True)
                if not valid_first:
                    cache = http_fixture.ObservedIdempotencyCache(dict(reversed(list(cache.items()))))
                self.assert_blocked(cache, ("f1-fresh-capacity-key", self.key), capacity=1)

    def test_prune_and_trim_validate_all_entries_before_any_mutation(self):
        for operation in ("prune", "trim"):
            for corruption in ("status", "access"):
                with self.subTest(operation=operation, corruption=corruption):
                    bad = self.entry_copy()
                    if corruption == "status":
                        bad["status"] = "corrupt-status"
                    else:
                        bad["result"]["access"] = {"idempotent_replay": False}
                    bad["expires_at"] = self.now - self.main.datetime.timedelta(seconds=1)
                    cache = self.corrupt_cache(bad, valid_first=True, expired_valid=True)
                    with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                            self.main, "AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE", 1), self.main._ai_review_idempotency_lock:
                        with self.assertRaises(ValueError):
                            if operation == "prune":
                                self.main._prune_ai_review_idempotency_cache(self.now)
                            else:
                                self.main._trim_ai_review_idempotency_cache()
                    self.assertEqual((0, 0, 0), (cache.writes, cache.overwrites, cache.removals))
                    self.assertIn("f1-valid-before-corruption", cache)
                    self.assertIs(bad, cache[self.cache_key])

    def access_dicts(self, access, path=()):
        yield path, access
        for name, value in access.items():
            if type(value) is dict:
                yield from self.access_dicts(value, (*path, name))

    def at_path(self, access, path):
        for name in path:
            access = access[name]
        return access

    def assert_bad_access(self, access, *, expired=False, cross_key=False):
        entry = {**self.done, "result": {**self.done["result"], "access": access}}
        if expired:
            entry["expires_at"] = self.now - self.main.datetime.timedelta(seconds=1)
        keys = ("f1-access-other-fresh", self.key) if cross_key else (self.key,)
        self.assert_blocked(self.corrupt_cache(entry, valid_first=expired, expired_valid=expired), keys)

    def test_access_required_fields_and_exact_replay_flag_are_closed(self):
        original = self.done["result"]["access"]
        cases = [{"idempotent_replay": False}, {**original, "wallet": "corrupt wallet"}]
        cases += [{name: value for name, value in original.items() if name != field} for field in original]
        cases += [{**original, "idempotent_replay": flag} for flag in (True, None, 0, 1, "false", [])]
        cases += [{**original, field: value} for field, value in (
            ("auth_mode", "corrupt"), ("plan", "corrupt"), ("review_type", "corrupt"),
            ("source", "corrupt"), ("refunded", not original["refunded"]))]
        nested_changes = (
            (("wallet",), "plan", "corrupt"),
            (("quota", "basic"), "purchased_remaining", original["quota"]["basic"]["purchased_remaining"] + 1),
            (("wallet", "products", "basic_review_15"), "kind", "corrupt"),
            (("wallet", "settings", "ad_policy"), "preferred_rewarded_ad_sequence", "corrupt"),
            (("wallet", "validity"), "timezone", "UTC"),
            (("wallet", "validity"), "daily_reset_at", "not-a-timestamp"),
            (("wallet", "validity"), "daily_reset_at", "2026-10-08T00:00"),
            (("wallet", "validity"), "pro_allowance_resets_at", "2026-10-09T00:00+09:00"),
            (("wallet", "advanced"), "purchased_remaining", -1),
        )
        for path, field, value in nested_changes:
            access = json.loads(json.dumps(original))
            self.at_path(access, path)[field] = value
            cases.append(access)
        for index, access in enumerate(cases):
            with self.subTest(case=index):
                self.assert_bad_access(access)

    def test_access_nested_missing_field_is_rejected(self):
        # Independent JSON nodes ensure a quota mutation cannot also corrupt
        # its wallet alias and conceal a missing validator on either path.
        original = json.loads(json.dumps(self.done["result"]["access"]))
        for path, fields in self.access_dicts(original):
            for field in fields:
                with self.subTest(path=path, missing=field):
                    access = copy.deepcopy(original)
                    self.at_path(access, path).pop(field)
                    self.assert_bad_access(access)

    def test_access_nested_extra_field_is_rejected(self):
        original = json.loads(json.dumps(self.done["result"]["access"]))
        for path, _ in self.access_dicts(original):
            with self.subTest(path=path):
                access = copy.deepcopy(original)
                self.at_path(access, path)["unexpected_f1_field"] = "synthetic"
                self.assert_bad_access(access)

    def test_access_nested_wrong_type_is_rejected(self):
        original = json.loads(json.dumps(self.done["result"]["access"]))
        for path, fields in self.access_dicts(original):
            for field, value in fields.items():
                with self.subTest(path=path, field=field):
                    access = copy.deepcopy(original)
                    self.at_path(access, path)[field] = (False if type(value) is int else 0 if type(value) is bool
                                                        else "wrong object" if type(value) is dict else [])
                    self.assert_bad_access(access)

    def test_access_expired_corruption_blocks_direct_and_cross_key_requests(self):
        original = self.done["result"]["access"]
        cases = [{"idempotent_replay": False}, {name: value for name, value in original.items() if name != "wallet"},
                 {**original, "wallet": "corrupt wallet"}, {**original, "idempotent_replay": True}]
        nested = copy.deepcopy(original)
        nested["wallet"]["settings"]["ad_policy"]["unexpected_f1_field"] = False
        cases.append(nested)
        for index, access in enumerate(cases):
            with self.subTest(case=index):
                self.assert_bad_access(access, expired=True, cross_key=True)

    def observe_execution(self, cache, key, *, capacity=1000):
        events = []
        validator = self.main._validate_ai_review_idempotency_entry
        def validate(entry):
            result = validator(entry)
            events.append(("validated", id(entry)))
            return result
        original_pop = cache.pop
        def pop(name, *args):
            events.append(("delete", name))
            return original_pop(name, *args)
        original_write = type(cache).__setitem__
        def write(target, name, entry):
            if target is cache:
                events.append(("write", id(entry)))
            return original_write(target, name, entry)
        with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                self.main, "AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE", capacity), patch.object(
                self.main, "_validate_ai_review_idempotency_entry", side_effect=validate), patch.object(
                cache, "pop", side_effect=pop), patch.object(type(cache), "__setitem__", write), patch.object(
                self.ai, "_call_openai_review", return_value=json.dumps(http_fixture.model_output("advanced"))) as model, patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as save:
            response = self.http.request("POST", "/api/journal/ai-review-once", http_fixture.SUPPORTED,
                                         review_type="advanced", key=key)
        for index, event in enumerate(events):
            if event[0] == "write":
                self.assertIn(("validated", event[1]), events[:index])
        return response, events, (model.call_count, charge.call_count, refund.call_count, save.call_count)

    def test_valid_done_pending_mismatch_and_fresh_share_validator(self):
        cache = http_fixture.ObservedIdempotencyCache({self.cache_key: self.done})
        response, events, effects = self.observe_execution(cache, self.key)
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["access"]["idempotent_replay"])
        self.assertIn(("validated", id(self.done)), events)
        self.assertEqual((0, 0, 0, 0), effects)
        self.assertEqual((0, 0, 0), (cache.writes, cache.overwrites, cache.removals))
        for mode in ("pending", "mismatch"):
            with self.subTest(mode=mode):
                entry = self.pending() if mode == "pending" else {**self.done, "payload_fingerprint": "a" * 64}
                if mode == "pending":
                    entry["payload_fingerprint"] = self.main._ai_review_payload_fingerprint(self.case.batch("advanced"))
                self.assert_blocked_valid_conflict(entry, mode)
        fresh = http_fixture.ObservedIdempotencyCache({self.cache_key: self.done})
        response, events, effects = self.observe_execution(fresh, "f1-normal-fresh")
        self.assertEqual(200, response.status_code, response.text)
        self.assertFalse(response.json()["access"]["idempotent_replay"])
        self.assertEqual((1, 1, 0, 1), effects)
        self.assertIn(("validated", id(self.done)), events)
        self.assertEqual((2, 1, 0), (fresh.writes, fresh.overwrites, fresh.removals))

    def assert_blocked_valid_conflict(self, entry, mode):
        response = self.http.assert_cached_request_has_no_effects("advanced", self.key, entry, status=409)
        if mode == "pending":
            self.assertEqual("5", response.headers["retry-after"])
        else:
            self.assertEqual({"detail": "Idempotency key was reused with a different AI review request."}, response.json())

    def test_valid_expiry_prunes_only_after_full_validation(self):
        expired = {**self.done, "expires_at": self.now - self.main.datetime.timedelta(seconds=1)}
        pending = self.pending(expired=True)
        cache = http_fixture.ObservedIdempotencyCache({self.cache_key: expired, "f1-expired-pending": pending})
        response, events, effects = self.observe_execution(cache, "f1-normal-expiry")
        self.assertEqual(200, response.status_code, response.text)
        first_delete = next(index for index, event in enumerate(events) if event[0] == "delete")
        self.assertTrue({("validated", id(expired)), ("validated", id(pending))} <= set(events[:first_delete]))
        self.assertEqual((1, 1, 0, 1), effects)
        self.assertEqual((2, 1, 2), (cache.writes, cache.overwrites, cache.removals))
        self.assertNotIn(self.cache_key, cache)
        self.assertNotIn("f1-expired-pending", cache)

    def test_valid_capacity_trims_only_after_full_validation(self):
        pending = self.pending()
        pending["expires_at"] += self.main.datetime.timedelta(seconds=30)
        cache = http_fixture.ObservedIdempotencyCache({self.cache_key: self.done, "f1-later-pending": pending})
        response, events, effects = self.observe_execution(cache, "f1-normal-capacity", capacity=1)
        self.assertEqual(200, response.status_code, response.text)
        first_delete = next(index for index, event in enumerate(events) if event[0] == "delete")
        self.assertTrue({("validated", id(self.done)), ("validated", id(pending))} <= set(events[:first_delete]))
        self.assertEqual((1, 1, 0, 1), effects)
        self.assertEqual((2, 1, 2), (cache.writes, cache.overwrites, cache.removals))
        self.assertEqual(1, len(cache))

    def test_pro_and_review_wallets_round_trip_through_real_cache(self):
        review_env = {
            "ALPHAMATE_REVIEW_ACCESS_ENABLED": "true", "ALPHAMATE_REVIEW_ACCESS_ID": "f1-synthetic-review",
            "ALPHAMATE_REVIEW_ACCESS_PASSWORD_HASH": self.case.accounts.hash_review_password("f1-synthetic-password", iterations=100_000),
            "ALPHAMATE_REVIEW_ACCESS_EXPIRES_AT": (self.now + self.main.datetime.timedelta(days=1)).isoformat(),
        }
        self.enterContext(patch.dict(os.environ, review_env))
        self.case.access.initialize_review_entitlement(self.case.user_id)
        for mode in ("pro", "review"):
            cache = http_fixture.ObservedIdempotencyCache(self.main._ai_review_idempotency_cache)
            key = "f1-wallet-round-trip-" + mode
            target = "_plan_for" if mode == "pro" else "_authenticate"
            value = "pro" if mode == "pro" else (self.case.user_id, "review")
            with self.subTest(mode=mode), patch.object(self.case.access, target, return_value=value):
                response, _, effects = self.observe_execution(cache, key)
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual((1, 1, 0, 1), effects)
                entry = cache[self.main._ai_review_idempotency_cache_key(self.case.token, key)]
                replay = self.http.assert_cached_request_has_no_effects("advanced", key, entry, status=200).json()
                self.assertEqual("pro", replay["access"]["wallet"]["plan"])
                self.assertEqual("review" if mode == "review" else "session", replay["access"]["auth_mode"])
                if mode == "review":
                    self.assertIsNone(replay["access"]["wallet"]["validity"]["daily_reset_at"])

    def test_finish_and_abort_cannot_mutate_corrupt_existing_entry(self):
        for operation in ("finish", "finish_none", "abort"):
            with self.subTest(operation=operation):
                bad = {**self.pending(), "unexpected_f1_field": True}
                cache = self.corrupt_cache(bad)
                with patch.object(self.main, "_ai_review_idempotency_cache", cache):
                    with self.assertRaises(ValueError):
                        if operation == "abort":
                            self.main._abort_ai_review_idempotency(self.cache_key)
                        elif operation == "finish_none":
                            self.main._finish_ai_review_idempotency(self.cache_key, None)
                        else:
                            self.main._finish_ai_review_idempotency(self.cache_key, self.done["result"], snapshot=self.done["snapshot"])
                self.assertEqual((0, 0, 0), (cache.writes, cache.overwrites, cache.removals))
                self.assertIs(bad, cache[self.cache_key])
        cache = http_fixture.ObservedIdempotencyCache({self.cache_key: self.done})
        key = "f1-corruption-during-builder-failure"
        failed_key = self.main._ai_review_idempotency_cache_key(self.case.token, key)
        def fail_builder(*args, **kwargs):
            cache[failed_key]["unexpected_f1_field"] = True
            raise RuntimeError("synthetic builder failure after cache corruption")
        balance, history = self.case.balance("advanced"), self.http.history_state()
        with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                self.main, "build_advanced_ai_review", side_effect=fail_builder), patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as save:
            response = self.http.request("POST", "/api/journal/ai-review-once", http_fixture.SUPPORTED,
                                         review_type="advanced", key=key)
        self.assertEqual(500, response.status_code)
        self.assertEqual((1, 1, 0), (charge.call_count, refund.call_count, save.call_count))
        self.assertEqual((1, 0, 0), (cache.writes, cache.overwrites, cache.removals))
        self.assertIn("unexpected_f1_field", cache[failed_key])
        self.assertEqual(balance, self.case.balance("advanced"))
        self.assertEqual(history, self.http.history_state())


if __name__ == "__main__":
    unittest.main()
