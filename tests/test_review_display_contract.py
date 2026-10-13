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
            with self.subTest(vector=vector["id"]), self.assertRaises(ref.ReferenceContractError) as raised:
                ref.validate_v2(ref.mutate(witness_for(vector["base"])["expected_v2"],
                                          vector["mutations"]), V2_SCHEMA)
            self.assertEqual(raised.exception.code, V2["expected_errors"][vector["id"]])
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
            with self.subTest(vector=vector["id"]), self.assertRaises(ref.ReferenceContractError) as raised:
                ref.validate_bundle(ref.mutate(ref.make_bundle(witness), vector["mutations"]),
                                    witness, V2_SCHEMA, contract.validate_document)
            self.assertEqual(raised.exception.code, V2["expected_errors"][vector["id"]])
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

def ready_v2_source(identity="basic-high", level="high"):
    from backend.core import review_source_contract as src
    w = witness_for(identity)
    value = w["source"]
    t = value["review_type"]
    semantic = {key: value["summary"][key] for key in ("decision_quality", "main_issue", "next_action")}
    semantic.update(copy.deepcopy(value[t]))
    memo = "손절 조건과 매도 조건 기록" if level != "medium" else "손절 조건 기록"
    trades = tuple(src.admit_trade_source(dict(trade_date=date, ticker="005930", name="합성테스트",
                   side=side, price=price, quantity=300, fee=0, tax=0, memo=memo, source="synthetic"))
                   for date, side, price in ((value["objective"]["period"]["first_trade_date"], "buy", 7000),
                                            (value["objective"]["period"]["last_trade_date"], "sell", 7100)))
    contexts = ()
    if level != "low":
        contexts = (src.admit_analysis_context_source(dict(trade_id=None, date="2026-01-02T09:10",
            market_date="2026-01-02", ticker="005930", name="합성테스트", side="buy", price=7000,
            quantity=300, memo=memo, close=7000, **{k: None for k in (
                "price_vs_close_pct", "ma5", "ma20", "ma60", "rsi14", "volume_ratio_20d",
                "return_10d_before", "position_in_20d_range", "next_5d_return", "next_20d_return")})),)
    return src.compose_review_source(review_type=t, trades=trades,
        objective=src.admit_objective_source(copy.deepcopy(value["objective"])),
        analysis_contexts=contexts, semantic=src.admit_semantic_source(semantic, t), status="ready", origin="openai")


