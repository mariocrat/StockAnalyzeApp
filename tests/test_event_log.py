import importlib
import os
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
            )

            rows = event_log.list_events(limit=10)
            self.assertEqual(1, len(rows))
            self.assertEqual(402, rows[0]["status_code"])
            self.assertIn("Basic review quota exhausted.", rows[0]["message"])

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


if __name__ == "__main__":
    unittest.main()
