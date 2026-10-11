"""Independently fixed legacy-safe grammar vectors, inside H4 before imports."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.core.review_legacy_compatibility import (
    CONTRACT_VERSION, LegacyCompatibilityContractError, admit_legacy_body, validate_legacy_body,
)


VECTORS = json.loads((Path(__file__).resolve().parents[1]
                     / "frontend/scripts/fixtures/review-legacy-compatibility-v1.json")
                    .read_text(encoding="utf-8"))


class LegacyCompatibilityContractTest(unittest.TestCase):
    def test_admission_only_generates_no_wire_and_preserves_all_a1_decisions(self):
        with patch("backend.core.review_legacy_compatibility.LegacyCompatibilitySummary", side_effect=AssertionError("unsealed wire")):
            for vector in VECTORS["pass"]:
                self.assertIsNone(validate_legacy_body(vector["document"]))
            for vector in VECTORS["fail"]:
                with self.subTest(vector=vector["id"]), self.assertRaises(LegacyCompatibilityContractError) as raised:
                    validate_legacy_body(vector["document"])
                self.assertEqual(raised.exception.code, vector["expected_rejection"])

    def test_fixed_pass_vectors_have_exact_deterministic_wire_without_mutation(self):
        self.assertEqual(VECTORS["contract"], CONTRACT_VERSION)
        self.assertEqual(len(VECTORS["pass"]), 10)
        for vector in VECTORS["pass"]:
            with self.subTest(vector=vector["id"]):
                before = copy.deepcopy(vector["document"])
                result = admit_legacy_body(vector["document"])
                self.assertEqual(result.status, "success")
                self.assertEqual(result.contract_version, CONTRACT_VERSION)
                self.assertEqual(result.summary, vector["expected_summary"])
                self.assertEqual(result, admit_legacy_body(before))
                self.assertEqual(vector["document"], before)

    def test_fixed_fail_vectors_reject_with_stable_explicit_codes(self):
        self.assertEqual(len(VECTORS["fail"]), 65)
        for vector in VECTORS["fail"]:
            with self.subTest(vector=vector["id"]):
                before = copy.deepcopy(vector["document"])
                with self.assertRaises(LegacyCompatibilityContractError) as raised:
                    admit_legacy_body(vector["document"])
                self.assertEqual(raised.exception.code, vector["expected_rejection"])
                self.assertEqual(str(raised.exception), vector["expected_rejection"])
                self.assertEqual(vector["document"], before)

    def test_p1_literals_and_strong_ast_with_bad_suffix_are_terminal_rejections(self):
        expected = {
            "p1_lone_star": "현재는 매**수** 추천합니다. *",
            "p1_link": "현재는 매**수** 추천합니다. [참고](url)",
        }
        for vector in VECTORS["fail"]:
            if vector["id"] in expected:
                self.assertEqual(vector["forbidden_wire"], expected[vector["id"]])
                self.assertEqual(vector["document"]["canonical_text"], expected[vector["id"]])
            if vector["id"] in (*expected, "p1_lone_star_runs", "p1_link_runs"):
                with self.subTest(vector=vector["id"]), self.assertRaises(LegacyCompatibilityContractError):
                    admit_legacy_body(vector["document"])

    def test_normal_strong_wire_intentionally_differs_from_visible_canonical_text(self):
        vector = next(v for v in VECTORS["pass"] if v["id"] == "normal_strong")
        result = admit_legacy_body(vector["document"])
        self.assertEqual(result.summary, "**체결 기록**을 확인합니다.")
        self.assertEqual(vector["document"]["canonical_text"], "체결 기록을 확인합니다.")
        self.assertNotEqual(result.summary, vector["document"]["canonical_text"])
        self.assertEqual(vector["expected_paragraphs"], [{"text": "체결 기록을 확인합니다.",
                                                       "strong": [{"start": 0, "end": 5, "text": "체결 기록"}]}])

    def test_raw_summary_semantic_tree_and_wrong_surface_are_not_inputs(self):
        for value in (None, "기록", {"summary": "기록"}, {"basic": {"lesson": "기록"}},
                      VECTORS["fail"][-2]["document"]):
            with self.subTest(value=type(value).__name__), self.assertRaises(LegacyCompatibilityContractError):
                admit_legacy_body(value)

    def test_unknown_fields_versions_types_and_mismatch_fail_closed(self):
        base = VECTORS["pass"][0]["document"]
        changes = []
        for level in ("document", "block", "run"):
            value = copy.deepcopy(base)
            target = value if level == "document" else value["blocks"][0] if level == "block" else value["blocks"][0]["runs"][0]
            target["unmapped"] = "기록"
            changes.append(value)
        for key, wrong in (("schema_version", "future"), ("blocks", []), ("canonical_text", "다른 기록")):
            value = copy.deepcopy(base)
            value[key] = wrong
            changes.append(value)
        for value in changes:
            with self.assertRaises(LegacyCompatibilityContractError) as raised:
                admit_legacy_body(value)
            self.assertEqual(raised.exception.code, "invalid_canonical_body")

    def test_reserved_sequences_reject_at_every_text_and_strong_run_boundary(self):
        # Repartition the literal fixed failures, rather than generating expected
        # output from a parser. Every cut must still reject the whole document.
        codes = {"literal_markdown", "reserved_basic_section", "reserved_display_token", "reserved_ma_token",
                 "consecutive_whitespace", "unsupported_whitespace", "paragraph_edge_whitespace"}
        for vector in VECTORS["fail"]:
            if vector["expected_rejection"] not in codes or len(vector["document"]["blocks"]) != 1:
                continue
            source = vector["document"]["canonical_text"]
            for cut in range(1, len(source)):
                for kind in ("text", "strong"):
                    value = copy.deepcopy(vector["document"])
                    value["blocks"][0]["runs"] = [{"type": "text", "text": source[:cut]},
                                                  {"type": kind, "text": source[cut:]}]
                    with self.subTest(vector=vector["id"], cut=cut, kind=kind), self.assertRaises(LegacyCompatibilityContractError):
                        admit_legacy_body(value)

    def test_plain_run_repartitioning_cannot_change_wire_or_visible_text(self):
        vector = VECTORS["pass"][0]
        source = vector["document"]["canonical_text"]
        for cut in range(1, len(source)):
            value = copy.deepcopy(vector["document"])
            value["blocks"][0]["runs"] = [{"type": "text", "text": source[:cut]},
                                          {"type": "text", "text": source[cut:]}]
            self.assertEqual(admit_legacy_body(value).summary, vector["expected_summary"])

    def test_reserved_tokens_spanning_owned_paragraph_boundaries_reject(self):
        vectors = [v for v in VECTORS["fail"] if v["id"].startswith("paragraph_boundary_")]
        self.assertEqual(len(vectors), 5)
        for vector in vectors:
            self.assertEqual(len(vector["document"]["blocks"]), 2)
            self.assertEqual(vector["document"]["blocks"][0]["separator_after"], "\n\n")
            with self.subTest(vector=vector["id"]), self.assertRaises(LegacyCompatibilityContractError) as raised:
                admit_legacy_body(vector["document"])
            self.assertEqual(raised.exception.code, vector["expected_rejection"])

    def test_advanced_fallback_fixed_shape_has_four_exact_ordered_paragraphs(self):
        for vector in VECTORS["pass"]:
            if not vector["id"].startswith("advanced_fallback_"):
                continue
            self.assertEqual(len(vector["document"]["blocks"]), 4)
            self.assertEqual([b["separator_after"] for b in vector["document"]["blocks"]], ["\n\n", "\n\n", "\n\n", ""])
            self.assertEqual(admit_legacy_body(vector["document"]).summary.split("\n\n"),
                             [p["text"] for p in vector["expected_paragraphs"]])

    def test_unicode_is_not_normalized_and_offsets_use_codepoints(self):
        vector = next(v for v in VECTORS["pass"] if v["id"] == "unicode_sequence")
        self.assertEqual(admit_legacy_body(vector["document"]).summary, "기록 **e\u0301 😀** 확인")
        self.assertEqual(vector["document"]["canonical_text"][3:7], "e\u0301 😀")
        self.assertNotEqual(vector["document"]["canonical_text"], "기록 é 😀 확인")

    def test_result_is_immutable_and_detached_from_later_document_mutation(self):
        value = copy.deepcopy(VECTORS["pass"][1]["document"])
        result = admit_legacy_body(value)
        value["blocks"][0]["runs"][0]["text"] = "변경"
        value["canonical_text"] = "변경을 확인합니다."
        self.assertEqual(result.summary, "**체결 기록**을 확인합니다.")
        with self.assertRaises(FrozenInstanceError):
            result.summary = "변경"

    def test_supported_document_bounds_still_apply_before_legacy_admission(self):
        value = copy.deepcopy(VECTORS["pass"][0]["document"])
        value["blocks"][0]["runs"] = [{"type": "text", "text": "기록"}] * 65
        value["canonical_text"] = "기록" * 65
        with self.assertRaises(LegacyCompatibilityContractError) as raised:
            admit_legacy_body(value)
        self.assertEqual(raised.exception.code, "invalid_canonical_body")
