import os
import sys
import unittest


BACKEND_DIR = os.path.join(os.getcwd(), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.ai_review_v2 import _fallback_basic_text, _trade_episode


class AiReviewQualityTest(unittest.TestCase):
    def test_basic_episode_keeps_buy_and_sell_for_target_symbol(self):
        trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "087010", "name": "펩트론", "side": "buy", "price": 116900, "quantity": 10},
            {"id": 2, "trade_date": "2026-07-10T09:34", "ticker": "087010", "name": "펩트론", "side": "sell", "price": 115400, "quantity": 10},
            {"id": 3, "trade_date": "2026-07-10T10:00", "ticker": "005930", "name": "삼성전자", "side": "buy", "price": 70000, "quantity": 1},
        ]

        episode = _trade_episode(trades, trades[1])

        self.assertEqual(["buy", "sell"], [trade["side"] for trade in episode])

    def test_fallback_uses_actual_prices_and_does_not_praise_recording(self):
        trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "087010", "name": "펩트론", "side": "buy", "price": 116900, "quantity": 10},
            {"id": 2, "trade_date": "2026-07-10T09:34", "ticker": "087010", "name": "펩트론", "side": "sell", "price": 115400, "quantity": 10},
        ]

        text = _fallback_basic_text(trades, {"rule_based_observations": []})

        self.assertIn("116,900원", text)
        self.assertIn("115,400원", text)
        self.assertNotIn("복기 가능한 상태", text)
        self.assertNotIn("매매 이유를 함께 점검", text)

    def test_fallback_checklist_uses_trade_specific_chart_metrics(self):
        trades = [
            {"id": 1, "trade_date": "2026-07-10T09:30", "ticker": "087010", "name": "Sample", "side": "buy", "price": 116900, "quantity": 10},
            {"id": 2, "trade_date": "2026-07-10T09:34", "ticker": "087010", "name": "Sample", "side": "sell", "price": 115400, "quantity": 10},
        ]
        first_snapshot = {
            "rule_based_observations": [
                {"trade_id": 1, "detail": "entry evidence", "metrics": {"after_5_bars": -2.5}},
                {"trade_id": 2, "detail": "exit evidence", "metrics": {"after_5_bars": 1.8}},
            ],
        }
        second_snapshot = {
            "rule_based_observations": [
                {"trade_id": 1, "detail": "entry evidence", "metrics": {"after_5_bars": 3.25}},
                {"trade_id": 2, "detail": "exit evidence", "metrics": {"after_5_bars": -0.75}},
            ],
        }

        first = _fallback_basic_text(trades, first_snapshot)
        second = _fallback_basic_text(trades, second_snapshot)

        self.assertIn("-2.50%", first)
        self.assertIn("+1.80%", first)
        self.assertIn("+3.25%", second)
        self.assertIn("-0.75%", second)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
