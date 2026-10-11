"""Pure strict content admission for new history writes; no production caller.

Metadata, structured semantics and result are checked independently of legacy
read adapters and semantic normalization. Inputs are never copied or repaired.
The existing pure display grammar/template is used only after exact admission
to check a document and ready body's rendering equality. No seal is consulted.
"""

from datetime import date, datetime
import math
import re

from backend.core.review_display_contract import (
    ReviewDisplayContractError, compile_structured_review, validate_document,
)
from backend.core.review_history_write_contract import (
    HistoryWriteContractError, validate_new_history_access,
)


_SAFE = 2**53 - 1
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?"
)
_PAIRS = {("intraday", "1m"): "1m intraday", ("intraday", "3m"): "3m intraday",
          ("daily", "1d"): "daily OHLCV", ("weekly", "1wk"): "weekly OHLCV"}
_PHASES = ("before_entry", "while_holding", "before_exit")
_METRIC_LABELS = {
    "price_vs_close_pct": ("체결가와 봉 종가 차이", "%"),
    "after_5_bars": ("이후 5개 봉 변화", "%"),
    "after_later_bars": ("이후 봉 변화", "%"),
    "ma5": ("5기간 이동평균", "원"), "ma20": ("20기간 이동평균", "원"),
}


def _require(condition, path):
    if not condition:
        raise HistoryWriteContractError("invalid new-history content: " + path)


def _plain_tree(value):
    """Bound plain JSON before any rendering or schema callback, without copy."""
    active, count = set(), [0]

    def visit(node, depth):
        count[0] += 1
        _require(depth <= 32 and count[0] <= 100_000, "json_bounds")
        if type(node) is dict or type(node) is list:
            _require(id(node) not in active, "json_cycle")
            _require(len(node) <= 100_000, "json_bounds")
            active.add(id(node))
            if type(node) is dict:
                _require(all(type(key) is str for key in node), "json_keys")
                children = node.values()
            else:
                children = node
            for child in children:
                visit(child, depth + 1)
            active.remove(id(node))
        elif type(node) is str:
            _text(node, "json_text", maximum=16384)
        elif type(node) is float:
            _require(math.isfinite(node), "json_number")
        else:
            _require(node is None or type(node) is bool or type(node) is int, "json_type")

    visit(value, 0)


def _object(value, fields, path):
    _require(type(value) is dict and all(type(key) is str for key in value), path)
    _require(value.keys() == fields.keys(), path)
    for key, check in fields.items():
        check(value[key], path + "." + key)


def _array(check, maximum, minimum=0):
    def validate(value, path):
        _require(type(value) is list and minimum <= len(value) <= maximum, path)
        for index, item in enumerate(value):
            check(item, path + "[" + str(index) + "]")
    return validate


def _nullable(check):
    def validate(value, path):
        if value is not None:
            check(value, path)
    return validate


def _text(value, path, *, maximum=900, nonempty=False):
    _require(type(value) is str and len(value) <= maximum, path)
    _require(not nonempty or any(not char.isspace() for char in value), path)
    _require(not any(ord(char) < 9 or 10 < ord(char) < 32 or ord(char) == 127
                     or 0xD800 <= ord(char) <= 0xDFFF for char in value), path)


def _string(maximum=900, *, nonempty=True):
    return lambda value, path: _text(value, path, maximum=maximum, nonempty=nonempty)


def _enum(*choices):
    return lambda value, path: _require(type(value) is str and value in choices, path)


def _integer(value, path, *, minimum=0):
    _require(type(value) is int and minimum <= value <= _SAFE, path)


def _id(value, path):
    _integer(value, path, minimum=1)


def _number(value, path, *, floating=False, minimum=None, positive=False):
    _require(type(value) is float or not floating and type(value) is int, path)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite and (minimum is None or value >= minimum) and (not positive or value > 0), path)


def _float(value, path):
    _number(value, path, floating=True)


def _positive_float(value, path):
    _number(value, path, floating=True, positive=True)


def _positive(value, path):
    _number(value, path, positive=True)


def _nonnegative(value, path):
    _number(value, path, minimum=0)


def _calendar_date(value, path):
    _require(type(value) is str and _DATE.fullmatch(value) is not None, path)
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HistoryWriteContractError("invalid new-history content: " + path) from None


