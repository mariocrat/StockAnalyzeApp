import os
import sys
import importlib
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException


@contextmanager
def patched_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AdminEventRoutesTest(unittest.TestCase):
    def setUp(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

    def test_admin_operational_events_route_is_registered(self):
        import main

        openapi = main.app.openapi()
        paths = set(openapi["paths"].keys())
        event_route = openapi["paths"]["/api/admin/operational-events"]["get"]
        parameter_names = {param["name"] for param in event_route["parameters"]}

        self.assertIn("/api/admin/operational-events", paths)
        self.assertIn("/api/admin/operational-events/summary", paths)
        self.assertIn("/api/admin/operational-events/retention", paths)
        self.assertIn("/api/admin/theme-cache/status", paths)
        self.assertIn("/api/admin/theme-cache/refresh", paths)
        self.assertIn("request_id", parameter_names)
        self.assertIn("user_id", parameter_names)
        self.assertIn("path", parameter_names)
        self.assertIn("status_code", parameter_names)
        self.assertIn("event_id", parameter_names)
        self.assertIn("created_after", parameter_names)
        self.assertIn("created_before", parameter_names)
        self.assertIn("offset", parameter_names)

        summary_route = openapi["paths"]["/api/admin/operational-events/summary"]["get"]
        summary_parameter_names = {param["name"] for param in summary_route["parameters"]}
        self.assertIn("offset", summary_parameter_names)
        self.assertIn("request_id", summary_parameter_names)
        self.assertIn("user_id", summary_parameter_names)
        self.assertIn("path", summary_parameter_names)
        self.assertIn("status_code", summary_parameter_names)
        self.assertIn("event_id", summary_parameter_names)
        self.assertIn("created_after", summary_parameter_names)
        self.assertIn("created_before", summary_parameter_names)

    def test_admin_purchase_credit_order_routes_are_registered(self):
        import main

        paths = set(main.app.openapi()["paths"].keys())
        self.assertIn("/api/admin/purchase-credit-orders/{order_id}", paths)
        self.assertIn("/api/admin/purchase-credit-orders/{order_id}/sync", paths)
        self.assertIn("/api/admin/purchase-credit-orders/reconcile-voided", paths)
        self.assertIn("/api/admin/purchase-credit-orders/{order_id}/lock", paths)
        self.assertIn("/api/admin/purchase-credit-orders/{order_id}/remaining", paths)

    def test_admin_can_query_and_sync_purchase_credit_order(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ALPHAMATE_ADMIN_TOKEN="admin-secret",
        ):
            import main
            from core import access_control
            from core.rate_limit import InMemoryRateLimiter

            access_control = importlib.reload(access_control)
            main._admin_rate_limiter = InMemoryRateLimiter()
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="basic_review_15",
            )
            conn = access_control._connect_access_db()
            try:
                order_id = conn.execute("SELECT order_id FROM purchase_credit_orders").fetchone()[0]
            finally:
                conn.close()

            request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
            with self.assertRaises(HTTPException) as missing:
                main.get_admin_purchase_credit_order(request, order_id, authorization=None)
            self.assertEqual(401, missing.exception.status_code)

            main._admin_rate_limiter = InMemoryRateLimiter()
            order = main.get_admin_purchase_credit_order(
                request,
                order_id,
                authorization="Bearer admin-secret",
            )
            self.assertEqual(order_id, order["order_id"])
            self.assertEqual(15, order["granted_quantity"])
            self.assertEqual(15, order["remaining_quantity"])
            self.assertNotIn("purchase_token_ciphertext", order)
            self.assertNotIn("purchase_token_hash", order)

            main._admin_rate_limiter = InMemoryRateLimiter()
            with patch.object(main, "sync_google_play_purchase_order_status", return_value={"status": "ignored"}) as sync:
                result = main.sync_admin_purchase_credit_order(
                    request,
                    order_id,
                    event_key="admin-sync-event-1",
                    authorization="Bearer admin-secret",
                )
            self.assertEqual({"status": "ignored"}, result)
            sync.assert_called_once_with(order_id=order_id, event_key="admin-sync-event-1")

    def test_admin_can_lock_unlock_and_adjust_purchase_credit_order(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ENV="development",
            ALPHAMATE_ACCESS_DB_PATH=os.path.join(tmpdir, "access.sqlite3"),
            ALPHAMATE_ALLOW_DEV_ACCESS="true",
            ALPHAMATE_ADMIN_TOKEN="admin-secret",
        ):
            import main
            from core import access_control
            from core.rate_limit import InMemoryRateLimiter

            access_control = importlib.reload(access_control)
            access_control.apply_dev_purchase(
                authorization="Bearer dev-token",
                entitlement_token="",
                product_id="advanced_review_10",
            )
            conn = access_control._connect_access_db()
            try:
                order_id = conn.execute("SELECT order_id FROM purchase_credit_orders").fetchone()[0]
            finally:
                conn.close()

            request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
            main._admin_rate_limiter = InMemoryRateLimiter()
            locked = main.set_admin_purchase_credit_order_lock(
                request,
                order_id,
                locked=True,
                event_key="admin-lock-1",
                authorization="Bearer admin-secret",
            )
            while_locked = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            main._admin_rate_limiter = InMemoryRateLimiter()
            repeated = main.set_admin_purchase_credit_order_lock(
                request,
                order_id,
                locked=True,
                event_key="admin-lock-1",
                authorization="Bearer admin-secret",
            )
            main._admin_rate_limiter = InMemoryRateLimiter()
            unlocked = main.set_admin_purchase_credit_order_lock(
                request,
                order_id,
                locked=False,
                event_key="admin-unlock-1",
                authorization="Bearer admin-secret",
            )
            after_unlock = access_control.get_user_entitlements(
                authorization="Bearer dev-token",
                entitlement_token="",
            )
            main._admin_rate_limiter = InMemoryRateLimiter()
            adjusted = main.adjust_admin_purchase_credit_order_remaining(
                request,
                order_id,
                remaining_quantity=4,
                event_key="admin-adjust-1",
                authorization="Bearer admin-secret",
            )

            self.assertEqual("updated", locked["status"])
            self.assertEqual(1, locked["order"]["balance_locked"])
            self.assertEqual(0, while_locked["advanced"]["purchased_remaining"])
            self.assertEqual("already_processed", repeated["status"])
            self.assertEqual(0, unlocked["order"]["balance_locked"])
            self.assertEqual(10, after_unlock["advanced"]["purchased_remaining"])
            self.assertEqual(4, adjusted["order"]["remaining_quantity"])

            main._admin_rate_limiter = InMemoryRateLimiter()
            with self.assertRaises(HTTPException) as invalid:
                main.adjust_admin_purchase_credit_order_remaining(
                    request,
                    order_id,
                    remaining_quantity=11,
                    event_key="admin-adjust-invalid",
                    authorization="Bearer admin-secret",
                )
            self.assertEqual(400, invalid.exception.status_code)

            conn = access_control._connect_access_db()
            try:
                conn.execute(
                    "UPDATE purchase_credit_orders "
                    "SET remaining_quantity = 0, balance_locked = 1, order_status = 'REFUNDED', refund_status = 'refunded' "
                    "WHERE order_id = ?",
                    (order_id,),
                )
                conn.commit()
            finally:
                conn.close()
            main._admin_rate_limiter = InMemoryRateLimiter()
            with self.assertRaises(HTTPException) as terminal:
                main.adjust_admin_purchase_credit_order_remaining(
                    request,
                    order_id,
                    remaining_quantity=1,
                    event_key="admin-adjust-refunded",
                    authorization="Bearer admin-secret",
                )
            self.assertEqual(409, terminal.exception.status_code)

    def test_admin_event_route_requires_admin_token(self):
        with patched_env(ALPHAMATE_ADMIN_TOKEN="admin-secret"):
            import main

            with self.assertRaises(HTTPException) as missing:
                main._require_admin_token(None)
            self.assertEqual(401, missing.exception.status_code)

            with self.assertRaises(HTTPException) as wrong:
                main._require_admin_token("Bearer wrong")
            self.assertEqual(403, wrong.exception.status_code)

            self.assertTrue(main._require_admin_token("Bearer admin-secret"))

    def test_admin_event_route_rejects_short_admin_token_in_production(self):
        with patched_env(ALPHAMATE_ENV="production", ALPHAMATE_ADMIN_TOKEN="short-admin-token"):
            import main

            with self.assertRaises(HTTPException) as blocked:
                main._require_admin_token("Bearer short-admin-token")

            self.assertEqual(503, blocked.exception.status_code)
            self.assertIn("Admin token", blocked.exception.detail)

    def test_admin_rate_limit_rejects_excessive_requests(self):
        with patched_env(ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._admin_rate_limiter = InMemoryRateLimiter()

            self.assertTrue(main._enforce_admin_rate_limit("client-a"))
            self.assertTrue(main._enforce_admin_rate_limit("client-a"))
            with self.assertRaises(HTTPException) as blocked:
                main._enforce_admin_rate_limit("client-a")
            self.assertEqual(429, blocked.exception.status_code)

    def test_admin_and_client_event_rate_limits_have_upper_bounds(self):
        with patched_env(
            ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE="999999",
            ALPHAMATE_CLIENT_EVENT_RATE_LIMIT_PER_MINUTE="999999",
            ALPHAMATE_CALLBACK_RATE_LIMIT_PER_MINUTE="999999",
        ):
            import main

            self.assertEqual(300, main._admin_rate_limit())
            self.assertEqual(600, main._client_event_rate_limit())
            self.assertEqual(300, main._callback_rate_limit())

    def test_external_callback_rate_limit_rejects_excessive_requests(self):
        with patched_env(ALPHAMATE_CALLBACK_RATE_LIMIT_PER_MINUTE="2"):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._callback_rate_limiter = InMemoryRateLimiter()

            self.assertTrue(main._enforce_callback_rate_limit("admob-ssv", "client-a"))
            self.assertTrue(main._enforce_callback_rate_limit("admob-ssv", "client-a"))
            with self.assertRaises(HTTPException) as blocked:
                main._enforce_callback_rate_limit("admob-ssv", "client-a")

            self.assertEqual(429, blocked.exception.status_code)
            self.assertIn("Retry-After", blocked.exception.headers)

    def test_admin_operational_events_reports_effective_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ADMIN_TOKEN="admin-secret",
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._admin_rate_limiter = InMemoryRateLimiter()
            main.record_event(level="warning", event_type="test_event", path="/api/test")

            response = main.get_admin_operational_events(
                SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1")),
                authorization="Bearer admin-secret",
                limit=999999,
                offset=-10,
            )

            self.assertEqual(1000, response["limit"])
            self.assertEqual(0, response["offset"])
            self.assertEqual(1, response["count"])

    def test_admin_theme_cache_status_is_token_protected(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_ADMIN_TOKEN="admin-secret",
            ALPHAMATE_CACHE_DIR=tmpdir,
        ):
            import main
            from core.rate_limit import InMemoryRateLimiter

            main._admin_rate_limiter = InMemoryRateLimiter()
            request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))

            with self.assertRaises(HTTPException) as missing:
                main.get_admin_theme_cache_status(request, authorization=None)
            self.assertEqual(401, missing.exception.status_code)

            main._admin_rate_limiter = InMemoryRateLimiter()
            response = main.get_admin_theme_cache_status(request, authorization="Bearer admin-secret")
            self.assertFalse(response["refreshing"])
            self.assertEqual({"1D", "1W", "1M", "1Y"}, set(response["periods"]))
            self.assertTrue(all(not row["ready"] for row in response["periods"].values()))


if __name__ == "__main__":
    unittest.main()
