from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageMode, ImageChops

# Establish the normal built-in plugin registrations under A1 before cases.
# PNG decoding remains real; no plugin import is deferred into a case snapshot.
Image.preinit()


ROOT = Path(__file__).resolve().parents[1]
BRAND_ROOT = ROOT / "frontend" / "src" / "assets" / "brand"


class FaviconAssetTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir)
        self.addCleanup(self._assert_case_restored, baseline)
        fixture = self.enterContext(storage_fixture())
        self.case_container = fixture.root.parent

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

    def _own(self, image):
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
        for name in ("case_container",):
            self.__dict__.pop(name, None)

    def test_favicon_uses_the_official_light_app_icon_pixels(self):
        source = self._own(Image.open(ROOT / "frontend" / "public" / "favicon.png"))
        actual = self._own(source.convert("RGBA"))
        icon_source = self._own(Image.open(BRAND_ROOT / "stockboda-app-icon-light.png"))
        icon = self._own(icon_source.convert("RGBA"))
        expected = self._own(icon.resize((48, 48), Image.Resampling.LANCZOS))
        self.assertIsNone(self._own(ImageChops.difference(actual, expected)).getbbox())
        self.assertFalse((ROOT / "frontend" / "public" / "favicon.svg").exists())


if __name__ == "__main__":
    unittest.main()
