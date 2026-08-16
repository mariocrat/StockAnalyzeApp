import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON_ROOT = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"
MIPMAP_DIRS = ["mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi"]
SPLASH_PATHS = sorted(ICON_ROOT.glob("drawable*/splash.png"))


def alpha_bounds(path: Path) -> tuple[int, int, int, int]:
    image = Image.open(path).convert("RGBA")
    box = image.getbbox()
    if box is None:
        raise AssertionError(f"{path} has no visible foreground pixels")
    return box


class AndroidIconAlignmentTest(unittest.TestCase):
    def test_launcher_foreground_art_is_centered_in_canvas(self):
        for directory in MIPMAP_DIRS:
            path = ICON_ROOT / directory / "ic_launcher_foreground.png"
            with self.subTest(path=str(path.relative_to(ROOT))):
                image = Image.open(path).convert("RGBA")
                left, top, right, bottom = alpha_bounds(path)
                content_center_x = (left + right - 1) / 2
                content_center_y = (top + bottom - 1) / 2
                canvas_center_x = (image.width - 1) / 2
                canvas_center_y = (image.height - 1) / 2

                self.assertLessEqual(abs(content_center_x - canvas_center_x), 2)
                self.assertLessEqual(abs(content_center_y - canvas_center_y), 2)

    def test_native_splash_images_have_an_opaque_light_background(self):
        self.assertEqual(len(SPLASH_PATHS), 11)
        for path in SPLASH_PATHS:
            with self.subTest(path=str(path.relative_to(ROOT))):
                image = Image.open(path).convert("RGBA")
                self.assertEqual(image.getchannel("A").getextrema(), (255, 255))
                self.assertEqual(image.getpixel((0, 0)), (248, 250, 252, 255))

    def test_adaptive_icon_uses_a_light_background_for_the_dark_foreground(self):
        background = (ICON_ROOT / "values" / "ic_launcher_background.xml").read_text(encoding="utf-8")
        self.assertIn("#F8FAFC", background)

        foreground = Image.open(ICON_ROOT / "mipmap-mdpi" / "ic_launcher_foreground.png").convert("RGBA")
        visible = [pixel for pixel in foreground.get_flattened_data() if pixel[3] >= 240]
        self.assertTrue(any(red < 20 and green < 80 and blue < 150 for red, green, blue, _ in visible))
        self.assertTrue(any(blue > 200 and blue > red * 1.5 for red, green, blue, _ in visible))


if __name__ == "__main__":
    unittest.main()
