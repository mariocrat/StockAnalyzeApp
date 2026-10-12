"""Pure review-display.v2 body admission; no route, fixture, store or model imports."""
from dataclasses import dataclass
import re

from backend.core.review_display_contract import (
    BLOCK_TYPES, RUN_TYPES, MAX_BLOCKS, MAX_RUNS_PER_BLOCK, MAX_TOTAL_RUNS,
    MAX_RUN_CODEPOINTS, MAX_CANONICAL_CODEPOINTS, MAX_SEPARATOR_CODEPOINTS,
)

SCHEMA_VERSION = "review-display.v2"
_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
BASIC_ROLES = ("summary", "data_quality", "good_points", "main_improvement", "next_trade_checks", "lesson")
ADVANCED_ROLES = ("summary", "data_quality", "entry_review", "risk_review", "exit_review",
                  "detailed_analysis", "next_trade_playbook", "lesson", "reflection_questions")
ROLES = frozenset(BASIC_ROLES + ADVANCED_ROLES)


class ReviewDisplayV2Error(ValueError):
    """Stable rejection code; message contains only a controlled contract path."""
    def __init__(self, code, path="$"):
        self.code = code
        self.path = path
        super().__init__(code + " at " + path)


def require(condition, code, path="$"):
    if not condition:
        raise ReviewDisplayV2Error(code, path)


def exact_keys(value, expected, path, *, missing="MISSING_FIELD"):
    require(type(value) is dict, "INVALID_TYPE", path)
    require(not (set(value) - set(expected)), "UNKNOWN_KEY", path)
    require(not (set(expected) - set(value)), missing, path)


def text(value, path, maximum, *, empty=False):
    require(type(value) is str, "INVALID_TYPE", path)
    require((empty or len(value) > 0) and len(value) <= maximum, "LIMIT_EXCEEDED", path)
    require(all(not (ord(c) < 9 or 10 < ord(c) < 32 or ord(c) == 127
                     or 0xD800 <= ord(c) <= 0xDFFF) for c in value), "INVALID_UNICODE", path)
    return value


@dataclass(frozen=True)
class _Array:
    item: object
    minimum: int
    maximum: int
    code: str = "INVALID_TYPE"


@dataclass(frozen=True)
class _Enum:
    values: tuple
    code: str


_REF = object()
_QUALITY = {"label": _REF, "explanation": _REF}
_CARD = {"title": _REF, "detail": _REF}
_LESSON = {"title": _REF, "concept": _REF, "applied_to_this_trade": _REF}
_FIELDS = {
    "summary": {"objective": {"realized_pnl": _REF, "realized_return_pct": _REF},
                "decision_quality": _QUALITY, "main_issue": _REF, "next_action": _REF},
    "data_quality": {"confidence": {"level": _Enum(("high", "medium", "low"), "INVALID_CONFIDENCE"),
                                   "label": _REF, "reasons": _Array(_REF, 0, 5)},
                     "missing_information": _Array(_REF, 0, 4, "INVALID_MISSING_INFORMATION")},
    "good_points": {"items": _Array(_CARD, 1, 2)},
    "main_improvement": _CARD,
    "next_trade_checks": {"items": _Array({"phase": _Enum(("before_entry", "while_holding", "before_exit"),
                                                       "INVALID_PHASE"), "text": _REF}, 1, 3)},
    "entry_review": {"assessment": _QUALITY, "evidence": _Array(_REF, 1, 4),
                     "uncertainty": _Array(_REF, 0, 4), "invalidation": _REF},
    "risk_review": {"planned_rule": _REF, "actual_response": _REF, "assessment": _QUALITY},
    "exit_review": {"profit_taking_assessment": _REF, "trend_exit_assessment": _REF, "explanation": _REF},
    "detailed_analysis": {"items": _Array(_CARD, 0, 5)},
    "next_trade_playbook": {"before_entry": _Array(_REF, 1, 3), "while_holding": _Array(_REF, 1, 3),
                            "before_exit": _Array(_REF, 1, 3)},
    "reflection_questions": {"items": _Array(_REF, 0, 2)},
}


def _identifier(value, path, code):
    require(type(value) is str and _ID.fullmatch(value) is not None, code, path)
    return value


def _field_refs(value, shape, path):
    if shape is _REF:
        return [_identifier(value, path, "INVALID_REFERENCE")]
    if type(shape) is _Enum:
        require(type(value) is str and value in shape.values, shape.code, path)
        return []
    if type(shape) is _Array:
        require(type(value) is list, shape.code, path)
        require(shape.minimum <= len(value) <= shape.maximum, "LIMIT_EXCEEDED", path)
        return [ref for i, child in enumerate(value)
                for ref in _field_refs(child, shape.item, f"{path}[{i}]")]
    exact_keys(value, shape, path)
    return [ref for key, child in shape.items() for ref in _field_refs(value[key], child, path + "." + key)]