def _trade_date(value, path):
    _require(type(value) is str, path)
    if _DATE.fullmatch(value):
        _calendar_date(value, path)
        return
    _require(_DATETIME.fullmatch(value) is not None, path)
    if re.search(r"[+-][0-9]{2}:[0-9]{2}$", value):
        _require(int(value[-5:-3]) <= 23 and int(value[-2:]) <= 59, path)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HistoryWriteContractError("invalid new-history content: " + path) from None


def _ticker(value, path, *, required=False):
    _require(type(value) is str and (not required and value == "" or re.fullmatch(r"[0-9]{6}", value)), path)


def _document(value, path, surface="body"):
    # Check plain keys and scalar types ourselves, including schema_version;
    # display validation cannot admit subclass equality or duck-typed values.
    _object(value, {"schema_version": _enum("review-display.v1"), "surface": _enum(surface),
                    "blocks": _array(_block, 64, 1), "canonical_text": _string(16384)}, path)
    try:
        validate_document(value, expected_surface=surface)
    except ReviewDisplayContractError:
        raise HistoryWriteContractError("invalid new-history content: " + path) from None


def _surface_document(value, path, surface, *, minimum=1, maximum=1, literal=False):
    _document(value, path, surface)
    blocks = value["blocks"]
    _require(minimum <= len(blocks) <= maximum, path + ".blocks")
    for index, block in enumerate(blocks):
        _require(block["type"] == "paragraph"
                 and block["separator_after"] == ("\n" if index < len(blocks) - 1 else ""), path + ".blocks")
        _require(not literal or all(run["type"] == "text" for run in block["runs"]), path + ".runs")


def _block(value, path):
    _object(value, {"type": _enum("heading", "paragraph", "list_item", "divider"),
                    "runs": _array(_run, 64, 1), "separator_after": _string(16, nonempty=False)}, path)


def _run(value, path):
    _object(value, {"type": _enum("text", "strong"),
                    "text": lambda v, p: _text(v, p, maximum=4096)}, path)
    _require(bool(value["text"]), path + ".text")


def _literal_relation(document, lines, path):
    _document(document, path)
    _require(len(document["blocks"]) == len(lines), path)
    for index, (block, line) in enumerate(zip(document["blocks"], lines)):
        _require(block["type"] == "paragraph" and all(run["type"] == "text" for run in block["runs"]), path)
        _require("".join(run["text"] for run in block["runs"]) == line, path)
        _require(block["separator_after"] == ("\n" if index < len(lines) - 1 else ""), path)


def _trade(value, path):
    _require(type(value) is dict, path)
    fields = {"trade_date": _trade_date, "ticker": _ticker, "name": _string(120),
              "side": _enum("buy", "sell"), "price": _positive_float, "quantity": _positive_float,
              "fee": lambda v, p: _number(v, p, floating=True, minimum=0),
              "tax": lambda v, p: _number(v, p, floating=True, minimum=0),
              "memo": _string(5000, nonempty=False), "source": _string(40), "display_snapshot": _document}
    if "id" in value:
        fields["id"] = _id
    _object(value, fields, path)
    lines = ["매매 기록"]
    for key, label in (("trade_date", "체결일"), ("ticker", "종목 코드"), ("name", "종목"),
                       ("side", "구분"), ("memo", "메모"), ("source", "기록 출처")):
        if value[key]:
            lines.append(label + ": " + value[key])
    lines.append("종목 및 메모: " + value["name"] + " " + value["memo"])
    _literal_relation(value["display_snapshot"], lines, path + ".display_snapshot")


def _chart_time(value, path, timeframe):
    if timeframe == "intraday":
        _integer(value, path)
    else:
        _calendar_date(value, path)


def _candle(value, path, timeframe, *, metadata=False):
    numeric = _float if metadata else _number
    fields = {"time": lambda v, p: _chart_time(v, p, timeframe),
              **dict.fromkeys(("open", "high", "low", "close", "volume"), numeric),
              "ma5": _nullable(numeric), "ma20": _nullable(numeric)}
    if metadata:
        fields["label"] = _string(16)
    _object(value, fields, path)
    _require(min(value[key] for key in ("open", "high", "low", "close")) > 0 and value["volume"] >= 0, path)
    _require(value["low"] <= min(value["open"], value["close"]) <= max(value["open"], value["close"]) <= value["high"], path)
    _require(all(value[key] is None or value[key] >= 0 for key in ("ma5", "ma20")), path)
    if metadata:
        if timeframe == "intraday":
            _require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", value["label"]), path)
            _trade_date(value["label"], path + ".label")
        else:
            _require(value["label"] == value["time"], path + ".label")


