import importlib
import datetime
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager

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


class EventLogTest(unittest.TestCase):
    def test_event_log_redacts_secret_like_details(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_api_failure_event_helper_records_without_authorization_token(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
            ALPHAMATE_ENV="development",
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_list_events_can_filter_by_request_id(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_list_events_can_filter_by_user_path_and_status_code(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_summarize_events_groups_recent_events(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_summarize_events_uses_the_same_filters_as_event_lookup(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
        ):
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

    def test_purge_configured_retention_skips_without_setting(self):
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
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
        with tempfile.TemporaryDirectory() as tmpdir, patched_env(
            ALPHAMATE_EVENT_LOG_DB_PATH=os.path.join(tmpdir, "events.sqlite3"),
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
