"""Pure review-display.v1 compiler and production body templates.

The document has a fixed depth: document -> blocks -> runs. All visible
separators, including list markers and final newlines, belong to the document.
Limits count Unicode code points so Python and the browser use one policy.
"""

import re


SCHEMA_VERSION = "review-display.v1"
SURFACES = frozenset({
    "body", "chart_card", "chart_header", "chart_tab", "marker_label",
    "marker_tooltip", "history_title", "trade_name", "notice",
})
BLOCK_TYPES = frozenset({"heading", "paragraph", "list_item", "divider"})
RUN_TYPES = frozenset({"text", "strong"})
MAX_BLOCKS = 64
MAX_RUNS_PER_BLOCK = 64
MAX_TOTAL_RUNS = 512
MAX_RUN_CODEPOINTS = 4096
MAX_CANONICAL_CODEPOINTS = 16384
MAX_SEPARATOR_CODEPOINTS = 16


class ReviewDisplayContractError(ValueError):
    """Unsupported or inconsistent display representation."""


def _exact_keys(value, expected, name):
    if type(value) is not dict or set(value) != expected:
        raise ReviewDisplayContractError(f"invalid {name} fields")


def _text(value, name, limit, *, allow_empty=False):
    if type(value) is not str or len(value) > limit or (not allow_empty and not value):
        raise ReviewDisplayContractError(f"invalid {name}")
    if any((code := ord(char)) < 9 or 10 < code < 32 or code == 127
           or 0xD800 <= code <= 0xDFFF for char in value):
        raise ReviewDisplayContractError(f"invalid {name} character")
    return value


def validate_document(document, *, expected_surface="body"):
    """Reject unknown fields/types, bounds, placement, and canonical mismatch."""
    _exact_keys(document, {"schema_version", "surface", "blocks", "canonical_text"}, "document")
    if (document["schema_version"] != SCHEMA_VERSION or type(document["surface"]) is not str
            or document["surface"] not in SURFACES):
        raise ReviewDisplayContractError("unsupported version or surface")
    if (type(expected_surface) is not str or expected_surface not in SURFACES
            or document["surface"] != expected_surface):
        raise ReviewDisplayContractError("display surface at wrong position")
    blocks = document["blocks"]
    if type(blocks) is not list or not 1 <= len(blocks) <= MAX_BLOCKS:
        raise ReviewDisplayContractError("invalid block count")
    pieces = []
    total_runs = 0
    visible_codepoints = 0
    for block in blocks:
        _exact_keys(block, {"type", "runs", "separator_after"}, "block")
        if type(block["type"]) is not str or block["type"] not in BLOCK_TYPES:
            raise ReviewDisplayContractError("unsupported block type")
        runs = block["runs"]
        if type(runs) is not list or not 1 <= len(runs) <= MAX_RUNS_PER_BLOCK:
            raise ReviewDisplayContractError("invalid run count")
        total_runs += len(runs)
        if total_runs > MAX_TOTAL_RUNS:
            raise ReviewDisplayContractError("too many runs")
        if block["type"] == "divider" and (len(runs) != 1 or type(runs[0]) is not dict
                                           or runs[0].get("type") != "text"):
            raise ReviewDisplayContractError("invalid divider")
        for run in runs:
            _exact_keys(run, {"type", "text"}, "run")
            if type(run["type"]) is not str or run["type"] not in RUN_TYPES:
                raise ReviewDisplayContractError("unsupported run type")
            piece = _text(run["text"], "run text", MAX_RUN_CODEPOINTS)
            visible_codepoints += len(piece)
            if visible_codepoints > MAX_CANONICAL_CODEPOINTS:
                raise ReviewDisplayContractError("canonical text too long")
            pieces.append(piece)
        separator = _text(block["separator_after"], "separator", MAX_SEPARATOR_CODEPOINTS,
                          allow_empty=True)
        if any(char not in " \t\n" for char in separator):
            raise ReviewDisplayContractError("unsupported separator")
        visible_codepoints += len(separator)
        if visible_codepoints > MAX_CANONICAL_CODEPOINTS:
            raise ReviewDisplayContractError("canonical text too long")
        pieces.append(separator)
    canonical = _text(document["canonical_text"], "canonical text", MAX_CANONICAL_CODEPOINTS)
    flattened = "".join(pieces)
    if flattened != canonical:
        raise ReviewDisplayContractError("canonical text mismatch")
    return flattened


