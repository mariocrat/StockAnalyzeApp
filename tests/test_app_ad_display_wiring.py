import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AppAdDisplayWiringTest(unittest.TestCase):
    def test_app_wires_resume_and_chart_detail_ads_through_policy(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        stock_chart = (ROOT / "frontend" / "src" / "components" / "StockChart.jsx").read_text(encoding="utf-8")

        self.assertIn("showResumeAppOpenAd", app)
        self.assertIn("shouldShowResumeAppOpenAd", app)
        self.assertIn("document.addEventListener('visibilitychange'", app)
        self.assertIn("showChartDetailInterstitial", app)
        self.assertIn("shouldShowChartDetailInterstitial", app)
        self.assertIn("onOpenDetailAd={handleChartDetailAd}", app)
        self.assertIn("onOpenDetailAd", stock_chart)
        self.assertIn("showAppBanner", app)
        self.assertIn("removeAppBanner", app)
        self.assertIn("shouldShowBannerAd", app)
        self.assertIn("app-container-mobile-banner", app)

    def test_pro_plan_changes_are_lifted_for_global_ad_suppression(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn("setAdPlan(wallet?.plan === 'pro' ? 'pro' : 'free')", app)
        self.assertIn("onEntitlementsChange={handleEntitlementsChange}", app)
        self.assertIn("onEntitlementsChange", journal)

    def test_non_blocking_ad_failures_are_reported_to_client_events(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        journal = (ROOT / "frontend" / "src" / "components" / "TradingJournal.jsx").read_text(encoding="utf-8")

        self.assertIn("reportClientEvent", app)
        self.assertIn("reportAdClientEvent", app)
        self.assertIn("ad_resume_app_open_failed", app)
        self.assertIn("ad_banner_show_failed", app)
        self.assertIn("ad_banner_remove_failed", app)
        self.assertIn("ad_chart_detail_interstitial_failed", app)
        self.assertIn("review_history_interstitial_failed", journal)


if __name__ == "__main__":
    unittest.main()