def _fill(value, path, side):
    fields = {"id": _nullable(_id), "date": _trade_date, "price": _positive_float, "quantity": _positive_float}
    if side == "sell":
        fields.update(profit_amount=_nullable(_float), return_rate=_nullable(_float))
    _object(value, fields, path)
    if side == "sell":
        _require(value["profit_amount"] is not None or value["return_rate"] is None, path + ".unmatched_return_rate")


def _metadata_marker(value, path, timeframe, candle_times):
    _require(type(value) is dict and type(value.get("side")) is str and value["side"] in ("buy", "sell"), path)
    side = value["side"]
    _object(value, {
        "time": lambda v, p: _chart_time(v, p, timeframe), "side": _enum(side),
        "position": _enum("belowBar" if side == "buy" else "aboveBar"),
        "color": _enum("#2962ff" if side == "buy" else "#ff5252"),
        "shape": _enum("arrowUp" if side == "buy" else "arrowDown"), "size": _integer,
        "text": _string(24), "trades": _array(lambda v, p: _fill(v, p, side), 300, 1),
        "tooltip": lambda v, p: _metadata_tooltip(v, p, side), "display_snapshot": _document,
    }, path)
    tooltip, fills = value["tooltip"], value["trades"]
    _require(value["size"] == 2 and value["time"] in candle_times, path)
    expected = ("B" if side == "buy" else "S") + (str(len(fills)) if len(fills) > 1 else "")
    _require(value["text"] == expected and tooltip["count"] == len(fills), path)
    _require(tooltip["prices"] == [row["price"] for row in fills], path + ".tooltip.prices")
    quantity = sum(row["quantity"] for row in fills)
    try:
        average = round(sum(row["price"] * row["quantity"] for row in fills) / quantity, 0)
    except (OverflowError, ZeroDivisionError):
        raise HistoryWriteContractError("invalid new-history content: " + path) from None
    _require(tooltip["total_quantity"] == round(quantity, 4) and tooltip["avg_price"] == average, path)
    if side == "sell":
        profits = [row["profit_amount"] for row in fills if row["profit_amount"] is not None]
        _require(tooltip["profit_amount"] == (round(sum(profits), 0) if profits else None), path)
        _require(bool(profits) or tooltip["return_rate"] is None, path + ".unmatched_return_rate")
    _literal_relation(value["display_snapshot"], [expected], path + ".display_snapshot")


def _metadata_tooltip(value, path, side):
    fields = {"label": _enum("매수" if side == "buy" else "매도"), "count": _id,
              "avg_price": _positive_float, "total_quantity": _positive_float,
              "prices": _array(_positive_float, 300, 1), "display_snapshot": _document}
    if side == "sell":
        fields.update(profit_amount=_nullable(_float), return_rate=_nullable(_float))
    _object(value, fields, path)
    _require(value["count"] == len(value["prices"]), path)
    lines = [value["label"] + (f" {value['count']}건" if value["count"] > 1 else ""),
             f"평균 {value['avg_price']:,.0f}원 · 수량 {value['total_quantity']}",
             ", ".join(f"{price:,.0f}" for price in value["prices"]) + "원"]
    if side == "sell" and value["profit_amount"] is not None:
        lines.append(f"실현 {value['profit_amount']:+,.0f}원 · {value['return_rate'] or 0:+}%")
    _literal_relation(value["display_snapshot"], lines, path + ".display_snapshot")


def _metadata_card(value, path, *, unavailable=False):
    fields = {"title": _string(160), "detail": _string(), "display_snapshot": _document}
    if not unavailable:
        fields.update(trade_id=_nullable(_id), metrics=lambda v, p: _object(v, {
            "price_vs_close_pct": _float, **dict.fromkeys(("after_5_bars", "after_later_bars", "ma5", "ma20"), _nullable(_float)),
        }, p))
    _object(value, fields, path)
    lines = [value["title"] + ": " + value["detail"]]
    if not unavailable:
        for key, (label, unit) in _METRIC_LABELS.items():
            if value["metrics"][key] is not None:
                lines.append(f"{label}: {value['metrics'][key]}{unit}")
    _literal_relation(value["display_snapshot"], lines, path + ".display_snapshot")