def flatten_document(document):
    """Return the exact validated visible text sequence."""
    return validate_document(document)


def serialize_compatibility_summary(document):
    """Serialize body runs and their owned separators exactly, in one direction.

    The caller supplies the approved canonical body. Strong is presentation
    metadata, so its text is emitted without Markdown markers. Validation
    rejects inconsistent documents; no semantic/raw-summary fallback exists.
    """
    return validate_document(document, expected_surface="body")


def parse_inline_strong(source):
    """Parse only nonnested **text** pairs; ambiguous markup stays wholly literal.

    Strong content must be nonempty and have no edge whitespace. An unclosed
    marker, a lone asterisk, or unsupported nested/link/code markup keeps the
    whole source as one text run. No trim or Unicode normalization is applied.
    """
    _text(source, "inline source", MAX_RUN_CODEPOINTS)
    literal = [{"type": "text", "text": source}]
    if "*" not in source or "__" in source or "`" in source or re.search(r"!?\[[^\]]+\]\([^)]*\)", source):
        return literal
    runs = []
    cursor = 0
    while cursor < len(source):
        opened = source.find("**", cursor)
        if opened < 0:
            tail = source[cursor:]
            if "*" in tail:
                return literal
            if tail:
                runs.append({"type": "text", "text": tail})
            break
        plain = source[cursor:opened]
        if "*" in plain:
            return literal
        if plain:
            runs.append({"type": "text", "text": plain})
        closed = source.find("**", opened + 2)
        if closed < 0:
            return literal
        content = source[opened + 2:closed]
        if not content or "*" in content or content[0].isspace() or content[-1].isspace():
            return literal
        runs.append({"type": "strong", "text": content})
        cursor = closed + 2
    return runs


def compile_paragraph(source):
    """Build one paragraph with supported model inline strong spans."""
    runs = parse_inline_strong(source)
    document = {"schema_version": SCHEMA_VERSION, "surface": "body",
                "blocks": [{"type": "paragraph", "runs": runs, "separator_after": ""}],
                "canonical_text": "".join(run["text"] for run in runs)}
    validate_document(document)
    return document


def compile_literal_text(source):
    """Adapt already-visible legacy or user text without parsing markup."""
    _text(source, "literal source", MAX_CANONICAL_CODEPOINTS)
    runs = [{"type": "text", "text": source[index:index + MAX_RUN_CODEPOINTS]}
            for index in range(0, len(source), MAX_RUN_CODEPOINTS)]
    document = {"schema_version": SCHEMA_VERSION, "surface": "body",
                "blocks": [{"type": "paragraph", "runs": runs, "separator_after": ""}],
                "canonical_text": source}
    validate_document(document)
    return document


def compile_literal_lines(lines):
    """Compile explicitly ordered backend chart/context sentences as literal text."""
    if type(lines) is not list or not lines:
        raise ReviewDisplayContractError("empty literal surface")
    blocks = []
    for line in lines:
        _text(line, "literal line", MAX_CANONICAL_CODEPOINTS)
        runs = [{"type": "text", "text": line[index:index + MAX_RUN_CODEPOINTS]}
                for index in range(0, len(line), MAX_RUN_CODEPOINTS)]
        blocks.append({"type": "paragraph", "runs": runs, "separator_after": "\n"})
    blocks[-1]["separator_after"] = ""
    document = {"schema_version": SCHEMA_VERSION, "surface": "body", "blocks": blocks,
                "canonical_text": "\n".join(lines)}
    validate_document(document)
    return document


