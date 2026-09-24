"""H4-D mobile Render source contract; C and OUT remain separate."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MobileRuntimeSourceChecksTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
        modules = dict(sys.modules)
        namespace = dict(vars(sys.modules[__name__]))
        self.addCleanup(self._assert_restored, baseline, modules, namespace)
        fixture = self.enterContext(storage_fixture())
        self._case_container = fixture.root.parent

    def _assert_restored(self, baseline, modules, namespace):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path)), baseline)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is module for name, module in modules.items()))
        current = vars(sys.modules[__name__])
        self.assertEqual(set(current), set(namespace))
        self.assertTrue(all(current[name] is value for name, value in namespace.items()))
        container = self.__dict__.pop("_case_container", None)
        if container is not None:
            self.assertFalse(container.exists())

    def test_render_uses_persistent_cache_and_bounded_workers(self):
        blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("ALPHAMATE_CACHE_DIR", blueprint)
        self.assertIn("/var/data/alphamate/cache", blueprint)
        self.assertIn("ALPHAMATE_THEME_FETCH_WORKERS", blueprint)
        self.assertIn("ALPHAMATE_WARM_CACHE_ON_STARTUP", blueprint)


if __name__ == "__main__":
    unittest.main()
