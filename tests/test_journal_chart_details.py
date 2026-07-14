import os
import sys
import unittest


BACKEND_DIR = os.path.join(os.getcwd(), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.journal import build_review
from core.journal_chart import _choose_intraday_interval, _markers_for_trades


class JournalChartDetailsTest(unittest.TestCase):
    def setUp(self):
        self.trades = [
            {
                "id": 1,
                "trade_date": "2026-07-10T09:31",
                "ticker": "087010",
                "name": "펩트론",
                "side": "buy",
                "price": 100,
                "quantity": 10,
                "fee": 1,
                "tax": 0,
            },
            {
                "id": 2,
                "trade_date": "2026-07-10T09:31",
                "ticker": "087010",
                "name": "펩트론",
                "side": "sell",
                "price": 110,
                "quantity": 10,
                "fee": 1,
                "tax": 0,
            },
        ]
        self.candles = [{
            "time": 1000,
            "label": "2026-07-10 09:31",
            "open": 100,
            "high": 112,
            "low": 98,
            "close": 108,
            "volume": 1000,
        }]

    def test_same_candle_keeps_buy_and_sell_markers(self):
        markers = _markers_for_trades(self.trades, self.candles, "intraday")

        self.assertEqual(2, len(markers))
        self.assertEqual({"buy", "sell"}, {marker["side"] for marker in markers})

    def test_sell_marker_includes_realized_profit_and_return(self):
        markers = _markers_for_trades(self.trades, self.candles, "intraday")
        sell = next(marker for marker in markers if marker["side"] == "sell")

        self.assertEqual(98, sell["tooltip"]["profit_amount"])
        self.assertAlmostEqual(9.79, sell["tooltip"]["return_rate"], places=2)

    def test_intraday_interval_matches_holding_time(self):
        self.assertEqual("1m", _choose_intraday_interval(self.trades))
        longer = [dict(self.trades[0]), {**self.trades[1], "trade_date": "2026-07-10T12:31"}]
        self.assertEqual("3m", _choose_intraday_interval(longer))

    def test_symbol_review_includes_dates_and_cost_breakdown(self):
        row = build_review(self.trades)["by_symbol"][0]

        self.assertEqual(2, row["trade_count"])
        self.assertEqual("2026-07-10T09:31", row["first_trade_date"])
        self.assertEqual("2026-07-10T09:31", row["last_trade_date"])
        self.assertEqual(2, row["total_fee"])
        self.assertEqual(0, row["total_tax"])


if __name__ == "__main__":
    unittest.main()
