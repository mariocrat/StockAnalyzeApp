import unittest
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
BRAND_ROOT = ROOT / "frontend" / "src" / "assets" / "brand"
STORE_ROOT = ROOT / "store-assets" / "google-play" / "ko-KR"


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

    def test_generated_app_header_has_an_opaque_light_logo_surface(self):
        source = Image.open(STORE_ROOT / "raw" / "05-ai-review-source.png").convert("RGB")
        actual_surface = source.crop((210, 8, 330, 50))
        self.assertGreater(sum(1 for pixel in actual_surface.get_flattened_data() if min(pixel) >= 240), 2500)

    def test_raw_screenshot_headers_use_the_official_horizontal_logo_pixels(self):
        expected = official_asset_on_background("stockboda-logo-horizontal.png", (102, 34), "#F8FAFC")
        for name in ("01-theme-ranking.png", "02-theme-stocks.png", "04-journal-input.png"):
            with self.subTest(name=name):
                source = Image.open(STORE_ROOT / "raw" / name).convert("RGB")
                self.assertIsNone(ImageChops.difference(source.crop((219, 12, 321, 46)), expected).getbbox())

    def test_favicon_uses_the_official_light_app_icon_pixels(self):
        actual = Image.open(ROOT / "frontend" / "public" / "favicon.png").convert("RGBA")
        expected = Image.open(BRAND_ROOT / "stockboda-app-icon-light.png").convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())


if __name__ == "__main__":
    unittest.main()
