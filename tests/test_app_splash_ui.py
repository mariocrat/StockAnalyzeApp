import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppSplashUiTest(unittest.TestCase):
    def test_app_renders_centered_pulsing_logo_splash(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        css = (ROOT / "frontend" / "src" / "App.css").read_text(encoding="utf-8")

        self.assertIn("app-icon.png", app)
        self.assertIn("function AppSplash", app)
        self.assertIn("showSplash", app)
        self.assertIn("setShowSplash(false)", app)
        self.assertIn('"app-splash app-splash-exit"', app)
        self.assertIn('"app-splash"', app)

        self.assertIn(".app-splash", css)
        self.assertIn(".app-splash-logo", css)
        self.assertIn("@keyframes app-splash-pulse", css)
        self.assertIn("animation: app-splash-pulse", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_public_app_icon_asset_exists_for_splash(self):
        icon = ROOT / "frontend" / "src" / "assets" / "app-icon.png"

        self.assertTrue(icon.exists())
        self.assertGreater(icon.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
