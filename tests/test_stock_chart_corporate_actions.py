from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import unittest

import pandas as pd


class StockChartCorporateActionTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())

    def test_chart_keeps_post_consolidation_price_and_adjusts_older_prices(self):
        import main

        source = pd.DataFrame(
            {
                "Open": [180, 1800],
                "High": [182, 1760],
                "Low": [179, 1590],
                "Close": [181, 1726],
                "Volume": [1000, 2000],
            },
            index=pd.to_datetime(["2026-07-16", "2026-07-20"]),
        )
        original = main.get_stock_ohlcv
        try:
            main.get_stock_ohlcv = lambda *_args, **_kwargs: source.copy()
            payload = main.get_stock_data(
                "009730",
                start_date="20260701",
                end_date="20260720",
            )
        finally:
            main.get_stock_ohlcv = original

        rows = payload["data"]
        self.assertEqual(2, len(rows))
        self.assertEqual(1810.0, rows[0]["Close"])
        self.assertEqual(1726.0, rows[1]["Close"])


if __name__ == "__main__":
    unittest.main()