def validate_document(document):
    """Exact shape, scalar bounds, roles, ownership/traversal, then canonical text.

    Missing/duplicate ownership precedes field relationship checks. Full field
    traversal is explicit in _FIELDS; incoming dictionary order has no authority.
    """
    exact_keys(document, ("schema_version", "surface", "review_type", "blocks", "sections", "canonical_text"), "$")
    require(document["schema_version"] == SCHEMA_VERSION, "INVALID_VERSION")
    require(document["surface"] == "body", "INVALID_SURFACE")
    review_type = document["review_type"]
    require(type(review_type) is str and review_type in ("basic", "advanced"), "INVALID_REVIEW_TYPE")
    blocks = document["blocks"]
    require(type(blocks) is list, "INVALID_TYPE", "$.blocks")
    require(1 <= len(blocks) <= MAX_BLOCKS, "LIMIT_EXCEEDED", "$.blocks")
    ids, pieces, total_runs, total_chars = [], [], 0, 0
    for i, block in enumerate(blocks):
        path = f"$.blocks[{i}]"
        require(type(block) is dict, "INVALID_TYPE", path)
        require("id" in block, "MISSING_BLOCK_ID", path)
        exact_keys(block, ("id", "type", "runs", "separator_after"), path)
        identity = _identifier(block["id"], path + ".id", "INVALID_BLOCK_ID")
        require(identity not in ids, "DUPLICATE_BLOCK_ID", path)
        ids.append(identity)
        require(type(block["type"]) is str and block["type"] in BLOCK_TYPES, "INVALID_BLOCK_TYPE", path)
        runs = block["runs"]
        require(type(runs) is list, "INVALID_TYPE", path + ".runs")
        require(1 <= len(runs) <= MAX_RUNS_PER_BLOCK, "LIMIT_EXCEEDED", path + ".runs")
        total_runs += len(runs)
        require(total_runs <= MAX_TOTAL_RUNS, "LIMIT_EXCEEDED", path)
        if block["type"] == "divider":
            require(len(runs) == 1 and type(runs[0]) is dict and runs[0].get("type") == "text",
                    "INVALID_DIVIDER", path)
        for j, run in enumerate(runs):
            run_path = path + f".runs[{j}]"
            exact_keys(run, ("type", "text"), run_path)
            require(type(run["type"]) is str and run["type"] in RUN_TYPES, "INVALID_RUN_TYPE", run_path)
            piece = text(run["text"], run_path + ".text", MAX_RUN_CODEPOINTS)
            total_chars += len(piece)
            require(total_chars <= MAX_CANONICAL_CODEPOINTS, "LIMIT_EXCEEDED", run_path)
            pieces.append(piece)
        separator = block["separator_after"]
        require(type(separator) is str and all(c in " \t\n" for c in separator),
                "INVALID_SEPARATOR", path)
        text(separator, path + ".separator_after", MAX_SEPARATOR_CODEPOINTS, empty=True)
        total_chars += len(separator)
        require(total_chars <= MAX_CANONICAL_CODEPOINTS, "LIMIT_EXCEEDED", path)
        pieces.append(separator)

    sections = document["sections"]
    order = BASIC_ROLES if review_type == "basic" else ADVANCED_ROLES
    require(type(sections) is list, "INVALID_TYPE", "$.sections")
    require(len(sections) == len(order), "WRONG_SECTION_ORDER")
    owned, traversals = [], []
    for i, (section, role) in enumerate(zip(sections, order)):
        path = f"$.sections[{i}]"
        require(type(section) is dict, "INVALID_TYPE", path)
        require("role" in section, "MISSING_FIELD", path)
        require(type(section["role"]) is str and section["role"] in ROLES, "UNKNOWN_ROLE", path)
        require(section["role"] == role, "WRONG_SECTION_ORDER", path)
        shape = ({**_LESSON, **({"next_trade_application": _REF} if review_type == "advanced" else {})}
                 if role == "lesson" else _FIELDS[role])
        exact_keys(section, ("role", "block_ids", *shape), path)
        owners = section["block_ids"]
        require(type(owners) is list, "INVALID_TYPE", path + ".block_ids")
        require(len(owners) <= MAX_BLOCKS, "LIMIT_EXCEEDED", path + ".block_ids")
        for identity in owners:
            _identifier(identity, path + ".block_ids", "INVALID_REFERENCE")
        owned.extend(owners)
        fields = {key: section[key] for key in shape}
        traversals.append(_field_refs(fields, shape, path))
    require(len(set(owned)) == len(owned), "DUPLICATE_OWNERSHIP")
    require(set(owned) <= set(ids), "MISSING_BLOCK_REFERENCE")
    require(set(ids) <= set(owned), "ORPHAN_BLOCK")
    for i, (section, refs) in enumerate(zip(sections, traversals)):
        path = f"$.sections[{i}]"
        require(set(refs) <= set(ids), "MISSING_BLOCK_REFERENCE", path)
        require(len(set(refs)) == len(refs), "DUPLICATE_BLOCK_REFERENCE", path)
        require(set(refs) <= set(section["block_ids"]), "FOREIGN_SECTION_REFERENCE", path)
        require(refs == section["block_ids"], "WRONG_REFERENCE_ORDER", path)
    require(ids == owned, "WRONG_BLOCK_ORDER")
    canonical = text(document["canonical_text"], "$.canonical_text", MAX_CANONICAL_CODEPOINTS)
    require("".join(pieces) == canonical, "CANONICAL_TEXT_MISMATCH")
    return canonical
