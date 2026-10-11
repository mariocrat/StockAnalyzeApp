"""Route-level structured AI review refund cases inside the H4 storage boundary."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from backend.core.review_display_contract import SCHEMA_VERSION

from tests.review_source_fixtures import compact_chart_fixture, fallback_model_fixture, review_input_fixture, history_chart_fixture

from tests.api_test_modules import api_module_state

import importlib
import copy
import json
import unittest
from unittest.mock import patch
from backend.core.review_legacy_compatibility import admit_legacy_body


def _valid_advanced_output():
    return {
        "decision_quality": {"label": "보통", "explanation": "당시 확인 가능한 근거로 평가합니다."},
        "main_issue": "사전 기준 기록이 부족합니다.",
        "next_action": "다음 주문 전에 판단 근거를 기록합니다.",
        "entry_review": {
            "evidence": ["매수 체결 가격을 확인했습니다."],
            "uncertainty": ["매수 이유 기록은 제한적입니다."],
            "invalidation": "기록 없음",
            "assessment": {"label": "근거 일부", "explanation": "확인 가능한 근거만 평가합니다."},
        },
        "risk_review": {
            "planned_rule": "기록 없음",
            "actual_response": "체결 대응을 확인합니다.",
            "assessment": {"label": "근거 부족", "explanation": "사전 위험 기준이 없습니다."},
        },
        "exit_review": {
            "profit_taking_assessment": "판단 보류",
            "trend_exit_assessment": "판단 보류",
            "explanation": "사후 가격만으로 판단하지 않습니다.",
        },
        "detailed_analysis": [{"title": "체결", "detail": "기록된 체결을 확인합니다."}],
        "next_trade_playbook": {
            "before_entry": ["진입 이유를 기록합니다."],
            "while_holding": ["실제 흐름을 비교합니다."],
            "before_exit": ["매도 이유를 기록합니다."],
        },
        "lesson": {
            "title": "판단과 결과 분리",
            "concept": "당시 근거로 판단합니다.",
            "applied_to_this_trade": "기록을 확인합니다.",
            "next_trade_application": "사전 기준을 기록합니다.",
        },
        "reflection_questions": ["당시 어떤 근거를 확인했나요?"],
    }


class TradeReviewRefundTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"))
        modules = self.enterContext(api_module_state())
        self.main = modules.main
        self.access_control = modules.access_control
        self.account_store = modules.account_store
        self.review_history = modules.review_history
        self.ai_review_v2 = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", return_value=[]))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})))

        session = modules.account_store.login_dev_provider(
            provider="kakao", provider_user_id="structured-refund-test", display_name="복기 환급 테스트",
        )
        self.token = f"Bearer {session['session_token']}"
        wallet = self.access_control._wallet_for(session["user"]["id"], "free")
        wallet.signup_advanced_remaining = 0
        self.access_control._save_wallet(session["user"]["id"], wallet)
        self.access_control.apply_dev_purchase(
            authorization=self.token, entitlement_token="", product_id="advanced_review_10",
        )
        self.batch = self.main.JournalAiReviewIn(
            privacy_consent=True,
            review_type="advanced",
            trades=[self.main.JournalTradeIn(
                trade_date="2026-07-10T09:30", ticker="005930", name="삼성전자",
                side="buy", price=70000, quantity=1,
            )],
        )

    def _assert_route_result(self, raw_output, *, status, refunded, internal_status=None, model_calls=1, bodyless=False):
        before = self.access_control.get_user_entitlements(authorization=self.token, entitlement_token="")
        self.assertEqual(10, before["advanced"]["purchased_remaining"])
        calls = {"model": 0, "refund": 0}
        original_refund = self.main.refund_ai_review_access

        def fake_model(payload, *, model, instructions):
            calls["model"] += 1
            return raw_output

        def tracked_refund(access):
            calls["refund"] += 1
            return original_refund(access)

        with patch.object(self.ai_review_v2, "_call_openai_review", fake_model), patch.object(
            self.main, "refund_ai_review_access", tracked_refund,
        ):
            result = self.main.get_journal_ai_review_once(
                self.batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="structured-refund-case",
            )
            replay = self.main.get_journal_ai_review_once(
                self.batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="structured-refund-case",
            )

        after = self.access_control.get_user_entitlements(authorization=self.token, entitlement_token="")
        self.assertEqual(status, result["status"])
        self.assertEqual(internal_status, result.get("internal_status"))
        self.assertEqual("purchased_advanced", result["access"]["source"])
        self.assertEqual(refunded, result["access"]["refunded"])
        self.assertEqual(10 if refunded else 9, after["advanced"]["purchased_remaining"])
        self.assertEqual(after["advanced"]["purchased_remaining"], result["access"]["quota"]["advanced"]["purchased_remaining"])
        self.assertTrue(replay["access"]["idempotent_replay"])
        if bodyless:
            for response in (result, replay):
                self.assertEqual(("none", ""), (response["source"], response["summary"]))
                self.assertNotIn("display_snapshot", response)
                self.assertNotIn("structured_review", response)
                self.assertNotIn("review_history_id", response)
            cache_key = self.main._ai_review_idempotency_cache_key(self.token, "structured-refund-case")
            self.assertIsNone(self.main._ai_review_idempotency_cache[cache_key]["snapshot"])
        else:
            self.assertEqual(result["display_snapshot"], replay["display_snapshot"])
            self.assertEqual(result["summary"], admit_legacy_body(result["display_snapshot"]).summary)
            self.assertEqual("trade-review.v1", result["structured_review"]["schema_version"])
        self.assertEqual(model_calls, calls["model"])
        self.assertEqual(1 if refunded else 0, calls["refund"])
        return result

    def test_valid_structured_result_consumes_purchased_review_once(self):
        original = self.ai_review_v2._finalize_ai_review
        finalized = []

        def track(*args, **kwargs):
            result = original(*args, **kwargs)
            finalized.append(result)
            return result

        with patch.object(self.ai_review_v2, "_finalize_ai_review", track):
            result = self._assert_route_result(
                json.dumps(_valid_advanced_output(), ensure_ascii=False), status="ready", refunded=False,
            )
        self.assertEqual("openai", result["source"])
        self.assertIn("상세 분석:", result["summary"])
        self.assertEqual(finalized[0]["summary"], result["summary"])
        self.assertEqual(finalized[0]["structured_review"], result["structured_review"])
        self.assertIsNot(finalized[0]["structured_review"], result["structured_review"])

    def test_malformed_json_is_terminal_and_refunds_purchased_review_once(self):
        result = self._assert_route_result(
            "not-json", status="error", refunded=True, internal_status="invalid_structured_output", bodyless=True,
        )
        self.assertEqual(("none", ""), (result["source"], result["summary"]))
        self.assertNotIn("not-json", result["summary"])

    def test_schema_invalid_json_falls_back_and_refunds_purchased_review_once(self):
        output = _valid_advanced_output()
        output.pop("lesson")
        result = self._assert_route_result(
            json.dumps(output, ensure_ascii=False),
            status="error", refunded=True, internal_status="invalid_structured_output",
        )
        self.assertEqual("chart-rules", result["source"])
        self.assertTrue(result["summary"].startswith("최근 패턴:"))
        self.assertEqual(result["summary"], result["display_snapshot"]["canonical_text"])

    def test_safety_rejection_falls_back_and_refunds_purchased_review_once(self):
        output = _valid_advanced_output()
        output["lesson"]["concept"] = "현재는 매수 추천합니다."
        result = self._assert_route_result(
            json.dumps(output, ensure_ascii=True),
            status="error", refunded=True, internal_status="safety_rejected",
        )
        self.assertNotIn("현재는 매수 추천합니다.", result["summary"])

    def test_composed_summary_safety_rejection_refunds_purchased_review_once(self):
        output = _valid_advanced_output()
        output["detailed_analysis"] = [{"title": "목표가", "detail": "80,000원입니다."}]
        chart = {"candles": [{"time": "2026-07-10", "close": 70000}], "rule_based_observations": []}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._assert_route_result(
                json.dumps(output, ensure_ascii=False),
                status="error", refunded=True, internal_status="safety_rejected",
            )
        self.assertEqual("chart-rules", result["source"])
        self.assertNotIn("목표가: 80,000원입니다.", result["summary"])
        self.assertNotIn("목표가: 80,000원입니다.", json.dumps(result["structured_review"], ensure_ascii=False))

    def test_basic_raw_safety_failure_refunds_signup_quota_once(self):
        batch = self.main.JournalAiReviewIn(
            privacy_consent=True, review_type="basic", trades=self.batch.trades,
        )
        before = self.access_control.get_user_entitlements(authorization=self.token, entitlement_token="")
        calls = {"model": 0, "refund": 0}
        original_refund = self.main.refund_ai_review_access

        def fake_model(payload, *, model, instructions):
            calls["model"] += 1
            return json.dumps({"main_issue": "현재는 매수 추천합니다."}, ensure_ascii=False)

        def tracked_refund(access):
            calls["refund"] += 1
            return original_refund(access)

        with patch.object(self.ai_review_v2, "_call_openai_review", fake_model), patch.object(
            self.main, "refund_ai_review_access", tracked_refund,
        ):
            result = self.main.get_journal_ai_review_once(
                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="basic-safety-failure",
            )
            replay = self.main.get_journal_ai_review_once(
                batch, authorization=self.token, x_review_display_contract=[SCHEMA_VERSION], x_idempotency_key="basic-safety-failure",
            )

        after = self.access_control.get_user_entitlements(authorization=self.token, entitlement_token="")
        self.assertEqual("error", result["status"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertEqual("signup_basic", result["access"]["source"])
        self.assertTrue(result["access"]["refunded"])
        self.assertEqual(before["basic"]["signup_remaining"], after["basic"]["signup_remaining"])
        self.assertEqual({"model": 1, "refund": 1}, calls)
        self.assertTrue(replay["access"]["idempotent_replay"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_normalized_truncation_safety_failure_refunds_purchased_review_once(self):
        output = _valid_advanced_output()
        suffix = "목표가: 80,000원"
        output["lesson"]["concept"] = "A" * (900 - len(suffix)) + suffix + "이라는 표현을 과거 기록에서 확인했습니다."
        chart = {"candles": [{"time": "2026-07-10", "close": 70000}], "rule_based_observations": []}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._assert_route_result(
                json.dumps(output, ensure_ascii=False),
                status="error", refunded=True, internal_status="safety_rejected",
            )
        self.assertNotIn("목표가: 80,000원", result["summary"])

    def test_final_structured_tree_safety_failure_refunds_purchased_review_once(self):
        original = self.ai_review_v2._build_structured_review

        def inject(*args, **kwargs):
            structured = original(*args, **kwargs)
            if args[0].status == "ready":
                structured["advanced"]["future_notes"] = {"items": ["현재는 매수 추천합니다."]}
            return structured

        chart = {"candles": [{"time": "2026-07-10", "close": 70000}], "rule_based_observations": []}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)), patch.object(
            self.ai_review_v2, "_build_structured_review", inject,
        ):
            result = self._assert_route_result(
                json.dumps(_valid_advanced_output(), ensure_ascii=False),
                status="error", refunded=True, internal_status="safety_rejected",
            )
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_unsafe_chart_fallback_refunds_once_and_returns_fixed_safe_text(self):
        chart = {
            "candles": [{"time": "2026-07-10", "close": 70000}],
            "rule_based_observations": [{
                "trade_id": 1, "title": "매수 시점: 아쉬움",
                "detail": "현재는 매수 추천합니다.", "metrics": {},
            }],
        }
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._assert_route_result(
                "not-json", status="error", refunded=True, internal_status="safety_rejected", model_calls=0,
            )
        self.assertIn("복기 내용을 안전하게 표시할 수 없습니다.", result["summary"])
        self.assertEqual([], result["chart_reviews"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_missing_api_key_result_keeps_existing_non_refund_status(self):
        result = self._assert_route_result("", status="missing_key", refunded=False)
        self.assertEqual("chart-rules", result["source"])

    def test_earlier_unsafe_chart_refunds_once_and_replay_never_calls_model(self):
        chart = {"candles": [{"time": "2026-07-10", "close": 70000}],
                 "rule_based_observations": [
                     {"title": "매수 시점", "detail": "현재는 매수 추천합니다."},
                     {"title": "매수 시점", "detail": "과거 체결을 확인합니다."},
                 ]}
        with patch.object(self.ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture(chart)):
            result = self._assert_route_result(
                json.dumps(_valid_advanced_output(), ensure_ascii=False),
                status="error", refunded=True, internal_status="safety_rejected", model_calls=0,
            )
        self.assertEqual([], result["chart_reviews"])
        self.assertNotIn("현재는 매수 추천합니다.", json.dumps(result, ensure_ascii=False))

    def test_unsafe_history_chart_refunds_once_without_storing_history(self):
        self.account_store.update_journal_storage_setting(authorization=self.token, enabled=True)
        chart_calls = {"count": 0}

        def unsafe_history_chart(trades):
            chart_calls["count"] += 1
            return {"charts": [{"name": "현재는 매수 추천합니다."}]}

        with patch.object(self.main, "build_journal_charts", unsafe_history_chart):
            result = self._assert_route_result(
                json.dumps(_valid_advanced_output(), ensure_ascii=False),
                status="error", refunded=True, internal_status="safety_rejected", model_calls=0,
            )
        self.assertEqual(1, chart_calls["count"])
        self.assertNotIn("review_history_id", result)
        self.assertEqual([], self.review_history.list_review_history(user_id=self.account_store.authenticate_session(self.token)["id"]))

    def test_safe_review_replay_preserves_approved_history_in_phase2c(self):
        self.account_store.update_journal_storage_setting(authorization=self.token, enabled=True)
        charts = history_chart_fixture([trade.model_dump() for trade in self.batch.trades])
        calls = {"chart": 0}

        def history_chart(trades):
            calls["chart"] += 1
            return charts

        with patch.object(self.main, "build_journal_charts", history_chart):
            result = self._assert_route_result(
                json.dumps(_valid_advanced_output(), ensure_ascii=False),
                status="ready", refunded=False,
            )
        self.assertEqual(1, calls["chart"])
        user_id = self.account_store.authenticate_session(self.token)["id"]
        rows = self.review_history.list_review_history(user_id=user_id)
        self.assertEqual([result["review_history_id"]], [row["id"] for row in rows])
        detail = self.main.get_journal_review_history_detail(result["review_history_id"], authorization=self.token, x_review_display_contract=[SCHEMA_VERSION])
        self.assertEqual(result["summary"], detail["ai_review"]["summary"])
        self.assertEqual(result["display_snapshot"], detail["ai_review"]["display_snapshot"])
        expected = copy.deepcopy(result)
        charts["charts"][0]["name"] = "현재는 매수 추천합니다."
        self.batch.trades[0].name = "현재는 매수 추천합니다."
        self.assertEqual(expected, result)
        cache_key = self.main._ai_review_idempotency_cache_key(self.token, "structured-refund-case")
        cached = self.main._ai_review_idempotency_cache[cache_key]["result"]
        self.assertEqual(expected["structured_review"], cached["structured_review"])
        self.assertEqual(expected["display_snapshot"], cached["display_snapshot"])
        result["structured_review"]["summary"]["main_issue"] = "changed after return"
        self.assertEqual(expected["structured_review"], cached["structured_review"])


if __name__ == "__main__":
    unittest.main()
