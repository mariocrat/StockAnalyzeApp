"""Deferred D Render (1), OUT admin-source (1); C moved to test_mobile_source_checks."""

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
    def test_render_uses_persistent_cache_and_bounded_workers(self):
        blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("ALPHAMATE_CACHE_DIR", blueprint)
        self.assertIn("/var/data/alphamate/cache", blueprint)
        self.assertIn("ALPHAMATE_THEME_FETCH_WORKERS", blueprint)
        self.assertIn("ALPHAMATE_WARM_CACHE_ON_STARTUP", blueprint)

    def test_admin_can_trigger_and_inspect_initial_theme_cache(self):
        source = (BACKEND / "main.py").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/admin/theme-cache/status")', source)
        self.assertIn('@app.post("/api/admin/theme-cache/refresh")', source)
        self.assertIn("_require_admin_token(authorization)", source)
        self.assertIn("_theme_cache_status_payload", source)


if __name__ == "__main__":
    unittest.main()