class ReviewDisplayV2ProductionTest(unittest.TestCase):
    def reject(self, call, code):
        from backend.core.review_display_v2_contract import ReviewDisplayV2Error
        with self.assertRaises(ReviewDisplayV2Error) as raised:
            call()
        self.assertEqual(raised.exception.code, code)

    def test_shared_valid_documents_match_reference_admission(self):
        from backend.core.review_display_v2_contract import validate_document
        for w in V2["witnesses"]:
            before = copy.deepcopy(w["expected_v2"])
            self.assertEqual(validate_document(before), ref.validate_v2(before, V2_SCHEMA)["canonical_text"])
            self.assertEqual(before, w["expected_v2"])

    def test_all_document_negative_codes_and_fixture_restoration(self):
        from backend.core.review_display_v2_contract import validate_document
        for v in V2["invalid_documents"]:
            w = witness_for(v["base"])
            before = copy.deepcopy(w)
            malformed = ref.mutate(w["expected_v2"], v["mutations"])
            with self.subTest(vector=v["id"]):
                self.reject(lambda: validate_document(malformed), V2["expected_errors"][v["id"]])
                with self.assertRaises(ref.ReferenceContractError) as error:
                    ref.validate_v2(malformed, V2_SCHEMA)
                self.assertEqual(error.exception.code, V2["expected_errors"][v["id"]])
            self.assertEqual(before, w)

    def test_all_bundle_negative_codes_match_reference_and_fixed_outputs(self):
        from backend.core.review_approval_bundle import _validate_candidate
        for v in V2["invalid_bundles"]:
            w = witness_for(v["base"])
            base = ref.make_bundle(w)
            before = copy.deepcopy(base)
            malformed = ref.mutate(base, v["mutations"])
            with self.subTest(vector=v["id"]):
                self.reject(lambda: _validate_candidate(malformed, base), V2["expected_errors"][v["id"]])
                with self.assertRaises(ref.ReferenceContractError) as error:
                    ref.validate_bundle(malformed, w, V2_SCHEMA, contract.validate_document)
                self.assertEqual(error.exception.code, V2["expected_errors"][v["id"]])
            self.assertEqual(base, before)
        self.assertEqual(set(V2["expected_errors"]), {v["id"] for v in V2["invalid_documents"] + V2["invalid_bundles"]})

    def test_internal_mapping_kernel_matches_three_fixed_v2_goldens(self):
        from backend.core.review_display_v2_compiler import _compile_projected
        for w in V2["witnesses"]:
            doc, coverage = _compile_projected(copy.deepcopy(w["source"]))
            self.assertEqual(doc, w["expected_v2"], w["id"])
            self.assertIn(("objective", "result", "realized_pnl"), coverage)
            self.assertIn(("summary", "data_confidence", "level"), coverage)

    def test_admitted_compiler_preserves_objective_and_quality_for_both_types(self):
        from backend.core.review_display_v2_compiler import compile_body
        from backend.core.review_source_projection import structured_review_payload
        for identity in ("basic-high", "advanced-low"):
            for level in ("high", "medium", "low"):
                source = ready_v2_source(identity, level)
                projected = structured_review_payload(source)
                doc = compile_body(source)
                self.assertEqual(doc["blocks"][0]["runs"][0]["text"], "+29,967원")
                self.assertEqual(doc["blocks"][1]["runs"][0]["text"], "+1.33%")
                quality = doc["sections"][1]
                self.assertEqual(quality["confidence"]["level"], level)
                self.assertEqual(len(quality["missing_information"]), len(projected["summary"]["missing_information"]))
                self.assertEqual(len(quality["missing_information"]), 1 if level == "medium" else 0)
                self.assertEqual(source.objective.result.weighted_buy_price, 7000)
        from backend.core import review_source_contract as src
        from backend.core.review_source_projection import objective_payload
        from backend.core.review_approval_bundle import compile_approval_bundle
        original = ready_v2_source()
        objective = objective_payload(original.objective)
        objective["result"].update(realized_pnl=0, realized_return_pct=0,
                                   weighted_buy_price=None, weighted_sell_price=None)
        zero = src.compose_review_source(review_type="basic", trades=original.trades,
            objective=src.admit_objective_source(objective), analysis_contexts=original.analysis_contexts,
            semantic=original.semantic, status="ready", origin="openai")
        body = compile_body(zero)
        self.assertEqual(body["blocks"][0]["runs"][0]["text"], "+0원")
        self.assertEqual(body["blocks"][1]["runs"][0]["text"], "+0.00%")
        self.assertIsNone(zero.objective.result.weighted_buy_price)
        self.assertNotEqual(compile_approval_bundle(zero).document["objective_identity"],
                            compile_approval_bundle(original).document["objective_identity"])

    def test_optional_collections_and_deterministic_dictionary_order(self):
        from backend.core import review_source_contract as src
        from backend.core.review_source_projection import semantic_payload
        from backend.core.review_display_v2_compiler import compile_body
        source = ready_v2_source("advanced-low")
        semantic = semantic_payload(source.semantic)
        semantic.update(detailed_analysis=[], reflection_questions=[])
        semantic["entry_review"]["uncertainty"] = []
        first = src.finish_review_source(source, semantic=src.admit_semantic_source(semantic, "advanced"),
                                         status="ready", origin="openai")
        second = src.finish_review_source(source, semantic=src.admit_semantic_source(
            dict(reversed(list(semantic.items()))), "advanced"), status="ready", origin="openai")
        doc = compile_body(first)
        self.assertEqual(doc, compile_body(first))
        self.assertEqual(doc, compile_body(second))
        empty_roles = {s["role"] for s in doc["sections"] if s["block_ids"] == []}
        self.assertEqual(empty_roles, {"detailed_analysis", "reflection_questions"})

    def test_ready_gate_rejects_fallback_error_empty_and_unavailable(self):
        from backend.core import review_source_contract as src
        from backend.core.review_display_v2_compiler import compile_body
        from backend.core.review_approval_bundle import compile_approval_bundle
        original = ready_v2_source()
        for status in ("missing_key", "error"):
            source = src.finish_review_source(original, semantic=original.semantic, status=status, origin="chart-rules")
            self.reject(lambda: compile_body(source), "UNSUPPORTED_V2_SOURCE")
            self.reject(lambda: compile_approval_bundle(source), "UNSUPPORTED_V2_SOURCE")
        empty = src.compose_review_source(review_type="basic", trades=(),
            objective=src.admit_objective_source(dict(kind="unavailable", reason="no_trades")),
            status="empty", origin="none")
        for source in (empty, src.unavailable_review_source("basic")):
            self.reject(lambda: compile_body(source), "UNSUPPORTED_V2_SOURCE")
        with self.assertRaises(TypeError):
            compile_body({})

    def test_v1_output_unchanged_and_pair_provenance_complete(self):
        from backend.core.review_body_compiler import compile_review_body
        from backend.core.review_approval_bundle import compile_approval_bundle, validate_bundle
        from backend.core.review_legacy_compatibility import admit_legacy_body
        for name in ("basic-high", "advanced-low"):
            source = ready_v2_source(name)
            original = compile_review_body(source)
            approval = compile_approval_bundle(source)
            bundle = approval.document
            self.assertEqual(bundle["representations"]["v1"]["document"], original)
            self.assertEqual(bundle["representations"]["v1"]["summary"], admit_legacy_body(original).summary)
            self.assertNotEqual(original["canonical_text"], bundle["representations"]["v2"]["document"]["canonical_text"])
            for rep in bundle["representations"].values():
                self.assertEqual(rep["source_identity"], bundle["source_identity"])
                self.assertEqual(rep["objective_identity"], bundle["objective_identity"])
            validate_bundle(bundle, approval=approval)

    def test_real_approval_corruption_rejects_without_recompilation(self):
        from unittest.mock import patch
        from backend.core import review_approval_bundle as bundle
        source = ready_v2_source()
        approval = bundle.compile_approval_bundle(source)
        for v in V2["invalid_bundles"]:
            malformed = ref.mutate(approval.document, v["mutations"])
            with self.subTest(vector=v["id"]), patch.object(bundle, "compile_body", side_effect=AssertionError("read compiler")):
                self.reject(lambda: bundle.validate_bundle(malformed, approval=approval), V2["expected_errors"][v["id"]])

    def test_atomic_failures_allocate_no_partial_approval(self):
        from unittest.mock import patch
        from backend.core import review_approval_bundle as bundle
        from backend.core.review_display_v2_compiler import compile_body
        source = ready_v2_source()
        for name in ("compile_review_body", "compile_body"):
            with patch.object(bundle, name, side_effect=RuntimeError("programming failure")), patch.object(bundle, "_allocate") as allocate:
                with self.assertRaisesRegex(RuntimeError, "programming failure"):
                    bundle.compile_approval_bundle(source)
                allocate.assert_not_called()
        bad = compile_body(source)
        bad["sections"][1]["confidence"]["level"] = "low"
        with patch.object(bundle, "compile_body", return_value=bad), patch.object(bundle, "_allocate") as allocate:
            self.reject(lambda: bundle.compile_approval_bundle(source), "COMPILER_OUTPUT_MISMATCH")
            allocate.assert_not_called()

    def test_approval_alias_copy_restore_and_owner_mutation(self):
        import pickle
        from backend.core import review_approval_bundle as bundle
        source = ready_v2_source()
        approval = bundle.compile_approval_bundle(source)
        digest, before = approval.digest, approval.json_text
        copy_value = approval.document
        copy_value["representations"]["v2"]["document"]["blocks"][0]["runs"][0]["text"] = "changed"
        self.assertEqual(approval.json_text, before)
        self.assertEqual(approval.digest, digest)
        for call in (lambda: bundle.ApprovedReviewBundle(), lambda: copy.copy(approval),
                     lambda: copy.deepcopy(approval), lambda: pickle.dumps(approval)):
            with self.assertRaises(TypeError):
                call()
        with self.assertRaises(AttributeError):
            approval._json = b"changed"
        fake = object.__new__(bundle.ApprovedReviewBundle)
        self.reject(lambda: bundle.validate_bundle(approval.document, approval=fake), "INVALID_APPROVAL")
        original = source.objective.result.weighted_buy_price
        try:
            object.__setattr__(source.objective.result, "weighted_buy_price", 1234)
            self.reject(lambda: bundle.validate_bundle(copy_value, approval=approval), "SOURCE_MUTATION")
        finally:
            object.__setattr__(source.objective.result, "weighted_buy_price", original)
        # Tampering must also fail when the attacker recomputes the local digest.
        tampered = bundle.compile_approval_bundle(source)
        payload = tampered.document
        payload["representations"]["v2"]["document"]["sections"][1]["confidence"]["level"] = "low"
        encoded = bundle.encode(payload)
        object.__setattr__(tampered, "_json", encoded)
        object.__setattr__(tampered, "_digest", bundle._digest(encoded, tampered._source, tampered._objective))
        self.reject(lambda: bundle.validate_bundle(payload, approval=tampered), "APPROVAL_MUTATION")
        from backend.core.review_display_v2_compiler import compile_body
        cyclic = ready_v2_source()
        object.__setattr__(cyclic.semantic.lesson, "concept", cyclic.semantic)
        self.reject(lambda: compile_body(cyclic), "INVALID_SOURCE")
        mutable = ready_v2_source()
        object.__setattr__(mutable.semantic, "good_points", list(mutable.semantic.good_points))
        self.reject(lambda: compile_body(mutable), "INVALID_SOURCE")

    def test_legitimate_v1_only_wrap_has_no_upgrade_or_source_reconstruction(self):
        from unittest.mock import patch
        from backend.core import review_approval_bundle as bundle
        from backend.core.review_envelope_compiler import compile_review_envelope, seal_review_envelope
        from backend.core import review_source_contract as src
        source = ready_v2_source()
        variants = [source, src.finish_review_source(source, semantic=source.semantic, status="missing_key", origin="chart-rules"),
                    src.compose_review_source(review_type="basic", trades=(),
                        objective=src.admit_objective_source(dict(kind="unavailable", reason="no_trades")),
                        status="empty", origin="none"), src.unavailable_review_source("basic")]
        for item in variants:
            snapshot = seal_review_envelope(compile_review_envelope(item))
            with patch.object(bundle, "compile_body", side_effect=AssertionError("no upgrade")):
                approval = bundle.approve_v1_only(snapshot)
            self.assertEqual(set(approval.document["representations"]), {"v1"})
            self.assertEqual(approval.document["status"], item.status)
            bundle.validate_bundle(approval.document, approval=approval)

    def test_unicode_resource_bounds_and_programming_errors_are_distinct(self):
        from backend.core.review_display_v2_contract import validate_document
        base = V2["witnesses"][0]["expected_v2"]
        for text in ("x" * 4097, chr(0xD800)):
            doc = copy.deepcopy(base)
            doc["blocks"][0]["runs"][0]["text"] = text
            doc["canonical_text"] = ref.flatten(doc)
            self.reject(lambda: validate_document(doc), "LIMIT_EXCEEDED" if len(text) > 4096 else "INVALID_UNICODE")
        doc = copy.deepcopy(base)
        doc["blocks"] *= 65
        self.reject(lambda: validate_document(doc), "LIMIT_EXCEEDED")
        doc = copy.deepcopy(base)
        doc["blocks"][0]["runs"][0]["text"] = "e\u0301 😀"
        doc["canonical_text"] = ref.flatten(doc)
        self.assertEqual(validate_document(doc), doc["canonical_text"])
        from backend.core.review_display_v2_compiler import compile_body
        with self.assertRaises(TypeError):
            compile_body(None)

    def test_new_pure_modules_are_absent_from_existing_runtime_import_graph(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        names = {"review_display_v2_contract", "review_display_v2_compiler", "review_approval_bundle",
                 "review_history_json_codec", "review_durable_storage_contract", "review_durable_storage_approval"}
        storage = {"review_history", "review_history_adapter", "review_history_paired"}
        durable = {"review_history_json_codec", "review_durable_storage_contract", "review_durable_storage_approval"}
        for path in (root / "backend").rglob("*.py"):
            if path.stem in names:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse((node.module or "").startswith(("tests", "frontend")), path)
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            allowed = durable if path.stem in storage else set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[-1], names - allowed, path)
                    self.assertFalse(any(alias.name in names - allowed for alias in node.names), path)
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.split(".")[-1] in names - allowed for alias in node.names), path)
