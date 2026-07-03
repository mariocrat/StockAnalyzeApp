import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AppAdDisplayWiringTest(unittest.TestCase):
    def test_app_wires_resume_and_chart_detail_ads_through_policy(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        stock_chart = (ROOT / "frontend" / "src" / "components" / "StockChart.jsx").read_text(encoding="utf-8")

        self.assertIn("showResumeInterstitial", app)
        self.assertIn("shouldShowResumeInterstitial", app)
        self.assertIn("document.addEventListener('visibilitychange'", app)
        self.assertIn("showChartDetailInterstitial", app)
        self.assertIn("shouldShowChartDetailInterstitial", app)
        self.assertIn("onOpenDetailAd={handleChartDetailAd}", app)
        self.assertIn("onOpenDetailAd", stock_chart)

    def test_pro_plan_changes_are_lifted_for_global_ad_suppression(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn("setAdPlan(wallet?.plan === 'pro' ? 'pro' : 'free')", app)
        self.assertIn("onEntitlementsChange={handleEntitlementsChange}", app)
        self.assertIn("onEntitlementsChange", journal)


if __name__ == "__main__":
    unittest.main()