class _BodyBuilder:
    def __init__(self, structured, separator="\n"):
        self.structured = structured
        self.separator = separator
        self.blocks = []
        self.covered_paths = set()

    def model(self, *path):
        value = self.structured
        for part in path:
            value = value[part]
        if type(value) is not str:
            raise ReviewDisplayContractError("invalid semantic text")
        self.covered_paths.add(path)
        return ("model", value)

    def mapped_phase(self, *path):
        value = self.structured
        for part in path:
            value = value[part]
        labels = {"before_entry": "진입 전", "while_holding": "보유 중", "before_exit": "매도 전"}
        if value not in labels:
            raise ReviewDisplayContractError("unknown review phase")
        self.covered_paths.add(path)
        return ("literal", labels[value])

    def line(self, *parts):
        runs = []
        for part in parts:
            kind, value = part if isinstance(part, tuple) else ("literal", part)
            if kind == "model":
                # The old UI removes these annotations, so their appearance in
                # model output cannot have a stable canonical visible meaning.
                if "[데이터 확인]" in value or "[합리적 추론]" in value:
                    raise ReviewDisplayContractError("unsupported legacy display annotation")
                new_runs = parse_inline_strong(value)
            else:
                _text(value, "template text", MAX_RUN_CODEPOINTS)
                new_runs = [{"type": "text", "text": value}]
            for run in new_runs:
                if runs and runs[-1]["type"] == run["type"] == "text" and len(runs[-1]["text"]) + len(run["text"]) <= MAX_RUN_CODEPOINTS:
                    runs[-1]["text"] += run["text"]
                else:
                    runs.append(dict(run))
        self.blocks.append({"type": "paragraph", "runs": runs, "separator_after": self.separator})

    def finish(self):
        self.blocks[-1]["separator_after"] = ""
        document = {"schema_version": SCHEMA_VERSION, "surface": "body", "blocks": self.blocks,
                    "canonical_text": "".join("".join(run["text"] for run in block["runs"]) + block["separator_after"]
                                              for block in self.blocks)}
        validate_document(document)
        return document, self.covered_paths


_CARD = {"title": str, "detail": str}
_QUALITY = {"label": str, "explanation": str}
_LESSON = {"title": str, "concept": str, "applied_to_this_trade": str}
_BASIC = {"good_points": [_CARD], "main_improvement": _CARD,
          "next_trade_checks": [{"phase": str, "text": str}], "lesson": _LESSON}
_ADVANCED = {
    "entry_review": {"evidence": [str], "uncertainty": [str], "invalidation": str,
                     "assessment": _QUALITY},
    "risk_review": {"planned_rule": str, "actual_response": str, "assessment": _QUALITY},
    "exit_review": {"profit_taking_assessment": str, "trend_exit_assessment": str, "explanation": str},
    "detailed_analysis": [_CARD],
    "next_trade_playbook": {"before_entry": [str], "while_holding": [str], "before_exit": [str]},
    "lesson": {**_LESSON, "next_trade_application": str},
    "reflection_questions": [str],
}


def _check_shape(value, shape):
    if shape is str:
        if type(value) is not str:
            raise ReviewDisplayContractError("invalid semantic text")
    elif type(shape) is list:
        if type(value) is not list:
            raise ReviewDisplayContractError("invalid semantic list")
        for item in value:
            _check_shape(item, shape[0])
    else:
        _exact_keys(value, set(shape), "semantic")
        for key, child_shape in shape.items():
            _check_shape(value[key], child_shape)