def _metadata_chart(value, path):
    _require(type(value) is dict and type(value.get("candles")) is list, path)
    available = bool(value["candles"])
    fields = {"ticker": lambda v, p: _ticker(v, p, required=True), "name": _string(120),
              "timeframe": _enum("intraday", "daily", "weekly"), "interval": _enum("1m", "3m", "1d", "1wk"),
              "source": _string(40), "candles": lambda v, p: None, "markers": lambda v, p: None,
              "reviews": _array(lambda v, p: _metadata_card(v, p, unavailable=not available), 100, 1),
              "display_snapshot": _document}
    if available:
        fields["period_label"] = _chart_period
    _object(value, fields, path)
    pair = value["timeframe"], value["interval"]
    _require(pair in _PAIRS and value["source"] == _PAIRS[pair], path)
    _array(lambda v, p: _candle(v, p, value["timeframe"], metadata=True), 500)(value["candles"], path + ".candles")
    times = {row["time"] for row in value["candles"]}
    _array(lambda v, p: _metadata_marker(v, p, value["timeframe"], times), 300)(value["markers"], path + ".markers")
    if not available:
        _require(pair == ("daily", "1d") and not value["markers"] and len(value["reviews"]) == 1, path)
        _require(value["reviews"][0]["title"] == value["name"]
                 and value["reviews"][0]["detail"] == "차트 데이터를 가져오지 못했습니다.", path)
    lines = ["매매 차트", "종목: " + value["name"], "종목 코드: " + value["ticker"],
             "차트 주기: " + value["timeframe"], "봉 간격: " + value["interval"]]
    if available:
        lines.append("기간: " + value["period_label"])
    lines.append("차트 출처: " + value["source"])
    _literal_relation(value["display_snapshot"], lines, path + ".display_snapshot")


def _chart_period(value, path):
    _require(type(value) is str and len(value) <= 23, path)
    parts = value.split(" ~ ")
    _require(1 <= len(parts) <= 2, path)
    for part in parts:
        _calendar_date(part, path)
    _require(parts[0] <= parts[-1], path)


def validate_new_history_metadata(metadata):
    """Validate complete canonical producer metadata, without a result/seal."""
    _plain_tree(metadata)
    _object(metadata, {"ticker": _ticker, "name": _string(120), "trade_date": _trade_date,
                       "target_trade_id": _nullable(_id), "trade_snapshot": _trade,
                       "recent_trades_snapshot": _array(_trade, 10, 1),
                       "chart_snapshot": lambda v, p: _object(v, {"charts": _array(_metadata_chart, 8)}, p)}, "metadata")
    _require(all(metadata[key] == metadata["trade_snapshot"][key] for key in ("ticker", "name", "trade_date")), "metadata.trade_identity")
    # Target may be absent, outside the recent window or an unmatched requested
    # ID. Neither target membership nor id equality is a producer invariant.


_QUALITY = lambda v, p: _object(v, {
    "label": _enum("탁월", "보통 이상", "보통", "보통 이하", "판단 보류"), "explanation": _string(),
}, p)
_ASSESSMENT = lambda v, p: _object(v, {
    "label": _enum("근거 충분", "근거 일부", "근거 부족", "판단 보류"), "explanation": _string(),
}, p)
_CARD = lambda v, p: _object(v, {"title": _string(160), "detail": _string()}, p)
_LESSON = {"title": _string(), "concept": _string(), "applied_to_this_trade": _string()}


