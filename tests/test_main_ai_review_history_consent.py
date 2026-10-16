from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.history_legacy_fixture import add_legacy_history_fixture

from core.review_display_contract import SCHEMA_VERSION

from tests.review_source_fixtures import approved_route_fixture, compact_chart_fixture, fallback_model_fixture, review_input_fixture, history_chart_fixture

from tests.api_test_modules import api_module_state

from contextlib import ExitStack
from unittest.mock import patch
import importlib
import json
import unittest


class MainAiReviewHistoryConsentTest(unittest.TestCase):
    def test_legacy_safe_history_remains_visible_through_routes(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules:
            session = modules.account_store.login_dev_provider(
                provider="kakao", provider_user_id="legacy-safe", display_name="이력 사용자",
            )
            token = f"Bearer {session['session_token']}"
            modules.account_store.update_journal_storage_setting(authorization=token, enabled=True)
            saved = add_legacy_history_fixture(modules.review_history,
                user_id=session["user"]["id"], review_type="basic", ticker="005930",
                name="삼성전자", ai_review={"summary": "과거 체결을 확인합니다."},
            )
            detail = modules.main.get_journal_review_history_detail(saved["id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            rows = modules.main.get_journal_review_history(authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            self.assertEqual("과거 체결을 확인합니다.", detail["ai_review"]["summary"])
            self.assertEqual(detail["ai_review"]["summary"], detail["ai_review"]["display_snapshot"]["canonical_text"])
            self.assertEqual("삼성전자", rows[0]["name"])
            self.assertEqual("종목: 005930 삼성전자", rows[0]["display_snapshot"]["canonical_text"])

    def test_legacy_unsafe_history_is_redacted_at_read_without_db_mutation(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules:
            session = modules.account_store.login_dev_provider(
                provider="kakao", provider_user_id="legacy-unsafe", display_name="이력 사용자",
            )
            token = f"Bearer {session['session_token']}"
            modules.account_store.update_journal_storage_setting(authorization=token, enabled=True)
            saved = add_legacy_history_fixture(modules.review_history,
                user_id=session["user"]["id"], review_type="basic", ticker="005930",
                name="목표[데이터 확인]가: 80,000원입니다.",
                chart_snapshot={"charts": [{"detail": "현재는 매수 추천합니다."}]},
                ai_review={"summary": "기존 복기"},
            )
            detail = modules.main.get_journal_review_history_detail(saved["id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            rows = modules.main.get_journal_review_history(authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            exported = modules.main.export_me_data(authorization=token, x_review_display_contract=[SCHEMA_VERSION])["review_history"][0]
            original = modules.review_history.get_review_history(saved["id"], user_id=session["user"]["id"])
            for visible in (detail, rows[0], exported):
                serialized = json.dumps(visible, ensure_ascii=False)
                self.assertNotIn("현재는 매수 추천합니다.", serialized)
                self.assertNotIn("목표[데이터 확인]가", serialized)
            self.assertEqual(detail["ai_review"]["summary"], detail["ai_review"]["display_snapshot"]["canonical_text"])
            self.assertEqual("현재는 매수 추천합니다.", original["chart_snapshot"]["charts"][0]["detail"])

    def test_legacy_split_chart_text_is_redacted_in_memory(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules:
            session = modules.account_store.login_dev_provider(
                provider="kakao", provider_user_id="legacy-split", display_name="이력 사용자",
            )
            token = f"Bearer {session['session_token']}"
            modules.account_store.update_journal_storage_setting(authorization=token, enabled=True)
            saved = add_legacy_history_fixture(modules.review_history,
                user_id=session["user"]["id"], review_type="basic", ticker="005930",
                name="삼성전자", ai_review={"summary": "과거 체결 기록"},
                chart_snapshot={"charts": [], "chart_contexts": [],
                                "chart_reviews": [{"title": "목표가", "detail": "80,000원입니다."}]},
            )
            detail = modules.main.get_journal_review_history_detail(saved["id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            original = modules.review_history.get_review_history(saved["id"], user_id=session["user"]["id"])
            self.assertNotIn("목표가", json.dumps(detail, ensure_ascii=False))
            self.assertEqual("목표가", original["chart_snapshot"]["chart_reviews"][0]["title"])

    def test_ai_review_once_saves_approved_history_in_phase2c(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            access_control = modules.access_control
            review_history = modules.review_history
            main = modules.main
            ai_review_v2 = importlib.import_module("core.ai_review_v2")
            patches.enter_context(patch.object(ai_review_v2, "_compact_chart_snapshot", return_value=compact_chart_fixture({})))
            patches.enter_context(patch.object(ai_review_v2, "_contexts_for_trades", return_value=[]))
            patches.enter_context(patch.object(ai_review_v2, "_call_openai_review", side_effect=lambda payload, *, model, instructions: json.dumps(
                fallback_model_fixture(payload), ensure_ascii=False,
            )))
            patches.enter_context(patch.object(main, "build_journal_charts", side_effect=history_chart_fixture))

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

            result = main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            rows = review_history.list_review_history(user_id=session["user"]["id"])
            self.assertEqual("ready", result["status"])
            self.assertEqual([result["review_history_id"]], [row["id"] for row in rows])
            detail = main.get_journal_review_history_detail(result["review_history_id"], authorization=token, x_review_display_contract=[SCHEMA_VERSION])
            self.assertEqual(result["summary"], detail["ai_review"]["summary"])
            self.assertEqual(result["display_snapshot"], detail["ai_review"]["display_snapshot"])

    def test_ai_review_once_does_not_save_history_when_storage_is_off(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            review_history = modules.review_history
            main = modules.main
            patches.enter_context(patch.object(main, "build_basic_ai_review", lambda trades, target_trade_id=None, analysis_focus="balanced", approval_state=None: approved_route_fixture(
                "transient basic review", approval_state=approval_state, model="gpt-5.4-mini")))

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

            result = main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])

            self.assertNotIn("review_history_id", result)
            self.assertEqual([], review_history.list_review_history(user_id=session["user"]["id"]))

    def test_ai_review_once_records_privacy_consent_for_authenticated_user(self):
        with storage_fixture(ALPHAMATE_ALLOW_DEV_ACCESS="true", ALPHAMATE_PRIVACY_CONSENT_VERSION="ai-review-privacy-test"), api_module_state() as modules, ExitStack() as patches:


            account_store = modules.account_store
            main = modules.main
            patches.enter_context(patch.object(main, "build_basic_ai_review", lambda trades, target_trade_id=None, analysis_focus="balanced", approval_state=None: approved_route_fixture(
                "consent saved", approval_state=approval_state, model="gpt-5.4-mini")))

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

            main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])
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
                main.get_journal_ai_review_once(batch, authorization=token, x_review_display_contract=[SCHEMA_VERSION])

            self.assertIn("Privacy consent is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
