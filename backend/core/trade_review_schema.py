"""Schema and normalization helpers for structured trade-review output.

The model is only allowed to provide qualitative review fields. Objective trade
numbers are calculated by the application and merged by ``ai_review_v2``.
"""

from __future__ import annotations


STRUCTURED_REVIEW_SCHEMA_VERSION = "trade-review.v1"
DECISION_QUALITY_LABELS = ("탁월", "보통 이상", "보통", "보통 이하", "판단 보류")
ASSESSMENT_LABELS = ("근거 충분", "근거 일부", "근거 부족", "판단 보류")
REVIEW_PHASES = ("before_entry", "while_holding", "before_exit")
MAX_REVIEW_TEXT_CHARS = 900


def _string_schema(*, minimum: int = 0, maximum: int = MAX_REVIEW_TEXT_CHARS) -> dict:
    schema = {"type": "string", "maxLength": maximum}
    if minimum:
        schema["minLength"] = minimum
    return schema


def _quality_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "enum": list(DECISION_QUALITY_LABELS)},
            "explanation": _string_schema(minimum=1),
        },
        "required": ["label", "explanation"],
    }


def _assessment_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "enum": list(ASSESSMENT_LABELS)},
            "explanation": _string_schema(minimum=1),
        },
        "required": ["label", "explanation"],
    }


def _lesson_schema(*, advanced: bool = False) -> dict:
    properties = {
        "title": _string_schema(minimum=1),
        "concept": _string_schema(minimum=1),
        "applied_to_this_trade": _string_schema(minimum=1),
    }
    required = ["title", "concept", "applied_to_this_trade"]
    if advanced:
        properties["next_trade_application"] = _string_schema(minimum=1)
        required.append("next_trade_application")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def structured_output_schema(review_type: str) -> dict:
    """Return the strict JSON Schema for model-generated semantic fields."""

    normalized = "advanced" if str(review_type or "").strip().lower() == "advanced" else "basic"
    common = {
        "decision_quality": _quality_schema(),
        "main_issue": _string_schema(minimum=1),
        "next_action": _string_schema(minimum=1),
    }
    if normalized == "basic":
        common.update({
            "good_points": {
                "type": "array",
                "minItems": 1,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": _string_schema(minimum=1, maximum=160),
                        "detail": _string_schema(minimum=1),
                    },
                    "required": ["title", "detail"],
                },
            },
            "main_improvement": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": _string_schema(minimum=1, maximum=160),
                    "detail": _string_schema(minimum=1),
                },
                "required": ["title", "detail"],
            },
            "next_trade_checks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "phase": {"type": "string", "enum": list(REVIEW_PHASES)},
                        "text": _string_schema(minimum=1),
                    },
                    "required": ["phase", "text"],
                },
            },
            "lesson": _lesson_schema(),
        })
    else:
        common.update({
            "entry_review": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "evidence": {"type": "array", "minItems": 1, "maxItems": 4, "items": _string_schema(minimum=1)},
                    "uncertainty": {"type": "array", "maxItems": 4, "items": _string_schema(minimum=1)},
                    "invalidation": _string_schema(minimum=1),
                    "assessment": _assessment_schema(),
                },
                "required": ["evidence", "uncertainty", "invalidation", "assessment"],
            },
            "risk_review": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "planned_rule": _string_schema(minimum=1),
                    "actual_response": _string_schema(minimum=1),
                    "assessment": _assessment_schema(),
                },
                "required": ["planned_rule", "actual_response", "assessment"],
            },
            "exit_review": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "profit_taking_assessment": _string_schema(minimum=1),
                    "trend_exit_assessment": _string_schema(minimum=1),
                    "explanation": _string_schema(minimum=1),
                },
                "required": ["profit_taking_assessment", "trend_exit_assessment", "explanation"],
            },
            "detailed_analysis": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": _string_schema(minimum=1, maximum=160),
                        "detail": _string_schema(minimum=1),
                    },
                    "required": ["title", "detail"],
                },
            },
            "next_trade_playbook": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "before_entry": {"type": "array", "minItems": 1, "maxItems": 3, "items": _string_schema(minimum=1)},
                    "while_holding": {"type": "array", "minItems": 1, "maxItems": 3, "items": _string_schema(minimum=1)},
                    "before_exit": {"type": "array", "minItems": 1, "maxItems": 3, "items": _string_schema(minimum=1)},
                },
                "required": ["before_entry", "while_holding", "before_exit"],
            },
            "lesson": _lesson_schema(advanced=True),
            "reflection_questions": {"type": "array", "maxItems": 2, "items": _string_schema(minimum=1)},
        })

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": common,
        "required": list(common),
    }


