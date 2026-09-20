"""Intentional failing child: catching Phase A denials must not hide them from A1."""

from tests.module_isolation import current_boundary

BOUNDARY = current_boundary()

import sys
import unittest

import requests
from tests.phase_a_isolation import isolated_runtime


class SwallowedPhaseAProbe(unittest.TestCase):
    def test_caught_audit_and_transport_denials_remain_unexpected(self):
        with isolated_runtime():
            operations = (
                lambda: sys.audit("socket.getaddrinfo", "synthetic.invalid", 443, 0, 0, 0),
                lambda: sys.audit("subprocess.Popen", "synthetic-never-launched"),
                lambda: (BOUNDARY.root / "synthetic-phase-outside.txt").write_text("blocked"),
                lambda: requests.get("https://synthetic.invalid"),
            )
            for operation in operations:
                before = len(BOUNDARY.violations)
                try:
                    operation()
                except AssertionError:
                    # Observe the ledger immediately, before either context exits.
                    self.assertEqual(len(BOUNDARY.violations), before + 1)
                else:
                    self.fail("Phase A did not block the synthetic operation")
        self.assertEqual(BOUNDARY.violations, ["network", "subprocess", "write", "network"])
        self.assertEqual(BOUNDARY.unexpected, 4)
        self.assertFalse((BOUNDARY.root / "synthetic-phase-outside.txt").exists())
