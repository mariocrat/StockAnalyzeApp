from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state

import importlib
import json
import os
import unittest
from unittest.mock import patch


class AiReviewOpenAiClientTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai_review_v2 = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai_review_v2.__dict__))
        importlib.reload(self.ai_review_v2)

    def test_ai_review_uses_expected_default_model_ids(self):
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append((payload["review_type"], model))
            return f"{payload['review_type']}-ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))

        basic = self.ai_review_v2.build_basic_ai_review([{
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }])
        advanced = self.ai_review_v2.build_advanced_ai_review([{
            "id": 2,
            "trade_date": "2026-06-20T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "sell",
            "price": 72000,
            "quantity": 1,
        }])

        self.assertEqual("gpt-5.6-luna", basic["model"])
        self.assertEqual("gpt-5.6-luna", advanced["model"])
        self.assertEqual([("basic", "gpt-5.6-luna"), ("advanced", "gpt-5.6-luna")], captured)

    def test_ai_review_model_ids_are_configurable(self):
        os.environ["OPENAI_BASIC_REVIEW_MODEL"] = "custom-basic-model"
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "custom-advanced-model"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            return "ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        trade = {
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }

        self.ai_review_v2.build_basic_ai_review([trade])
        self.ai_review_v2.build_advanced_ai_review([trade])

        self.assertEqual(["custom-basic-model", "custom-advanced-model"], captured)

    def test_advanced_review_requests_readable_korean_indicator_terms(self):
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured["payload"] = payload
            captured["instructions"] = instructions
            return "ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        self.ai_review_v2.build_advanced_ai_review([{
            "id": 1,
            "trade_date": "2026-07-16T09:06",
            "ticker": "004310",
            "name": "현대약품",
            "side": "buy",
            "price": 7250,
            "quantity": 69,
        }])

        self.assertEqual("structured markdown", captured["payload"]["output_contract"]["format"])
        self.assertIn("MA5, MA10, MA20처럼 띄어쓰기 없는 표준 약어", captured["instructions"])
        self.assertIn("1분봉 차트의 MA5", captured["instructions"])
        self.assertIn("일봉 차트의 MA20", captured["instructions"])
        self.assertIn("'5분선'처럼", captured["instructions"])
        self.assertIn("결과와 당시 판단의 품질을 반드시 분리", captured["instructions"])
        self.assertIn("완결된 매매가 5개 미만", captured["instructions"])
        self.assertIn(
            "향후 특정 종목, 가격, 시각, 날짜 또는 조건에서 매수하거나 매도하라고",
            captured["instructions"],
        )
        self.assertIn(
            "새로운 가격·시간·비율·조건을 만들어 지시하지 않는다",
            captured["instructions"],
        )
        self.assertIn(
            "[데이터 확인], [합리적 추론] 같은 내부 분류 표시는 출력하지 않는다",
            captured["instructions"],
        )

    def test_trade_guidance_validator_blocks_future_actionable_advice(self):
        blocked_examples = (
            "다음에는 80,000원 돌파 시 매수하세요.",
            "75,000원 돌파 시 매수하세요.",
            "75,000원을 돌파하면 매수하세요.",
            "MA20 이탈 시 매도하세요.",
            "MA20을 이탈하면 매도하세요.",
            "-5%에서 손절하세요.",
            "손실이 5%가 되면 손절하세요.",
            "80,000원에 도달하면 청산하세요.",
            "70,000원 아래로 내려가면 매도하세요.",
            "오후 2시에 전량 매도하는 것을 권장합니다.",
            "추천 매수가 75,000원",
            "목표가 80,000원",
            "손절가를 68,000원으로 설정하세요.",
            "5% 하락하면 손절하세요.",
            "MA20 이탈 시 매도를 고려하세요.",
            "MA20 이탈 시 매도하는 편이 좋습니다.",
            "MA20 이탈 시 매도할 계획을 세우세요.",
            "75,000원 돌파 시 매수를 고려하세요.",
            "75,000원 돌파 시 매수하는 편이 좋습니다.",
            "75,000원 돌파 시 매수할 계획을 세우세요.",
            "손실이 5%가 되면 손절을 고려하세요.",
            "손실이 5%가 되면 손절하는 편이 좋습니다.",
            "손실이 5%가 되면 손절할 계획을 세우세요.",
            "MA20 이탈 시 매도해보세요.",
            "75,000원 돌파 시 매수를 검토하세요.",
            "80,000원에 도달하면 청산을 생각해보세요.",
        )

        for example in blocked_examples:
            with self.subTest(example=example):
                self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(example))
                self.assertTrue(
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example)
                )

    def test_trade_guidance_validator_allows_retrospective_review_language(self):
        allowed_examples = (
            "당시 70,000원에 매수했다.",
            "당시 68,000원을 손절 기준으로 기록했다.",
            "당시 MA20 이탈 시 매도하기로 정했는지 확인해보세요.",
            "실제로 -5% 손실에서 매도했다.",
            "당시 정한 손절 기준과 실제 행동이 일치했는지 점검해보세요.",
            "실제 수익률은 2.1%였고 당시 대응이 합리적이었는지 점검하세요.",
            "이번 매매에서는 오전 9시 10분에 7,430원으로 매도했습니다. 당시 근거를 확인하세요.",
            "당시 MA20 이탈 시 매도를 고려했다고 기록했다.",
            "당시 MA20 이탈 시 매도할 계획을 세웠다.",
            "당시 MA20 이탈 시 매도하는 편이 좋다고 판단했다.",
            "당시 68,000원을 손절 기준으로 정했다.",
            "당시 정한 매도 계획이 실제 행동과 일치했는지 확인해보세요.",
        )

        for example in allowed_examples:
            with self.subTest(example=example):
                self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(example))
                self.assertEqual(
                    [],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                )
                self.assertEqual(
                    [],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                )

    def test_rule_1_allows_negated_and_retrospective_mentions(self):
        allowed_examples = (
            "목표가를 제시하지 않습니다.",
            "목표가를 정하는 대신 당시 판단 근거를 점검해보세요.",
            "이 내용은 매수 추천이 아닙니다.",
            "특정 종목의 매도 추천을 제공하지 않습니다.",
            "당시 목표가를 정해두었는지는 기록에서 확인되지 않습니다.",
            "당시 목표가를 정했던 이유가 무엇인지 복기해보세요.",
            "당시 추천 매수가를 참고했는지는 기록에서 알 수 없습니다.",
            "당시 목표가를 약 80,000원으로 기록했다.",
            "당시 80,000원을 목표가로 잡았는지 기록을 확인해보세요.",
            "당시 추천 매수 가격을 참고했다고 기록했다.",
            "당시 매수 쪽이 좋다고 판단한 이유를 복기해보세요.",
            "당시 매도하는 편이 낫다고 생각했던 근거를 확인해보세요.",
            "당시 목표가는 8만원이었다고 기록했다.",
            "당시 목표가를 80,000원으로 잡았던 이유를 복기해보세요.",
            "당시 매수하는 게 좋다고 판단했다.",
            "당시 매도하는 게 낫다고 생각했던 이유를 복기해보세요.",
        )

        for example in allowed_examples:
            with self.subTest(example=example):
                self.assertFalse(self.ai_review_v2._contains_prohibited_trade_guidance(example))
                self.assertEqual(
                    [],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                )
                self.assertEqual(
                    [],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                )

    def test_rule_1_blocks_exact_independent_review_regressions(self):
        blocked_examples = {
            "목표가는 8만원입니다.": "target_price",
            "목표가를 80,000원으로 잡으세요.": "target_price",
            "현재는 매수하는 게 좋습니다.": "buy_recommendation",
            "현재는 매도하는 게 낫습니다.": "sell_recommendation",
        }

        for example, category in blocked_examples.items():
            with self.subTest(example=example):
                self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(example))
                self.assertEqual(
                    ["rule_1"],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                )
                self.assertEqual(
                    [category],
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                )

    def test_rule_1_blocks_target_term_and_price_notation_combinations(self):
        target_terms = (("목표가", "는"), ("목표 가격", "은"), ("목표주가", "는"))
        prices = ("80,000원", "80000원", "8만원")

        for target_term, particle in target_terms:
            for price in prices:
                example = f"{target_term}{particle} {price}입니다."
                with self.subTest(target_term=target_term, price=price):
                    self.assertEqual(
                        ["rule_1"],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                    )
                    self.assertEqual(
                        ["target_price"],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                    )

        for price in prices:
            for directive in ("잡으세요", "설정하세요"):
                example = f"목표가를 {price}으로 {directive}."
                with self.subTest(price=price, directive=directive):
                    self.assertEqual(
                        ["rule_1"],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                    )
                    self.assertEqual(
                        ["target_price"],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                    )

    def test_rule_1_blocks_trade_action_and_positive_predicate_combinations(self):
        actions = (("매수", "buy_recommendation"), ("매도", "sell_recommendation"))
        recommendation_phrases = (
            "하는 것이 좋습니다",
            "하는 게 좋습니다",
            "하는 편이 좋습니다",
            "하는 것이 낫습니다",
            "하는 게 낫습니다",
            "하는 편이 낫습니다",
        )

        for action, category in actions:
            for recommendation_phrase in recommendation_phrases:
                example = f"현재는 {action}{recommendation_phrase}."
                with self.subTest(action=action, recommendation_phrase=recommendation_phrase):
                    self.assertEqual(
                        ["rule_1"],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                    )
                    self.assertEqual(
                        [category],
                        self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                    )

    def test_rule_1_blocks_actionable_recommendations_with_categories(self):
        blocked_examples = {
            "목표가는 80,000원입니다.": ("rule_1", "target_price"),
            "목표가를 80,000원으로 설정하세요.": ("rule_1", "target_price"),
            "추천 매수가는 75,000원입니다.": ("rule_1", "recommended_entry_price"),
            "추천 매도가는 82,000원입니다.": ("rule_1", "recommended_exit_price"),
            "이 종목은 매수 추천합니다.": ("rule_1", "buy_recommendation"),
            "현재는 매도 추천합니다.": ("rule_1", "sell_recommendation"),
            "목표가는 약 80,000원으로 보입니다.": ("rule_1", "target_price"),
            "목표 가격은 80,000원입니다.": ("rule_1", "target_price"),
            "목표주가는 80,000원 정도가 적절합니다.": ("rule_1", "target_price"),
            "80,000원을 목표가로 잡는 것이 좋습니다.": ("rule_1", "target_price"),
            "80,000원을 목표 가격으로 설정하는 편이 좋습니다.": (
                "rule_1",
                "target_price",
            ),
            "80,000원을 목표가로 잡는 게 좋습니다.": ("rule_1", "target_price"),
            "추천 매수 가격은 75,000원입니다.": (
                "rule_1",
                "recommended_entry_price",
            ),
            "추천 매도 가격은 82,000원입니다.": (
                "rule_1",
                "recommended_exit_price",
            ),
            "이 종목은 매수 쪽이 좋아 보입니다.": ("rule_1", "buy_recommendation"),
            "현재는 매도하는 편이 낫습니다.": ("rule_1", "sell_recommendation"),
            "매수 쪽이 더 유리해 보입니다.": ("rule_1", "buy_recommendation"),
            "매도하는 것이 적절해 보입니다.": ("rule_1", "sell_recommendation"),
            "매수 추천은 아니지만, 현재는 매수 쪽이 좋아 보입니다.": (
                "rule_1",
                "buy_recommendation",
            ),
            "목표가를 제시하지 않지만, 80,000원을 목표가로 잡는 것이 좋습니다.": (
                "rule_1",
                "target_price",
            ),
            "75,000원에 매수하는 것을 추천합니다.": (
                "rule_3",
                "price_or_time_trade_instruction",
            ),
        }

        for example, (rule_id, category) in blocked_examples.items():
            with self.subTest(example=example):
                self.assertTrue(self.ai_review_v2._contains_prohibited_trade_guidance(example))
                self.assertIn(
                    rule_id,
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_ids(example),
                )
                self.assertIn(
                    category,
                    self.ai_review_v2._matched_prohibited_trade_guidance_rule_categories(example),
                )

    def test_safety_rejection_records_only_rule_ids_and_internal_status(self):
        rejected_text = "목표가는 80,000원입니다."
        captured_events = []

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: (
            self.ai_review_v2._OpenAiReviewText(rejected_text, response_status="completed")
        )))
        self.enterContext(patch.object(self.ai_review_v2, "record_event", lambda **kwargs: captured_events.append(kwargs)))

        result = self.ai_review_v2.build_advanced_ai_review([{
            "id": 1,
            "trade_date": "2026-07-10T09:36",
            "ticker": "017900",
            "name": "광전자",
            "side": "buy",
            "price": 6980,
            "quantity": 10,
        }])

        self.assertEqual("missing_key", result["status"])
        self.assertEqual("chart-rules", result["source"])
        self.assertEqual("safety_rejected", result["internal_status"])
        self.assertEqual(1, len(captured_events))
        event = captured_events[0]
        self.assertEqual("openai_review_safety_rejected", event["event_type"])
        self.assertEqual("advanced", event["details"]["review_type"])
        self.assertEqual("gpt-5.6-luna", event["details"]["model"])
        self.assertEqual(["rule_1"], event["details"]["matched_rule_ids"])
        self.assertEqual(["target_price"], event["details"]["matched_rule_categories"])
        self.assertEqual("completed", event["details"]["response_status"])
        serialized_event = json.dumps(event, ensure_ascii=False)
        self.assertNotIn(rejected_text, serialized_event)
        self.assertNotIn("prompt", serialized_event.lower())
        self.assertNotIn("snippet", serialized_event.lower())

    def test_advanced_review_uses_configurable_fallback_model_after_primary_failure(self):
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "primary-advanced-model"
        os.environ["OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL"] = "fallback-advanced-model"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            if model == "primary-advanced-model":
                raise RuntimeError("primary failed")
            return "fallback-ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        result = self.ai_review_v2.build_advanced_ai_review([{
            "id": 1,
            "trade_date": "2026-06-19T10:30",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "buy",
            "price": 70000,
            "quantity": 1,
        }])

        self.assertEqual("ready", result["status"])
        self.assertEqual("fallback-advanced-model", result["model"])
        self.assertEqual(["primary-advanced-model", "fallback-advanced-model"], captured)

    def test_successful_openai_review_results_expose_plain_string_summaries(self):
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", lambda payload, *, model, instructions: (
            self.ai_review_v2._OpenAiReviewText(
                f"{payload['review_type']} review",
                response_status="completed",
            )
        )))
        trades = [{
            "id": 1,
            "trade_date": "2026-07-10T09:36",
            "ticker": "017900",
            "name": "광전자",
            "side": "buy",
            "price": 6980,
            "quantity": 10,
        }]

        basic = self.ai_review_v2.build_basic_ai_review(trades)
        advanced = self.ai_review_v2.build_advanced_ai_review(trades)

        self.assertIs(str, type(basic["summary"]))
        self.assertIs(str, type(advanced["summary"]))
        self.assertEqual("basic review", basic["summary"])
        self.assertEqual("advanced review", advanced["summary"])

    def test_many_trades_keep_basic_episode_and_advanced_history_scopes_separate(self):
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured[payload["review_type"]] = payload
            return "ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        trades = [
            {
                "id": index,
                "trade_date": f"2026-07-{index:02d}T10:30",
                "ticker": "005930" if index % 2 else "000660",
                "name": "Samsung Electronics" if index % 2 else "SK hynix",
                "side": "buy" if index % 3 else "sell",
                "price": 70000 + index * 100,
                "quantity": 1,
            }
            for index in range(1, 13)
        ]

        self.ai_review_v2.build_basic_ai_review(trades, target_trade_id=12)
        self.ai_review_v2.build_advanced_ai_review(trades, target_trade_id=12)

        basic_episode = captured["basic"]["trade_episode"]
        self.assertEqual(6, len(basic_episode))
        self.assertEqual({"000660"}, {trade["ticker"] for trade in basic_episode})
        self.assertEqual(list(range(2, 13, 2)), [trade["id"] for trade in basic_episode])

        advanced_history = captured["advanced"]["recent_trades"]
        self.assertEqual(6, len(advanced_history))
        self.assertEqual({"000660"}, {trade["ticker"] for trade in advanced_history})
        self.assertEqual(list(range(2, 13, 2)), [trade["id"] for trade in advanced_history])
        self.assertEqual(12, captured["advanced"]["target_trade"]["id"])

    def test_advanced_review_targets_only_the_selected_round_trip(self):
        captured = {}

        def fake_call(payload, *, model, instructions):
            captured.update(payload)
            return "ok"

        self.enterContext(patch.object(self.ai_review_v2, "_contexts_for_trades", lambda trades: []))
        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda trades: {}))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))
        trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "017900", "name": "Gwangjeonja", "side": "buy", "price": 7000, "quantity": 10},
            {"id": 2, "trade_date": "2026-07-10T09:40", "ticker": "017900", "name": "Gwangjeonja", "side": "sell", "price": 7100, "quantity": 10},
            {"id": 3, "trade_date": "2026-07-16T09:06", "ticker": "004310", "name": "Hyundai Pharm", "side": "buy", "price": 7250, "quantity": 69},
            {"id": 4, "trade_date": "2026-07-16T09:10", "ticker": "004310", "name": "Hyundai Pharm", "side": "sell", "price": 7430, "quantity": 69},
        ]

        self.ai_review_v2.build_advanced_ai_review(trades, target_trade_id=2)

        self.assertEqual([1, 2], [trade["id"] for trade in captured["recent_trades"]])
        self.assertEqual({"017900"}, {trade["ticker"] for trade in captured["recent_trades"]})
        self.assertEqual(2, captured["target_trade"]["id"])

    def test_basic_review_anchors_verdict_and_changes_only_analysis_focus(self):
        captured = {}
        trades = [
            {
                "id": 1,
                "trade_date": "2026-07-10T09:30",
                "ticker": "087010",
                "name": "Sample",
                "side": "buy",
                "price": 10000,
                "quantity": 10,
            },
            {
                "id": 2,
                "trade_date": "2026-07-10T09:40",
                "ticker": "087010",
                "name": "Sample",
                "side": "sell",
                "price": 10500,
                "quantity": 10,
            },
        ]
        snapshot = {
            "ticker": "087010",
            "rule_based_observations": [
                {
                    "trade_id": 1,
                    "title": "entry grade",
                    "detail": "entry evidence",
                    "metrics": {"after_5_bars": 1.25, "price_vs_close_pct": -0.2},
                },
                {
                    "trade_id": 2,
                    "title": "exit grade",
                    "detail": "exit evidence",
                    "metrics": {"after_5_bars": -0.8, "price_vs_close_pct": 0.1},
                },
            ],
        }

        def fake_call(payload, *, model, instructions):
            captured["payload"] = payload
            captured["instructions"] = instructions
            return "ok"

        self.enterContext(patch.object(self.ai_review_v2, "_compact_chart_snapshot", lambda rows: snapshot))
        self.enterContext(patch.object(self.ai_review_v2, "_call_openai_review", fake_call))

        result = self.ai_review_v2.build_basic_ai_review(
            trades,
            target_trade_id=2,
            analysis_focus="exit_timing",
        )

        self.assertEqual("ready", result["status"])
        self.assertEqual("exit_timing", captured["payload"]["analysis_focus"]["key"])
        self.assertEqual("profit", captured["payload"]["evaluation_anchor"]["outcome"]["direction"])
        self.assertEqual(2, len(captured["payload"]["evaluation_anchor"]["execution_evidence"]))
        self.assertIn("<consistency_rules>", captured["instructions"])
        self.assertIn("<quality_rules>", captured["instructions"])


if __name__ == "__main__":
    unittest.main()
