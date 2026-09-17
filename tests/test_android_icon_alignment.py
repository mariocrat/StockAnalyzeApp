from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import tempfile
import unittest
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageMode

# Establish the normal built-in plugin registrations under A1 before cases.
# PNG decoding remains real; no plugin import is deferred into a case snapshot.
Image.preinit()


ROOT = Path(__file__).resolve().parents[1]
MIPMAP_DIRS = ("mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi")


def alpha_bounds(path: Path) -> tuple[int, int, int, int]:
    with closing(Image.open(path)) as source, closing(source.convert("RGBA")) as image:
        box = image.getbbox()
    if box is None:
        raise AssertionError(f"{path} has no visible foreground pixels")
    return box


class AndroidIconAlignmentTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir)
        self.addCleanup(self._assert_case_restored, baseline)
        fixture = self.enterContext(storage_fixture())
        self.case_container = fixture.root.parent
        self.icon_root = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"
        self.splash_paths = tuple(sorted(self.icon_root.glob("drawable*/splash.png")))

        names = ("ID", "OPEN", "MIME", "SAVE", "SAVE_ALL", "EXTENSION", "DECODERS", "ENCODERS")
        registries = {name: (getattr(Image, name), getattr(Image, name).copy()) for name in names}
        initialized = Image._initialized
        getmode = ImageMode.getmode
        cache_info = getmode.cache_info()
        self.addCleanup(self._assert_pillow_restored, registries, initialized, getmode, cache_info)
        for name, (_, contents) in registries.items():
            self.enterContext(patch.object(Image, name, contents.copy()))
        self.enterContext(patch.object(Image, "_initialized", initialized))
        # Preserve the original cache (including hits/misses); use the same real
        # mode calculation behind a fresh, testcase-owned cache.
        self.enterContext(patch.object(ImageMode, "getmode", lru_cache()(getmode.__wrapped__)))
        self.images = []
        self.addCleanup(self._assert_images_closed)

    def _rgba(self, path):
        with closing(Image.open(path)) as source:
            image = source.convert("RGBA")
        self.images.append(image)
        self.addCleanup(image.close)
        return image

    def _assert_images_closed(self):
        for image in self.images:
            with self.assertRaises(ValueError):
                image.getbbox()
        self.images.clear()

    def _assert_pillow_restored(self, registries, initialized, getmode, cache_info):
        for name, (original, contents) in registries.items():
            self.assertIs(getattr(Image, name), original)
            self.assertEqual(getattr(Image, name), contents)
        self.assertEqual(Image._initialized, initialized)
        self.assertIs(ImageMode.getmode, getmode)
        self.assertEqual(getmode.cache_info(), cache_info)

    def _assert_case_restored(self, baseline):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir), baseline)
        if hasattr(self, "case_container"):
            self.assertFalse(self.case_container.exists())
        for name in ("case_container", "icon_root", "splash_paths"):
            self.__dict__.pop(name, None)

    def test_launcher_foreground_art_is_centered_in_canvas(self):
        for directory in MIPMAP_DIRS:
            path = self.icon_root / directory / "ic_launcher_foreground.png"
            with self.subTest(path=str(path.relative_to(ROOT))):
                image = self._rgba(path)
                left, top, right, bottom = alpha_bounds(path)
                content_center_x = (left + right - 1) / 2
                content_center_y = (top + bottom - 1) / 2
                canvas_center_x = (image.width - 1) / 2
                canvas_center_y = (image.height - 1) / 2

                self.assertLessEqual(abs(content_center_x - canvas_center_x), 2)
                self.assertLessEqual(abs(content_center_y - canvas_center_y), 2)

    def test_native_splash_images_have_an_opaque_light_background(self):
        self.assertEqual(len(self.splash_paths), 11)
        for path in self.splash_paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                image = self._rgba(path)
                with closing(image.getchannel("A")) as alpha:
                    self.assertEqual(alpha.getextrema(), (255, 255))
                self.assertEqual(image.getpixel((0, 0)), (248, 250, 252, 255))

    def test_adaptive_icon_uses_a_light_background_for_the_dark_foreground(self):
        background = (self.icon_root / "values" / "ic_launcher_background.xml").read_text(encoding="utf-8")
        self.assertIn("#F8FAFC", background)

        foreground = self._rgba(self.icon_root / "mipmap-mdpi" / "ic_launcher_foreground.png")
        visible = [pixel for pixel in foreground.get_flattened_data() if pixel[3] >= 240]
        self.assertTrue(any(red < 20 and green < 80 and blue < 150 for red, green, blue, _ in visible))
        self.assertTrue(any(blue > 200 and blue > red * 1.5 for red, green, blue, _ in visible))


if __name__ == "__main__":
    unittest.main()