def structured_output_format(review_type: str) -> dict:
    normalized = "advanced" if str(review_type or "").strip().lower() == "advanced" else "basic"
    return {
        "type": "json_schema",
        "name": f"trade_review_{normalized}",
        "strict": True,
        "schema": structured_output_schema(normalized),
    }


def _text(value, *, required: bool = False, maximum: int = MAX_REVIEW_TEXT_CHARS) -> str | None:
    if not isinstance(value, str):
        return None if required else ""
    normalized = value.strip()
    if required and not normalized:
        return None
    return normalized[:maximum]


def _quality(value: dict) -> dict | None:
    if not isinstance(value, dict):
        return None
    label = _text(value.get("label"), required=True, maximum=40)
    explanation = _text(value.get("explanation"), required=True)
    if label is None or explanation is None:
        return None
    if label not in DECISION_QUALITY_LABELS:
        label = "판단 보류"
    return {"label": label, "explanation": explanation}


def _assessment(value: dict) -> dict | None:
    if not isinstance(value, dict):
        return None
    label = _text(value.get("label"), required=True, maximum=40)
    explanation = _text(value.get("explanation"), required=True)
    if label is None or explanation is None:
        return None
    if label not in ASSESSMENT_LABELS:
        label = "판단 보류"
    return {"label": label, "explanation": explanation}


def _string_list(value, *, maximum_items: int, minimum_items: int = 0) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if len(value) < minimum_items:
        return None
    result = []
    for item in value[:maximum_items]:
        normalized = _text(item, required=True)
        if normalized is None:
            return None
        result.append(normalized)
    return result


def _cards(value, *, maximum_items: int, minimum_items: int = 0) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    if len(value) < minimum_items:
        return None
    result = []
    for item in value[:maximum_items]:
        if not isinstance(item, dict):
            return None
        title = _text(item.get("title"), required=True, maximum=160)
        detail = _text(item.get("detail"), required=True)
        if title is None or detail is None:
            return None
        result.append({"title": title, "detail": detail})
    return result


def _lesson(value: dict, *, advanced: bool) -> dict | None:
    if not isinstance(value, dict):
        return None
    keys = ["title", "concept", "applied_to_this_trade"]
    if advanced:
        keys.append("next_trade_application")
    result = {}
    for key in keys:
        normalized = _text(value.get(key), required=True)
        if normalized is None:
            return None
        result[key] = normalized
    return result


def _matches_closed_model_shape(value, schema: dict) -> bool:
    """Reject semantic fields the canonical body has no approved mapping for."""
    kind = schema["type"]
    if kind == "object":
        return (type(value) is dict and set(value) == set(schema["properties"])
                and all(_matches_closed_model_shape(value[key], child)
                        for key, child in schema["properties"].items()))
    if kind == "array":
        return type(value) is list and all(_matches_closed_model_shape(item, schema["items"]) for item in value)
    return type(value) is str


