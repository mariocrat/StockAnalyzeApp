"""OUT admin-source (1); C and D moved to dedicated source-check modules."""

import os
import sys
import tempfile
import unittest
import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


class MobileRuntimeSourceChecksTest(unittest.TestCase):
    def test_admin_can_trigger_and_inspect_initial_theme_cache(self):
        source = (BACKEND / "main.py").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/admin/theme-cache/status")', source)
        self.assertIn('@app.post("/api/admin/theme-cache/refresh")', source)
        self.assertIn("_require_admin_token(authorization)", source)
        self.assertIn("_theme_cache_status_payload", source)


if __name__ == "__main__":
    unittest.main()
