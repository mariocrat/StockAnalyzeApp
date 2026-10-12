"""Pure v2 compilation from admitted immutable source DTOs; no request wiring."""
from dataclasses import fields, is_dataclass
import hashlib
import json

from backend.core.review_display_contract import parse_inline_strong
from backend.core.review_display_v2_contract import (
    SCHEMA_VERSION, ReviewDisplayV2Error, require, validate_document,
)
from backend.core.review_source_contract import (
    ValidatedReviewSource, ObjectiveSource, UnavailableObjectiveSource, SourceAdmissionError, admit_review_source,
    unavailable_review_source,
)
from backend.core.review_source_projection import (
    trade_payload, chart_payload, context_payload, objective_payload, semantic_payload,
    structured_review_payload,
)

COMPILER_VERSION = "review-body.v2.0"
_JSON = dict(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def encode(value):
    # Encoding errors are not silently reported as successful display admission.
    try:
        return json.dumps(value, **_JSON).encode("utf-8")
    except (ValueError, UnicodeError, OverflowError, RecursionError) as error:
        raise ReviewDisplayV2Error("INVALID_JSON") from error


def capture_source(source):
    """Recheck admitted DTO fields without accepting a raw dict or normalizing a change.

    The existing admission factories validate every nested variant. Compare
    type-preserving serialized DTO values after their round trip: trimming,
    coercion or a damaged factory-only DTO cannot disappear in a projection.
    """
    if type(source) is not ValidatedReviewSource:
        raise TypeError("expected ValidatedReviewSource")
    try:
        before = encode(_dto_tree(source))
        raw = dict(review_type=source.review_type, status=source.status, origin=source.origin,
                   trades=[trade_payload(t) for t in source.trades],
                   objective=({"kind": source.objective.kind, "reason": source.objective.reason}
                              if type(source.objective) is UnavailableObjectiveSource
                              else objective_payload(source.objective)),
                   charts=[chart_payload(c) for c in source.charts],
                   analysis_contexts=[context_payload(c) for c in source.analysis_contexts],
                   semantic=None if source.semantic is None else semantic_payload(source.semantic),
                   has_market_data=source.has_market_data, notice=source.notice)
        checked = (unavailable_review_source(source.review_type) if source.status == "error" and not source.trades
                   else admit_review_source(raw))
        require(encode(_dto_tree(checked)) == before, "INVALID_SOURCE")
        require(encode(_dto_tree(source)) == before, "SOURCE_MUTATION")
    except (AttributeError, SourceAdmissionError) as error:
        raise ReviewDisplayV2Error("INVALID_SOURCE") from error
    return before


def _dto_tree(value, _active=None, _depth=0):
    if type(value) in (str, int, float, bool, type(None)):
        return value
    require(_depth <= 32, "INVALID_SOURCE")
    active = set() if _active is None else _active
    require(id(value) not in active, "INVALID_SOURCE")
    active.add(id(value))
    try:
        if type(value) is tuple:
            return [_dto_tree(child, active, _depth + 1) for child in value]
        require(is_dataclass(value) and type(value).__module__ == ValidatedReviewSource.__module__, "INVALID_SOURCE")
        return {"dto": type(value).__name__, "fields": {
            field.name: _dto_tree(getattr(value, field.name), active, _depth + 1) for field in fields(value)}}
    finally:
        active.remove(id(value))


def require_ready(source):
    require(source.status == "ready" and source.origin == "openai" and source.semantic is not None
            and type(source.objective) is ObjectiveSource, "UNSUPPORTED_V2_SOURCE")


def text_leaf_paths(value, path=()):
    if type(value) is str:
        yield path
    elif type(value) is dict:
        for key, child in value.items():
            yield from text_leaf_paths(child, (*path, key))
    elif type(value) is list:
        for i, child in enumerate(value):
            yield from text_leaf_paths(child, (*path, i))


class _Body:
    def __init__(self, structured):
        self.structured = structured
        self.blocks = []
        self.sections = []
        self.covered = set()

    def block(self, path, *, formatted=None):
        value = self.structured
        for key in path:
            value = value[key]
        if formatted is None:
            require(type(value) is str, "INVALID_SOURCE")
            runs = parse_inline_strong(value)
        else:
            runs = [{"type": "text", "text": formatted}]
        identity = "b" + str(len(self.blocks))
        self.blocks.append(dict(id=identity, type="paragraph", runs=runs, separator_after="\n\n"))
        self.covered.add(path)
        return identity

    def quality(self, path):
        return dict(label=self.block((*path, "label")), explanation=self.block((*path, "explanation")))

    def card(self, path):
        return dict(title=self.block((*path, "title")), detail=self.block((*path, "detail")))

    def refs(self, path):
        value = self.structured
        for key in path:
            value = value[key]
        return [self.block((*path, i)) for i in range(len(value))]

    def section(self, role, start, **fields):
        self.sections.append(dict(role=role, block_ids=[b["id"] for b in self.blocks[start:]], **fields))


def _compile_projected(structured):
    """Internal mapping kernel; public compilation first captures an admitted DTO."""
    body = _Body(structured)
    t = structured["review_type"]
    result = structured["objective"]["result"]
    # Do not substitute zero for unavailable/null. The ready source gate requires
    # a real ObjectiveSource; its nullable average prices remain in the receipt.
    pnl, rate = result["realized_pnl"], result["realized_return_pct"]
    objective = dict(realized_pnl=body.block(("objective", "result", "realized_pnl"), formatted=f"{pnl:+,.0f}원"),
                     realized_return_pct=body.block(("objective", "result", "realized_return_pct"), formatted=f"{rate:+.2f}%"))
    body.section("summary", 0, objective=objective, decision_quality=body.quality(("summary", "decision_quality")),
                 main_issue=body.block(("summary", "main_issue")), next_action=body.block(("summary", "next_action")))
    start = len(body.blocks)
    confidence = structured["summary"]["data_confidence"]
    body.covered.add(("summary", "data_confidence", "level"))
    body.section("data_quality", start, confidence=dict(level=confidence["level"],
                 label=body.block(("summary", "data_confidence", "label")),
                 reasons=body.refs(("summary", "data_confidence", "reasons"))),
                 missing_information=body.refs(("summary", "missing_information")))
    content = structured[t]
    if t == "basic":
        start = len(body.blocks)
        items = [body.card((t, "good_points", i)) for i in range(len(content["good_points"]))]
        body.section("good_points", start, items=items)
        start = len(body.blocks)
        body.section("main_improvement", start, **body.card((t, "main_improvement")))
        start = len(body.blocks)
        items = []
        for i, check in enumerate(content["next_trade_checks"]):
            body.covered.add((t, "next_trade_checks", i, "phase"))
            items.append(dict(phase=check["phase"], text=body.block((t, "next_trade_checks", i, "text"))))
        body.section("next_trade_checks", start, items=items)
    else:
        start = len(body.blocks)
        body.section("entry_review", start, assessment=body.quality((t, "entry_review", "assessment")),
                     evidence=body.refs((t, "entry_review", "evidence")),
                     uncertainty=body.refs((t, "entry_review", "uncertainty")),
                     invalidation=body.block((t, "entry_review", "invalidation")))
        start = len(body.blocks)
        body.section("risk_review", start, planned_rule=body.block((t, "risk_review", "planned_rule")),
                     actual_response=body.block((t, "risk_review", "actual_response")),
                     assessment=body.quality((t, "risk_review", "assessment")))
        start = len(body.blocks)
        body.section("exit_review", start, profit_taking_assessment=body.block((t, "exit_review", "profit_taking_assessment")),
                     trend_exit_assessment=body.block((t, "exit_review", "trend_exit_assessment")),
                     explanation=body.block((t, "exit_review", "explanation")))
        start = len(body.blocks)
        items = [body.card((t, "detailed_analysis", i)) for i in range(len(content["detailed_analysis"]))]
        body.section("detailed_analysis", start, items=items)
        start = len(body.blocks)
        body.section("next_trade_playbook", start, before_entry=body.refs((t, "next_trade_playbook", "before_entry")),
                     while_holding=body.refs((t, "next_trade_playbook", "while_holding")),
                     before_exit=body.refs((t, "next_trade_playbook", "before_exit")))
    start = len(body.blocks)
    lesson = dict(title=body.block((t, "lesson", "title")), concept=body.block((t, "lesson", "concept")),
                  applied_to_this_trade=body.block((t, "lesson", "applied_to_this_trade")))
    if t == "advanced":
        lesson["next_trade_application"] = body.block((t, "lesson", "next_trade_application"))
    body.section("lesson", start, **lesson)
    if t == "advanced":
        start = len(body.blocks)
        body.section("reflection_questions", start, items=body.refs((t, "reflection_questions")))
    body.blocks[-1]["separator_after"] = ""
    document = dict(schema_version=SCHEMA_VERSION, surface="body", review_type=t, blocks=body.blocks,
                    sections=body.sections, canonical_text="".join(
                        "".join(run["text"] for run in block["runs"]) + block["separator_after"] for block in body.blocks))
    expected = set(text_leaf_paths(structured["summary"], ("summary",)))
    expected.update(text_leaf_paths(structured[t], (t,)))
    expected.update({("objective", "result", "realized_pnl"), ("objective", "result", "realized_return_pct")})
    require(body.covered == expected, "SEMANTIC_COVERAGE_MISMATCH")
    validate_document(document)
    return document, frozenset(body.covered)


def compile_body(source):
    frozen = capture_source(source)
    require_ready(source)
    document, _coverage = _compile_projected(structured_review_payload(source))
    require(capture_source(source) == frozen, "SOURCE_MUTATION")
    return document


def identity(buffer):
    return hashlib.sha256(buffer).hexdigest()
