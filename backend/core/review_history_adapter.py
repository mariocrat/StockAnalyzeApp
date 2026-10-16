"""Closed whole-record history admission, with deterministic memory projection.

The stored contract is review_history's metadata plus its five JSON snapshots.
Canonical documents currently stored by Phase 2C are review-display.v1 bodies,
including the older chart/trade metadata documents. They are checked alongside
every separate legacy field, never used to bypass the rest of the row.

This module has no storage, environment, provider, model or billing dependency.
The caller supplies the existing pure safety predicate and display projections;
none of the production generation/finalization policy is changed here.
"""

import json
import math
import re
from datetime import date, datetime

from core.review_display_contract import (
    MAX_CANONICAL_CODEPOINTS, MAX_RUN_CODEPOINTS, compile_literal_text,
    compile_structured_review, parse_inline_strong, validate_document,
)
from core.review_envelope_contract import (
    MAX_DEPTH, MAX_NODES, MAX_SAFE_INTEGER, validate_chart_display_snapshot,
)
from core.review_legacy_compatibility import admit_legacy_body
from core.review_source_contract import (
    UNAVAILABLE_REVIEW_TEXT, admit_objective_source, admit_semantic_source,
)
from core.trade_review_schema import structured_output_schema


SUMMARY_FIELDS = (
    "id", "review_type", "ticker", "name", "trade_date", "target_trade_id",
    "model", "source", "created_at", "display_snapshot", "history_read_status",
    "trade_restore_allowed",
)
_METRICS = (
    "price_vs_close_pct", "after_5_bars", "after_later_bars", "ma5", "ma20",
    "rsi14", "return_10d_before", "volume_ratio_20d", "next_5d_return", "next_20d_return",
)
_ACCESS_SOURCES = (
    "signup_basic", "signup_advanced", "free_daily_basic", "rewarded_ad_basic",
    "pro_monthly_basic", "pro_monthly_advanced", "purchased_basic",
    "purchased_advanced", "purchased_advanced_as_basic", "weekly_ad_advanced",
    "review_basic", "review_advanced",
)


def _reject():
    raise ValueError("unsupported history record")


def _json_copy(value):
    """Own bounded, finite, plain JSON values before any projection callback."""
    active, count = set(), [0]

    def visit(node, depth):
        count[0] += 1
        if depth > MAX_DEPTH or count[0] > MAX_NODES:
            _reject()
        if type(node) in (dict, list):
            if id(node) in active:
                _reject()
            active.add(id(node))
            try:
                if type(node) is dict:
                    if any(type(key) is not str for key in node):
                        _reject()
                    return {key: visit(child, depth + 1) for key, child in node.items()}
                return [visit(child, depth + 1) for child in node]
            finally:
                active.remove(id(node))
        if node is None or type(node) in (str, bool, int):
            return node
        if type(node) is float and math.isfinite(node):
            return node
        _reject()

    return visit(value, 0)


def _object(value, fields, required=()):
    if type(value) is not dict or set(value) - set(fields) or set(required) - set(value):
        _reject()
    for key, child in value.items():
        fields[key](child)


def _text(value, maximum=MAX_CANONICAL_CODEPOINTS):
    if type(value) is not str or len(value) > maximum:
        _reject()
    # Empty optional fields are legitimate; nonempty text uses the current
    # display validator's exact character policy, including surrogate rejection.
    if value:
        compile_literal_text(value)


def _enum(*choices):
    def check(value):
        if type(value) is not str or value not in choices:
            _reject()
    return check


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        _reject()


def _positive(value):
    _number(value)
    if value <= 0:
        _reject()


def _nonnegative(value):
    _number(value)
    if value < 0:
        _reject()


def _integer(value):
    if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
        _reject()


def _id(value):
    _integer(value)
    if value == 0:
        _reject()


def _boolean(value):
    if type(value) is not bool:
        _reject()


def _nullable(check):
    return lambda value: check(value) if value is not None else None


