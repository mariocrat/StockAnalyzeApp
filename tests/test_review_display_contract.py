"""Fixed cross-language review-display.v1 vectors under the H4 boundary."""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import copy
import json
from pathlib import Path
import unittest

from backend.core import review_display_contract as contract

from tests import review_display_v2_reference as ref

_FIXTURES = Path(__file__).resolve().parents[1] / "frontend/scripts/fixtures"
V2 = json.loads((_FIXTURES / "review-display-v2-vectors.json").read_text(encoding="utf-8"))
V2_SCHEMA = json.loads((_FIXTURES / "review-display-v2.schema.json").read_text(encoding="utf-8"))


def witness_for(identity):
    return next(w for w in V2["witnesses"] if w["id"] == identity)


def text_paths(value, path):
    if type(value) is str:
        yield path
    elif type(value) is dict:
        for key, child in value.items():
            yield from text_paths(child, (*path, key))
    elif type(value) is list:
        for i, child in enumerate(value):
            yield from text_paths(child, (*path, i))



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

    def test_v2_shared_documents_and_negative_mutations(self):
        for witness in V2["witnesses"]:
            with self.subTest(witness=witness["id"]):
                ref.validate_v2(witness["expected_v2"], V2_SCHEMA)
                # Slice 1 must not make the production v1 validator accept v2.
                with self.assertRaises(contract.ReviewDisplayContractError):
                    contract.validate_document(witness["expected_v2"])
        for vector in V2["invalid_documents"]:
            with self.subTest(vector=vector["id"]), self.assertRaises(ValueError):
                ref.validate_v2(ref.mutate(witness_for(vector["base"])["expected_v2"],
                                          vector["mutations"]), V2_SCHEMA)
        base = V2["witnesses"][0]["expected_v2"]
        for text in ("x" * 4097, chr(0xD800), "x\r"):
            doc = copy.deepcopy(base)
            doc["blocks"][0]["runs"][0]["text"] = text
            doc["canonical_text"] = ref.flatten(doc)
            with self.assertRaises(ValueError):
                ref.validate_v2(doc, V2_SCHEMA)
        doc = copy.deepcopy(base)
        doc["blocks"][0]["runs"][0]["text"] = "e\u0301 😀"
        doc["canonical_text"] = ref.flatten(doc)
        self.assertEqual(ref.validate_v2(doc, V2_SCHEMA), doc)

    def test_v2_atomic_bundle_and_corruption_vectors(self):
        for witness in V2["witnesses"]:
            for kind in ("v1_only", "paired_v1_v2"):
                bundle = ref.make_bundle(witness, kind)
                ref.validate_bundle(bundle, witness, V2_SCHEMA, contract.validate_document)
        for vector in V2["invalid_bundles"]:
            witness = witness_for(vector["base"])
            with self.subTest(vector=vector["id"]), self.assertRaises(ValueError):
                ref.validate_bundle(ref.mutate(ref.make_bundle(witness), vector["mutations"]),
                                    witness, V2_SCHEMA, contract.validate_document)
        # No semantic reconstruction is needed for a previously admitted v1-only body.
        witness = V2["witnesses"][0]
        for status in ("ready", "missing_key", "error", "empty"):
            bundle = ref.make_bundle(witness, "v1_only")
            bundle["status"] = status
            ref.validate_bundle(bundle, witness, V2_SCHEMA, contract.validate_document)

    def test_v2_witnesses_match_existing_v1_compiler_and_source_coverage(self):
        from backend.core.review_legacy_compatibility import admit_legacy_body
        for witness in V2["witnesses"]:
            source = witness["source"]
            doc, coverage = contract.compile_structured_review(source)
            self.assertEqual(doc, witness["expected_v1"], witness["id"])
            self.assertEqual(admit_legacy_body(doc).summary, witness["expected_summary"])
            bindings = witness["bindings"]
            self.assertEqual([b["block_id"] for b in bindings],
                             [b["id"] for b in witness["expected_v2"]["blocks"]])
            expected_paths = set(text_paths(source["summary"], ("summary",)))
            expected_paths |= set(text_paths(source[source["review_type"]], (source["review_type"],)))
            expected_paths -= {("summary", "data_confidence", "level")}
            expected_paths = {p for p in expected_paths if p[-1] != "phase"}
            actual_paths = {tuple(b["source_path"]) for b in bindings if b["source_path"][0] != "objective"}
            self.assertEqual(actual_paths, expected_paths)
            # v1 compiler covers model paths, with phase enums mapped to labels;
            # confidence/missing are backend-derived literals in the v1 compiler.
            model_paths = {p for p in expected_paths if p[:2] not in
                           (("summary", "data_confidence"), ("summary", "missing_information"))}
            phases = {p for p in text_paths(source[source["review_type"]], (source["review_type"],))
                      if p[-1] == "phase"}
            self.assertEqual(set(coverage), model_paths | phases)
            for binding in bindings:
                value = ref.at(source, binding["source_path"])
                block = next(b for b in witness["expected_v2"]["blocks"] if b["id"] == binding["block_id"])
                text = "".join(r["text"] for r in block["runs"])
                expected = (f"{value:+,.0f}원" if binding["source_path"][-1] == "realized_pnl"
                            else f"{value:+.2f}%" if binding["source_path"][-1] == "realized_return_pct"
                            else value)
                self.assertEqual(text, expected)

    def test_v2_whole_document_identity_and_independent_confidence(self):
        for witness in V2["witnesses"]:
            doc = witness["expected_v2"]
            quality = doc["sections"][1]
            self.assertEqual(quality["confidence"]["level"], witness["source"]["summary"]["data_confidence"]["level"])
            self.assertEqual(len(quality["missing_information"]), len(witness["source"]["summary"]["missing_information"]))
        witness = V2["witnesses"][0]
        changed = copy.deepcopy(witness["expected_v2"])
        changed["sections"][1]["confidence"]["level"] = "low"
        ref.validate_v2(changed, V2_SCHEMA)  # shape valid; same text is NOT same approval
        self.assertEqual(changed["canonical_text"], witness["expected_v2"]["canonical_text"])
        self.assertNotEqual(ref.stable(changed), ref.stable(witness["expected_v2"]))
        bundle = ref.make_bundle(witness)
        bundle["representations"]["v2"]["document"] = changed
        with self.assertRaises(ValueError):
            ref.validate_bundle(bundle, witness, V2_SCHEMA, contract.validate_document)

    def test_v2_replay_generation_and_expiry_contract(self):
        witness = V2["witnesses"][0]
        args = dict(witness=witness, schema=V2_SCHEMA, validate_v1=contract.validate_document)
        for row in V2["replay"]:
            trace = []
            result = ref.replay(capability=row["capability"], record=ref.make_bundle(witness, row["kind"]),
                                trace=trace, **args)
            self.assertEqual(result["version"], row["expected"])
            self.assertEqual([result[k] for k in ("ai", "charge", "history_insert")], [0, 0, 0])
            self.assertEqual(trace, ["capability_gate", "execution_identity", "bundle_validation",
                                     "representation_selection", "projection"])
        for capability in ("v3", "", "v1,dual", ["v1", "dual"], None):
            trace = []
            with self.assertRaises(ValueError):
                ref.replay(capability=capability, record=None, trace=trace, **args)
            self.assertEqual(trace, ["capability_gate"])
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            ref.replay(capability="dual", record=ref.make_bundle(witness), same_body=False, **args)
        self.assertEqual(ref.replay(capability="dual", record=None, **args),
                         {"kind": "new_execution_requires_normal_gates"})
        for vector in V2["invalid_bundles"]:
            record = ref.mutate(ref.make_bundle(witness_for(vector["base"])), vector["mutations"])
            for capability in ("v1", "dual"):
                trace = []
                with self.assertRaises(ValueError):
                    ref.replay(capability=capability, record=record, trace=trace,
                               **{**args, "witness": witness_for(vector["base"])})
                self.assertNotIn("projection", trace)
        for row in V2["generation"]:
            self.assertEqual(ref.generation(row), row["expected"])
