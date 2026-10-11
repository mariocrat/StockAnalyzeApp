"""A3 real route/storage/refund/replay contracts inside the H4 boundary."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from backend.core.review_display_contract import SCHEMA_VERSION

import copy
from contextlib import contextmanager
import importlib
import json
import os
import sys
import unittest
from unittest.mock import patch

from backend.core.review_legacy_compatibility import admit_legacy_body
from tests.api_test_modules import api_module_state
from tests.review_source_fixtures import compact_chart_fixture, approved_chart_fixture, history_chart_fixture
from tests.test_review_finalizer_compatibility import model_output


def sentence_body(*, strong=False):
    runs = ([{"type": "strong", "text": "체결 기록"}, {"type": "text", "text": "을 확인합니다."}]
            if strong else [{"type": "text", "text": "체결 기록을 확인합니다."}])
    return {"schema_version": "review-display.v1", "surface": "body",
            "blocks": [{"type": "paragraph", "runs": runs, "separator_after": ""}],
            "canonical_text": "체결 기록을 확인합니다."}


def duplicate_json_model_output(review_type, location, *, escaped_key=None,
                                unsafe_position=None, escape_value=True):
    """Inject raw duplicate pairs into an otherwise valid independent fixture."""
    value = model_output(review_type)
    if location == "top-level":
        target, key = value, "main_issue"
    elif location == "nested":
        target, key = value["lesson"], "concept"
    else:
        target = value["good_points" if review_type == "basic" else "detailed_analysis"][0]
        key = "detail"
    values = [target[key], target[key]]
    if unsafe_position is not None:
        values[unsafe_position] = "현재는 매수 추천합니다."
    keys = [json.dumps(key), json.dumps(key)]
    if escaped_key is not None:
        keys[escaped_key] = '"' + "".join(f"\\u{ord(char):04x}" for char in key) + '"'
    marker = "F2_DUPLICATE_JSON_SLOT"
    target[key] = marker
    raw = json.dumps(value, ensure_ascii=False)
    slot = json.dumps(key) + ": " + json.dumps(marker)
    pairs = ", ".join(encoded_key + ": " + json.dumps(item, ensure_ascii=escape_value)
                      for encoded_key, item in zip(keys, values))
    assert raw.count(slot) == 1
    return raw.replace(slot, pairs, 1)


class ProductionRouteCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.fixture = self.enterContext(storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true",
                                          ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE="60"))
        modules = self.enterContext(api_module_state())
        self.main, self.accounts, self.access, self.history = (
            modules.main, modules.account_store, modules.access_control, modules.review_history)
        self.ai = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai.__dict__))
        importlib.reload(self.ai)
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic", "ALPHAMATE_OPENAI_API_KEY": ""}))
        self.context_provider = self.enterContext(patch.object(self.ai, "_contexts_for_trades", return_value=[]))
        self.compact_provider = self.enterContext(patch.object(self.ai, "_compact_chart_snapshot", return_value=compact_chart_fixture({
            "candles": [{"time": "2026-07-10", "close": 70400}], "rule_based_observations": [],
        })))
        self.market_provider = self.enterContext(patch.object(self.ai, "get_review_stock_ohlcv", side_effect=AssertionError("unexpected market query")))
        self.chart_endpoint = self.enterContext(patch.object(self.main, "get_journal_charts_once", side_effect=AssertionError("AI route charts-once")))
        session = self.accounts.login_dev_provider(
            provider="kakao", provider_user_id="a3-synthetic-route", display_name="합성 복기 테스트")
        self.user_id = session["user"]["id"]
        self.token = f"Bearer {session['session_token']}"
        wallet = self.access._wallet_for(self.user_id, "free")
        wallet.signup_advanced_remaining = 0
        self.access._save_wallet(self.user_id, wallet)
        self.access.apply_dev_purchase(authorization=self.token, entitlement_token="", product_id="advanced_review_10")
        self.trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "005930", "name": "삼성전자",
             "side": "buy", "price": 70000, "quantity": 10, "fee": 105, "tax": 0,
             "memo": "거래량 증가를 보고 진입", "source": "manual"},
            {"id": 2, "trade_date": "2026-07-10T10:00", "ticker": "005930", "name": "삼성전자",
             "side": "sell", "price": 70900, "quantity": 10, "fee": 106, "tax": 0,
             "memo": "수익 확정으로 매도", "source": "manual"},
        ]
        self.charts = history_chart_fixture(self.trades)
        self.general_chart_provider = self.enterContext(patch.object(self.main, "build_journal_charts", return_value=self.charts))
        self.sequence = 0

    def batch(self, review_type):
        return self.main.JournalAiReviewIn(
            privacy_consent=True, review_type=review_type, target_trade_id=2,
            trades=[self.main.JournalTradeIn(**trade) for trade in self.trades])

    def balance(self, review_type):
        wallet = self.access.get_user_entitlements(authorization=self.token, entitlement_token="")
        return wallet[review_type]["signup_remaining" if review_type == "basic" else "purchased_remaining"]

    @contextmanager
    def candidate_body(self, document):
        # Independent body fixture at the real compiler boundary; route, safety,
        # A1 admission, sealing, serialization, charging and persistence stay real.
        original = self.ai.compile_review_envelope

        def envelope(source):
            result = original(source)
            result["body"] = copy.deepcopy(document)
            return result

        with patch.object(self.ai, "compile_review_body", side_effect=lambda source: copy.deepcopy(document)), patch.object(
                self.ai, "compile_review_envelope", side_effect=envelope):
            yield

    def run_route(self, review_type, *, raw=None, output=None, status="ready", internal=None,
                  storage=False, bodyless=False):
        self.accounts.update_journal_storage_setting(authorization=self.token, enabled=storage)
        self.sequence += 1
        key = f"a3-route-{self.sequence}-{review_type}"
        batch = self.batch(review_type)
        if raw is None:
            raw = json.dumps(model_output(review_type) if output is None else output, ensure_ascii=False)
        records = []
        original = self.ai._finalize_ai_review

        def finalize(*args, **kwargs):
            result = original(*args, **kwargs)
            history_state = kwargs.get("history_state")
            records.append({"result": copy.deepcopy(result), "snapshot": kwargs["approval_state"]["snapshot"],
                            "history": history_state["approved"] if history_state else None})
            return result

        before = self.balance(review_type)
        rows_before = self.history.list_review_history(user_id=self.user_id)
        with patch.object(self.ai, "_call_openai_review", return_value=raw) as model, patch.object(
                self.ai, "_finalize_ai_review", side_effect=finalize), patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as save:
            result = self.main.get_journal_ai_review_once(batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
            counts = (model.call_count, charge.call_count, refund.call_count, save.call_count)
            provider_counts = tuple(spy.call_count for spy in (
                self.context_provider, self.compact_provider, self.general_chart_provider, self.market_provider))
            charts_once_before = self.chart_endpoint.call_count
            # Replay cannot revisit any raw/semantic producer or operation.
            with patch.object(self.main, "build_basic_ai_review", side_effect=AssertionError("replay basic builder")), patch.object(
                    self.main, "build_advanced_ai_review", side_effect=AssertionError("replay advanced builder")), patch.object(
                    self.main, "_prepare_ai_review_history_state", side_effect=AssertionError("replay history preparation")), patch.object(
                    self.main, "record_privacy_consent", side_effect=AssertionError("replay consent write")):
                replay = self.main.get_journal_ai_review_once(batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
            self.assertEqual(counts, (model.call_count, charge.call_count, refund.call_count, save.call_count))
            self.assertEqual(provider_counts, tuple(spy.call_count for spy in (
                self.context_provider, self.compact_provider, self.general_chart_provider, self.market_provider)))
            self.last_replay_effects = {
                "model": model.call_count - counts[0], "charge": charge.call_count - counts[1],
                "refund": refund.call_count - counts[2], "history": save.call_count - counts[3],
                "provider": sum(spy.call_count for spy in (self.context_provider, self.compact_provider, self.general_chart_provider)) - sum(provider_counts[:3]),
                "market": self.market_provider.call_count - provider_counts[3],
                "charts_once": self.chart_endpoint.call_count - charts_once_before,
            }
            self.assertEqual(dict.fromkeys(self.last_replay_effects, 0), self.last_replay_effects)
            self.last_prompt = model.call_args.kwargs["instructions"]
        self.assertEqual((1, 1, int(status == "error"), int(storage and status in {"ready", "missing_key"})), counts)
        self.assertEqual((status, internal), (result["status"], result.get("internal_status")))
        self.assertEqual(status == "error", result["access"]["refunded"])
        self.assertEqual(before - int(status != "error"), self.balance(review_type))
        self.assertEqual(result["summary"], records[0]["result"]["summary"])
        expected_replay = copy.deepcopy(result)
        expected_replay["access"]["idempotent_replay"] = True
        self.assertEqual(expected_replay, replay)
        self.last_replay = replay
        cache_key = self.main._ai_review_idempotency_cache_key(self.token, key)
        cached = self.main._ai_review_idempotency_cache[cache_key]
        self.assertIs(cached["snapshot"], records[0]["snapshot"])
        self.assertIsNot(result, cached["result"])
        if bodyless:
            self.assertEqual("", result["summary"])
            self.assertNotIn("display_snapshot", result)
            self.assertNotIn("structured_review", result)
            self.assertIsNone(records[0]["snapshot"])
        else:
            snapshot = records[0]["snapshot"]
            sealed = json.loads(snapshot.json_text)
            self.assertEqual(sealed["body"], result["display_snapshot"])
            self.assertEqual(admit_legacy_body(sealed["body"]).summary, result["summary"])
            self.assertIsNot(result["display_snapshot"], cached["result"]["display_snapshot"])
        rows = self.history.list_review_history(user_id=self.user_id)
        if storage and status in {"ready", "missing_key"}:
            self.assertIs(records[0]["snapshot"], records[0]["history"]["snapshot"])
            self.assertEqual(len(rows_before) + 1, len(rows))
            detail = self.main.get_journal_review_history_detail(result["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
            self.assertEqual(result["display_snapshot"], detail["ai_review"]["display_snapshot"])
            self.assertEqual(result["summary"], detail["ai_review"]["summary"])
        else:
            self.assertIsNone(records[0]["history"])
            self.assertNotIn("review_history_id", result)
            self.assertEqual(rows_before, rows)
        self.last = (batch, key, cached, records[0])
        return result

    def chart_route(self, review_type, *, storage=True):
        self.compact_provider.return_value = approved_chart_fixture()
        result = self.run_route(review_type, storage=storage)
        self.assertEqual(0, self.chart_endpoint.call_count)
        sealed = json.loads(self.last[3]["snapshot"].json_text)
        expected = {key: sealed[key] for key in ("charts", "chart_cards")}
        self.assertEqual(expected, result["chart_display_snapshot"])
        self.assertEqual(expected, self.last_replay["chart_display_snapshot"])
        self.assertEqual(expected, self.last[2]["result"]["chart_display_snapshot"])
        self.assertNotEqual(self.charts["charts"][0]["candles"][0]["close"], expected["charts"][0]["candles"][0]["close"])
        return result, expected

    def test_approved_chart_content_identity_response_storage_detail_export_and_replay(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                result, expected = self.chart_route(review_type)
                raw = self.history.get_review_history(result["review_history_id"], user_id=self.user_id)
                detail = self.main.get_journal_review_history_detail(result["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                export = self.main.export_me_data(authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
                exported = next(row for row in export if row["id"] == result["review_history_id"])
                self.assertEqual("canonical", detail["history_read_status"])
                for record in (raw, detail, exported):
                    self.assertEqual(expected, record["ai_review"]["chart_display_snapshot"])
                self.assertNotEqual(expected["charts"], raw["chart_snapshot"]["charts"])

    def test_operational_metadata_cannot_change_chart_projection(self):
        result, expected = self.chart_route("basic")
        changed = copy.deepcopy(result)
        changed["review_history_id"] = 999
        changed["access"]["idempotent_replay"] = True
        self.assertEqual(expected, self.main._normalize_ai_review_result(changed, snapshot=self.last[3]["snapshot"])["chart_display_snapshot"])
        changed["chart_display_snapshot"]["charts"][0]["candles"][0]["close"] += 1
        with self.assertRaisesRegex(ValueError, "chart differs"):
            self.main._normalize_ai_review_result(changed, snapshot=self.last[3]["snapshot"])

    def test_unknown_nested_history_candle_is_rejected_before_ready_or_write(self):
        self.charts["charts"][0]["candles"][0]["unknown_nested"] = {"text": "합성 미정의 필드"}
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                result = self.run_route(review_type, storage=True, status="error", internal="invalid_structured_output")
                self.assertNotIn("합성 미정의 필드", json.dumps(result, ensure_ascii=False))
                self.assertFalse(self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].exists())

    def test_nested_history_missing_extra_and_wrong_types_fail_closed(self):
        chart = copy.deepcopy(self.charts["charts"][0])
        chart["markers"] = [{
            "time": "2026-07-10", "side": "buy", "text": "B",
            "trades": [{"date": "2026-07-10T09:30", "price": 70000, "quantity": 1}],
            "tooltip": {"label": "매수", "count": 1, "prices": [70000]},
        }]
        chart["reviews"] = [{
            "title": "과거 체결", "detail": "당시 기록을 확인했습니다.",
            "metrics": {"ma5": {"label": "이동평균", "unit": "원", "description": "과거 평균", "value": 70000}},
        }]
        cases = (
            ("candle missing", ("candles", 0), "time", None, True),
            ("candle extra", ("candles", 0), "extra", {"text": "합성 필드"}, False),
            ("candle type", ("candles", 0), "close", {"value": 70400}, False),
            ("marker missing", ("markers", 0), "time", None, True),
            ("marker extra", ("markers", 0), "extra", {"text": "합성 필드"}, False),
            ("marker type", ("markers", 0), "time", {"date": "2026-07-10"}, False),
            ("fill missing", ("markers", 0, "trades", 0), "date", None, True),
            ("fill extra", ("markers", 0, "trades", 0), "extra", {"value": 1}, False),
            ("fill type", ("markers", 0, "trades", 0), "quantity", {"value": 1}, False),
            ("tooltip missing", ("markers", 0, "tooltip"), "label", None, True),
            ("tooltip extra", ("markers", 0, "tooltip"), "extra", {"text": "합성 필드"}, False),
            ("tooltip type", ("markers", 0, "tooltip"), "count", {"value": 1}, False),
            ("card missing", ("reviews", 0), "detail", None, True),
            ("card extra", ("reviews", 0), "extra", {"text": "합성 필드"}, False),
            ("card type", ("reviews", 0), "metrics", [], False),
            ("metric missing", ("reviews", 0, "metrics", "ma5"), "value", None, True),
            ("metric extra", ("reviews", 0, "metrics", "ma5"), "extra", {"value": 1}, False),
            ("metric type", ("reviews", 0, "metrics", "ma5"), "value", {"value": 70000}, False),
        )
        for review_type in ("basic", "advanced"):
            for label, path, key, value, missing in cases:
                with self.subTest(review_type=review_type, case=label):
                    candidate = copy.deepcopy(chart)
                    nested = candidate
                    for component in path:
                        nested = nested[component]
                    if missing:
                        nested.pop(key)
                    else:
                        nested[key] = value
                    self.general_chart_provider.return_value = {"charts": [candidate]}
                    self.run_route(review_type, storage=True, status="error", internal="invalid_structured_output")
        self.assertFalse(self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].exists())

    def test_new_history_identity_survives_all_reads_for_ready_and_missing_key(self):
        from backend.core.review_history_adapter import history_list_projection

        self.compact_provider.return_value = approved_chart_fixture()
        for review_type in ("basic", "advanced"):
            for status in ("ready", "missing_key"):
                with self.subTest(review_type=review_type, status=status):
                    result = self.run_route(review_type, raw="" if status == "missing_key" else None,
                                            storage=True, status=status)
                    identity = result["review_history_id"]
                    raw = self.history.get_review_history(identity, user_id=self.user_id)
                    detail = self.main.get_journal_review_history_detail(
                        identity, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                    listed = next(row for row in self.main.get_journal_review_history(
                        authorization=self.token, x_review_display_contract=[SCHEMA_VERSION]) if row["id"] == identity)
                    exported = next(row for row in self.main.export_me_data(
                        authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
                                    if row["id"] == identity)
                    self.assertEqual("canonical", detail["history_read_status"])
                    self.assertEqual(history_list_projection(detail), listed)
                    self.assertEqual(detail, exported)
                    for record in (raw, detail, exported):
                        for key in ("summary", "display_snapshot", "structured_review", "chart_display_snapshot", "access"):
                            self.assertEqual(result[key], record["ai_review"][key])
                        self.assertEqual(result["access"], record["access_snapshot"])
                    for key in ("trade_snapshot", "recent_trades_snapshot", "chart_snapshot"):
                        self.assertEqual(raw[key], detail[key])
                    self.assertEqual(self.trades, [
                        {key: value for key, value in trade.items() if key != "display_snapshot"}
                        for trade in detail["recent_trades_snapshot"]])
                    for key in ("summary", "display_snapshot", "chart_display_snapshot", "structured_review"):
                        self.assertEqual(result[key], self.last_replay[key])

    def assert_new_history_rejections(self, review_type, cases):
        self.compact_provider.return_value = approved_chart_fixture()
        self.run_route(review_type, storage=True)
        before = self.balance(review_type)
        rows_before = self.history.list_review_history(user_id=self.user_id)
        db_before = self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes()
        original_save = self.main._save_ai_review_history_if_enabled
        attempts = 0
        with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(model_output(review_type))) as model, patch.object(
                self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as write, patch.object(
                self.history, "_connect", wraps=self.history._connect) as connection, patch.object(
                self.main, "delete_review_history", wraps=self.main.delete_review_history) as delete:
            for operation, path in cases:
                self.sequence += 1
                key = f"f3-strict-{review_type}-{self.sequence}"
                batch = self.batch(review_type)
                cache_key = self.main._ai_review_idempotency_cache_key(self.token, key)

                def corrupt(*, history_state, result):
                    # Break quota/wallet aliases to test each required copy on
                    # its own, as it will exist after JSON persistence.
                    result["access"] = json.loads(json.dumps(result["access"]))
                    parent = result
                    for component in path[:-1]:
                        parent = parent[component]
                    if operation == "missing":
                        parent.pop(path[-1])
                    elif operation == "empty":
                        parent[path[-1]] = {"charts": [], "chart_cards": []}
                    elif operation == "number type":
                        value = parent[path[-1]]
                        parent[path[-1]] = float(value) if type(value) is int else int(value)
                    else:
                        parent[path[-1]] += 1
                    original = copy.deepcopy(result)
                    try:
                        return original_save(history_state=history_state, result=result)
                    finally:
                        self.assertEqual(original, result, "admission must not fill or normalize input")

                with patch.object(self.main, "_save_ai_review_history_if_enabled", side_effect=corrupt):
                    for _ in range(2):
                        with self.assertRaises(ValueError, msg=str((operation, path))):
                            self.main.get_journal_ai_review_once(
                                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                        attempts += 1
                        self.assertEqual((attempts, attempts, attempts, 0, 0, 0), (
                            model.call_count, charge.call_count, refund.call_count, write.call_count,
                            connection.call_count, delete.call_count), str((operation, path)))
                        self.assertNotIn(cache_key, self.main._ai_review_idempotency_cache)
                        self.assertEqual(before, self.balance(review_type))
                        self.assertEqual(rows_before, self.history.list_review_history(user_id=self.user_id))
                        self.assertEqual(db_before, self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes())
            retry = self.main.get_journal_ai_review_once(
                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
            counts = (model.call_count, charge.call_count, refund.call_count, write.call_count, connection.call_count)
            providers = tuple(spy.call_count for spy in (
                self.context_provider, self.compact_provider, self.general_chart_provider, self.market_provider))
            replay = self.main.get_journal_ai_review_once(
                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
            self.assertEqual((attempts + 1, attempts + 1, attempts, 1, 1), counts)
            self.assertEqual(counts, (model.call_count, charge.call_count, refund.call_count, write.call_count, connection.call_count))
            self.assertEqual(providers, tuple(spy.call_count for spy in (
                self.context_provider, self.compact_provider, self.general_chart_provider, self.market_provider)))
            self.assertEqual(0, delete.call_count)
            self.assertEqual(before - 1, self.balance(review_type))
            self.assertTrue(replay["access"]["idempotent_replay"])
            detail = self.main.get_journal_review_history_detail(
                retry["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
            self.assertEqual("canonical", detail["history_read_status"])
            for field in ("summary", "display_snapshot", "chart_display_snapshot", "structured_review"):
                self.assertEqual(retry[field], replay[field])
                self.assertEqual(retry[field], detail["ai_review"][field])

    def test_new_history_missing_access_fields_fail_before_connection_and_cannot_replay(self):
        paths = (
            ("access",), ("access", "quota"), ("access", "wallet"),
            ("access", "quota", "basic", "signup_remaining"),
            ("access", "quota", "advanced", "signup_remaining"),
            ("access", "wallet", "basic", "signup_remaining"),
            ("access", "wallet", "advanced", "signup_remaining"),
            ("access", "wallet", "settings", "free_policy"),
            ("access", "wallet", "settings", "free_policy", "daily_basic"),
            ("access", "wallet", "settings", "ad_policy", "ads_per_advanced_ticket"),
            ("access", "wallet", "products", "advanced_review_10", "price_krw"),
            ("access", "wallet", "validity", "signup_pass_expires_at"),
        )
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                self.assert_new_history_rejections(review_type, [("missing", path) for path in paths])

    def test_new_history_requires_original_canonical_projections_to_match_seal(self):
        cases = (
            ("missing", ("chart_display_snapshot",)),
            ("missing", ("display_snapshot",)),
            ("missing", ("structured_review",)),
            ("empty", ("chart_display_snapshot",)),
            ("different", ("chart_display_snapshot", "charts", 0, "candles", 0, "close")),
            ("number type", ("chart_display_snapshot", "charts", 0, "candles", 0, "open")),
        )
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                self.assert_new_history_rejections(review_type, cases)

    def test_new_history_requires_every_access_field_produced_by_real_wallet(self):
        def field_paths(value, prefix=()):
            for key, child in value.items():
                yield prefix + (key,)
                if type(child) is dict:
                    yield from field_paths(child, prefix + (key,))

        for review_type in ("basic", "advanced"):
            result = self.run_route(review_type, storage=True)
            result.pop("review_history_id")
            history_state = {"user_id": self.user_id, "approved": self.last[3]["history"]}
            rows_before = self.history.list_review_history(user_id=self.user_id)
            db_before = self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes()
            paths = list(field_paths(result["access"]))
            self.assertGreater(len(paths), 80)
            with patch.object(self.main, "add_review_history", side_effect=AssertionError("INSERT reached")) as write, patch.object(
                    self.history, "_connect", side_effect=AssertionError("write connection reached")) as connection:
                for path in paths:
                    candidate = json.loads(json.dumps(result))
                    parent = candidate["access"]
                    for component in path[:-1]:
                        parent = parent[component]
                    parent.pop(path[-1])
                    original = copy.deepcopy(candidate)
                    with self.assertRaises(ValueError, msg=str((review_type, path))):
                        self.main._save_ai_review_history_if_enabled(history_state=history_state, result=candidate)
                    self.assertEqual(original, candidate)
                self.assertEqual((0, 0), (write.call_count, connection.call_count))
            self.assertEqual(rows_before, self.history.list_review_history(user_id=self.user_id))
            self.assertEqual(db_before, self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes())

    def test_invalid_final_history_record_writes_zero_refunds_once_and_allows_retry(self):
        self.run_route("advanced", storage=True)
        original_save = self.main._save_ai_review_history_if_enabled
        cases = ("unknown", "missing", "wrong type", "trade", "recent trade", "access", "semantic")
        for case in cases:
            with self.subTest(case=case):
                rows_before = self.history.list_review_history(user_id=self.user_id)
                db_before = self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes()
                before = self.balance("advanced")
                self.sequence += 1
                key = f"f3-final-{self.sequence}"
                batch = self.batch("advanced")
                cache_key = self.main._ai_review_idempotency_cache_key(self.token, key)

                def corrupt(*, history_state, result):
                    metadata = json.loads(history_state["approved"]["metadata_json"])
                    candle = metadata["chart_snapshot"]["charts"][0]["candles"][0]
                    if case == "unknown":
                        candle["unknown_nested"] = {"text": "합성 미정의 필드"}
                    elif case == "missing":
                        candle.pop("time")
                    elif case == "wrong type":
                        candle["close"] = {"value": 70400}
                    elif case == "trade":
                        metadata["trade_snapshot"]["price"] = {"value": 70000}
                    elif case == "recent trade":
                        metadata["recent_trades_snapshot"][0]["extra"] = {"text": "합성 필드"}
                    elif case == "access":
                        result["access"]["wallet"]["basic"]["extra"] = {"value": 1}
                    else:
                        result["structured_review"]["summary"]["decision_quality"].pop("label")
                    history_state["approved"]["metadata_json"] = json.dumps(metadata, ensure_ascii=False)
                    return original_save(history_state=history_state, result=result)

                with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(model_output("advanced"))) as model, patch.object(
                        self.main, "verify_ai_review_access", wraps=self.main.verify_ai_review_access) as charge, patch.object(
                        self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                        self.main, "add_review_history", wraps=self.main.add_review_history) as write, patch.object(
                        self.history, "_connect", wraps=self.history._connect) as connection, patch.object(
                        self.main, "delete_review_history", wraps=self.main.delete_review_history) as delete:
                    with patch.object(self.main, "_save_ai_review_history_if_enabled", side_effect=corrupt):
                        with self.assertRaises(ValueError):
                            self.main.get_journal_ai_review_once(
                                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                    self.assertEqual((1, 1, 1, 0, 0, 0), (
                        model.call_count, charge.call_count, refund.call_count, write.call_count,
                        connection.call_count, delete.call_count))
                    self.assertEqual(before, self.balance("advanced"))
                    self.assertNotIn(cache_key, self.main._ai_review_idempotency_cache)
                    self.assertEqual(rows_before, self.history.list_review_history(user_id=self.user_id))
                    self.assertEqual(db_before, self.fixture.paths["ALPHAMATE_REVIEW_HISTORY_DB_PATH"].read_bytes())
                    retry = self.main.get_journal_ai_review_once(
                        batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                    replay = self.main.get_journal_ai_review_once(
                        batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                    self.assertEqual((2, 2, 1, 1), (model.call_count, charge.call_count, refund.call_count, write.call_count))
                    self.assertEqual("ready", retry["status"])
                    self.assertEqual(before - 1, self.balance("advanced"))
                    self.assertEqual(retry["review_history_id"], replay["review_history_id"])
                    self.assertTrue(replay["access"]["idempotent_replay"])

    def test_chart_documents_are_original_sealed_strings_not_general_chart_text(self):
        result, expected = self.chart_route("advanced", storage=False)
        chart = expected["charts"][0]
        self.assertEqual("합성 승인 종목", chart["tab"]["canonical_text"])
        self.assertEqual("일봉 · 1d · 2026-07-10", chart["header"]["canonical_text"])
        self.assertEqual(["B2", "S"], [marker["label"]["canonical_text"] for marker in chart["markers"]])
        self.assertEqual("매수 2건\n평균 70,200원 · 수량 2\n70,000, 70,400원", chart["markers"][0]["tooltip"]["canonical_text"])
        self.assertEqual("과거 체결: 승인된 과거 차트 기록을 확인했습니다.", expected["chart_cards"][0]["display"]["canonical_text"])
        original = copy.deepcopy(expected)
        result["chart_display_snapshot"]["charts"][0]["markers"].clear()
        self.assertEqual(original, self.last[2]["result"]["chart_display_snapshot"])
        self.assertEqual(original, self.last_replay["chart_display_snapshot"])

    def test_unsafe_invalid_and_compatibility_errors_publish_no_chart_fallback(self):
        self.compact_provider.return_value = approved_chart_fixture()
        for review_type in ("basic", "advanced"):
            for mode in ("safety", "invalid", "compatibility"):
                with self.subTest(review_type=review_type, mode=mode):
                    output = model_output(review_type)
                    output["main_issue"] = "현재는 매수 추천합니다." if mode == "safety" else "MA20을 확인했습니다."
                    result = self.run_route(review_type, output=output, raw="{" if mode == "invalid" else None,
                                            status="error", internal="safety_rejected" if mode == "safety" else "invalid_structured_output",
                                            storage=True, bodyless=mode in {"invalid", "compatibility"})
                    self.assertEqual({"charts": [], "chart_cards": []}, result.get("chart_display_snapshot", {"charts": [], "chart_cards": []}))
                    self.assertEqual(result.get("chart_display_snapshot"), self.last_replay.get("chart_display_snapshot"))

    def strong_route(self, review_type, *, storage=True):
        output = model_output(review_type)
        output["main_issue"] = "**체결 기록**을 확인합니다."
        result = self.run_route(review_type, output=output, storage=storage)
        self.assertIn("**체결 기록**을 확인합니다.", result["summary"])
        self.assertIn("체결 기록을 확인합니다.", result["display_snapshot"]["canonical_text"])
        self.assertNotEqual(result["summary"], result["display_snapshot"]["canonical_text"])
        self.assertEqual(["체결 기록"], [run["text"] for block in result["display_snapshot"]["blocks"]
                                       for run in block["runs"] if run["type"] == "strong"])
        return result

    def test_plain_body_exact_wire_through_both_routes(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type), self.candidate_body(sentence_body()):
                result = self.run_route(review_type)
                self.assertEqual("체결 기록을 확인합니다.", result["summary"])

    def test_strong_body_exact_wire_through_both_routes(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                result = self.strong_route(review_type, storage=True)
                body = result["display_snapshot"]
                wire = admit_legacy_body(body).summary
                stored = self.history.get_review_history(result["review_history_id"], user_id=self.user_id)
                self.assertEqual(wire, result["summary"])
                self.assertEqual(body, stored["ai_review"]["display_snapshot"])
                self.assertEqual(wire, stored["ai_review"]["summary"])
                self.assertEqual(wire, self.last_replay["summary"])

    def test_basic_normal_route(self):
        self.run_route("basic", storage=True)

    def test_advanced_normal_route(self):
        self.run_route("advanced", storage=True)

    def test_advanced_prompt_and_moving_average_admission_are_consistent(self):
        cases = [("일봉 차트의 20일 이동평균과 체결 기록을 비교했습니다.", "ready")]
        cases += [(f"일봉 차트의 {token}과 체결 기록을 비교했습니다.", "error")
                  for token in ("MA20", "MA5", "MA 20", "ma20")]
        for text, status in cases:
            output = model_output("advanced")
            output["main_issue"] = text
            with self.subTest(text=text), patch.object(
                    self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope) as seal, patch.object(
                    self.ai, "admit_legacy_body", wraps=self.ai.admit_legacy_body) as serializer:
                result = self.run_route("advanced", output=output, status=status,
                                        internal="invalid_structured_output" if status == "error" else None,
                                        storage=True, bodyless=status == "error")
                self.assertEqual(int(status == "ready"), seal.call_count)
                if status == "ready":
                    sealed_body = json.loads(self.last[3]["snapshot"].json_text)["body"]
                    self.assertGreaterEqual(serializer.call_count, 1)
                    for call in serializer.call_args_list:
                        self.assertEqual(sealed_body, call.args[0])
                    self.assertEqual(admit_legacy_body(sealed_body).summary, result["summary"])
                    self.assertIn(text, sealed_body["canonical_text"])
                else:
                    self.assertEqual(0, serializer.call_count)
                self.assertIn("5일 이동평균", self.last_prompt)
                self.assertIn("20일 이동평균", self.last_prompt)
                self.assertIn("1분봉 차트의 5개 봉 이동평균", self.last_prompt)
                self.assertNotRegex(self.last_prompt, r"(?i)ma\s*[0-9]")

    def test_basic_normal_strong_route(self):
        self.strong_route("basic")

    def test_advanced_normal_strong_route(self):
        self.strong_route("advanced")

    def test_basic_missing_key_fallback_route(self):
        self.run_route("basic", raw="", status="missing_key", storage=True)

    def test_advanced_missing_key_fallback_route(self):
        self.run_route("advanced", raw="", status="missing_key", storage=True)

    def test_compatibility_failure_is_terminal_refunded_once_and_never_saved(self):
        for review_type in ("basic", "advanced"):
            for text in ("현재는 매**수** 추천합니다. *", "현재는 매**수** 추천합니다. [참고](url)", "MA20을 기록합니다."):
                output = model_output(review_type)
                output["main_issue"] = text
                with self.subTest(review_type=review_type, text=text):
                    self.run_route(review_type, output=output, status="error", internal="invalid_structured_output",
                                   storage=True, bodyless=True)

    def test_fallback_compatibility_failure_cannot_promote_missing_key(self):
        document = sentence_body()
        document["blocks"][0]["separator_after"] = "\n"
        document["canonical_text"] += "\n"
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type), self.candidate_body(document):
                self.run_route(review_type, raw="", status="error", internal="invalid_structured_output",
                               storage=True, bodyless=True)

    def test_compatibility_failure_preserves_prior_safety_rejection(self):
        document = sentence_body()
        document["blocks"][0]["separator_after"] = "\n"
        document["canonical_text"] += "\n"
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output["main_issue"] = "현재는 매수 추천합니다."
            with self.subTest(review_type=review_type), self.candidate_body(document):
                self.run_route(review_type, output=output, status="error", internal="safety_rejected",
                               storage=True, bodyless=True)

    def test_safety_rejection_refunds_once_without_history_approval(self):
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output["lesson"]["concept"] = "현재는 매수 추천합니다."
            with self.subTest(review_type=review_type):
                result = self.run_route(review_type, output=output, status="error", internal="safety_rejected", storage=True)
                self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def assert_terminal_decode_route(self, review_type, raw):
        with patch.object(self.ai, "seal_review_envelope", wraps=self.ai.seal_review_envelope) as seal, patch.object(
                self.ai, "admit_semantic_source", wraps=self.ai.admit_semantic_source) as admit, patch.object(
                self.ai, "_default_basic_semantics", wraps=self.ai._default_basic_semantics) as basic_fallback, patch.object(
                self.ai, "_default_advanced_semantics", wraps=self.ai._default_advanced_semantics) as advanced_fallback:
            result = self.run_route(review_type, raw=raw, status="error", internal="invalid_structured_output",
                                    storage=True, bodyless=True)
        self.assertEqual((0, 0, 0, 0), (seal.call_count, admit.call_count,
                                       basic_fallback.call_count, advanced_fallback.call_count))
        cached, record = self.last[2:]
        self.assertEqual("none", result["source"])
        self.assertEqual("done", cached["status"])
        self.assertIsNone(cached["snapshot"])
        self.assertIsNone(record["history"])
        for response in (result, self.last_replay, cached["result"]):
            self.assertEqual("", response["summary"])
            for key in ("structured_review", "display_snapshot", "chart_display_snapshot", "review_history_id"):
                self.assertNotIn(key, response)
            self.assertNotIn("현재는 매수 추천합니다.", json.dumps(response, ensure_ascii=False))

    def test_duplicate_json_keys_at_all_depths_are_terminal_and_refunded_once(self):
        for review_type in ("basic", "advanced"):
            for location in ("top-level", "nested", "array"):
                with self.subTest(review_type=review_type, location=location):
                    self.assert_terminal_decode_route(review_type, duplicate_json_model_output(review_type, location))

    def test_unicode_equivalent_duplicate_json_keys_are_terminal_and_refunded_once(self):
        for review_type in ("basic", "advanced"):
            for location in ("top-level", "nested", "array"):
                for escaped_key in (0, 1):
                    with self.subTest(review_type=review_type, location=location, escaped_key=escaped_key):
                        self.assert_terminal_decode_route(review_type, duplicate_json_model_output(
                            review_type, location, escaped_key=escaped_key))

    def test_duplicate_json_keys_cannot_hide_forbidden_first_or_second_values(self):
        for review_type in ("basic", "advanced"):
            for location in ("top-level", "nested", "array"):
                for unsafe_position in (0, 1):
                    for escape_value in (False, True):
                        for escaped_key in (None, 1):
                            with self.subTest(review_type=review_type, location=location,
                                              unsafe_position=unsafe_position, escape_value=escape_value,
                                              escaped_key=escaped_key):
                                raw = duplicate_json_model_output(review_type, location, escaped_key=escaped_key,
                                                                  unsafe_position=unsafe_position, escape_value=escape_value)
                                self.assert_terminal_decode_route(review_type, raw)

    def test_integer_digit_boundary_and_duplicate_order_on_both_routes(self):
        self.addCleanup(sys.set_int_max_str_digits, sys.get_int_max_str_digits())
        sys.set_int_max_str_digits(4300)
        for review_type in ("basic", "advanced"):
            value = model_output(review_type)
            safe = json.dumps(value.pop("main_issue"), ensure_ascii=False)
            fields = json.dumps(value, ensure_ascii=False)[1:-1]
            for digits in (4300, 4301):
                number = "9" * digits
                pairs = '"main_issue": ' + safe + ', "main_issue": ' + safe
                cases = {
                    "unique": fields + ', "main_issue": ' + number,
                    "number-first": fields + ', "main_issue": ' + number + ', "main_issue": ' + safe,
                    "number-second": fields + ', "main_issue": ' + safe + ', "main_issue": ' + number,
                    "duplicate-before-number": pairs + ', "number": ' + number + ', ' + fields,
                    "duplicate-after-number": '"number": ' + number + ', ' + fields + ', ' + pairs,
                }
                for case, fields_with_number in cases.items():
                    raw = '{' + fields_with_number + '}'
                    with self.subTest(review_type=review_type, digits=digits, case=case):
                        if digits == 4300 and case == "unique":
                            self.run_route(review_type, raw=raw, status="error", internal="invalid_structured_output", storage=True)
                            self.assertIsNotNone(self.last[2]["snapshot"])
                        else:
                            self.assert_terminal_decode_route(review_type, raw)

    def test_post_decode_semantic_value_error_keeps_fallback_on_both_routes(self):
        for review_type in ("basic", "advanced"):
            original = self.ai.admit_semantic_source
            rejected = []

            def reject_model_once(*args, **kwargs):
                if not rejected:
                    rejected.append(True)
                    raise ValueError("synthetic post-decode semantic error")
                return original(*args, **kwargs)

            with self.subTest(review_type=review_type), patch.object(
                    self.ai, "admit_semantic_source", side_effect=reject_model_once):
                result = self.run_route(review_type, status="error", internal="invalid_structured_output", storage=True)
                self.assertEqual([True], rejected)
                self.assertEqual("chart-rules", result["source"])
                self.assertIsNotNone(self.last[2]["snapshot"])

    def test_malformed_output_refunds_once_without_history_approval(self):
        for review_type in ("basic", "advanced"):
            for case, raw in enumerate(("not-json", "{", " ", '```json\n\n```', '{"key": 1,}', '{"key": 1} trailing',
                                        '{"nested": ' + '[' * 10000 + '0' + ']' * 10000 + '}')):
                with self.subTest(review_type=review_type, case=case):
                    self.assert_terminal_decode_route(review_type, raw)

    def test_schema_invalid_output_refunds_once_without_history_approval(self):
        for review_type in ("basic", "advanced"):
            output = model_output(review_type)
            output.pop("main_issue")
            with self.subTest(review_type=review_type):
                self.run_route(review_type, output=output, status="error", internal="invalid_structured_output", storage=True)

    def test_storage_off_strong_result_replays_without_history_preparation(self):
        with patch.object(self.main, "build_journal_charts", side_effect=AssertionError("storage-off chart")):
            self.strong_route("basic", storage=False)
            self.strong_route("advanced", storage=False)

    def test_source_response_history_cache_and_replay_have_no_mutable_alias(self):
        for review_type in ("basic", "advanced"):
            with self.subTest(review_type=review_type):
                result = self.strong_route(review_type)
                batch, key, cached, record = self.last
                expected = copy.deepcopy(result)
                sealed_text = record["snapshot"].json_text
                metadata_text = record["history"]["metadata_json"]
                result["summary"] = "changed wire"
                result["display_snapshot"]["blocks"][0]["runs"][0]["text"] = "changed body"
                result["structured_review"]["summary"]["main_issue"] = "changed semantic"
                result["access"]["quota"][review_type]["signup_remaining"] = -1
                self.charts["charts"][0]["name"] = "changed chart"
                batch.trades[0].memo = "changed trade"
                self.assertEqual(sealed_text, record["snapshot"].json_text)
                self.assertEqual(metadata_text, record["history"]["metadata_json"])
                self.assertEqual(expected, cached["result"])
                # Fingerprint uses the original request, so use a fresh identical batch.
                replay = self.main.get_journal_ai_review_once(self.batch(review_type), authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
                expected["access"]["idempotent_replay"] = True
                self.assertEqual(expected, replay)
                replay["display_snapshot"]["blocks"][0]["runs"][0]["text"] = "changed replay"
                detail = self.main.get_journal_review_history_detail(expected["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
                self.assertEqual(expected["summary"], detail["ai_review"]["summary"])
                self.assertEqual(expected["display_snapshot"], detail["ai_review"]["display_snapshot"])
                with self.assertRaises(AttributeError):
                    record["snapshot"]._json = b"{}"

    def test_history_restore_reads_body_without_semantic_summary_reconstruction(self):
        result = self.strong_route("advanced")
        raw = self.history.get_review_history(result["review_history_id"], user_id=self.user_id)
        raw["ai_review"]["structured_review"]["summary"]["main_issue"] = "別の安全な記録"
        with patch.object(self.main, "get_review_history", return_value=raw), patch.object(
                self.ai, "compile_structured_review", side_effect=AssertionError("history semantic rebuild")):
            detail = self.main.get_journal_review_history_detail(result["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
        self.assertEqual(result["summary"], detail["ai_review"]["summary"])
        self.assertEqual(result["display_snapshot"], detail["ai_review"]["display_snapshot"])

    def test_history_wrong_wire_is_withheld_without_semantic_or_raw_repair(self):
        result = self.strong_route("advanced")
        raw = self.history.get_review_history(result["review_history_id"], user_id=self.user_id)
        raw["ai_review"]["summary"] = result["display_snapshot"]["canonical_text"]
        with patch.object(self.main, "get_review_history", return_value=raw), patch.object(
                self.ai, "compile_structured_review", side_effect=AssertionError("history semantic rebuild")):
            detail = self.main.get_journal_review_history_detail(result["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
        self.assertEqual("error", detail["ai_review"]["status"])
        self.assertNotEqual(result["display_snapshot"], detail["ai_review"]["display_snapshot"])
        original = self.history.get_review_history(result["review_history_id"], user_id=self.user_id)
        self.assertEqual(result["summary"], original["ai_review"]["summary"])

    def test_route_rejects_unsealed_or_changed_content_with_one_refund(self):
        for change in ("unsealed", "body", "wire", "status"):
            with self.subTest(change=change):
                self.accounts.update_journal_storage_setting(authorization=self.token, enabled=True)
                original = self.main.build_advanced_ai_review

                def changed(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if change == "unsealed":
                        kwargs["approval_state"]["snapshot"] = None
                    elif change == "body":
                        result["display_snapshot"] = sentence_body()
                    elif change == "wire":
                        result["summary"] = "legacy raw replacement"
                    else:
                        result["status"] = "missing_key"
                    return result

                before, rows = self.balance("advanced"), self.history.list_review_history(user_id=self.user_id)
                with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(model_output("advanced"))), patch.object(
                        self.main, "build_advanced_ai_review", side_effect=changed), patch.object(
                        self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                        self.main, "add_review_history", wraps=self.main.add_review_history) as save:
                    with self.assertRaises(ValueError):
                        self.main.get_journal_ai_review_once(self.batch("advanced"), authorization=self.token, x_review_display_contract=[SCHEMA_VERSION],
                                                           x_idempotency_key=f"a3-changed-{change}")
                    self.assertEqual((1, 0), (refund.call_count, save.call_count))
                self.assertEqual(before, self.balance("advanced"))
                self.assertEqual(rows, self.history.list_review_history(user_id=self.user_id))

    def test_tampered_cache_wire_cannot_become_an_independent_authority(self):
        self.strong_route("advanced")
        batch, key, cached, record = self.last
        cached["result"]["summary"] = cached["result"]["display_snapshot"]["canonical_text"]
        with patch.object(self.ai, "_call_openai_review", side_effect=AssertionError("cache model")), patch.object(
                self.main, "verify_ai_review_access", side_effect=AssertionError("cache charge")), patch.object(
                self.main, "refund_ai_review_access", side_effect=AssertionError("cache refund")), patch.object(
                self.main, "add_review_history", side_effect=AssertionError("cache history")):
            with self.assertRaises(ValueError):
                self.main.get_journal_ai_review_once(batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key=key)
        self.assertEqual(1, len(self.history.list_review_history(user_id=self.user_id)))

    def test_terminal_error_then_cache_failure_still_refunds_exactly_once(self):
        output = model_output("advanced")
        output["main_issue"] = "MA20을 기록합니다."
        self.accounts.update_journal_storage_setting(authorization=self.token, enabled=True)
        before = self.balance("advanced")
        with patch.object(self.ai, "_call_openai_review", return_value=json.dumps(output)), patch.object(
                self.main, "_finish_ai_review_idempotency", side_effect=RuntimeError("synthetic cache failure")), patch.object(
                self.main, "refund_ai_review_access", wraps=self.main.refund_ai_review_access) as refund, patch.object(
                self.main, "add_review_history", wraps=self.main.add_review_history) as save:
            with self.assertRaisesRegex(RuntimeError, "synthetic cache failure"):
                self.main.get_journal_ai_review_once(self.batch("advanced"), authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="a3-error-cache-failure")
            self.assertEqual((1, 0), (refund.call_count, save.call_count))
        self.assertEqual(before, self.balance("advanced"))
        self.assertEqual([], self.history.list_review_history(user_id=self.user_id))


if __name__ == "__main__":
    unittest.main()
