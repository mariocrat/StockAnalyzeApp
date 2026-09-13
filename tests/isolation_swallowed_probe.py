"""Deliberately swallowed import-time violation; only run as a negative child."""
from pathlib import Path
import unittest
from tests.module_isolation import current_boundary, IsolationViolation

try:
    (current_boundary().root.parent / "synthetic-swallowed").write_text("forbidden")
except IsolationViolation:
    pass


class SwallowedProbe(unittest.TestCase):
    def test_application_reports_success(self):
        self.assertTrue(True)
