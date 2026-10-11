"""Closed outbound review-envelope.v1 foundation; no production caller yet.

Only review-display documents contain free text. Every other string is an
explicit enum, KRX code, or validated date. The JSON Schema describes the
wire shape; the validator also checks finite numbers, calendar dates, and
exact display canonical text.
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import math
import re

from backend.core.review_display_contract import (
    MAX_BLOCKS, MAX_CANONICAL_CODEPOINTS, MAX_RUNS_PER_BLOCK,
    MAX_RUN_CODEPOINTS, MAX_SEPARATOR_CODEPOINTS, SCHEMA_VERSION as DISPLAY_VERSION,
    SURFACES, validate_document,
)


SCHEMA_VERSION = "review-envelope.v1"
MAX_SAFE_INTEGER = 2**53 - 1
MAX_NODES = 100_000
MAX_DEPTH = 32


class ReviewEnvelopeContractError(ValueError):
    """The proposed outbound value is outside the closed contract."""


def _object(properties, *, required=None):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties if required is None else required)}


def _array(items, maximum):
    return {"type": "array", "items": items, "maxItems": maximum}


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _number():
    return {"type": "number"}


def _integer(*, minimum=0):
    return {"type": "integer", "minimum": minimum, "maximum": MAX_SAFE_INTEGER}


def _nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def _date():
    return {"type": "string", "format": "date", "pattern": r"[0-9]{4}-[0-9]{2}-[0-9]{2}"}


def _date_time():
    return {"type": "string", "format": "date-time",
            "pattern": r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})"}


def _code():
    # The current journal chart provider uses six-digit KRX tickers.
    return {"type": "string", "pattern": r"[0-9]{6}"}


def _display(surface):
    if surface not in SURFACES:
        raise ReviewEnvelopeContractError("unknown display surface")
    run = _object({"type": _enum("text", "strong"),
                   "text": {"type": "string", "minLength": 1, "maxLength": MAX_RUN_CODEPOINTS}})
    block = _object({
        "type": _enum("heading", "paragraph", "list_item", "divider"),
        "runs": {"type": "array", "items": run, "minItems": 1, "maxItems": MAX_RUNS_PER_BLOCK},
        "separator_after": {"type": "string", "maxLength": MAX_SEPARATOR_CODEPOINTS,
                            "pattern": r"[ \t\n]*"},
    })
    return {**_object({
        "schema_version": {"const": DISPLAY_VERSION}, "surface": {"const": surface},
        "blocks": {"type": "array", "items": block, "minItems": 1, "maxItems": MAX_BLOCKS},
        "canonical_text": {"type": "string", "minLength": 1,
                           "maxLength": MAX_CANONICAL_CODEPOINTS},
    }), "x-review-surface": surface}


def review_envelope_schema():
    """Return an independent strict JSON Schema for the Phase 2A wire shape."""
    chart_time = {"anyOf": [_date(), _integer()]}
    candle = _object({
        "time": chart_time, "open": _number(), "high": _number(), "low": _number(),
        "close": _number(), "volume": _number(),
        "ma5": _nullable(_number()), "ma20": _nullable(_number()),
    })
    marker = _object({
        "time": chart_time, "side": _enum("buy", "sell"),
        "label": _nullable(_display("marker_label")),
        "tooltip": _nullable(_display("marker_tooltip")),
    })
    chart = _object({
        "ticker": _code(), "timeframe": _enum("intraday", "daily", "weekly"),
        "interval": _enum("1m", "3m", "1d", "1wk"),
        "header": _display("chart_header"), "tab": _display("chart_tab"),
        "candles": _array(candle, 500), "markers": _array(marker, 300),
    })
    card_metrics = _object({
        "rsi14": _nullable(_number()), "return_10d_before": _nullable(_number()),
        "volume_ratio_20d": _nullable(_number()),
        "next_5d_return": _nullable(_number()), "next_20d_return": _nullable(_number()),
    })
    card = _object({"trade_id": _nullable(_integer(minimum=1)),
                    "display": _display("chart_card"), "metrics": card_metrics})
    trade = _object({
        "id": _integer(minimum=1), "trade_date": {"anyOf": [_date(), _date_time()]},
        "ticker": _code(), "side": _enum("buy", "sell"),
        "name": _display("trade_name"), "price": _number(), "quantity": _number(),
    })
    objective = _object({
        "trade_count": _integer(), "realized_pnl": _number(),
        "realized_return_pct": _number(), "win_rate_pct": _number(),
        "weighted_buy_price": _nullable(_number()), "has_market_data": {"type": "boolean"},
    })
    history = _object({"id": _integer(minimum=1), "created_at": _date_time(),
                       "title": _display("history_title")})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": SCHEMA_VERSION,
            **_object({
                "schema_version": {"const": SCHEMA_VERSION},
                "review_type": _enum("basic", "advanced"),
                "status": _enum("ready", "error", "missing_key", "empty"),
                "source": _enum("openai", "chart-rules", "none"),
                "body": _display("body"), "objective": objective,
                "chart_cards": _array(card, 100), "charts": _array(chart, 8),
                "trades": _array(trade, 100), "history": _nullable(history),
                "notice": _nullable(_display("notice")),
            })}


def _validate(value, schema, path, active, count, depth):
    if depth > MAX_DEPTH or count[0] >= MAX_NODES:
        raise ReviewEnvelopeContractError("envelope depth or size exceeded")
    count[0] += 1
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                _validate(value, candidate, path, active, count, depth + 1)
                return
            except ReviewEnvelopeContractError:
                pass
        raise ReviewEnvelopeContractError(f"invalid value at {path}")
    if "const" in schema:
        if type(value) is not type(schema["const"]) or value != schema["const"]:
            raise ReviewEnvelopeContractError(f"invalid constant at {path}")
        return
    kind = schema["type"]
    if kind == "null":
        if value is not None:
            raise ReviewEnvelopeContractError(f"invalid null at {path}")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ReviewEnvelopeContractError(f"invalid boolean at {path}")
    elif kind in ("number", "integer"):
        if type(value) not in ((int,) if kind == "integer" else (int, float)):
            raise ReviewEnvelopeContractError(f"invalid number at {path}")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite or value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ReviewEnvelopeContractError(f"non-finite or out-of-range number at {path}")
    elif kind == "string":
        if type(value) is not str or len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", MAX_SAFE_INTEGER):
            raise ReviewEnvelopeContractError(f"invalid string at {path}")
        if "enum" in schema and value not in schema["enum"]:
            raise ReviewEnvelopeContractError(f"unknown enum at {path}")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise ReviewEnvelopeContractError(f"invalid code/date at {path}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ReviewEnvelopeContractError(f"invalid calendar date at {path}") from error
        elif schema.get("format") == "date-time":
            if value[-1] != "Z":
                offset = value[-6:]
                if int(offset[1:3]) > 23 or int(offset[4:6]) > 59:
                    raise ReviewEnvelopeContractError(f"invalid timezone offset at {path}")
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ReviewEnvelopeContractError(f"invalid calendar datetime at {path}") from error
    elif kind in ("object", "array"):
        if (kind == "object" and type(value) is not dict) or (kind == "array" and type(value) is not list):
            raise ReviewEnvelopeContractError(f"invalid container at {path}")
        identity = id(value)
        if identity in active:
            raise ReviewEnvelopeContractError("cyclic envelope")
        active.add(identity)
        try:
            if kind == "object":
                properties = schema["properties"]
                if set(value) - set(properties) or set(schema["required"]) - set(value):
                    raise ReviewEnvelopeContractError(f"unknown or missing field at {path}")
                for key, child in value.items():
                    _validate(child, properties[key], f"{path}.{key}", active, count, depth + 1)
            else:
                if len(value) < schema.get("minItems", 0) or len(value) > schema["maxItems"]:
                    raise ReviewEnvelopeContractError(f"invalid list length at {path}")
                for index, child in enumerate(value):
                    _validate(child, schema["items"], f"{path}[{index}]", active, count, depth + 1)
        finally:
            active.remove(identity)
        if "x-review-surface" in schema:
            try:
                validate_document(value, expected_surface=schema["x-review-surface"])
            except ValueError as error:
                raise ReviewEnvelopeContractError(f"invalid canonical display at {path}") from error
    else:
        raise ReviewEnvelopeContractError("invalid contract schema")


def validate_envelope(envelope):
    """Validate the complete outbound value; return None on success."""
    try:
        _validate(envelope, review_envelope_schema(), "$", set(), [0], 0)
    except (RecursionError, OverflowError) as error:
        raise ReviewEnvelopeContractError("invalid envelope") from error


def validate_chart_display_snapshot(value):
    """The unchanged envelope chart schemas, with no legacy/raw fallback."""
    properties = review_envelope_schema()["properties"]
    schema = _object({key: properties[key] for key in ("charts", "chart_cards")})
    try:
        _validate(value, schema, "$", set(), [0], 0)
    except (RecursionError, OverflowError) as error:
        raise ReviewEnvelopeContractError("invalid chart display snapshot") from error


def approved_chart_display_snapshot(snapshot):
    """Own a chart-only JSON copy of the seal; metadata cannot affect it."""
    if type(snapshot) is not ApprovedReviewSnapshot:
        raise ReviewEnvelopeContractError("expected approved review snapshot")
    envelope = json.loads(snapshot.json_text)
    if envelope["status"] == "error":
        return {"charts": [], "chart_cards": []}
    return {key: envelope[key] for key in ("charts", "chart_cards")}


class ApprovedReviewSnapshot:
    """Validated, sealed canonical JSON bytes; restoration is unsupported."""

    __slots__ = ("_json",)

    def __init_subclass__(cls, **kwargs):
        raise TypeError("approved snapshots cannot be subclassed")

    def __init__(self, envelope):
        if hasattr(self, "_json"):
            raise TypeError("approved snapshot is already initialized")
        # Validate both the source and the independent JSON value that will be
        # sealed. A source mutation during serialization cannot approve bytes
        # that were never checked.
        validate_envelope(envelope)
        try:
            serialized = json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")
            validate_envelope(json.loads(serialized))
        except (TypeError, ValueError, UnicodeError, OverflowError) as error:
            raise ReviewEnvelopeContractError("invalid serialized envelope") from error
        object.__setattr__(self, "_json", serialized)

    def __setattr__(self, name, value):
        raise AttributeError("approved snapshot is sealed")

    def __delattr__(self, name):
        raise AttributeError("approved snapshot is sealed")

    def __getstate__(self):
        raise TypeError("approved snapshot serialization is unsupported")

    def __setstate__(self, state):
        raise TypeError("approved snapshot restoration is unsupported")

    def __reduce__(self):
        raise TypeError("approved snapshot serialization is unsupported")

    def __reduce_ex__(self, protocol):
        raise TypeError("approved snapshot serialization is unsupported")

    @property
    def json_text(self):
        return self._json.decode("utf-8")

    @property
    def digest(self):
        return hashlib.sha256(self._json).hexdigest()

    def __repr__(self):
        return f"ApprovedReviewSnapshot(digest={self.digest})"
