"""Fixed cross-language review-display.v1 vectors under the H4 boundary."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
from pathlib import Path
import unittest

from backend.core import review_display_contract as contract


VECTORS = json.loads((Path(__file__).resolve().parents[1] / "frontend/scripts/fixtures/review-display-v1.json")
                     .read_text(encoding="utf-8"))


class ReviewDisplayContractTest(unittest.TestCase):
    def test_shared_valid_vectors_compile_and_flatten_exactly(self):
        self.assertEqual(VECTORS["schema_version"], contract.SCHEMA_VERSION)
        for vector in VECTORS["valid"]:
            with self.subTest(vector=vector["id"]):
                document = vector["document"]
                self.assertEqual(contract.flatten_document(document), vector["expected_canonical_text"])
                self.assertEqual(document["canonical_text"], vector["expected_canonical_text"])
                if "input" in vector:
                    self.assertEqual(contract.parse_inline_strong(vector["input"]), vector["expected_runs"])
                    self.assertEqual(contract.compile_paragraph(vector["input"]), document)

    def test_mid_word_bold_counterexample_keeps_one_strong_syllable(self):
        vector = next(item for item in VECTORS["valid"] if item["id"] == "mid_word_bold_counterexample")
        self.assertEqual(vector["expected_runs"], [
            {"type": "text", "text": "현재는 매"}, {"type": "strong", "text": "수"},
            {"type": "text", "text": " 추천합니다."},
        ])
        self.assertEqual(contract.compile_paragraph(vector["input"])["canonical_text"], "현재는 매수 추천합니다.")

    def test_normal_bold_retains_strong_run_and_exact_text(self):
        vector = next(item for item in VECTORS["valid"] if item["id"] == "normal_bold")
        self.assertEqual(vector["expected_runs"][0], {"type": "strong", "text": "체결 기록"})
        self.assertEqual(contract.flatten_document(vector["document"]), "체결 기록을 확인합니다.")

    def test_unclosed_nested_and_unsupported_markup_stay_literal(self):
        for source in ("**미완성", "**바깥 __안쪽__**", "*기울임*과 **굵게**",
                       "**앞 **중간** 뒤**", "** **", "**굵게** [link](url)", "**코드 `표기`**"):
            with self.subTest(source=source):
                self.assertEqual(contract.parse_inline_strong(source), [{"type": "text", "text": source}])

    def test_shared_invalid_vectors_reject(self):
        for vector in VECTORS["invalid"]:
            with self.subTest(vector=vector["id"]):
                with self.assertRaises(contract.ReviewDisplayContractError):
                    contract.flatten_document(vector["document"])

    def test_unknown_structural_fields_at_every_level_reject(self):
        base = VECTORS["valid"][0]["document"]
        for level in ("document", "block", "run"):
            document = copy.deepcopy(base)
            target = (document if level == "document" else document["blocks"][0] if level == "block"
                      else document["blocks"][0]["runs"][0])
            target["html"] = "<b>not allowed</b>"
            with self.subTest(level=level), self.assertRaises(contract.ReviewDisplayContractError):
                contract.validate_document(document)

    def test_count_size_and_depth_boundaries_reject(self):
        base = VECTORS["valid"][0]["document"]
        cases = []
        many_blocks = copy.deepcopy(base)
        many_blocks["blocks"] *= 65
        cases.append(many_blocks)
        many_runs = copy.deepcopy(base)
        many_runs["blocks"][0]["runs"] *= 65
        cases.append(many_runs)
        long_run = copy.deepcopy(base)
        long_run["blocks"][0]["runs"][0]["text"] = "x" * 4097
        cases.append(long_run)
        long_document = copy.deepcopy(base)
        long_document["blocks"] = [{"type": "paragraph", "runs": [{"type": "text", "text": "x" * 4096}],
                                     "separator_after": ""} for _ in range(5)]
        long_document["canonical_text"] = "x" * (4096 * 5)
        cases.append(long_document)
        nested = copy.deepcopy(base)
        nested["blocks"][0]["runs"][0]["text"] = {"nested": "x"}
        cases.append(nested)
        for document in cases:
            with self.subTest(case=len(cases)), self.assertRaises(contract.ReviewDisplayContractError):
                contract.validate_document(document)

    def test_unicode_and_whitespace_are_not_normalized(self):
        source = "e\u0301 **😀** \n끝"
        document = contract.compile_paragraph(source)
        self.assertEqual(document["canonical_text"], "e\u0301 😀 \n끝")
        self.assertNotEqual(document["canonical_text"], "é 😀 \n끝")
        self.assertEqual(contract.flatten_document(document), "e\u0301 😀 \n끝")

    def test_invalid_character_and_strong_edges_reject_or_literal(self):
        for source in ("x\rnext", "x\x00next", "x\ud800"):
            with self.subTest(source=repr(source)), self.assertRaises(contract.ReviewDisplayContractError):
                contract.compile_paragraph(source)
        for source in ("** leading**", "**trailing **", "****"):
            self.assertEqual(contract.parse_inline_strong(source), [{"type": "text", "text": source}])

    def test_compatibility_preserves_every_block_run_and_separator_exactly(self):
        blocks = [
            {"type": "heading", "runs": [{"type": "text", "text": "  제목"}], "separator_after": "\n\n"},
            {"type": "paragraph", "runs": [{"type": "strong", "text": "체결 기록"}, {"type": "text", "text": "을 확인합니다.\n다음 줄  "}], "separator_after": "\n\n"},
            {"type": "list_item", "runs": [{"type": "text", "text": "1) 첫 항목"}], "separator_after": "\n"},
            {"type": "list_item", "runs": [{"type": "text", "text": "2) 둘째 항목"}], "separator_after": "\n\t "},
        ]
        expected = "  제목\n\n체결 기록을 확인합니다.\n다음 줄  \n\n1) 첫 항목\n2) 둘째 항목\n\t "
        document = {"schema_version": contract.SCHEMA_VERSION, "surface": "body", "blocks": blocks, "canonical_text": expected}
        before = copy.deepcopy(document)
        self.assertEqual(expected, contract.serialize_compatibility_summary(document))
        self.assertEqual(before, document)

    def test_compatibility_whitespace_and_newline_edges_are_not_trimmed(self):
        for source in (" \t\n", "\n첫 줄\n\n끝\n", " e\u0301 😀 ", "**literal** [link](url)"):
            document = contract.compile_literal_text(source)
            self.assertEqual(source, contract.serialize_compatibility_summary(document))

    def test_compatibility_rejects_raw_semantics_summary_and_wrong_surface(self):
        for value in ("raw summary", {"summary": "raw summary"}, {"structured_review": {}}, None):
            with self.subTest(value=value), self.assertRaises(contract.ReviewDisplayContractError):
                contract.serialize_compatibility_summary(value)
        document = contract.compile_paragraph("체결 기록")
        document["canonical_text"] = "tampered"
        with self.assertRaises(contract.ReviewDisplayContractError):
            contract.serialize_compatibility_summary(document)
        document = contract.compile_paragraph("체결 기록")
        document["surface"] = "chart_card"
        with self.assertRaises(contract.ReviewDisplayContractError):
            contract.serialize_compatibility_summary(document)

    def test_compatibility_has_no_markdown_or_semantic_reassembly(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(contract.serialize_compatibility_summary))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertEqual(["validate_document"], [node.func.id for node in calls])
        self.assertEqual(1, len(inspect.signature(contract.serialize_compatibility_summary).parameters))

    def test_compatibility_string_survives_document_mutation(self):
        source = "체결 기록을 확인합니다.\n "
        document = contract.compile_literal_text(source)
        summary = contract.serialize_compatibility_summary(document)
        document["canonical_text"] = "changed"
        document["blocks"][0]["runs"][0]["text"] = "changed"
        document["blocks"][0]["separator_after"] = "\n\n"
        self.assertEqual(source, summary)
