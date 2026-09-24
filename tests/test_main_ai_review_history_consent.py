from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

from contextlib import ExitStack
from unittest.mock import patch
import unittest


class MainAiReviewHistoryConsentTest(unittest.TestCase):
    def test_ai_review_once_saves_history_for_authenticated_storage_user(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            access_control = modules.access_control
            review_history = modules.review_history
            main = modules.main
            patches.enter_context(patch.object(main, "build_advanced_ai_review", lambda trades, target_trade_id=None: {
                "status": "ready",
                "source": "openai",
                "review_type": "advanced",
                "model": "gpt-5.5",
                "summary": "saved advanced review",
                "chart_contexts": [{"ticker": "005930"}],
            }))
            patches.enter_context(patch.object(main, "build_journal_charts", lambda trades: {
                "charts": [{
                    "ticker": "005930",
                    "name": "삼성전자",
                    "candles": [{"time": "2026-06-19", "open": 70000, "high": 71000, "low": 69000, "close": 70500}],
                    "markers": [{"time": "2026-06-19", "text": "B"}],
                }],
            }))

            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="review-save-user",
                display_name="복기 저장",
            )
            token = f"Bearer {session['session_token']}"
            account_store.update_journal_storage_setting(authorization=token, enabled=True)
            access_control.apply_dev_purchase(
                authorization=token,
                entitlement_token="",
                product_id="advanced_review_10",
            )
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="advanced",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-19T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            result = main.get_journal_ai_review_once(batch, authorization=token)
            rows = review_history.list_review_history(user_id=session["user"]["id"])
            detail = review_history.get_review_history(rows[0]["id"], user_id=session["user"]["id"])

            self.assertIn("review_history_id", result)
            self.assertEqual(1, len(rows))
            self.assertEqual("advanced", rows[0]["review_type"])
            self.assertEqual("saved advanced review", detail["ai_review"]["summary"])
            self.assertEqual([{"ticker": "005930"}], detail["chart_snapshot"]["chart_contexts"])
            self.assertEqual("005930", detail["chart_snapshot"]["charts"][0]["ticker"])

    def test_ai_review_once_does_not_save_history_when_storage_is_off(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            review_history = modules.review_history
            main = modules.main
            patches.enter_context(patch.object(main, "build_basic_ai_review", lambda trades, target_trade_id=None, analysis_focus="balanced": {
                "status": "ready",
                "source": "openai",
                "review_type": "basic",
                "model": "gpt-5.4-mini",
                "summary": "transient basic review",
            }))

            session = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="review-nosave-user",
                display_name="복기 미저장",
            )
            token = f"Bearer {session['session_token']}"
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="basic",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-19T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            result = main.get_journal_ai_review_once(batch, authorization=token)

            self.assertNotIn("review_history_id", result)
            self.assertEqual([], review_history.list_review_history(user_id=session["user"]["id"]))

    def test_ai_review_once_records_privacy_consent_for_authenticated_user(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true", ALPHAMATE_PRIVACY_CONSENT_VERSION="ai-review-privacy-test"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            main = modules.main
            patches.enter_context(patch.object(main, "build_basic_ai_review", lambda trades, target_trade_id=None, analysis_focus="balanced": {
                "status": "ready",
                "source": "openai",
                "review_type": "basic",
                "model": "gpt-5.4-mini",
                "summary": "consent saved",
            }))

            session = account_store.login_dev_provider(
                provider="kakao",
                provider_user_id="ai-consent-user",
                display_name="AI 동의",
            )
            token = f"Bearer {session['session_token']}"
            batch = main.JournalAiReviewIn(
                privacy_consent=True,
                review_type="basic",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-21T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            main.get_journal_ai_review_once(batch, authorization=token)
            current = account_store.authenticate_session(token)

            self.assertEqual("ai-review-privacy-test", current["privacy_consent_version"])
            self.assertTrue(current["privacy_consented_at"])

    def test_ai_review_once_rejects_missing_privacy_consent(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            main = modules.main
            session = account_store.login_dev_provider(
                provider="naver",
                provider_user_id="ai-no-consent-user",
                display_name="AI 미동의",
            )
            token = f"Bearer {session['session_token']}"
            batch = main.JournalAiReviewIn(
                privacy_consent=False,
                review_type="basic",
                trades=[main.JournalTradeIn(
                    trade_date="2026-06-21T10:30",
                    ticker="005930",
                    name="삼성전자",
                    side="buy",
                    price=70000,
                    quantity=1,
                )],
            )

            with self.assertRaises(Exception) as ctx:
                main.get_journal_ai_review_once(batch, authorization=token)

            self.assertIn("Privacy consent is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
