from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import importlib
import datetime
import sqlite3
import unittest
from time import perf_counter

from fastapi import HTTPException


class EventLogTest(unittest.TestCase):
    def test_long_user_agent_is_bounded_before_sanitizing_and_boundary_secret_is_redacted(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            boundary_value = (
                "x" * (event_log.MAX_DETAIL_STRING_LENGTH - 100)
                + r' {\"verification_token\":\"SYNTHETIC_BOUNDARY_SECRET_DO_NOT_LOG'
            )
            multiline_value = (
                "x" * (event_log.MAX_DETAIL_STRING_LENGTH - 180)
                + ' private_key="SYNTHETIC_MULTILINE_FIRST\n'
                + "SYNTHETIC_MULTILINE_SECOND"
                + "y" * 300
                + '"'
            )
            started_at = perf_counter()
            event_log.record_event(
                level="warning",
                event_type="not_found",
                method="GET",
                path="/api/missing",
                status_code=404,
                details={
                    "user_agent": "-" * 4_000,
                    "boundary": boundary_value,
                    "multiline_boundary": multiline_value,
                },
            )
            elapsed = perf_counter() - started_at
            row = event_log.list_events(limit=1)[0]

            self.assertLess(elapsed, 0.75)
            self.assertLessEqual(
                len(row["details"]["user_agent"]),
                event_log.MAX_DETAIL_STRING_LENGTH,
            )
            self.assertIn("[truncated]", row["details"]["user_agent"])
            self.assertNotIn("SYNTHETIC_", str(row))
            self.assertIn("[redacted]", row["details"]["boundary"])
            self.assertIn("[redacted]", row["details"]["multiline_boundary"])
            self.assertIn("[truncated]", row["details"]["multiline_boundary"])

    def test_event_log_redacts_credentials_but_preserves_operational_fields(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="error",
                event_type="oauth_callback_failed",
                method="GET",
                path=(
                    "/api/auth/kakao/callback?%63ode=SYNTHETIC_ENCODED_CODE_DO_NOT_LOG"
                    "&%73tate=SYNTHETIC_ENCODED_STATE_DO_NOT_LOG"
                    "&code=SYNTHETIC_DUPLICATE_CODE?part=value#fragment"
                ),
                message=(
                    "callback failed?verification_token=SYNTHETIC_VERIFICATION_TOKEN_DO_NOT_LOG"
                    "&shared_token=SYNTHETIC_SHARED_TOKEN&next=a=b?#fragment "
                    "status-code=401 error-code=DENIED status_code=401 error_code=DENIED"
                ),
                details={
                    "access_token": "SYNTHETIC_ACCESS_TOKEN_DO_NOT_LOG",
                    "refreshToken": "SYNTHETIC_REFRESH_TOKEN_DO_NOT_LOG",
                    "session_token": "SYNTHETIC_SESSION_TOKEN_DO_NOT_LOG",
                    "verification_token": "SYNTHETIC_VERIFICATION_TOKEN_DO_NOT_LOG",
                    "shared_token": "SYNTHETIC_SHARED_TOKEN_DO_NOT_LOG",
                    "X-AlphaMate-RTDN-Token": "SYNTHETIC_RTDN_HEADER_DO_NOT_LOG",
                    "KAKAO_CLIENT_SECRET": "SYNTHETIC_CLIENT_SECRET_DO_NOT_LOG",
                    "authorization": "Bearer SYNTHETIC_AUTHORIZATION_DO_NOT_LOG",
                    "cookie": "session=SYNTHETIC_COOKIE_DO_NOT_LOG",
                    "input_tokens": 123,
                    "output_tokens": 45,
                    "status_code": 401,
                    "error_code": "OAUTH_CALLBACK_FAILED",
                    "status-code": 401,
                    "error-code": "DENIED",
                    "note": (
                        r'payload={\"verification_token\":'
                        r'\"SYNTHETIC_ESCAPED\\\"VALUE&x=y?#fragment\"}'
                    ),
                },
            )

            row = event_log.list_events(limit=1)[0]
            row_text = str(row)

            self.assertNotIn("SYNTHETIC_", row_text)
            self.assertIn("[redacted]", row_text)
            self.assertEqual(123, row["details"]["input_tokens"])
            self.assertEqual(45, row["details"]["output_tokens"])
            self.assertEqual(401, row["details"]["status_code"])
            self.assertEqual("OAUTH_CALLBACK_FAILED", row["details"]["error_code"])
            self.assertEqual(401, row["details"]["status-code"])
            self.assertEqual("DENIED", row["details"]["error-code"])
            self.assertIn("status-code=401", row["message"])
            self.assertIn("error-code=DENIED", row["message"])
            self.assertIn("status_code=401", row["message"])
            self.assertIn("error_code=DENIED", row["message"])

    def test_event_log_redacts_secret_like_details(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="error",
                event_type="test_failure",
                method="POST",
                path="/api/test",
                status_code=500,
                user_id="user-1",
                message="failed",
                details={
                    "purchase_token": "secret-token",
                    "nested": {"client_secret": "secret-value", "safe": "visible"},
                },
            )

            rows = event_log.list_events(limit=10)
            self.assertEqual(1, len(rows))
            row_text = str(rows[0])
            self.assertIn("test_failure", row_text)
            self.assertIn("visible", row_text)
            self.assertNotIn("secret-token", row_text)
            self.assertNotIn("secret-value", row_text)
            self.assertIn("[redacted]", row_text)

    def test_event_log_truncates_oversized_detail_values(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="warning",
                event_type="oversized_client_event",
                details={
                    "long_text": "x" * 5000,
                    "items": list(range(100)),
                    "many_keys": {f"key_{index}": index for index in range(80)},
                },
            )

            row = event_log.list_events(limit=1)[0]

            self.assertLessEqual(len(row["details"]["long_text"]), event_log.MAX_DETAIL_STRING_LENGTH + 20)
            self.assertIn("[truncated]", row["details"]["long_text"])
            self.assertEqual(event_log.MAX_DETAIL_LIST_LENGTH, len(row["details"]["items"]))
            self.assertLessEqual(len(row["details"]["many_keys"]), event_log.MAX_DETAIL_DICT_KEYS + 1)
            self.assertIn("__truncated_keys__", row["details"]["many_keys"])

    def test_event_log_truncates_oversized_top_level_fields(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="warning" * 100,
                event_type="event-type-" + ("x" * 5000),
                method="POST" * 100,
                path="/api/" + ("path" * 2000),
                user_id="user-" + ("id" * 2000),
                message="message-" + ("m" * 5000),
            )

            row = event_log.list_events(limit=1)[0]

            self.assertLessEqual(len(row["level"]), event_log.MAX_EVENT_FIELD_LENGTH)
            self.assertLessEqual(len(row["event_type"]), event_log.MAX_EVENT_FIELD_LENGTH)
            self.assertLessEqual(len(row["method"]), event_log.MAX_EVENT_FIELD_LENGTH)
            self.assertLessEqual(len(row["path"]), event_log.MAX_EVENT_FIELD_LENGTH)
            self.assertLessEqual(len(row["user_id"]), event_log.MAX_EVENT_FIELD_LENGTH)
            self.assertLessEqual(len(row["message"]), event_log.MAX_EVENT_MESSAGE_LENGTH)

    def test_event_log_truncates_oversized_detail_keys(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="warning",
                event_type="oversized_client_event",
                details={
                    "client_field_" + ("x" * 5000): "visible",
                    "authorization_" + ("y" * 5000): "secret-session-token",
                },
            )

            row = event_log.list_events(limit=1)[0]
            detail_keys = list(row["details"].keys())
            row_text = str(row)

            self.assertTrue(detail_keys)
            self.assertTrue(all(len(key) <= event_log.MAX_DETAIL_KEY_LENGTH for key in detail_keys))
            self.assertIn("visible", row_text)
            self.assertIn("[redacted]", row_text)
            self.assertNotIn("secret-session-token", row_text)

    def test_event_log_truncates_deeply_nested_detail_values(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            nested = "leaf"
            for _ in range(2000):
                nested = {"nested": nested}

            event_log.record_event(
                level="warning",
                event_type="deep_client_event",
                details={"root": nested},
            )

            row = event_log.list_events(limit=1)[0]
            row_text = str(row)

            self.assertIn("[max_depth_exceeded]", row_text)
            self.assertNotIn("leaf", row_text)

    def test_event_log_truncates_oversized_details_json(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            large_details = {f"field_{index}": "x" * 1000 for index in range(50)}
            large_details["authorization"] = "secret-session-token"

            event_log.record_event(
                level="warning",
                event_type="large_client_event",
                details=large_details,
            )

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                details_json = conn.execute(
                    "SELECT details_json FROM operational_events LIMIT 1",
                ).fetchone()[0]
            finally:
                conn.close()
            row = event_log.list_events(limit=1)[0]
            row_text = str(row)

            self.assertLessEqual(len(details_json), event_log.MAX_DETAILS_JSON_LENGTH)
            self.assertTrue(row["details"]["__details_json_truncated__"])
            self.assertNotIn("secret-session-token", row_text)

    def test_api_failure_event_helper_records_without_authorization_token(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=400,
                message="Unknown product id.",
                user_id="",
                details={
                    "authorization": "Bearer secret-session-token",
                    "purchase_token": "secret-purchase-token",
                    "safe": "visible",
                },
            )

            rows = event_log.list_events(limit=10)
            self.assertEqual(1, len(rows))
            row = rows[0]
            self.assertEqual("api_request_failed", row["event_type"])
            self.assertEqual("/api/journal/google-play-purchase", row["path"])
            self.assertEqual(400, row["status_code"])
            row_text = str(row)
            self.assertIn("visible", row_text)
            self.assertNotIn("secret-session-token", row_text)
            self.assertNotIn("secret-purchase-token", row_text)

    def test_http_exception_message_is_safe_for_event_log(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            error = HTTPException(status_code=402, detail="Basic review quota exhausted.")
            event_log.record_api_exception(
                method="POST",
                path="/api/journal/ai-review-once",
                exc=error,
                user_id="user-1",
                details={"request_id": "request-123"},
            )

            rows = event_log.list_events(limit=10)
            self.assertEqual(1, len(rows))
            self.assertEqual(402, rows[0]["status_code"])
            self.assertIn("Basic review quota exhausted.", rows[0]["message"])
            self.assertEqual("request-123", rows[0]["details"]["request_id"])

    def test_list_events_can_filter_by_level_and_event_type(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="warning",
                event_type="google_play_purchase_failed",
                path="/journal",
                message="purchase failed",
            )
            event_log.record_event(
                level="info",
                event_type="client_navigation",
                path="/journal",
                message="opened",
            )

            rows = event_log.list_events(limit=10, level="warning", event_type="google_play_purchase_failed")

            self.assertEqual(1, len(rows))
            self.assertEqual("warning", rows[0]["level"])
            self.assertEqual("google_play_purchase_failed", rows[0]["event_type"])

    def test_list_events_survives_invalid_details_json_rows(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            broken_event = event_log.record_event(
                level="warning",
                event_type="broken_details",
                path="/api/client-events",
            )

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.execute(
                    "UPDATE operational_events SET details_json = ? WHERE id = ?",
                    ("{broken-json", broken_event["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            rows = event_log.list_events(limit=1)

            self.assertEqual(1, len(rows))
            self.assertEqual("broken_details", rows[0]["event_type"])
            self.assertTrue(rows[0]["details"]["__invalid_details_json__"])

    def test_list_events_omits_raw_details_json_from_results(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(
                level="warning",
                event_type="client_event",
                details={"safe": "visible"},
            )

            row = event_log.list_events(limit=1)[0]

            self.assertIn("details", row)
            self.assertNotIn("details_json", row)
            self.assertEqual("visible", row["details"]["safe"])

    def test_list_events_can_filter_by_request_id(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=500,
                message="failed",
                details={"request_id": "request-target"},
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=500,
                message="other",
                details={"request_id": "request-other"},
            )

            rows = event_log.list_events(limit=10, request_id="request-target")

            self.assertEqual(1, len(rows))
            self.assertEqual("request-target", rows[0]["details"]["request_id"])

    def test_list_events_treats_request_id_like_wildcards_literally(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=500,
                message="failed",
                details={"request_id": "request-target"},
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=500,
                message="other",
                details={"request_id": "request-other"},
            )

            rows = event_log.list_events(limit=10, request_id="%")

            self.assertEqual([], rows)

    def test_list_events_can_filter_by_user_path_and_status_code(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=402,
                user_id="user-target",
                message="purchase failed",
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=402,
                user_id="user-target",
                message="review failed",
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=500,
                user_id="user-other",
                message="other failed",
            )

            rows = event_log.list_events(
                limit=10,
                user_id="user-target",
                path="/api/journal/google-play-purchase",
                status_code=402,
            )

            self.assertEqual(1, len(rows))
            self.assertEqual("user-target", rows[0]["user_id"])
            self.assertEqual("/api/journal/google-play-purchase", rows[0]["path"])
            self.assertEqual(402, rows[0]["status_code"])

    def test_list_events_can_filter_by_event_id_and_created_range(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            old_event = event_log.record_event(level="warning", event_type="old", path="/old")
            target_event = event_log.record_event(level="error", event_type="target", path="/target")
            new_event = event_log.record_event(level="warning", event_type="new", path="/new")
            old_created_at = "2026-06-22T09:00:00+00:00"
            target_created_at = "2026-06-22T12:00:00+00:00"
            new_created_at = "2026-06-22T15:00:00+00:00"

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.executemany(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    [
                        (old_created_at, old_event["id"]),
                        (target_created_at, target_event["id"]),
                        (new_created_at, new_event["id"]),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            rows = event_log.list_events(
                limit=10,
                event_id=target_event["id"],
                created_after="2026-06-22T10:00:00+00:00",
                created_before="2026-06-22T13:00:00+00:00",
            )

            self.assertEqual(1, len(rows))
            self.assertEqual(target_event["id"], rows[0]["id"])
            self.assertEqual(target_created_at, rows[0]["created_at"])

    def test_list_events_can_offset_for_next_page(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            first = event_log.record_event(level="warning", event_type="first", path="/first")
            second = event_log.record_event(level="warning", event_type="second", path="/second")
            third = event_log.record_event(level="warning", event_type="third", path="/third")

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.executemany(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    [
                        ("2026-06-22T10:00:00+00:00", first["id"]),
                        ("2026-06-22T11:00:00+00:00", second["id"]),
                        ("2026-06-22T12:00:00+00:00", third["id"]),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            first_page = event_log.list_events(limit=2, offset=0)
            second_page = event_log.list_events(limit=2, offset=2)

            self.assertEqual([third["id"], second["id"]], [row["id"] for row in first_page])
            self.assertEqual([first["id"]], [row["id"] for row in second_page])

    def test_summarize_events_groups_recent_events(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(level="error", event_type="google_play_purchase_failed", path="/journal")
            event_log.record_event(level="error", event_type="google_play_purchase_failed", path="/journal")
            event_log.record_event(level="warning", event_type="rewarded_ad_basic_review_failed", path="/journal")

            summary = event_log.summarize_events(limit=100)

            self.assertEqual(3, summary["total"])
            self.assertEqual({"error": 2, "warning": 1}, summary["by_level"])
            self.assertEqual(2, summary["by_event_type"]["google_play_purchase_failed"])
            self.assertEqual(1, summary["by_event_type"]["rewarded_ad_basic_review_failed"])
            self.assertEqual(2, summary["top_events"][0]["count"])

    def test_summarize_events_groups_status_codes_and_users(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=402,
                user_id="user-a",
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=402,
                user_id="user-a",
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=500,
                user_id="user-b",
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/client-events",
                status_code=429,
                user_id="",
            )

            summary = event_log.summarize_events(limit=100)

            self.assertEqual({402: 2, 500: 1, 429: 1}, summary["by_status_code"])
            self.assertEqual({"user-a": 2, "user-b": 1}, summary["by_user"])
            self.assertEqual({"name": "user-a", "count": 2}, summary["top_users"][0])

    def test_summarize_events_reports_sample_offset(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            first = event_log.record_event(level="warning", event_type="first", path="/first")
            second = event_log.record_event(level="warning", event_type="second", path="/second")
            third = event_log.record_event(level="warning", event_type="third", path="/third")

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.executemany(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    [
                        ("2026-06-22T10:00:00+00:00", first["id"]),
                        ("2026-06-22T11:00:00+00:00", second["id"]),
                        ("2026-06-22T12:00:00+00:00", third["id"]),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            summary = event_log.summarize_events(limit=1, offset=1)

            self.assertEqual(1, summary["total"])
            self.assertEqual(1, summary["sample_limit"])
            self.assertEqual(1, summary["sample_offset"])
            self.assertEqual({"/second": 1}, summary["by_path"])

    def test_summarize_events_uses_the_same_filters_as_event_lookup(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            target_event = event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=402,
                user_id="user-target",
                message="purchase failed",
                details={"request_id": "request-target"},
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/ai-review-once",
                status_code=402,
                user_id="user-target",
                message="review failed",
                details={"request_id": "request-other"},
            )
            event_log.record_api_failure(
                method="POST",
                path="/api/journal/google-play-purchase",
                status_code=500,
                user_id="user-other",
                message="other failed",
                details={"request_id": "request-other"},
            )

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.execute(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    ("2026-06-22T12:00:00+00:00", target_event["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            summary = event_log.summarize_events(
                limit=100,
                request_id="request-target",
                user_id="user-target",
                path="/api/journal/google-play-purchase",
                status_code=402,
                created_after="2026-06-22T11:00:00+00:00",
                created_before="2026-06-22T13:00:00+00:00",
            )

            self.assertEqual(1, summary["total"])
            self.assertEqual({"warning": 1}, summary["by_level"])
            self.assertEqual({"api_request_failed": 1}, summary["by_event_type"])
            self.assertEqual({"/api/journal/google-play-purchase": 1}, summary["by_path"])

    def test_purge_events_older_than_retention_days_keeps_recent_events(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            old_event = event_log.record_event(level="error", event_type="old_error", path="/old")
            recent_event = event_log.record_event(level="warning", event_type="recent_warning", path="/recent")
            old_created_at = (
                datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)
            ).isoformat(timespec="seconds")

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.execute(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    (old_created_at, old_event["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            result = event_log.purge_events_older_than(retention_days=90)
            rows = event_log.list_events(limit=10)

            self.assertEqual(1, result["deleted_count"])
            self.assertEqual(90, result["retention_days"])
            self.assertEqual([recent_event["id"]], [row["id"] for row in rows])

    def test_purge_events_older_than_rejects_excessive_retention_days(self):
        with storage_fixture():
            from backend.core import event_log

            event_log = importlib.reload(event_log)

            with self.assertRaises(ValueError) as blocked:
                event_log.purge_events_older_than(retention_days=999999999)

            self.assertIn("retention_days", str(blocked.exception))

    def test_purge_configured_retention_skips_without_setting(self):
        with storage_fixture(
            ALPHAMATE_EVENT_LOG_RETENTION_DAYS=None,
        ):
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            event_log.record_event(level="error", event_type="kept", path="/kept")

            result = event_log.purge_configured_retention()
            rows = event_log.list_events(limit=10)

            self.assertEqual({"skipped": True, "reason": "not_configured"}, result)
            self.assertEqual(1, len(rows))

    def test_purge_configured_retention_uses_environment_setting(self):
        with storage_fixture(
            ALPHAMATE_EVENT_LOG_RETENTION_DAYS="90",
        ):
            from backend.core import event_log

            event_log = importlib.reload(event_log)
            old_event = event_log.record_event(level="error", event_type="old_error", path="/old")
            event_log.record_event(level="warning", event_type="recent_warning", path="/recent")
            old_created_at = (
                datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)
            ).isoformat(timespec="seconds")

            conn = sqlite3.connect(event_log.event_log_db_path())
            try:
                conn.execute(
                    "UPDATE operational_events SET created_at = ? WHERE id = ?",
                    (old_created_at, old_event["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            result = event_log.purge_configured_retention()

            self.assertEqual(1, result["deleted_count"])
            self.assertEqual(90, result["retention_days"])


if __name__ == "__main__":
    unittest.main()