def _objective(value, path):
    counts = ("trade_count", "closed_count", "buy_fill_count", "sell_fill_count", "symbol_count")
    fields = {**dict.fromkeys(counts, _integer),
              **dict.fromkeys(("realized_pnl", "realized_return_pct", "win_rate_pct"), _number),
              **dict.fromkeys(("total_fee", "total_tax", "open_quantity"), _nonnegative),
              "weighted_buy_price": _nullable(_positive), "weighted_sell_price": _nullable(_positive)}
    _object(value, {"symbol": lambda v, p: _object(v, {"ticker": _ticker, "name": _string(120)}, p),
                    "period": lambda v, p: _object(v, {"first_trade_date": _trade_date, "last_trade_date": _trade_date}, p),
                    "result": lambda v, p: _object(v, fields, p)}, path)
    result = value["result"]
    _require(value["period"]["first_trade_date"][:10] <= value["period"]["last_trade_date"][:10], path + ".period")
    _require(result["closed_count"] <= result["trade_count"]
             and result["buy_fill_count"] + result["sell_fill_count"] == result["trade_count"], path + ".counts")


def _structured(value, review_type, path):
    section = {
        "good_points": _array(_CARD, 2, 1), "main_improvement": _CARD,
        "next_trade_checks": _array(lambda v, p: _object(v, {"phase": _enum(*_PHASES), "text": _string()}, p), 3, 1),
        "lesson": lambda v, p: _object(v, _LESSON, p),
    } if review_type == "basic" else {
        "entry_review": lambda v, p: _object(v, {"evidence": _array(_string(), 4, 1), "uncertainty": _array(_string(), 4),
                                                 "invalidation": _string(), "assessment": _ASSESSMENT}, p),
        "risk_review": lambda v, p: _object(v, {"planned_rule": _string(), "actual_response": _string(), "assessment": _ASSESSMENT}, p),
        "exit_review": lambda v, p: _object(v, dict.fromkeys(("profit_taking_assessment", "trend_exit_assessment", "explanation"), _string()), p),
        "detailed_analysis": _array(_CARD, 5),
        "next_trade_playbook": lambda v, p: _object(v, dict.fromkeys(_PHASES, _array(_string(), 3, 1)), p),
        "lesson": lambda v, p: _object(v, {**_LESSON, "next_trade_application": _string()}, p),
        "reflection_questions": _array(_string(), 2),
    }
    _object(value, {"schema_version": _enum("trade-review.v1"), "review_type": _enum(review_type),
                    "objective": _objective, "summary": lambda v, p: _object(v, {
                        "decision_quality": _QUALITY, "main_issue": _string(), "next_action": _string(),
                        "data_confidence": lambda v, p: _object(v, {"level": _enum("low", "medium", "high"),
                            "label": _enum("낮음", "보통", "높음"), "reasons": _array(_string(), 5)}, p),
                        "missing_information": _array(_string(), 4),
                    }, p), review_type: lambda v, p: _object(v, section, p)}, path)
    confidence = value["summary"]["data_confidence"]
    _require(confidence["label"] == {"low": "낮음", "medium": "보통", "high": "높음"}[confidence["level"]], path + ".confidence")


def validate_new_history_structured_review(structured, *, review_type):
    """Check complete emitted semantics; never normalize a model/legacy tree."""
    _require(type(review_type) is str and review_type in ("basic", "advanced"), "review_type")
    _plain_tree(structured)
    _structured(structured, review_type, "structured_review")


