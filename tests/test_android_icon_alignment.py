import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON_ROOT = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"
MIPMAP_DIRS = ["mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi"]


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


if __name__ == "__main__":
    unittest.main()
