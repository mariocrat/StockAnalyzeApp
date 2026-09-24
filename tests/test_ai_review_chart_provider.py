"""Chart/market seams inside the H4-A1 boundary."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import _import_state
from unittest.mock import patch
import pandas as pd

import importlib
import io
import json
import os
import tempfile
import unittest
import urllib.error


class AiReviewChartProviderTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(_import_state())
        self.ai_review_v2 = importlib.import_module("core.ai_review_v2")
        self.enterContext(patch.dict(self.ai_review_v2.__dict__))
        importlib.reload(self.ai_review_v2)
        # Empty synthetic charts exercise the local OHLCV-context fallback too.
        self.enterContext(patch.object(
            self.ai_review_v2, "build_journal_charts", return_value={"charts": []}))
        self.enterContext(patch.object(
            self.ai_review_v2, "get_stock_ohlcv", side_effect=lambda *args: pd.DataFrame()))

    def _success_response(self, text="ok"):
        body = json.dumps({"output_text": text}).encode("utf-8")

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()

        return Response(body)

    def test_advanced_review_override_can_disable_fallback_for_qa_comparison(self):
        os.environ["OPENAI_ADVANCED_REVIEW_MODEL"] = "configured-primary"
        os.environ["OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL"] = "configured-fallback"
        captured = []

        def fake_call(payload, *, model, instructions):
            captured.append(model)
            raise RuntimeError("model failed")

        self.ai_review_v2._call_openai_review = fake_call
        result = self.ai_review_v2.build_advanced_ai_review(
            [{
                "id": 1,
                "trade_date": "2026-07-10T09:36",
                "ticker": "017900",
                "name": "광전자",
                "side": "buy",
                "price": 6980,
                "quantity": 10,
            }],
            model_override="gpt-5.6-luna",
            allow_fallback=False,
        )

        self.assertEqual(["gpt-5.6-luna"], captured)
        self.assertEqual("error", result["status"])
        self.assertEqual("advanced", result["review_type"])



if __name__ == "__main__":
    unittest.main()
