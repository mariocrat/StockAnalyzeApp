import unittest
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
BRAND_ROOT = ROOT / "frontend" / "src" / "assets" / "brand"
STORE_ROOT = ROOT / "store-assets" / "google-play" / "ko-KR"


def expected_store_app_screen(source_path: Path) -> Image.Image:
    source = Image.open(source_path).convert("RGB")
    crop_right = max(1, source.width - (7 if source.width <= 600 else 10))
    target_height = min(source.height, round(crop_right * 16 / 9))
    source = source.crop((0, 0, crop_right, target_height))
    scale = max(900 / source.width, 1600 / source.height)
    resized = source.resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - 900) // 2)
    return resized.crop((left, 0, left + 900, 1600))


def official_asset_on_background(asset_name: str, size: tuple[int, int], background: str) -> Image.Image:
    expected = Image.new("RGB", size, background)
    logo = Image.open(BRAND_ROOT / asset_name).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    expected.paste(logo, (0, 0), logo)
    return expected


class BrandImageAssetsTest(unittest.TestCase):
    def test_play_feature_uses_the_official_wordmark_pixels(self):
        feature = Image.open(STORE_ROOT / "feature-graphic-1024x500.png").convert("RGB")
        actual = feature.crop((344, 81, 644, 181))
        expected = official_asset_on_background("stockboda-wordmark.png", (300, 100), "#F8FAFC")
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_play_screenshot_uses_the_official_horizontal_logo_pixels(self):
        screenshot = Image.open(STORE_ROOT / "screenshots" / "01-theme-ranking-1080x1920.png").convert("RGB")
        actual = screenshot.crop((81, 34, 297, 106))
        expected = official_asset_on_background("stockboda-logo-horizontal.png", (216, 72), "#F8FAFC")
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_play_icon_matches_the_dedicated_console_source(self):
        actual = Image.open(STORE_ROOT / "icon-512.png").convert("RGBA")
        expected = Image.open(ROOT / "stockboda-play-icon-512.png").convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_raw_screenshots_are_native_play_resolution(self):
        for name in (
            "01-theme-ranking.png",
            "02-theme-stocks.png",
            "03-chart-detail.png",
            "04-journal-input.png",
            "05-ai-review-source.png",
        ):
            with self.subTest(name=name):
                source = Image.open(STORE_ROOT / "raw" / name).convert("RGB")
                self.assertGreaterEqual(source.width, 1080)
                self.assertGreaterEqual(source.height, 1920)

    def test_generated_screenshots_match_their_raw_sources(self):
        pairs = (
            ("01-theme-ranking.png", "01-theme-ranking-1080x1920.png"),
            ("02-theme-stocks.png", "02-theme-stocks-1080x1920.png"),
            ("03-chart-detail.png", "03-chart-detail-1080x1920.png"),
            ("04-journal-input.png", "04-journal-input-1080x1920.png"),
            ("05-ai-review-source.png", "05-ai-review-1080x1920.png"),
        )
        for raw_name, output_name in pairs:
            with self.subTest(output=output_name):
                expected = expected_store_app_screen(STORE_ROOT / "raw" / raw_name).crop((30, 30, 870, 1570))
                actual = Image.open(STORE_ROOT / "screenshots" / output_name).convert("RGB").crop((120, 330, 960, 1870))
                self.assertIsNone(ImageChops.difference(actual, expected).getbbox())

    def test_capture_guide_describes_the_approved_mobile_workflow(self):
        guide = (STORE_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("실제 Android 기기", guide)
        self.assertIn("CSS viewport 390×844, DPR 3", guide)
        self.assertIn("원본 비율을 유지한 crop/resize", guide)

    def test_favicon_uses_the_official_light_app_icon_pixels(self):
        actual = Image.open(ROOT / "frontend" / "public" / "favicon.png").convert("RGBA")
        expected = Image.open(BRAND_ROOT / "stockboda-app-icon-light.png").convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
        self.assertFalse((ROOT / "frontend" / "public" / "favicon.svg").exists())


if __name__ == "__main__":
    unittest.main()
