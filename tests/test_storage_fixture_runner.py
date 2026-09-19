"""Coordinator checks; never import the storage target modules here."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.module_isolation import sanitized_environment
from tests.run_isolated_tests import REPOSITORY, run_module


STORAGE_MODULES = (
    "tests.test_quick_verify_docs",
    "tests.test_owner_facing_messages",
    "tests.test_policy_documentation",
    "tests.test_render_blueprint",
    "tests.test_secret_scan_output",
    "tests.test_mobile_render_source_checks",
    "tests.test_android_release_verification",
    "tests.test_backend_release_check_docs",
    "tests.test_release_env_file_setup_docs",
    "tests.test_release_secret_generation_docs",
    "tests.test_batch_wrappers",
    "tests.test_private_release_setup",
    "tests.test_android_upload_key_generation",
    "tests.test_favicon_asset",
    "tests.test_android_signing_checks",
    "tests.test_mobile_source_checks",
    "tests.test_app_ad_display_wiring",
    "tests.test_app_splash_ui",
    "tests.test_android_icon_alignment",
    "tests.test_account_store",
    "tests.test_access_control_persistence",
    "tests.test_user_journal_storage",
    "tests.test_review_history",
    "tests.test_event_log",
    "tests.test_me_data_routes",
    "tests.test_admin_event_routes",
    "tests.test_billing_rate_limits",
    "tests.test_request_id",
    "tests.test_market_rate_limits",
    "tests.test_auth_routes",
    "tests.test_auth_lifespan",
    "tests.test_journal_batch_limits",
    "tests.test_journal_query_limits",
    "tests.test_main_ai_review_history_consent",
    "tests.test_journal_chart_details",
    "tests.test_ai_review_quality",
    "tests.test_stock_chart_corporate_actions",
    "tests.test_review_access",
    "tests.test_review_access_concurrency",
    "tests.test_production_dev_guards",
    "tests.test_cors_config",
    "tests.test_privacy_policy",
    "tests.test_ai_review_openai_client",
    "tests.test_ai_review_openai_transport",
    "tests.test_oauth_login",
    "tests.test_oauth_login_transport",
    "tests.test_theme_cache_memory",
    "tests.test_theme_cache_workers",
    "tests.test_mobile_runtime_recovery",
    "tests.test_ai_review_safety",
    "tests.test_ai_review_chart_provider",
    "tests.test_ai_review_safety_finalization",
    "tests.test_billing_readiness",
    "tests.test_billing_purchase_transport",
    "tests.test_billing_subscription_transport",
    "tests.test_billing_provider_verification",
    "tests.test_backend_release_check",
    "tests.test_release_alignment",
    "tests.test_release_env_file_setup",
    "tests.test_release_secret_generation",
)


class StorageFixtureRunnerTest(unittest.TestCase):
    def test_direct_import_fails_before_storage_dependencies_or_files(self):
        # Forged test env alone must not substitute for the actual A1 boundary.
        with tempfile.TemporaryDirectory(prefix="storage-direct-probe-") as directory:
            container = Path(directory).resolve()
            root = container / "runtime"
            env = sanitized_environment(os.environ, root)
            for module in STORAGE_MODULES:
                with self.subTest(module=module):
                    code = f'''
import importlib, sys
sys.path.insert(0, {str(REPOSITORY)!r})
try:
    importlib.import_module({module!r})
except RuntimeError as error:
    assert str(error) == "isolation is not installed"
else:
    raise AssertionError("unguarded module import succeeded")
assert not any(name in sys.modules for name in (
    "backend.core.account_store", "backend.core.access_control",
    "backend.core.journal", "backend.core.review_history", "backend.core.event_log",
    "main", "backend.main"))
'''
                    result = subprocess.run([sys.executable, "-I", "-B", "-c", code],
                                            cwd=container, env=env, capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual([], list(container.iterdir()))
        self.assertFalse(container.exists())

    def test_focused_fixture_regression_in_sanitized_child(self):
        host = dict(os.environ)
        host["STORAGE_HOST_SENTINEL"] = "synthetic"
        report = run_module("tests.test_storage_fixture", host=host)
        self.assertTrue(report["passed"], report)
        self.assertEqual(4, report["tests"])
        self.assertEqual(0, report["unexpected"])
        self.assertTrue(report["restored"])
        self.assertTrue(report["patches_restored"])
        self.assertTrue(report["cleanup"])
        self.assertFalse(Path(report["root"]).parent.exists())
