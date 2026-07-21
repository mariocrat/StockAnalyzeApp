import importlib
import os
import sys
import tempfile
import unittest


class QaAdvancedComparisonStoreTest(unittest.TestCase):
    def setUp(self):
        self.previous_access_db = os.environ.get("ALPHAMATE_ACCESS_DB_PATH")
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(self.tempdir.name, "access.sqlite3")
        self.store = importlib.reload(importlib.import_module("backend.core.qa_advanced_compare"))

    def tearDown(self):
        if self.previous_access_db is None:
            os.environ.pop("ALPHAMATE_ACCESS_DB_PATH", None)
        else:
            os.environ["ALPHAMATE_ACCESS_DB_PATH"] = self.previous_access_db
        self.tempdir.cleanup()

    def test_each_model_runs_once_and_replays_the_saved_result(self):
        first = self.store.begin_comparison(user_id="user-a", model_variant="luna")
        self.assertTrue(first["run"])
        self.store.complete_comparison(
            user_id="user-a",
            model_variant="luna",
            result={"summary": "luna result"},
        )

        replay = self.store.begin_comparison(user_id="user-a", model_variant="luna")
        terra = self.store.begin_comparison(user_id="user-a", model_variant="terra")

        self.assertFalse(replay["run"])
        self.assertEqual("luna result", replay["cached_result"]["summary"])
        self.assertTrue(terra["run"])

    def test_comparison_is_reserved_for_the_first_test_account(self):
        self.store.begin_comparison(user_id="user-a", model_variant="luna")

        with self.assertRaises(self.store.QaComparisonUnavailable):
            self.store.begin_comparison(user_id="user-b", model_variant="terra")

    def test_failed_run_can_be_retried(self):
        self.store.begin_comparison(user_id="user-a", model_variant="luna")
        self.store.release_comparison(user_id="user-a", model_variant="luna")

        retry = self.store.begin_comparison(user_id="user-a", model_variant="luna")

        self.assertTrue(retry["run"])


class QaAdvancedComparisonEndpointTest(unittest.TestCase):
    ENV_KEYS = [
        "ALPHAMATE_ACCOUNT_DB_PATH",
        "ALPHAMATE_ACCESS_DB_PATH",
        "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
        "ALPHAMATE_ALLOW_DEV_ACCESS",
    ]

    def setUp(self):
        self.previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ALPHAMATE_ACCOUNT_DB_PATH"] = os.path.join(self.tempdir.name, "accounts.sqlite3")
        os.environ["ALPHAMATE_ACCESS_DB_PATH"] = os.path.join(self.tempdir.name, "access.sqlite3")
        os.environ["ALPHAMATE_REVIEW_HISTORY_DB_PATH"] = os.path.join(self.tempdir.name, "reviews.sqlite3")
        os.environ["ALPHAMATE_ALLOW_DEV_ACCESS"] = "true"
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        self.account_store = importlib.reload(importlib.import_module("core.account_store"))
        importlib.reload(importlib.import_module("core.qa_advanced_compare"))
        self.main = importlib.reload(importlib.import_module("main"))

    def tearDown(self):
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def _batch(self, variant="luna"):
        return self.main.JournalQaAdvancedCompareIn(
            privacy_consent=True,
            model_variant=variant,
            trades=[self.main.JournalTradeIn(
                trade_date="2026-07-10T09:36",
                ticker="017900",
                name="광전자",
                side="buy",
                price=6980,
                quantity=10,
            )],
        )

    def test_endpoint_uses_selected_model_without_ticket_or_fallback(self):
        session = self.account_store.login_dev_provider(
            provider="kakao",
            provider_user_id="qa-model-user",
            display_name="QA 모델 비교",
        )
        authorization = f"Bearer {session['session_token']}"
        calls = []

        def fake_review(trades, *, model_override="", allow_fallback=True):
            calls.append((model_override, allow_fallback))
            return {
                "status": "ready",
                "source": "openai",
                "review_type": "advanced",
                "model": model_override,
                "summary": f"{model_override} result",
            }

        self.main.build_advanced_ai_review = fake_review

        first = self.main.post_journal_qa_advanced_comparison(
            self._batch("luna"),
            authorization=authorization,
            x_alphamate_qa_comparison="luna-terra-v1",
        )
        replay = self.main.post_journal_qa_advanced_comparison(
            self._batch("luna"),
            authorization=authorization,
            x_alphamate_qa_comparison="luna-terra-v1",
        )

        self.assertEqual([("gpt-5.6-luna", False)], calls)
        self.assertFalse(first["qa_comparison"]["ticket_consumed"])
        self.assertTrue(replay["qa_cached_result"])

    def test_endpoint_is_hidden_without_the_qa_header(self):
        session = self.account_store.login_dev_provider(
            provider="naver",
            provider_user_id="qa-hidden-user",
            display_name="QA 숨김",
        )
        with self.assertRaises(self.main.HTTPException) as raised:
            self.main.post_journal_qa_advanced_comparison(
                self._batch("terra"),
                authorization=f"Bearer {session['session_token']}",
                x_alphamate_qa_comparison=None,
            )

        self.assertEqual(404, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