def _display_chart(value, path):
    _require(type(value) is dict, path)
    _object(value, {"ticker": lambda v, p: _ticker(v, p, required=True), "timeframe": _enum("intraday", "daily", "weekly"),
                    "interval": _enum("1m", "3m", "1d", "1wk"),
                    "header": lambda v, p: _surface_document(v, p, "chart_header", literal=True),
                    "tab": lambda v, p: _surface_document(v, p, "chart_tab"),
                    "candles": lambda v, p: None, "markers": lambda v, p: None}, path)
    _require((value["timeframe"], value["interval"]) in _PAIRS, path)
    prefix = {"intraday": "분봉", "daily": "일봉", "weekly": "주봉"}[value["timeframe"]] + " · " + value["interval"] + " · "
    _require(value["header"]["canonical_text"].startswith(prefix), path + ".header")
    _chart_period(value["header"]["canonical_text"][len(prefix):], path + ".header_period")
    _text(value["tab"]["canonical_text"], path + ".tab", maximum=120, nonempty=True)
    _array(lambda v, p: _candle(v, p, value["timeframe"]), 500, 1)(value["candles"], path + ".candles")
    times = {row["time"] for row in value["candles"]}

    def marker(item, marker_path):
        _object(item, {"time": lambda v, p: _chart_time(v, p, value["timeframe"]), "side": _enum("buy", "sell"),
                       "label": _nullable(lambda v, p: _surface_document(v, p, "marker_label", literal=True)),
                       "tooltip": _nullable(lambda v, p: _surface_document(v, p, "marker_tooltip", minimum=3, maximum=4, literal=True))}, marker_path)
        _require(item["time"] in times, marker_path)
        count = None
        if item["label"] is not None:
            label = item["label"]["canonical_text"]
            initial = "B" if item["side"] == "buy" else "S"
            _require(re.fullmatch(initial + r"(?:[1-9][0-9]{0,2})?", label), marker_path + ".label")
            count = 1 if label == initial else int(label[1:])
            _require(label == initial or 2 <= count <= 300, marker_path + ".label_count")
        if item["tooltip"] is not None:
            _require(item["side"] == "sell" or len(item["tooltip"]["blocks"]) == 3, marker_path + ".tooltip_blocks")
            first_block = item["tooltip"]["blocks"][0]
            title = "".join(run["text"] for run in first_block["runs"])
            match = re.fullmatch(("매수" if item["side"] == "buy" else "매도") + r" ([1-9][0-9]{0,2})건", title)
            _require(match is not None, marker_path + ".tooltip_title")
            actual_count = int(match[1])
            _require(actual_count <= 300 and (count is None or count == actual_count), marker_path + ".tooltip_count")

    _array(marker, 300)(value["markers"], path + ".markers")


def _display_card(value, path):
    _object(value, {"trade_id": _nullable(_id), "display": lambda v, p: _surface_document(v, p, "chart_card"),
                    "metrics": lambda v, p: _object(v, dict.fromkeys(("rsi14", "return_10d_before", "volume_ratio_20d",
                                                                      "next_5d_return", "next_20d_return"), _nullable(_number)), p)}, path)


def validate_new_history_result(result):
    """Validate the new producer result including unchanged Step 2 access.

    Ready body equality checks a pure display template after independent strict
    semantic admission. Missing-key uses a distinct chart-rules body; its text
    is not reconstructed from the partial metadata window. Seal identity and
    authorization/write approval remain outside this contract.
    """
    _plain_tree(result)
    _require(type(result) is dict and type(result.get("review_type")) is str
             and result["review_type"] in ("basic", "advanced"), "result.review_type")
    review_type = result["review_type"]
    fields = {"status": _enum("ready", "missing_key"), "source": _enum("openai", "chart-rules"),
              "review_type": _enum(review_type), "model": _nullable(_string(100)), "summary": _string(16384),
              "display_snapshot": _document, "structured_review": lambda v, p: _structured(v, review_type, p),
              "chart_display_snapshot": lambda v, p: _object(v, {"charts": _array(_display_chart, 8),
                                                                  "chart_cards": _array(_display_card, 100)}, p),
              "chart_contexts": _array(lambda v, p: None, 0), "chart_reviews": _array(lambda v, p: None, 0),
              "access": lambda v, p: None}
    fields["chart_snapshot" if review_type == "basic" else "chart_snapshots"] = (
        (lambda v, p: _object(v, {}, p)) if review_type == "basic" else _array(lambda v, p: None, 0))
    _object(result, fields, "result")
    if result["status"] == "ready":
        _require(result["source"] == "openai" and type(result["model"]) is str
                 and re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", result["model"]), "result.ready_origin")
        try:
            expected_body, _paths = compile_structured_review(result["structured_review"])
        except ReviewDisplayContractError:
            raise HistoryWriteContractError("invalid new-history content: result.ready_body") from None
        _require(result["display_snapshot"] == expected_body, "result.ready_body")
    else:
        _require(result["source"] == "chart-rules" and result["model"] is None, "result.missing_key_origin")
    body = result["display_snapshot"]
    _require(all(block["type"] == "paragraph" for block in body["blocks"]), "result.body_blocks")
    summary = "".join("".join("**" + run["text"] + "**" if run["type"] == "strong" else run["text"]
                              for run in block["runs"]) + block["separator_after"] for block in body["blocks"])
    _require(result["summary"] == summary, "result.summary_body")
    validate_new_history_access(result["access"], review_type=review_type, status=result["status"])