def compile_structured_review(structured):
    """Map every model semantic path to an ordered, validated canonical body."""
    if type(structured) is not dict or structured.get("schema_version") != "trade-review.v1":
        raise ReviewDisplayContractError("unsupported review schema")
    review_type = structured.get("review_type")
    if review_type not in ("basic", "advanced"):
        raise ReviewDisplayContractError("unsupported review type")
    _exact_keys(structured, {"schema_version", "review_type", "objective", "summary", review_type}, "review")
    if type(structured["objective"]) is not dict:
        raise ReviewDisplayContractError("invalid objective")
    summary = structured["summary"]
    common = {"decision_quality", "main_issue", "next_action"}
    if type(summary) is not dict or set(summary) not in (common, common | {"data_confidence", "missing_information"}):
        raise ReviewDisplayContractError("unmapped summary field")
    _check_shape({key: summary[key] for key in common},
                 {"decision_quality": _QUALITY, "main_issue": str, "next_action": str})
    confidence_parts = []
    if "data_confidence" in summary:
        _check_shape(summary["data_confidence"], {"level": str, "label": str, "reasons": [str]})
        _check_shape(summary["missing_information"], [str])
    _check_shape(structured[review_type], _BASIC if review_type == "basic" else _ADVANCED)

    # Every section owns a paragraph boundary, independent of legacy section
    # or checklist reinterpretation. Semantic strings remain unchanged.
    body = _BodyBuilder(structured, "\n\n")
    m, phase, line = body.model, body.mapped_phase, body.line
    if "data_confidence" in summary:
        confidence_parts.extend((" / 데이터 신뢰도: ", summary["data_confidence"]["label"]))
        for reason in summary["data_confidence"]["reasons"]:
            confidence_parts.extend((" / 근거: ", reason))
        for missing in summary["missing_information"]:
            confidence_parts.extend((" / 추가 확인: ", missing))
    if review_type == "basic":
        lesson = ("basic", "lesson")
        line("이번 매매 판단: 판단 품질: ", m("summary", "decision_quality", "label"), " — ",
             m("summary", "decision_quality", "explanation"), " / 핵심 문제: ", m("summary", "main_issue"),
             " / 핵심 실천: ", m("summary", "next_action"),
             " / 이번에 배울 점: ", m(*lesson, "title"), " / ", m(*lesson, "concept"),
             " / 이번 거래 적용: ", m(*lesson, "applied_to_this_trade"), *confidence_parts)
        points = ["확인된 강점:"]
        for index, _ in enumerate(structured["basic"]["good_points"]):
            if index:
                points.append(" / ")
            else:
                points.append(" ")
            points.extend((m("basic", "good_points", index, "title"), ": ",
                           m("basic", "good_points", index, "detail")))
        line(*points)
        line("개선할 점: ", m("basic", "main_improvement", "title"), ": ",
             m("basic", "main_improvement", "detail"))
        checks = ["다음 매매 점검:"]
        for index, _ in enumerate(structured["basic"]["next_trade_checks"]):
            if index:
                checks.append(" / ")
            else:
                checks.append(" ")
            checks.extend((phase("basic", "next_trade_checks", index, "phase"), ": ",
                           m("basic", "next_trade_checks", index, "text")))
        line(*checks)
    else:
        line("이번 매매 판단: 판단 품질: ", m("summary", "decision_quality", "label"), " — ",
             m("summary", "decision_quality", "explanation"), " / 핵심 문제: ",
             m("summary", "main_issue"), *confidence_parts)
        entry = ("advanced", "entry_review")
        parts = ["진입 가설 검토: ", m(*entry, "assessment", "explanation"), " / 평가: ",
                 m(*entry, "assessment", "label"), " / 근거:"]
        for index, _ in enumerate(structured["advanced"]["entry_review"]["evidence"]):
            parts.append(" ")
            parts.append(m(*entry, "evidence", index))
        parts.append(" / 불확실성:")
        for index, _ in enumerate(structured["advanced"]["entry_review"]["uncertainty"]):
            parts.append(" ")
            parts.append(m(*entry, "uncertainty", index))
        parts.extend((" / 무효화 기준: ", m(*entry, "invalidation")))
        line(*parts)
        risk = ("advanced", "risk_review")
        line("위험 관리 검토: ", m(*risk, "assessment", "explanation"), " / 평가: ",
             m(*risk, "assessment", "label"), " / 사전 기준: ", m(*risk, "planned_rule"),
             " / 실제 대응: ", m(*risk, "actual_response"))
        exit_path = ("advanced", "exit_review")
        line("매수·매도 대응: ", m(*exit_path, "explanation"), " / 수익 확정: ",
             m(*exit_path, "profit_taking_assessment"), " / 추세 종료: ",
             m(*exit_path, "trend_exit_assessment"))
        details = ["상세 분석:"]
        for index, _ in enumerate(structured["advanced"]["detailed_analysis"]):
            if index:
                details.append(" / ")
            else:
                details.append(" ")
            details.extend((m("advanced", "detailed_analysis", index, "title"), ": ",
                            m("advanced", "detailed_analysis", index, "detail")))
        line(*details)
        playbook = ["다음 매매 체크: "]
        for phase_key, label in (("before_entry", "진입 전"), ("while_holding", "보유 중"),
                                 ("before_exit", "매도 전")):
            if len(playbook) > 1:
                playbook.append(" / ")
            playbook.append(f"{label}:")
            for index, _ in enumerate(structured["advanced"]["next_trade_playbook"][phase_key]):
                playbook.append(" ")
                playbook.append(m("advanced", "next_trade_playbook", phase_key, index))
        playbook.extend((" / 핵심 실천: ", m("summary", "next_action")))
        line(*playbook)
        lesson = ("advanced", "lesson")
        line("이번에 배울 점: ", m(*lesson, "title"), " / ", m(*lesson, "concept"),
             " / 이번 거래 적용: ", m(*lesson, "applied_to_this_trade"),
             " / 다음 거래 적용: ", m(*lesson, "next_trade_application"))
        questions = ["다음 복기 질문:"]
        for index, _ in enumerate(structured["advanced"]["reflection_questions"]):
            if index:
                questions.append(" / ")
            else:
                questions.append(" ")
            questions.append(m("advanced", "reflection_questions", index))
        line(*questions)
    return body.finish()
