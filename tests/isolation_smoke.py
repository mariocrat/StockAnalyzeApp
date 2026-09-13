"""Small pre-suite import smoke; this target must never be imported by the parent."""
from tests.module_isolation import current_boundary

BOUNDARY = current_boundary()  # Guard already active before any target dependency import.
import pathlib
import contextlib
import requests
import unittest


class ImportSmoke(unittest.TestCase):
    def test_runtime_and_dependency_reads_under_guard(self):
        for module in (pathlib, contextlib, requests):
            self.assertTrue(pathlib.Path(module.__file__).read_bytes())
        self.assertEqual(BOUNDARY.unexpected, 0, BOUNDARY.violations)
        # Report whether this machine actually exercised the historical Codex runtime location.
        runtime = pathlib.Path(contextlib.__file__)
        print("codex runtime read exercised:", "codex-runtimes" in runtime.parts)