def _array(check, maximum=100):
    def validate(value):
        if type(value) is not list or len(value) > maximum:
            _reject()
        for item in value:
            check(item)
    return validate


def _date(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        _reject()
    date.fromisoformat(value)


def _datetime(value):
    if (type(value) is not str or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
            r"(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?", value) is None):
        _reject()
    if len(value) >= 6 and value[-6] in "+-" and value[-3] == ":":
        if int(value[-5:-3]) > 23 or int(value[-2:]) > 59:
            _reject()
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _trade_date(value):
    if value == "":
        return
    (_date if type(value) is str and len(value) == 10 else _datetime)(value)


def _chart_time(value):
    (_integer if type(value) is int else _date)(value)


def _candle_label(value):
    if type(value) is str and len(value) == 10:
        _date(value)
    elif type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", value):
        _datetime(value)
    else:
        _reject()


def _ticker(value):
    if type(value) is not str or value and re.fullmatch(r"[0-9]{6}", value) is None:
        _reject()


def _model(value):
    if value is not None and (type(value) is not str or value and
                             re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", value) is None):
        _reject()


def _document(value):
    # Current persisted chart/trade documents also have the body surface.
    validate_document(value, expected_surface="body")


def _trade(value):
    _object(value, {
        "id": _nullable(_id), "trade_date": _trade_date, "ticker": _ticker,
        "name": lambda v: _text(v, 120), "side": _enum("buy", "sell"),
        "price": _positive, "quantity": _positive, "fee": _nonnegative, "tax": _nonnegative,
        "memo": lambda v: _text(v, 5000), "source": lambda v: _text(v, 40),
        "created_at": _datetime, "user_id": lambda v: _text(v, 256),
        "display_snapshot": _document,
    })
    # Partial legacy trade metadata can be displayed, but only a complete trade
    # is ever offered for restoration (see _restorable below).


def _metric(value):
    if type(value) is dict:
        _object(value, {"label": _text, "unit": _text, "description": _text,
                        "value": _nullable(_number)}, {"label", "unit", "description", "value"})
    else:
        _nullable(_number)(value)


def _card(value):
    _object(value, {"trade_id": _nullable(_id), "title": _text, "detail": _text,
                    "metrics": lambda v: _object(v, dict.fromkeys(_METRICS, _metric)),
                    "display_snapshot": _document}, {"title", "detail"})
    if not value["title"] or not value["detail"]:
        _reject()


def _tooltip(value):
    _object(value, {"label": _enum("매수", "매도"), "count": _id, "avg_price": _positive,
                    "total_quantity": _positive, "prices": _array(_positive, 300),
                    "profit_amount": _nullable(_number), "return_rate": _nullable(_number),
                    "display_snapshot": _document}, {"label"})
    if not value["label"]:
        _reject()
    if "count" in value and "prices" in value and value["count"] != len(value["prices"]):
        _reject()


def _fill(value):
    _object(value, {"id": _nullable(_id), "date": _trade_date, "price": _positive,
                    "quantity": _positive, "profit_amount": _nullable(_number),
                    "return_rate": _nullable(_number)}, {"date", "price", "quantity"})


def _marker(value):
    _object(value, {
        "time": _chart_time, "side": _enum("buy", "sell"), "text": _text,
        "position": _enum("belowBar", "aboveBar"),
        "color": _enum("#2962ff", "#ff5252"), "shape": _enum("arrowUp", "arrowDown"),
        "size": _integer, "trades": _array(_fill, 300), "tooltip": _tooltip,
        "display_snapshot": _document,
    }, {"time"})
    if "size" in value and value["size"] != 2:
        _reject()
    if "side" in value:
        controls = (("belowBar", "#2962ff", "arrowUp", "매수") if value["side"] == "buy"
                    else ("aboveBar", "#ff5252", "arrowDown", "매도"))
        for key, expected in zip(("position", "color", "shape"), controls):
            if key in value and value[key] != expected:
                _reject()
        tooltip = value.get("tooltip")
        if tooltip is not None and tooltip["label"] != controls[3]:
            _reject()
        if tooltip is not None and "trades" in value and "count" in tooltip and len(value["trades"]) != tooltip["count"]:
            _reject()


def _candle(value):
    _object(value, {
        "time": _chart_time, "t": _candle_label, "label": _candle_label,
        **dict.fromkeys(("open", "high", "low", "close", "o", "h", "l", "c"), _number),
        "volume": _nonnegative, "v": _nonnegative, "ma5": _nullable(_number), "ma20": _nullable(_number),
    }, {"time"})


def _chart(value):
    _object(value, {
        "ticker": _ticker, "name": lambda v: _text(v, 120), "label": _text,
        "timeframe": _enum("intraday", "daily", "weekly"), "interval": _enum("1m", "3m", "1d", "1wk"),
        "period": _text, "period_label": _text,
        "source": _enum("1m intraday", "3m intraday", "daily OHLCV", "weekly OHLCV"),
        "candles": _array(_candle, 500), "markers": _array(_marker, 300),
        "trade_markers": _array(_marker, 300), "reviews": _array(_card),
        "rule_based_observations": _array(_card), "display_snapshot": _document,
    })
    if "timeframe" in value and "interval" in value:
        sources = {("intraday", "1m"): "1m intraday", ("intraday", "3m"): "3m intraday",
                   ("daily", "1d"): "daily OHLCV", ("weekly", "1wk"): "weekly OHLCV"}
        pair = value["timeframe"], value["interval"]
        if pair not in sources or "source" in value and value["source"] != sources[pair]:
            _reject()


def _context(value):
    _object(value, {
        "error": _text, "trade": _trade, "trade_id": _nullable(_id),
        "date": _trade_date, "market_date": _date, "ticker": _ticker,
        "name": lambda v: _text(v, 120), "side": _enum("buy", "sell"),
        "memo": lambda v: _text(v, 5000), "price": _number, "quantity": _number,
        **dict.fromkeys((*_METRICS, "close", "ma60", "position_in_20d_range"), _nullable(_number)),
        "display_snapshot": _document,
    })


def _chart_snapshot(value):
    _object(value, {"charts": _array(_chart, 8), "chart_contexts": _array(_context),
                    "chart_reviews": _array(_card)})


def _semantic_shape(value, schema):
    """Check original sections before normalization or cross-section assembly."""
    kind = schema["type"]
    if kind == "object":
        fields = schema["properties"]
        if type(value) is not dict or set(value) != set(fields):
            _reject()
        for key, child in value.items():
            _semantic_shape(child, fields[key])
    elif kind == "array":
        if type(value) is not list:
            _reject()
        for child in value:
            _semantic_shape(child, schema["items"])
    elif kind == "string":
        if type(value) is not str:
            _reject()
    else:
        _reject()


def _structured(value):
    _object(value, {"schema_version": _enum("trade-review.v1"),
                    "review_type": _enum("basic", "advanced"), "objective": lambda v: None,
                    "summary": lambda v: None, "basic": lambda v: None, "advanced": lambda v: None},
            {"schema_version", "review_type", "objective", "summary", "basic" if value.get("review_type") == "basic" else "advanced"})
    review_type = value["review_type"]
    if set(value) != {"schema_version", "review_type", "objective", "summary", review_type}:
        _reject()
    summary = value["summary"]
    common = {"decision_quality", "main_issue", "next_action"}
    if type(summary) is not dict or set(summary) not in (common, common | {"data_confidence", "missing_information"}):
        _reject()
    fields = structured_output_schema(review_type)["properties"]
    for key in common:
        _semantic_shape(summary[key], fields[key])
    section = value[review_type]
    # Even equal duplicate values are unsupported. Never let a later section
    # overwrite or hide an original, including with a canonical body.
    if type(section) is not dict or set(summary) & set(section):
        _reject()
    _semantic_shape(section, {"type": "object", "properties": {
        key: schema for key, schema in fields.items() if key not in common}})
    if "data_confidence" in summary:
        _object(summary["data_confidence"], {"level": _enum("low", "medium", "high"),
                                            "label": _text, "reasons": _array(_text)},
                {"level", "label", "reasons"})
        _array(_text)(summary["missing_information"])
    semantic = {key: summary[key] for key in common}
    for key, child in section.items():
        semantic[key] = child
    # Preserve current semantic admission policy and avoid rebuilding an
    # already-canonical Phase 2C body; only validated disjoint inputs reach it.
    admit_semantic_source(semantic, review_type)
    if value["objective"] != {}:
        admit_objective_source(value["objective"])


_BASIC_QUOTA = dict.fromkeys((
    "signup_remaining", "free_daily_remaining", "free_daily_max_remaining", "free_available_now",
    "rewarded_ad_available", "rewarded_ad_daily_remaining", "free_monthly_remaining",
    "free_monthly_limit", "pro_monthly_remaining", "purchased_remaining",
), _integer)
_ADVANCED_QUOTA = dict.fromkeys((
    "signup_remaining", "pro_monthly_remaining", "weekly_reward_remaining", "weekly_advanced_granted",
    "weekly_ad_views", "weekly_ad_views_needed", "purchased_remaining", "max_hold",
), _integer)


def _quota(value):
    _object(value, {"basic": lambda v: _object(v, _BASIC_QUOTA),
                    "advanced": lambda v: _object(v, _ADVANCED_QUOTA)}, {"basic", "advanced"})


def _wallet(value):
    _object(value, {
        "plan": _enum("free", "pro"),
        "basic": lambda v: _object(v, _BASIC_QUOTA), "advanced": lambda v: _object(v, _ADVANCED_QUOTA),
        "products": lambda v: _object(v, dict.fromkeys(
            ("basic_review_15", "basic_review_25", "advanced_review_10", "advanced_review_20"),
            lambda p: _object(p, {"kind": _enum("basic", "advanced"), "quantity": _integer, "price_krw": _integer},
                              {"kind", "quantity", "price_krw"}))),
        "settings": lambda v: _object(v, {
            "allow_advanced_ticket_for_basic": _boolean,
            "ad_policy": lambda p: _object(p, {
                **dict.fromkeys(("basic_reviews_per_rewarded_ad", "rewarded_basic_daily_max", "ads_per_advanced_ticket"), _integer),
                "force_rewarded_ad_chain": _boolean, "preferred_rewarded_ad_sequence": _enum("single"),
            }),
            "free_policy": lambda p: _object(p, dict.fromkeys(
                ("daily_basic", "rewarded_basic_daily_max", "monthly_basic_max", "weekly_advanced_max"), _integer)),
        }),
        "validity": lambda v: _object(v, {
            "timezone": _enum("Asia/Seoul"),
            **dict.fromkeys(("daily_reset_at", "weekly_reset_at", "monthly_reset_at", "signup_pass_expires_at",
                             "purchased_pass_expires_at", "weekly_reward_expires_at", "pro_allowance_resets_at"), _nullable(_trade_date)),
        }),
    })


def _access(value):
    _object(value, {"auth_mode": _enum("session", "dev", "review"), "plan": _enum("free", "pro"),
                    "review_type": _enum("basic", "advanced"), "source": _enum(*_ACCESS_SOURCES),
                    "quota": _quota, "wallet": _wallet, "refunded": _boolean, "idempotent_replay": _boolean})


def _review(value):
    _object(value, {
        "summary": _text, "display_snapshot": _document, "structured_review": _structured,
        "status": _enum("ready", "error", "missing_key", "empty"),
        "source": _enum("openai", "chart-rules", "none"), "review_type": _enum("basic", "advanced"),
        "model": _model, "internal_status": _enum("safety_rejected", "invalid_structured_output"),
        "chart_snapshot": _chart, "chart_snapshots": _array(_chart, 8),
        "chart_contexts": _array(_context), "chart_reviews": _array(_card),
        "chart_display_snapshot": validate_chart_display_snapshot,
        "access": _access, "review_history_id": _id,
    }, {"summary"})


def _record(value):
    fields = {
        "id": _id, "review_type": _enum("basic", "advanced"), "ticker": _ticker,
        "name": lambda v: _text(v, 120), "trade_date": _trade_date,
        "target_trade_id": _nullable(_id), "model": _model,
        "source": _enum("", "openai", "chart-rules", "none"), "created_at": _datetime,
        "trade_snapshot": _trade, "recent_trades_snapshot": _array(_trade),
        "chart_snapshot": _chart_snapshot, "ai_review": _review, "access_snapshot": _access,
    }
    _object(value, fields, set(fields))
    review = value["ai_review"]
    if review.get("review_type", value["review_type"]) != value["review_type"]:
        _reject()
    if "structured_review" in review and review["structured_review"]["review_type"] != value["review_type"]:
        _reject()
    if "chart_display_snapshot" in review:
        if "display_snapshot" not in review or "status" not in review:
            _reject()
        if review["status"] in {"error", "empty"} and review["chart_display_snapshot"] != {"charts": [], "chart_cards": []}:
            _reject()


def _check_content(value, unsafe_text):
    """Check raw, joined canonical and restoration text without control bypasses."""
    if type(value) is str:
        _text(value)
        candidates = [value]
        if value and len(value) <= MAX_RUN_CODEPOINTS:
            candidates.append("".join(run["text"] for run in parse_inline_strong(value)))
        if any("[데이터 확인]" in text or "[합리적 추론]" in text or unsafe_text(text) for text in candidates):
            _reject()
    elif type(value) is dict:
        # Actual frontend card/restoration composition may join safe leaves into
        # an unsafe sentence. Validate these compositions as well as each leaf.
        for keys in (("title", "detail"), ("name", "memo")):
            if all(type(value.get(key)) is str for key in keys):
                _check_content(" ".join(value[key] for key in keys), unsafe_text)
        for child in value.values():
            _check_content(child, unsafe_text)
    elif type(value) is list:
        for child in value:
            _check_content(child, unsafe_text)


def _without_documents(value):
    if type(value) is dict:
        # The existing display compiler knows only visible trade fields. Typed
        # stored-trade identity metadata is retained separately after projection.
        return {key: _without_documents(child) for key, child in value.items()
                if key not in {"display_snapshot", "created_at", "user_id"}}
    if type(value) is list:
        return [_without_documents(child) for child in value]
    return value


def _retain_and_check_projection(original, projected):
    if type(original) is dict:
        for key, child in original.items():
            if key == "display_snapshot":
                if child != projected.get(key):
                    _reject()
            elif key in {"created_at", "user_id"}:
                projected[key] = child
            else:
                _retain_and_check_projection(child, projected[key])
    elif type(original) is list:
        if len(original) != len(projected):
            _reject()
        for before, after in zip(original, projected):
            _retain_and_check_projection(before, after)


def _restorable(trade):
    required = {"trade_date", "ticker", "name", "side", "price", "quantity"}
    return (required <= set(trade) and bool(trade["trade_date"]) and bool(trade["name"])
            and trade["price"] > 0 and trade["quantity"] > 0)


def _unavailable(value):
    # Only bounded identity/control values survive rejection. No restoration
    # target, free-text metadata, original access object or content is retained.
    identity = value.get("id") if type(value) is dict else None
    review_type = value.get("review_type") if type(value) is dict else None
    body = compile_literal_text(UNAVAILABLE_REVIEW_TEXT)
    return {
        "id": identity if type(identity) is int and 0 < identity <= MAX_SAFE_INTEGER else None,
        "review_type": review_type if type(review_type) is str and review_type in ("basic", "advanced") else "basic",
        "ticker": "", "name": "", "trade_date": "", "target_trade_id": None,
        "model": "", "source": "none", "created_at": "",
        "trade_snapshot": None, "recent_trades_snapshot": [], "chart_snapshot": {},
        "ai_review": {"status": "error", "source": "none", "summary": admit_legacy_body(body).summary,
                      "display_snapshot": body}, "access_snapshot": {},
        "display_snapshot": compile_literal_text(UNAVAILABLE_REVIEW_TEXT),
        "history_read_status": "unavailable", "trade_restore_allowed": False,
    }


def adapt_history_record(value, *, unsafe_text, project_trade, project_chart, project_context, project_card,
                         paired_storage_enabled=True, display_capability="review-display.v1"):
    """Approve the whole stored record or return one fixed unavailable copy.

    The supplied projection functions are the existing pure legacy display
    compilers. All input is closed/typed and content checked before they run;
    supplied documents must agree with their deterministic projections.
    """
    from core.review_display_capability import require_display_capability
    require_display_capability(display_capability)
    from core.review_history_paired import (
        StoredPairedHistoryRow, admit_stored_paired_history, paired_history_projection, paired_marker,
    )
    from core.review_history_json_codec import DurableStorageError
    if type(value) is StoredPairedHistoryRow:
        if paired_storage_enabled is not True:
            return _unavailable(value.context)
        try:
            admission = admit_stored_paired_history(value, unsafe_text=unsafe_text)
            return paired_history_projection(admission, unsafe_text=unsafe_text, display_capability=display_capability)
        except DurableStorageError:
            return _unavailable(value.context)
    # Raw unwrapped markers never enter the legacy compiler/normalizer path.
    if type(value) is dict and paired_marker(value.get("ai_review")):
        return _unavailable(value)
    if value is None:
        return None
    try:
        record = _json_copy(value)
        _record(record)
        _check_content(record, unsafe_text)
        review = record["ai_review"]
        canonical = "display_snapshot" in review
        if canonical:
            body = review["display_snapshot"]
            if admit_legacy_body(body).summary != review["summary"]:
                _reject()
        else:
            if "structured_review" in review:
                body, _paths = compile_structured_review(review["structured_review"])
                # Raw semantics cannot become another display authority.
                review.pop("structured_review")
            else:
                body = compile_literal_text(review["summary"])
            review["display_snapshot"] = body
            review["summary"] = admit_legacy_body(body).summary

        def project(original, compiler):
            projected = compiler(_without_documents(original))
            _retain_and_check_projection(original, projected)
            return projected

        record["trade_snapshot"] = project(record["trade_snapshot"], project_trade)
        record["recent_trades_snapshot"] = [project(trade, project_trade) for trade in record["recent_trades_snapshot"]]
        snapshots = [record["chart_snapshot"], review]
        for container in snapshots:
            for key, compiler in (("charts", project_chart), ("chart_snapshots", project_chart),
                                  ("chart_contexts", project_context), ("chart_reviews", project_card)):
                if key in container:
                    container[key] = [project(item, compiler) for item in container[key]]
        if "chart_snapshot" in review:
            review["chart_snapshot"] = project(review["chart_snapshot"], project_chart)

        _record(record)
        _check_content(record, unsafe_text)
        record["display_snapshot"] = compile_literal_text(
            f"종목: {record['ticker']} {record['name']}" if record["ticker"] or record["name"] else "저장된 복기")
        _check_content(record["display_snapshot"], unsafe_text)
        record["history_read_status"] = "canonical" if canonical else "adapted"
        record["recent_trades_snapshot"] = [trade for trade in record["recent_trades_snapshot"] if _restorable(trade)]
        if not _restorable(record["trade_snapshot"]):
            record["trade_snapshot"] = None
        record["trade_restore_allowed"] = bool(record["recent_trades_snapshot"] or record["trade_snapshot"])
        # A final JSON round trip owns every returned container, including any
        # compiler-owned result, and refuses non-finite/non-serializable values.
        return json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False))
    except (TypeError, KeyError, AttributeError, ValueError, RecursionError, OverflowError):
        return _unavailable(value)


def history_list_projection(approved_record):
    """Project metadata only after the same full admission used by detail/export."""
    return {key: approved_record[key] for key in SUMMARY_FIELDS}