def normalize_semantic_output(value, review_type: str) -> dict | None:
    """Validate and bound a model JSON object with closed display paths.

    Returning ``None`` for a malformed object makes the caller use its
    deterministic chart-rules fallback instead of partially trusting output.
    """

    normalized_type = "advanced" if str(review_type or "").strip().lower() == "advanced" else "basic"
    if not isinstance(value, dict):
        return None
    if not _matches_closed_model_shape(value, structured_output_schema(normalized_type)):
        return None

    quality = _quality(value.get("decision_quality"))
    main_issue = _text(value.get("main_issue"), required=True)
    next_action = _text(value.get("next_action"), required=True)
    if quality is None or main_issue is None or next_action is None:
        return None

    result = {
        "decision_quality": quality,
        "main_issue": main_issue,
        "next_action": next_action,
    }
    if normalized_type == "basic":
        good_points = _cards(value.get("good_points"), maximum_items=2, minimum_items=1)
        improvement = value.get("main_improvement")
        if good_points is None or not isinstance(improvement, dict):
            return None
        improvement_title = _text(improvement.get("title"), required=True, maximum=160)
        improvement_detail = _text(improvement.get("detail"), required=True)
        checks = value.get("next_trade_checks")
        if improvement_title is None or improvement_detail is None or not isinstance(checks, list) or not checks:
            return None
        normalized_checks = []
        for item in checks[:3]:
            if not isinstance(item, dict):
                return None
            phase = _text(item.get("phase"), required=True, maximum=40)
            text = _text(item.get("text"), required=True)
            if phase not in REVIEW_PHASES or text is None:
                return None
            normalized_checks.append({"phase": phase, "text": text})
        lesson = _lesson(value.get("lesson"), advanced=False)
        if lesson is None:
            return None
        result.update({
            "good_points": good_points,
            "main_improvement": {"title": improvement_title, "detail": improvement_detail},
            "next_trade_checks": normalized_checks,
            "lesson": lesson,
        })
        return result

    entry = value.get("entry_review")
    risk = value.get("risk_review")
    exit_review = value.get("exit_review")
    playbook = value.get("next_trade_playbook")
    if not isinstance(entry, dict) or not isinstance(risk, dict) or not isinstance(exit_review, dict) or not isinstance(playbook, dict):
        return None
    entry_evidence = _string_list(entry.get("evidence"), maximum_items=4, minimum_items=1)
    entry_uncertainty = _string_list(entry.get("uncertainty"), maximum_items=4)
    invalidation = _text(entry.get("invalidation"), required=True)
    entry_assessment = _assessment(entry.get("assessment"))
    planned_rule = _text(risk.get("planned_rule"), required=True)
    actual_response = _text(risk.get("actual_response"), required=True)
    risk_assessment = _assessment(risk.get("assessment"))
    profit_assessment = _text(exit_review.get("profit_taking_assessment"), required=True)
    trend_assessment = _text(exit_review.get("trend_exit_assessment"), required=True)
    exit_explanation = _text(exit_review.get("explanation"), required=True)
    if (
        entry_evidence is None or entry_uncertainty is None or invalidation is None or entry_assessment is None
        or planned_rule is None or actual_response is None or risk_assessment is None
        or profit_assessment is None or trend_assessment is None or exit_explanation is None
    ):
        return None
    detailed = _cards(value.get("detailed_analysis"), maximum_items=5)
    if detailed is None:
        return None
    normalized_playbook = {}
    for phase in REVIEW_PHASES:
        items = _string_list(playbook.get(phase), maximum_items=3, minimum_items=1)
        if items is None:
            return None
        normalized_playbook[phase] = items
    lesson = _lesson(value.get("lesson"), advanced=True)
    questions = _string_list(value.get("reflection_questions"), maximum_items=2)
    if lesson is None or questions is None:
        return None

    result.update({
        "entry_review": {
            "evidence": entry_evidence,
            "uncertainty": entry_uncertainty,
            "invalidation": invalidation,
            "assessment": entry_assessment,
        },
        "risk_review": {
            "planned_rule": planned_rule,
            "actual_response": actual_response,
            "assessment": risk_assessment,
        },
        "exit_review": {
            "profit_taking_assessment": profit_assessment,
            "trend_exit_assessment": trend_assessment,
            "explanation": exit_explanation,
        },
        "detailed_analysis": detailed,
        "next_trade_playbook": normalized_playbook,
        "lesson": lesson,
        "reflection_questions": questions,
    })
    return result
