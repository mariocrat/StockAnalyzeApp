"""Phase 2D-4 production HTTP routes in H4, with synthetic storage/providers."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

from tests.history_legacy_fixture import add_legacy_history_fixture

import asyncio
import copy
from contextlib import ExitStack, contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.review_display_contract import SCHEMA_VERSION
from core.review_history_adapter import history_list_projection
from tests.test_review_history_adapter import canonical_record, legacy_record, UNSAFE
from tests import test_review_route_compatibility as route_fixture
from tests.test_review_route_compatibility import model_output


HEADER = "X-Review-Display-Contract"
SUPPORTED = [(HEADER, SCHEMA_VERSION)]
UNSUPPORTED = {
    "missing": [],
    "wrong": [(HEADER, "review-display.v3")],
    "empty": [(HEADER, "")],
    "leading_space": [(HEADER, " " + SCHEMA_VERSION)],
    "trailing_space": [(HEADER, SCHEMA_VERSION + " ")],
    "case": [(HEADER, "REVIEW-DISPLAY.V1")],
    "comma": [(HEADER, SCHEMA_VERSION + "," + SCHEMA_VERSION)],
    "parameter": [(HEADER, SCHEMA_VERSION + ";version=1")],
    "duplicate": [(HEADER, SCHEMA_VERSION), (HEADER.lower(), SCHEMA_VERSION)],
    "mixed_duplicate": [(HEADER, SCHEMA_VERSION), (HEADER.lower(), "unsupported raw value")],
}
FIXED_ERROR = {"detail": {"code": "unsupported_review_display_client",
                          "message": "AI 복기를 표시하려면 앱을 업데이트해 주세요."}}


class ObservedIdempotencyCache(dict):
    """Count actual production dictionary writes, replacements and removals."""

    def __init__(self, entries):
        super().__init__(entries)
        self.writes = self.overwrites = self.removals = 0

    def __setitem__(self, key, value):
        self.writes += 1
        self.overwrites += int(key in self)
        super().__setitem__(key, value)

    def pop(self, key, *args):
        self.removals += int(key in self)
        return super().pop(key, *args)


class ReviewDisplayClientGateTest(unittest.TestCase):
    def setUp(self):
        # Reuse setup, never inherit its testcase IDs or clone the production route.
        self.case = route_fixture.ProductionRouteCompatibilityTest()
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.main, self.ai = self.case.main, self.case.ai
        self.case.accounts.update_journal_storage_setting(authorization=self.case.token, enabled=True)
        self.enterContext(patch.object(asyncio.events, "_event_loop_policy", None))

    def request(self, method, path, headers, *, review_type="basic", key="d4-synthetic-key", token=None, batch=None):
        async def send():
            fields = [("Authorization", self.case.token if token is None else token),
                      ("X-Idempotency-Key", key), *headers]
            payload = json.dumps((self.case.batch(review_type) if batch is None else batch).model_dump()).encode() if method == "POST" else b""
            fields += [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                     "http_version": "1.1", "method": method, "scheme": "http", "path": path,
                     "query_string": b"", "headers": [(name.lower().encode(), value.encode()) for name, value in fields],
                     "server": ("synthetic.invalid", 80), "client": ("127.0.0.1", 1), "root_path": ""}
            messages, received = [], False
            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": payload, "more_body": False}
                await asyncio.Event().wait()
            async def capture(message):
                messages.append(message)
            try:
                await self.main.app(scope, receive, capture)
            except Exception:
                # ServerErrorMiddleware sends a fixed 500 then reraises, exactly
                # as a real HTTP server does; no test replacement of route logic.
                if not messages or messages[0].get("status", 0) < 500:
                    raise
            text = b"".join(message.get("body", b"") for message in messages).decode()
            return SimpleNamespace(status_code=messages[0]["status"], text=text, json=lambda: json.loads(text),
                                   headers={name.decode(): value.decode() for name, value in messages[0].get("headers", [])})
        return asyncio.run(send())

    def history_state(self):
        path = self.case.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"]
        return path.read_bytes() if path.exists() else None

    @contextmanager
    def no_effects(self, *, lookup=True, reads=True):
        names = ["verify_ai_review_access", "refund_ai_review_access", "add_review_history",
                 "build_basic_ai_review", "build_advanced_ai_review", "build_journal_charts",
                 "get_journal_charts_once", "_prepare_ai_review_history_state", "record_privacy_consent",
                 "_finish_ai_review_idempotency", "_abort_ai_review_idempotency"]
        if lookup:
            names += ["_begin_ai_review_idempotency", "_ai_review_payload_fingerprint",
                      "_enforce_ai_review_rate_limit", "_acquire_ai_review_capacity"]
        if reads:
            # Existing HTTP audit middleware reads the session before dispatch;
            # it is not an entitlement/quota access check or a history read.
            names += ["get_user_entitlements", "list_review_history",
                      "get_review_history", "list_trades", "safe_legacy_history_snapshot"]
        targets = [(self.main, name) for name in names]
        targets += [(self.ai, name) for name in ("_call_openai_review", "get_review_stock_ohlcv",
                    "_contexts_for_trades", "_compact_chart_snapshot")]
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name)))
                     for module, name in targets]
            yield {name: spy for (_, name), spy in zip(targets, spies)}
            self.assertEqual([0] * len(spies), [spy.call_count for spy in spies])

    def pending_entry(self, kind):
        key = "p1-pending-" + kind
        cache_key, replay = self.main._begin_ai_review_idempotency(
            self.case.token, key, self.main._ai_review_payload_fingerprint(self.case.batch(kind)))
        self.assertIsNone(replay)
        return key, self.main._ai_review_idempotency_cache[cache_key]

    def assert_cached_request_has_no_effects(self, kind, key, entry, *, status=500, pressure=False, batch=None):
        cache_key = self.main._ai_review_idempotency_cache_key(self.case.token, key)
        entries = {**self.main._ai_review_idempotency_cache, cache_key: entry}
        if pressure:
            entries["p1-eviction-pressure"] = {name: entry[name] for name in
                ("status", "payload_fingerprint", "expires_at") if name in entry}
            entries["p1-eviction-pressure"]["status"] = "pending"
        cache = ObservedIdempotencyCache(entries)
        expected = ({name: value if name in {"snapshot", "execution"} else copy.deepcopy(value) for name, value in entry.items()}
                    if type(entry) is dict else copy.deepcopy(entry))
        balance, history = self.case.balance(kind), self.history_state()
        with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                self.main, "AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE", 1 if pressure else 1000), self.no_effects(lookup=False) as spies:
            response = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type=kind, key=key, batch=batch)
        effects = {
            "model": spies["_call_openai_review"].call_count,
            "provider": sum(spies[name].call_count for name in (
                "_contexts_for_trades", "_compact_chart_snapshot", "get_review_stock_ohlcv",
                "build_journal_charts", "get_journal_charts_once")),
            "charge": spies["verify_ai_review_access"].call_count,
            "refund": spies["refund_ai_review_access"].call_count,
            "history": spies["add_review_history"].call_count,
            "cache_overwrite": cache.overwrites, "cache_write": cache.writes, "cache_remove": cache.removals,
        }
        self.assertEqual(dict.fromkeys(effects, 0), effects)
        self.assertEqual(status, response.status_code, response.text)
        if status == 500:
            self.assertEqual("Internal Server Error", response.text)
        if status != 200:
            self.assertNotIn("display_snapshot", response.text)
            self.assertNotIn("idempotent_replay", response.text)
        self.assertEqual(set(entries), set(cache))
        self.assertIs(entry, cache[cache_key])
        self.assertEqual(expected, cache[cache_key])
        self.assertEqual(balance, self.case.balance(kind))
        self.assertEqual(history, self.history_state())
        return response

    def test_corrupt_cache_unknown_status_is_fail_closed_before_expiry_or_eviction(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, key, valid, _ = self.case.last
            for value in ("corrupt-status", "", None, False, 17, [], {}):
                with self.subTest(kind=kind, status=value):
                    self.assert_cached_request_has_no_effects(kind, key, {**valid, "status": value})
            expired = {**valid, "status": "corrupt-status", "expires_at":
                       self.main.datetime.datetime.now(self.main.datetime.timezone.utc) - self.main.datetime.timedelta(seconds=1)}
            with self.subTest(kind=kind, expired_and_over_capacity=True):
                self.assert_cached_request_has_no_effects(kind, key, expired, pressure=True)

    def test_corrupt_cache_missing_required_fields_is_fail_closed(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, done_key, done, _ = self.case.last
            pending_key, pending = self.pending_entry(kind)
            for key, entry in ((done_key, done), (pending_key, pending)):
                for field in entry:
                    with self.subTest(kind=kind, status=entry["status"], missing=field):
                        malformed = {name: value for name, value in entry.items() if name != field}
                        self.assert_cached_request_has_no_effects(kind, key, malformed)

    def test_corrupt_cache_malformed_entry_is_fail_closed(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, key, _, _ = self.case.last
            for entry in (None, {}, [], "", "raw cache", 0, False):
                with self.subTest(kind=kind, entry=entry):
                    self.assert_cached_request_has_no_effects(kind, key, entry)

    def test_corrupt_cache_malformed_done_is_fail_closed(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, key, valid, _ = self.case.last
            cases = [("result", value) for value in (None, {}, [], "raw result", False)]
            cases += [("snapshot", value) for value in (None, {}, "raw approval", False)]
            cases += [("payload_fingerprint", value) for value in (None, "", "short", "g" * 64, "A" * 64, [], False)]
            now = self.main.datetime.datetime.now(self.main.datetime.timezone.utc)
            cases += [("expires_at", value) for value in (None, "", "tomorrow", 0, False, [], now.replace(tzinfo=None))]
            cases += [("unexpected", True)]
            for field, value in cases:
                with self.subTest(kind=kind, field=field, value=value):
                    self.assert_cached_request_has_no_effects(kind, key, {**valid, field: value})
            for field in ("status", "source", "review_type", "summary", "access"):
                with self.subTest(kind=kind, result_missing=field):
                    result = {name: value for name, value in valid["result"].items() if name != field}
                    self.assert_cached_request_has_no_effects(kind, key, {**valid, "result": result})
            for access in (None, {}, [], "raw access", {"idempotent_replay": True}, {"idempotent_replay": 0}):
                with self.subTest(kind=kind, access=access):
                    self.assert_cached_request_has_no_effects(kind, key, {
                        **valid, "result": {**valid["result"], "access": access}})

    def test_corrupt_cache_malformed_pending_is_fail_closed(self):
        for kind in ("basic", "advanced"):
            key, pending = self.pending_entry(kind)
            cases = [("payload_fingerprint", value) for value in (None, "", "short", "g" * 64, "A" * 64, [], False)]
            now = self.main.datetime.datetime.now(self.main.datetime.timezone.utc)
            cases += [("expires_at", value) for value in (None, "", "tomorrow", 0, False, [], now.replace(tzinfo=None))]
            cases += [("result", {}), ("snapshot", None), ("unexpected", True)]
            for field, value in cases:
                with self.subTest(kind=kind, field=field, value=value):
                    self.assert_cached_request_has_no_effects(kind, key, {**pending, field: value})

    def test_idempotency_valid_done_replays_without_effects(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, key, entry, _ = self.case.last
            response = self.assert_cached_request_has_no_effects(kind, key, entry, status=200, pressure=True)
            expected = copy.deepcopy(entry["result"])
            expected["access"]["idempotent_replay"] = True
            self.assertEqual(expected, response.json())

    def test_idempotency_valid_pending_preserves_retry_conflict(self):
        for kind in ("basic", "advanced"):
            key, entry = self.pending_entry(kind)
            response = self.assert_cached_request_has_no_effects(kind, key, entry, status=409)
            self.assertEqual({"detail": "AI review request is already running. Please retry shortly."}, response.json())
            self.assertEqual("5", response.headers["retry-after"])

    def assert_fresh_idempotent_execution(self, kind, key):
        cache = ObservedIdempotencyCache(self.main._ai_review_idempotency_cache)
        balance, rows = self.case.balance(kind), self.case.history.list_review_history(user_id=self.case.user_id)
        with patch.object(self.main, "_ai_review_idempotency_cache", cache), patch.object(
                self.ai, "_call_openai_review", return_value=json.dumps(model_output(kind))) as model, patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as save:
            response = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type=kind, key=key)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("ready", response.json()["status"])
        self.assertFalse(response.json()["access"]["idempotent_replay"])
        self.assertEqual((1, 1, 0, 1), (model.call_count, charge.call_count, refund.call_count, save.call_count))
        self.assertEqual((2, 1), (cache.writes, cache.overwrites))
        self.assertEqual(balance - 1, self.case.balance(kind))
        self.assertEqual(len(rows) + 1, len(self.case.history.list_review_history(user_id=self.case.user_id)))
        cache_key = self.main._ai_review_idempotency_cache_key(self.case.token, key)
        self.assertEqual("done", cache[cache_key]["status"])
        return cache

    def test_idempotency_fresh_key_executes_once(self):
        for kind in ("basic", "advanced"):
            with self.subTest(kind=kind):
                self.assert_fresh_idempotent_execution(kind, "p1-fresh-" + kind)

    def test_idempotency_payload_mismatch_preserves_conflict(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, done_key, done, _ = self.case.last
            pending_key, pending = self.pending_entry(kind)
            for key, entry in ((done_key, done), (pending_key, pending)):
                with self.subTest(kind=kind, status=entry["status"]):
                    different = self.case.batch(kind).model_copy(update={"analysis_focus": "entry"})
                    response = self.assert_cached_request_has_no_effects(kind, key, entry, status=409, batch=different)
                    self.assertEqual({"detail": "Idempotency key was reused with a different AI review request."}, response.json())

    def test_idempotency_valid_expired_entry_keeps_ttl_behavior(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            _, done_key, done, _ = self.case.last
            pending_key, pending = self.pending_entry(kind)
            for key, entry in ((done_key, done), (pending_key, pending)):
                with self.subTest(kind=kind, status=entry["status"]):
                    clock = entry["expires_at"] + self.main.datetime.timedelta(seconds=1)
                    with patch.object(self.main, "_ai_review_idempotency_now", return_value=clock):
                        cache = self.assert_fresh_idempotent_execution(kind, key)
                    self.assertGreaterEqual(cache.removals, 1)

    def assert_unsupported_execution(self, headers):
        before = self.history_state()
        wallets = [self.case.balance(kind) for kind in ("basic", "advanced")]
        with self.no_effects():
            for kind in ("basic", "advanced"):
                result = self.request("POST", "/api/journal/ai-review-once", headers, review_type=kind)
                self.assertEqual(426, result.status_code)
                self.assertEqual(FIXED_ERROR, result.json())
        self.assertEqual({}, self.main._ai_review_idempotency_cache)
        self.assertEqual(before, self.history_state())
        self.assertEqual(wallets, [self.case.balance(kind) for kind in ("basic", "advanced")])

    def test_missing_header_blocks_execute_before_lookup_charge_refund_provider_history(self):
        self.assert_unsupported_execution(UNSUPPORTED["missing"])

    def test_wrong_version_blocks_execute_before_lookup_charge_refund_provider_history(self):
        self.assert_unsupported_execution(UNSUPPORTED["wrong"])

    def test_malformed_and_comma_values_are_fixed_fail_closed_on_actual_http_route(self):
        for name in ("empty", "leading_space", "trailing_space", "case", "comma", "parameter"):
            with self.subTest(name=name):
                self.assert_unsupported_execution(UNSUPPORTED[name])

    def test_duplicate_header_lines_including_identical_values_are_unsupported(self):
        for name in ("duplicate", "mixed_duplicate"):
            with self.subTest(name=name):
                self.assert_unsupported_execution(UNSUPPORTED[name])

    def test_supported_http_execution_orders_gate_lookup_charge_model_and_replay_has_zero_effects(self):
        for kind in ("basic", "advanced"):
            with self.subTest(kind=kind), ExitStack() as stack:
                events = []
                for name, event in (("require_review_display_client", "gate"),
                                    ("_begin_ai_review_idempotency", "lookup"),
                                    ("verify_ai_review_access", "charge")):
                    original = getattr(self.main, name)
                    def observe(*args, _original=original, _event=event, **kwargs):
                        events.append(_event)
                        return _original(*args, **kwargs)
                    stack.enter_context(patch.object(self.main, name, side_effect=observe))
                def model(*args, **kwargs):
                    events.append("model")
                    return json.dumps(model_output(kind), ensure_ascii=False)
                stack.enter_context(patch.object(self.ai, "_call_openai_review", side_effect=model))
                charge_before, history_before = self.case.balance(kind), self.case.history.list_review_history(user_id=self.case.user_id)
                response = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type=kind, key="d4-supported-" + kind)
                self.assertEqual(200, response.status_code, response.text)
                first = response.json()
                self.assertEqual("ready", first["status"])
                self.assertEqual(SCHEMA_VERSION, first["display_snapshot"]["schema_version"])
                self.assertEqual(["gate", "lookup", "charge", "model"], events)
                self.assertEqual(charge_before - 1, self.case.balance(kind))
                self.assertEqual(len(history_before) + 1, len(self.case.history.list_review_history(user_id=self.case.user_id)))
                before = self.history_state()
                with self.no_effects(lookup=False):
                    replay = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type=kind, key="d4-supported-" + kind)
                self.assertEqual(200, replay.status_code)
                first["access"]["idempotent_replay"] = True
                self.assertEqual(first, replay.json())
                self.assertEqual(["gate", "lookup", "charge", "model", "gate", "lookup"], events)
                self.assertEqual(before, self.history_state())
                self.assertEqual(charge_before - 1, self.case.balance(kind))

    def test_unsupported_clients_cannot_read_existing_replay_or_change_cache_wallet_history(self):
        for kind in ("basic", "advanced"):
            self.case.strong_route(kind)
            batch, key, cached, _ = self.case.last
            before, expected = self.history_state(), copy.deepcopy(cached["result"])
            balance = self.case.balance(kind)
            keys = set(self.main._ai_review_idempotency_cache)
            with self.no_effects():
                for name, headers in UNSUPPORTED.items():
                    with self.subTest(kind=kind, name=name):
                        response = self.request("POST", "/api/journal/ai-review-once", headers, review_type=kind, key=key)
                        self.assertEqual(426, response.status_code)
                        self.assertEqual(FIXED_ERROR, response.json())
                        self.assertNotIn("display_snapshot", response.text)
                        self.assertNotIn(expected["summary"], response.text)
            self.assertEqual(keys, set(self.main._ai_review_idempotency_cache))
            self.assertEqual(expected, cached["result"])
            self.assertIs(cached, self.main._ai_review_idempotency_cache[self.main._ai_review_idempotency_cache_key(self.case.token, key)])
            self.assertEqual(before, self.history_state())
            self.assertEqual(balance, self.case.balance(kind))

    def test_supported_old_cache_without_sealed_approval_never_returns_raw_or_reexecutes(self):
        self.case.strong_route("advanced")
        _, key, cached, _ = self.case.last
        original, before, balance = dict(cached), self.history_state(), self.case.balance("advanced")
        for mode in ("missing", "none", "raw", "changed_wire"):
            cached.clear()
            cached.update(original)
            if mode == "missing":
                cached.pop("snapshot")
            elif mode == "none":
                cached["snapshot"] = None
            elif mode == "raw":
                cached["snapshot"] = {"summary": "unapproved raw cache"}
            else:
                cached["result"] = {**original["result"], "summary": "unapproved raw cache"}
            with self.subTest(mode=mode), self.no_effects(lookup=False):
                response = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type="advanced", key=key)
                self.assertEqual(500, response.status_code)
                self.assertNotIn("display_snapshot", response.text)
                self.assertNotIn(original["result"]["summary"], response.text)
                self.assertNotIn("unapproved raw cache", response.text)
            self.assertEqual(before, self.history_state())
            self.assertEqual(balance, self.case.balance("advanced"))
        cached.clear()
        cached.update(original)
        with self.no_effects(lookup=False):
            response = self.request("POST", "/api/journal/ai-review-once", SUPPORTED, review_type="advanced", key=key)
        self.assertEqual(200, response.status_code)
        self.assertEqual(original["result"]["display_snapshot"], response.json()["display_snapshot"])

    def save(self, record):
        fields = {name: record[name] for name in ("review_type", "ticker", "name", "trade_date", "target_trade_id",
                  "model", "source", "trade_snapshot", "recent_trades_snapshot", "chart_snapshot", "ai_review", "access_snapshot")}
        return add_legacy_history_fixture(self.case.history, user_id=self.case.user_id, **fields)["id"]

    def test_history_list_detail_export_unsupported_gate_precedes_reads_adapter_and_all_effects(self):
        identity = self.save(legacy_record())
        self.save(canonical_record())
        before = self.history_state()
        with self.no_effects():
            for name, headers in UNSUPPORTED.items():
                for path in ("/api/journal/review-history", f"/api/journal/review-history/{identity}", "/api/me/export-data"):
                    with self.subTest(name=name, path=path):
                        response = self.request("GET", path, headers)
                        self.assertEqual(426, response.status_code)
                        self.assertEqual(FIXED_ERROR, response.json())
                        self.assertNotIn("ai_review", response.text)
        self.assertEqual(before, self.history_state())

    def test_supported_history_uses_whole_record_adapter_for_canonical_legacy_unsafe_without_db_writes(self):
        unsafe = legacy_record()
        unsafe["trade_snapshot"]["memo"] = UNSAFE
        records = [legacy_record(), canonical_record(), unsafe]
        identities = [self.save(row) for row in records]
        before = self.history_state()
        with self.no_effects(reads=False), patch.object(
                self.main, "safe_legacy_history_snapshot", wraps=self.ai.safe_legacy_history_snapshot) as adapter:
            listed = self.request("GET", "/api/journal/review-history", SUPPORTED)
            details = [self.request("GET", f"/api/journal/review-history/{identity}", SUPPORTED) for identity in identities]
            exported = self.request("GET", "/api/me/export-data", SUPPORTED)
        self.assertEqual([200] * 5, [listed.status_code, *[row.status_code for row in details], exported.status_code])
        rows = [row.json() for row in details]
        self.assertEqual(["adapted", "canonical", "unavailable"], [row["history_read_status"] for row in rows])
        self.assertEqual(9, adapter.call_count)
        for call in adapter.call_args_list:
            self.assertTrue({"ai_review", "chart_snapshot", "trade_snapshot", "access_snapshot"} <= set(call.args[0]))
        for row in rows:
            self.assertEqual(history_list_projection(row), next(item for item in listed.json() if item["id"] == row["id"]))
            self.assertEqual(row, next(item for item in exported.json()["review_history"] if item["id"] == row["id"]))
        self.assertNotIn(UNSAFE, json.dumps(rows, ensure_ascii=False))
        self.assertEqual(before, self.history_state())

    def test_supported_header_preserves_history_authentication_storage_opt_in_and_ownership(self):
        identity = self.save(canonical_record())
        response = self.request("GET", f"/api/journal/review-history/{identity}", SUPPORTED, token="Bearer invalid-synthetic")
        self.assertEqual(401, response.status_code)
        other = self.case.accounts.login_dev_provider(provider="naver", provider_user_id="d4-other-synthetic", display_name="합성 다른 계정")
        token = "Bearer " + other["session_token"]
        self.case.accounts.update_journal_storage_setting(authorization=token, enabled=True)
        response = self.request("GET", f"/api/journal/review-history/{identity}", SUPPORTED, token=token)
        self.assertEqual(404, response.status_code)
        self.case.accounts.update_journal_storage_setting(authorization=self.case.token, enabled=False)
        response = self.request("GET", f"/api/journal/review-history/{identity}", SUPPORTED)
        self.assertEqual(403, response.status_code)
        response = self.request("GET", "/api/journal/review-history", SUPPORTED)
        self.assertEqual([], response.json())

    def test_unrelated_journal_routes_do_not_require_display_header(self):
        with patch.object(self.main, "require_review_display_client", side_effect=AssertionError("unrelated gate")) as gate:
            trades = self.request("GET", "/api/journal/trades", [])
            review = self.request("GET", "/api/journal/review", [])
        self.assertEqual((200, 200, 0), (trades.status_code, review.status_code, gate.call_count))
