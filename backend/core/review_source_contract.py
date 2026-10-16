"""Pure, fail-closed admission for canonical review compiler inputs.
Raw dictionaries are accepted only by the public ``admit_*`` factories. DTOs
own immutable scalar values and tuples, never caller-owned containers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
from typing import Literal

from core.trade_review_schema import (
    MAX_REVIEW_TEXT_CHARS, normalize_semantic_output, structured_output_schema,
)


MAX_SAFE_INTEGER = 2**53 - 1
MAX_NAME_CHARS = 120
MAX_SOURCE_CHARS = 40
DEFAULT_MEMO_MAX_CHARS = 2000
MAX_MEMO_CHARS = 5000
EMPTY_REVIEW_TEXT = "매매 기록을 먼저 입력하세요."
UNAVAILABLE_REVIEW_TEXT = "AI 복기 내용을 안전하게 표시할 수 없습니다. 거래 기록을 직접 확인해 주세요."
_CODE = re.compile(r"[0-9]{6}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?\Z"
)
_CANDLE_LABEL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\Z")
_INTERVALS = {("intraday", "1m"), ("intraday", "3m"),
              ("daily", "1d"), ("weekly", "1wk")}
_TECHNICAL_METRICS = ("price_vs_close_pct", "after_5_bars", "after_later_bars", "ma5", "ma20")
_CONTEXT_METRICS = ("close", "price_vs_close_pct", "ma5", "ma20", "ma60", "rsi14",
                    "volume_ratio_20d", "return_10d_before", "position_in_20d_range",
                    "next_5d_return", "next_20d_return")


class SourceAdmissionError(ValueError):
    """A raw producer or model value violates the source contract."""


class _FactoryOnly:
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        raise TypeError("use an admit_* source factory")

    def __reduce_ex__(self, protocol):
        raise TypeError("source DTO restoration is unsupported")


def _reject_source_state_restore(self, state):
    raise TypeError("source DTO state restoration is unsupported")


def _source_dto(cls):
    """Build a factory-only DTO and replace dataclasses' generated state loader."""
    dto = dataclass(frozen=True, slots=True, init=False)(cls)
    dto.__setstate__ = _reject_source_state_restore
    return dto


def _make(cls, **fields):
    value = object.__new__(cls)
    for key, field in fields.items():
        object.__setattr__(value, key, field)
    return value


@_source_dto
class TradeSource(_FactoryOnly):
    variant: Literal["basic", "identified", "stored"]
    symbol_kind: Literal["krx", "name_only"]
    trade_date: str
    ticker: str
    name: str
    side: Literal["buy", "sell"]
    price: int | float
    quantity: int | float
    fee: int | float
    tax: int | float
    memo: str
    source: str
    id: int | None
    created_at: str | None
    user_id: str | None


@_source_dto
class ObjectiveSymbol(_FactoryOnly):
    ticker: str
    name: str
    symbol_kind: Literal["krx", "name_only"]


@_source_dto
class ObjectivePeriod(_FactoryOnly):
    first_trade_date: str
    last_trade_date: str


@_source_dto
class ObjectiveResult(_FactoryOnly):
    trade_count: int
    closed_count: int
    realized_pnl: int | float
    realized_return_pct: int | float
    win_rate_pct: int | float
    weighted_buy_price: int | float | None
    weighted_sell_price: int | float | None
    total_fee: int | float
    total_tax: int | float
    buy_fill_count: int
    sell_fill_count: int
    open_quantity: int | float
    symbol_count: int


@_source_dto
class ObjectiveSource(_FactoryOnly):
    symbol: ObjectiveSymbol
    period: ObjectivePeriod
    result: ObjectiveResult


@_source_dto
class UnavailableObjectiveSource(_FactoryOnly):
    kind: Literal["unavailable"]
    reason: Literal["no_trades"]


@_source_dto
class CandleSource(_FactoryOnly):
    time: str | int
    t: str
    o: int | float
    h: int | float
    l: int | float
    c: int | float
    v: int | float
    ma5: int | float | None
    ma20: int | float | None


@_source_dto
class BuyTooltipSource(_FactoryOnly):
    label: Literal["매수"]
    count: int
    avg_price: int | float
    total_quantity: int | float
    prices: tuple[int | float, ...]


@_source_dto
class SellTooltipSource(_FactoryOnly):
    label: Literal["매도"]
    count: int
    avg_price: int | float
    total_quantity: int | float
    prices: tuple[int | float, ...]
    profit_amount: int | float | None
    return_rate: int | float | None


@_source_dto
class MarkerSource(_FactoryOnly):
    time: str | int
    side: Literal["buy", "sell"]
    text: str | None
    tooltip: BuyTooltipSource | SellTooltipSource


@_source_dto
class TechnicalMetricsSource(_FactoryOnly):
    price_vs_close_pct: int | float
    after_5_bars: int | float | None
    after_later_bars: int | float | None
    ma5: int | float | None
    ma20: int | float | None


@_source_dto
class TechnicalObservationSource(_FactoryOnly):
    trade_id: int | None
    title: str
    detail: str
    metrics: TechnicalMetricsSource


@_source_dto
class UnavailableObservationSource(_FactoryOnly):
    title: str
    detail: str


@_source_dto
class CompactChartSource(_FactoryOnly):
    ticker: str
    name: str
    timeframe: Literal["intraday", "daily", "weekly"]
    interval: Literal["1m", "3m", "1d", "1wk"]
    period: str
    candles: tuple[CandleSource, ...]
    trade_markers: tuple[MarkerSource, ...]
    rule_based_observations: tuple[TechnicalObservationSource | UnavailableObservationSource, ...]


@_source_dto
class UnavailableChartSource(_FactoryOnly):
    kind: Literal["unavailable"]
    reason: Literal["no_market_data", "provider_error"]


@_source_dto
class AnalysisContextSource(_FactoryOnly):
    trade_id: int | None
    date: str
    market_date: str
    ticker: str
    name: str
    side: Literal["buy", "sell"]
    price: int | float
    quantity: int | float
    memo: str
    close: int | float
    price_vs_close_pct: int | float | None
    ma5: int | float | None
    ma20: int | float | None
    ma60: int | float | None
    rsi14: int | float | None
    volume_ratio_20d: int | float | None
    return_10d_before: int | float | None
    position_in_20d_range: int | float | None
    next_5d_return: int | float | None
    next_20d_return: int | float | None


@_source_dto
class AnalysisContextErrorSource(_FactoryOnly):
    error: str
    trade: TradeSource


@_source_dto
class SemanticQuality(_FactoryOnly):
    label: str
    explanation: str


@_source_dto
class SemanticCard(_FactoryOnly):
    title: str
    detail: str


@_source_dto
class SemanticCheck(_FactoryOnly):
    phase: Literal["before_entry", "while_holding", "before_exit"]
    text: str


@_source_dto
class SemanticLesson(_FactoryOnly):
    title: str
    concept: str
    applied_to_this_trade: str
    next_trade_application: str | None


@_source_dto
class BasicSemanticSource(_FactoryOnly):
    decision_quality: SemanticQuality
    main_issue: str
    next_action: str
    good_points: tuple[SemanticCard, ...]
    main_improvement: SemanticCard
    next_trade_checks: tuple[SemanticCheck, ...]
    lesson: SemanticLesson


@_source_dto
class SemanticEntryReview(_FactoryOnly):
    evidence: tuple[str, ...]
    uncertainty: tuple[str, ...]
    invalidation: str
    assessment: SemanticQuality


@_source_dto
class SemanticRiskReview(_FactoryOnly):
    planned_rule: str
    actual_response: str
    assessment: SemanticQuality


@_source_dto
class SemanticExitReview(_FactoryOnly):
    profit_taking_assessment: str
    trend_exit_assessment: str
    explanation: str


@_source_dto
class SemanticPlaybook(_FactoryOnly):
    before_entry: tuple[str, ...]
    while_holding: tuple[str, ...]
    before_exit: tuple[str, ...]


@_source_dto
class AdvancedSemanticSource(_FactoryOnly):
    decision_quality: SemanticQuality
    main_issue: str
    next_action: str
    entry_review: SemanticEntryReview
    risk_review: SemanticRiskReview
    exit_review: SemanticExitReview
    detailed_analysis: tuple[SemanticCard, ...]
    next_trade_playbook: SemanticPlaybook
    lesson: SemanticLesson
    reflection_questions: tuple[str, ...]


@_source_dto
class ValidatedReviewSource(_FactoryOnly):
    review_type: Literal["basic", "advanced"]
    status: Literal["ready", "error", "missing_key", "empty"]
    origin: Literal["openai", "chart-rules", "none"]
    trades: tuple[TradeSource, ...]
    objective: ObjectiveSource | UnavailableObjectiveSource
    charts: tuple[CompactChartSource | UnavailableChartSource, ...]
    analysis_contexts: tuple[AnalysisContextSource | AnalysisContextErrorSource, ...]
    semantic: BasicSemanticSource | AdvancedSemanticSource | None
    has_market_data: bool
    notice: str | None


def _keys(value, variants, path):
    if type(value) is not dict or not any(set(value) == set(keys) for keys in variants):
        raise SourceAdmissionError(f"invalid exact object at {path}")


def _list(value, path):
    if type(value) is not list:
        raise SourceAdmissionError(f"expected raw list at {path}")
    return value


def _text(value, path, *, maximum, nonempty=False):
    if type(value) is not str or len(value) > maximum or (nonempty and not value.strip()):
        raise SourceAdmissionError(f"invalid text at {path}")
    return value


def _enum(value, choices, path):
    if type(value) is not str or value not in choices:
        raise SourceAdmissionError(f"invalid enum at {path}")
    return value


def _number(value, path, *, minimum=None, nullable=False):
    if value is None and nullable:
        return None
    if type(value) not in (int, float):
        raise SourceAdmissionError(f"invalid number at {path}")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (minimum is not None and value < minimum):
        raise SourceAdmissionError(f"invalid finite number at {path}")
    return value


def _count(value, path, *, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise SourceAdmissionError(f"invalid integer at {path}")
    return value


def _calendar_date(value, path):
    if type(value) is not str or _DATE.fullmatch(value) is None:
        raise SourceAdmissionError(f"invalid date at {path}")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise SourceAdmissionError(f"invalid calendar date at {path}") from error
    return value


def _date_time(value, path, *, date_allowed=False):
    if date_allowed and type(value) is str and _DATE.fullmatch(value):
        return _calendar_date(value, path)
    if type(value) is not str or _DATETIME.fullmatch(value) is None:
        raise SourceAdmissionError(f"invalid datetime at {path}")
    if value[-1] != "Z" and re.search(r"[+-][0-9]{2}:[0-9]{2}\Z", value):
        offset = value[-6:]
        if int(offset[1:3]) > 23 or int(offset[4:6]) > 59:
            raise SourceAdmissionError(f"invalid timezone offset at {path}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SourceAdmissionError(f"invalid calendar datetime at {path}") from error
    return value


def _ticker(value, path):
    if type(value) is not str or (value and _CODE.fullmatch(value) is None):
        raise SourceAdmissionError(f"invalid KRX code at {path}")
    return value


def _symbol(ticker, name, path):
    code = _ticker(ticker, path + ".ticker")
    _text(name, path + ".name", maximum=MAX_NAME_CHARS, nonempty=True)
    return "krx" if code else "name_only"


def admit_trade_source(raw, *, memo_max_chars=DEFAULT_MEMO_MAX_CHARS):
    """Admit all fields before any display eligibility or prompt windowing."""
    limit = _count(memo_max_chars, "memo_max_chars", minimum=1)
    if limit > MAX_MEMO_CHARS:
        raise SourceAdmissionError("memo limit exceeds product maximum")
    base = {"trade_date", "ticker", "name", "side", "price", "quantity", "fee", "tax", "memo", "source"}
    _keys(raw, (base, base | {"id"}, base | {"id", "created_at", "user_id"}), "trade")
    variant = "stored" if "created_at" in raw else "identified" if "id" in raw else "basic"
    symbol_kind = _symbol(raw["ticker"], raw["name"], "trade")
    fields = dict(
        variant=variant, symbol_kind=symbol_kind,
        trade_date=_date_time(raw["trade_date"], "trade.trade_date", date_allowed=True),
        ticker=raw["ticker"], name=raw["name"],
        side=_enum(raw["side"], ("buy", "sell"), "trade.side"),
        price=_number(raw["price"], "trade.price", minimum=0),
        quantity=_number(raw["quantity"], "trade.quantity", minimum=0),
        fee=_number(raw["fee"], "trade.fee", minimum=0),
        tax=_number(raw["tax"], "trade.tax", minimum=0),
        memo=_text(raw["memo"], "trade.memo", maximum=limit),
        source=_text(raw["source"], "trade.source", maximum=MAX_SOURCE_CHARS, nonempty=True),
        id=_count(raw["id"], "trade.id", minimum=1) if "id" in raw else None,
        created_at=_date_time(raw["created_at"], "trade.created_at") if variant == "stored" else None,
        user_id=_text(raw["user_id"], "trade.user_id", maximum=256) if variant == "stored" else None,
    )
    if fields["price"] <= 0 or fields["quantity"] <= 0:
        raise SourceAdmissionError("trade price and quantity must be positive")
    return _make(TradeSource, **fields)


_RESULT_KEYS = {"trade_count", "closed_count", "realized_pnl", "realized_return_pct",
                "win_rate_pct", "weighted_buy_price", "weighted_sell_price", "total_fee",
                "total_tax", "buy_fill_count", "sell_fill_count", "open_quantity", "symbol_count"}


def admit_objective_source(raw):
    if type(raw) is dict and set(raw) == {"kind", "reason"}:
        if raw["kind"] != "unavailable" or raw["reason"] != "no_trades":
            raise SourceAdmissionError("invalid unavailable objective")
        return _make(UnavailableObjectiveSource, kind="unavailable", reason="no_trades")
    _keys(raw, ({"symbol", "period", "result"},), "objective")
    symbol, period, result = raw["symbol"], raw["period"], raw["result"]
    _keys(symbol, ({"ticker", "name"},), "objective.symbol")
    symbol_kind = _symbol(symbol["ticker"], symbol["name"], "objective.symbol")
    _keys(period, ({"first_trade_date", "last_trade_date"},), "objective.period")
    first = _date_time(period["first_trade_date"], "objective.period.first", date_allowed=True)
    last = _date_time(period["last_trade_date"], "objective.period.last", date_allowed=True)
    if first[:10] > last[:10]:
        raise SourceAdmissionError("objective period is reversed")
    _keys(result, (_RESULT_KEYS,), "objective.result")
    counts = {key: _count(result[key], "objective.result." + key)
              for key in ("trade_count", "closed_count", "buy_fill_count", "sell_fill_count", "symbol_count")}
    if (counts["closed_count"] > counts["trade_count"] or
            counts["buy_fill_count"] + counts["sell_fill_count"] != counts["trade_count"]):
        raise SourceAdmissionError("inconsistent objective counts")
    numeric = {key: _number(result[key], "objective.result." + key,
                            minimum=0 if key in {"total_fee", "total_tax", "open_quantity"} else None,
                            nullable=key in {"weighted_buy_price", "weighted_sell_price"})
               for key in _RESULT_KEYS - set(counts)}
    for key in ("weighted_buy_price", "weighted_sell_price"):
        if numeric[key] is not None and numeric[key] <= 0:
            raise SourceAdmissionError("weighted price must be positive")
    return _make(ObjectiveSource,
                 symbol=_make(ObjectiveSymbol, ticker=symbol["ticker"], name=symbol["name"],
                              symbol_kind=symbol_kind),
                 period=_make(ObjectivePeriod, first_trade_date=first, last_trade_date=last),
                 result=_make(ObjectiveResult, **counts, **numeric))


def _chart_time(value, path):
    if type(value) is int:
        return _count(value, path)
    return _calendar_date(value, path)


def _chart_label(value, path):
    if type(value) is str and _CANDLE_LABEL.fullmatch(value):
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError as error:
            raise SourceAdmissionError(f"invalid candle label at {path}") from error
        return value
    return _calendar_date(value, path)


def admit_candle_source(raw, *, timeframe):
    _keys(raw, ({"time", "t", "o", "h", "l", "c", "v", "ma5", "ma20"},), "candle")
    _enum(timeframe, ("intraday", "daily", "weekly"), "candle.timeframe")
    time = _chart_time(raw["time"], "candle.time")
    label = _chart_label(raw["t"], "candle.t")
    if timeframe == "intraday":
        if type(time) is not int or _CANDLE_LABEL.fullmatch(label) is None:
            raise SourceAdmissionError("intraday candle time/label mismatch")
    elif type(time) is not str or label != time:
        raise SourceAdmissionError("daily candle time/label mismatch")
    values = {key: _number(raw[key], "candle." + key, minimum=0) for key in ("o", "h", "l", "c", "v")}
    if (any(values[key] <= 0 for key in ("o", "h", "l", "c")) or
            values["l"] > min(values["o"], values["c"]) or
            max(values["o"], values["c"]) > values["h"]):
        raise SourceAdmissionError("invalid candle OHLC")
    averages = {key: _number(raw[key], "candle." + key, minimum=0, nullable=True)
                for key in ("ma5", "ma20")}
    return _make(CandleSource, time=time, t=label, **values, **averages)


def _tooltip(raw, side):
    common = {"label", "count", "avg_price", "total_quantity", "prices"}
    _keys(raw, (common if side == "buy" else common | {"profit_amount", "return_rate"},), "marker.tooltip")
    expected = "매수" if side == "buy" else "매도"
    if raw["label"] != expected or type(raw["label"]) is not str:
        raise SourceAdmissionError("tooltip label/side mismatch")
    count = _count(raw["count"], "marker.tooltip.count", minimum=1)
    prices = tuple(_number(item, "marker.tooltip.prices", minimum=0)
                   for item in _list(raw["prices"], "marker.tooltip.prices"))
    if len(prices) != count or any(price <= 0 for price in prices):
        raise SourceAdmissionError("tooltip prices/count mismatch")
    avg = _number(raw["avg_price"], "marker.tooltip.avg_price", minimum=0)
    quantity = _number(raw["total_quantity"], "marker.tooltip.total_quantity", minimum=0)
    if avg <= 0 or quantity <= 0:
        raise SourceAdmissionError("invalid tooltip price/quantity")
    common_fields = dict(label=expected, count=count, avg_price=avg,
                         total_quantity=quantity, prices=prices)
    if side == "buy":
        return _make(BuyTooltipSource, **common_fields)
    return _make(SellTooltipSource, **common_fields,
                 profit_amount=_number(raw["profit_amount"], "marker.tooltip.profit_amount", nullable=True),
                 return_rate=_number(raw["return_rate"], "marker.tooltip.return_rate", nullable=True))


def admit_marker_source(raw, *, timeframe):
    base = {"time", "side", "tooltip"}
    _keys(raw, (base, base | {"text"}), "marker")
    _enum(timeframe, ("intraday", "daily", "weekly"), "marker.timeframe")
    side = _enum(raw["side"], ("buy", "sell"), "marker.side")
    time = _chart_time(raw["time"], "marker.time")
    if (timeframe == "intraday") != (type(time) is int):
        raise SourceAdmissionError("marker time/timeframe mismatch")
    tooltip = _tooltip(raw["tooltip"], side)
    text = None
    if "text" in raw:
        text = _text(raw["text"], "marker.text", maximum=24, nonempty=True)
        expected = ("B" if side == "buy" else "S") + (str(tooltip.count) if tooltip.count > 1 else "")
        if text != expected:
            raise SourceAdmissionError("marker text/side/count mismatch")
    return _make(MarkerSource, time=time, side=side, text=text, tooltip=tooltip)


def _observation(raw):
    unavailable = {"title", "detail"}
    technical = unavailable | {"trade_id", "metrics"}
    _keys(raw, (unavailable, technical), "observation")
    title = _text(raw["title"], "observation.title", maximum=160, nonempty=True)
    detail = _text(raw["detail"], "observation.detail", maximum=MAX_REVIEW_TEXT_CHARS, nonempty=True)
    if set(raw) == unavailable:
        return _make(UnavailableObservationSource, title=title, detail=detail)
    metrics = raw["metrics"]
    _keys(metrics, (_TECHNICAL_METRICS,), "observation.metrics")
    values = {key: _number(metrics[key], "observation.metrics." + key,
                           nullable=key != "price_vs_close_pct") for key in _TECHNICAL_METRICS}
    return _make(TechnicalObservationSource,
                 trade_id=None if raw["trade_id"] is None else _count(raw["trade_id"], "observation.trade_id", minimum=1),
                 title=title, detail=detail, metrics=_make(TechnicalMetricsSource, **values))


def _chart_period(value):
    if type(value) is not str:
        raise SourceAdmissionError("invalid chart period")
    parts = value.split(" ~ ")
    if not 1 <= len(parts) <= 2:
        raise SourceAdmissionError("invalid chart period")
    for part in parts:
        _calendar_date(part, "chart.period")
    if len(parts) == 2 and parts[0] > parts[1]:
        raise SourceAdmissionError("reversed chart period")
    return value


def admit_chart_source(raw):
    """A real chart has all eight keys; absence uses an explicit variant."""
    if type(raw) is dict and set(raw) == {"kind", "reason"}:
        _enum(raw["kind"], ("unavailable",), "chart.kind")
        reason = _enum(raw["reason"], ("no_market_data", "provider_error"), "chart.reason")
        return _make(UnavailableChartSource, kind="unavailable", reason=reason)
    _keys(raw, ({"ticker", "name", "timeframe", "interval", "period", "candles",
                  "trade_markers", "rule_based_observations"},), "chart")
    ticker = _ticker(raw["ticker"], "chart.ticker")
    if not ticker:
        raise SourceAdmissionError("available chart requires KRX ticker")
    name = _text(raw["name"], "chart.name", maximum=MAX_NAME_CHARS, nonempty=True)
    timeframe = _enum(raw["timeframe"], ("intraday", "daily", "weekly"), "chart.timeframe")
    interval = _enum(raw["interval"], ("1m", "3m", "1d", "1wk"), "chart.interval")
    if (timeframe, interval) not in _INTERVALS:
        raise SourceAdmissionError("invalid timeframe/interval pair")
    period = _chart_period(raw["period"])
    candles = tuple(admit_candle_source(item, timeframe=timeframe)
                    for item in _list(raw["candles"], "chart.candles"))
    if not candles:
        raise SourceAdmissionError("available chart requires candles")
    markers = tuple(admit_marker_source(item, timeframe=timeframe)
                    for item in _list(raw["trade_markers"], "chart.trade_markers"))
    observations = tuple(_observation(item)
                         for item in _list(raw["rule_based_observations"], "chart.rule_based_observations"))
    return _make(CompactChartSource, ticker=ticker, name=name, timeframe=timeframe,
                 interval=interval, period=period, candles=candles,
                 trade_markers=markers, rule_based_observations=observations)


def admit_analysis_context_source(raw, *, memo_max_chars=DEFAULT_MEMO_MAX_CHARS):
    """Context is typed analysis input and has no canonical display authority."""
    if type(raw) is dict and set(raw) == {"error", "trade"}:
        error = _enum(raw["error"], ("날짜를 해석하지 못했습니다.", "매매일 이전 차트 데이터가 없습니다."),
                      "context.error")
        return _make(AnalysisContextErrorSource, error=error,
                     trade=admit_trade_source(raw["trade"], memo_max_chars=memo_max_chars))
    keys = {"trade_id", "date", "market_date", "ticker", "name", "side", "price",
            "quantity", "memo", *_CONTEXT_METRICS}
    _keys(raw, (keys,), "context")
    _symbol(raw["ticker"], raw["name"], "context")
    _date_time(raw["date"], "context.date", date_allowed=True)
    _calendar_date(raw["market_date"], "context.market_date")
    limit = _count(memo_max_chars, "memo_max_chars", minimum=1)
    if limit > MAX_MEMO_CHARS:
        raise SourceAdmissionError("memo limit exceeds product maximum")
    fields = {
        "trade_id": None if raw["trade_id"] is None else _count(raw["trade_id"], "context.trade_id", minimum=1),
        "date": raw["date"], "market_date": raw["market_date"],
        "ticker": raw["ticker"], "name": raw["name"],
        "side": _enum(raw["side"], ("buy", "sell"), "context.side"),
        "price": _number(raw["price"], "context.price", minimum=0),
        "quantity": _number(raw["quantity"], "context.quantity", minimum=0),
        "memo": _text(raw["memo"], "context.memo", maximum=limit),
    }
    if fields["price"] <= 0 or fields["quantity"] <= 0:
        raise SourceAdmissionError("context trade price/quantity must be positive")
    for key in _CONTEXT_METRICS:
        fields[key] = _number(raw[key], "context." + key, nullable=key != "close")
    if fields["close"] <= 0:
        raise SourceAdmissionError("context close must be positive")
    return _make(AnalysisContextSource, **fields)


def _semantic_shape(value, schema, path, *, normalized, active, count, depth):
    if depth > 32 or count[0] >= 4096:
        raise SourceAdmissionError("semantic shape depth/size exceeded")
    count[0] += 1
    kind = schema["type"]
    if kind in ("object", "array"):
        if (kind == "object" and type(value) is not dict) or (kind == "array" and type(value) is not list):
            raise SourceAdmissionError(f"invalid semantic container at {path}")
        identity = id(value)
        if identity in active:
            raise SourceAdmissionError("cyclic semantic source")
        active.add(identity)
        try:
            if kind == "object":
                if set(value) != set(schema["properties"]):
                    raise SourceAdmissionError(f"unknown or missing semantic field at {path}")
                for key, child in schema["properties"].items():
                    _semantic_shape(value[key], child, path + "." + key, normalized=normalized,
                                    active=active, count=count, depth=depth + 1)
            else:
                if len(value) < schema.get("minItems", 0) or (normalized and len(value) > schema["maxItems"]):
                    raise SourceAdmissionError(f"invalid semantic list length at {path}")
                for index, item in enumerate(value):
                    _semantic_shape(item, schema["items"], f"{path}[{index}]", normalized=normalized,
                                    active=active, count=count, depth=depth + 1)
        finally:
            active.remove(identity)
    elif kind == "string":
        if type(value) is not str:
            raise SourceAdmissionError(f"invalid semantic text at {path}")
        if not normalized and (schema.get("minLength", 0) and not value.strip() or
                               "enum" in schema and not path.endswith(".label") and
                               value.strip() not in schema["enum"]):
            raise SourceAdmissionError(f"invalid raw semantic text at {path}")
        if normalized and (len(value) < schema.get("minLength", 0) or
                           len(value) > schema.get("maxLength", MAX_REVIEW_TEXT_CHARS) or
                           "enum" in schema and value not in schema["enum"]):
            raise SourceAdmissionError(f"invalid normalized semantic text at {path}")
    else:
        raise SourceAdmissionError("unsupported semantic schema")


def _semantic_dto(value, review_type):
    quality = lambda item: _make(SemanticQuality, label=item["label"], explanation=item["explanation"])
    card = lambda item: _make(SemanticCard, title=item["title"], detail=item["detail"])
    lesson = value["lesson"]
    lesson_dto = _make(SemanticLesson, title=lesson["title"], concept=lesson["concept"],
                       applied_to_this_trade=lesson["applied_to_this_trade"],
                       next_trade_application=lesson["next_trade_application"] if review_type == "advanced" else None)
    common = dict(decision_quality=quality(value["decision_quality"]),
                  main_issue=value["main_issue"], next_action=value["next_action"], lesson=lesson_dto)
    if review_type == "basic":
        return _make(BasicSemanticSource, **common,
                     good_points=tuple(card(item) for item in value["good_points"]),
                     main_improvement=card(value["main_improvement"]),
                     next_trade_checks=tuple(_make(SemanticCheck, phase=item["phase"], text=item["text"])
                                             for item in value["next_trade_checks"]))
    entry, risk, exit_review, playbook = (value[key] for key in
        ("entry_review", "risk_review", "exit_review", "next_trade_playbook"))
    return _make(AdvancedSemanticSource, **common,
                 entry_review=_make(SemanticEntryReview, evidence=tuple(entry["evidence"]),
                                    uncertainty=tuple(entry["uncertainty"]),
                                    invalidation=entry["invalidation"], assessment=quality(entry["assessment"])),
                 risk_review=_make(SemanticRiskReview, planned_rule=risk["planned_rule"],
                                   actual_response=risk["actual_response"], assessment=quality(risk["assessment"])),
                 exit_review=_make(SemanticExitReview, **exit_review),
                 detailed_analysis=tuple(card(item) for item in value["detailed_analysis"]),
                 next_trade_playbook=_make(SemanticPlaybook, **{key: tuple(playbook[key]) for key in playbook}),
                 reflection_questions=tuple(value["reflection_questions"]))


def admit_semantic_source(raw, review_type):
    """Raw exact shape -> approved normalization -> normalized exact validation."""
    _enum(review_type, ("basic", "advanced"), "review_type")
    schema = structured_output_schema(review_type)
    try:
        _semantic_shape(raw, schema, "semantic", normalized=False, active=set(), count=[0], depth=0)
        normalized = normalize_semantic_output(raw, review_type)
        if normalized is None:
            raise SourceAdmissionError("semantic normalization rejected source")
        _semantic_shape(normalized, schema, "semantic", normalized=True, active=set(), count=[0], depth=0)
    except RecursionError as error:
        raise SourceAdmissionError("recursive semantic source") from error
    return _semantic_dto(normalized, review_type)


def admit_review_source(raw, *, memo_max_chars=DEFAULT_MEMO_MAX_CHARS):
    """Admit the full episode and all nested source items without projection."""
    _keys(raw, ({"review_type", "status", "origin", "trades", "objective", "charts",
                  "analysis_contexts", "semantic", "has_market_data", "notice"},), "review")
    review_type = _enum(raw["review_type"], ("basic", "advanced"), "review_type")
    status = _enum(raw["status"], ("ready", "error", "missing_key", "empty"), "status")
    origin = _enum(raw["origin"], ("openai", "chart-rules", "none"), "origin")
    trades = tuple(admit_trade_source(item, memo_max_chars=memo_max_chars)
                   for item in _list(raw["trades"], "trades"))
    objective = admit_objective_source(raw["objective"])
    if not trades:
        if type(objective) is not UnavailableObjectiveSource or status != "empty":
            raise SourceAdmissionError("empty episode requires explicit unavailable objective and empty status")
    elif type(objective) is not ObjectiveSource or objective.result.trade_count != len(trades):
        raise SourceAdmissionError("full episode/objective count mismatch")
    charts = tuple(admit_chart_source(item) for item in _list(raw["charts"], "charts"))
    contexts = tuple(admit_analysis_context_source(item, memo_max_chars=memo_max_chars)
                     for item in _list(raw["analysis_contexts"], "analysis_contexts"))
    semantic = None if raw["semantic"] is None else admit_semantic_source(raw["semantic"], review_type)
    if status == "ready" and semantic is None:
        raise SourceAdmissionError("ready review requires validated semantic source")
    if type(raw["has_market_data"]) is not bool:
        raise SourceAdmissionError("has_market_data must be boolean")
    notice = None if raw["notice"] is None else _text(raw["notice"], "notice", maximum=MAX_REVIEW_TEXT_CHARS,
                                                       nonempty=True)
    return _make(ValidatedReviewSource, review_type=review_type, status=status, origin=origin,
                 trades=trades, objective=objective, charts=charts, analysis_contexts=contexts,
                 semantic=semantic, has_market_data=raw["has_market_data"], notice=notice)


def admit_trade_sources(raw, *, memo_max_chars=DEFAULT_MEMO_MAX_CHARS):
    return tuple(admit_trade_source(item, memo_max_chars=memo_max_chars)
                 for item in _list(raw, "trades"))


def admit_journal_chart_source(raw):
    """Admit the complete journal producer shape before compact/window projection.

    Render controls and marker fill metadata have no AI display authority, but
    must still match their declared producer variants before being projected.
    """
    base = {"ticker", "name", "timeframe", "interval", "source", "candles", "markers", "reviews"}
    _keys(raw, (base, base | {"period_label"}), "journal_chart")
    _symbol(raw["ticker"], raw["name"], "journal_chart")
    timeframe = _enum(raw["timeframe"], ("intraday", "daily", "weekly"), "journal_chart.timeframe")
    interval = _enum(raw["interval"], ("1m", "3m", "1d", "1wk"), "journal_chart.interval")
    if (timeframe, interval) not in _INTERVALS:
        raise SourceAdmissionError("invalid journal timeframe/interval")
    expected_source = {("intraday", "1m"): "1m intraday", ("intraday", "3m"): "3m intraday",
                       ("daily", "1d"): "daily OHLCV", ("weekly", "1wk"): "weekly OHLCV"}[timeframe, interval]
    _enum(raw["source"], (expected_source,), "journal_chart.source")
    candles = []
    for row in _list(raw["candles"], "journal_chart.candles"):
        _keys(row, ({"time", "label", "open", "high", "low", "close", "volume", "ma5", "ma20"},),
              "journal_chart.candle")
        candles.append({"time": row["time"], "t": row["label"], "o": row["open"],
                        "h": row["high"], "l": row["low"], "c": row["close"],
                        "v": row["volume"], "ma5": row["ma5"], "ma20": row["ma20"]})
    markers = []
    for row in _list(raw["markers"], "journal_chart.markers"):
        _keys(row, ({"time", "position", "color", "shape", "text", "size", "side", "trades", "tooltip"},),
              "journal_chart.marker")
        side = _enum(row["side"], ("buy", "sell"), "journal_chart.marker.side")
        expected = ("belowBar", "#2962ff", "arrowUp") if side == "buy" else ("aboveBar", "#ff5252", "arrowDown")
        if (row["position"], row["color"], row["shape"]) != expected or type(row["size"]) is not int or row["size"] != 2:
            raise SourceAdmissionError("invalid journal marker controls")
        fills = _list(row["trades"], "journal_chart.marker.trades")
        fill_keys = {"id", "date", "price", "quantity"}
        for fill in fills:
            _keys(fill, (fill_keys if side == "buy" else fill_keys | {"profit_amount", "return_rate"},),
                  "journal_chart.marker.fill")
            if fill["id"] is not None:
                _count(fill["id"], "journal_chart.marker.fill.id", minimum=1)
            _date_time(fill["date"], "journal_chart.marker.fill.date", date_allowed=True)
            for key in ("price", "quantity"):
                if _number(fill[key], "journal_chart.marker.fill." + key, minimum=0) <= 0:
                    raise SourceAdmissionError("invalid journal fill price/quantity")
            if side == "sell":
                for key in ("profit_amount", "return_rate"):
                    _number(fill[key], "journal_chart.marker.fill." + key, nullable=True)
        tooltip = _tooltip(row["tooltip"], side)
        if len(fills) != tooltip.count or tuple(fill["price"] for fill in fills) != tooltip.prices:
            raise SourceAdmissionError("journal marker fills/tooltip mismatch")
        markers.append({"time": row["time"], "side": side, "text": row["text"], "tooltip": row["tooltip"]})
    observations = _list(raw["reviews"], "journal_chart.reviews")
    # Validate absence too: unknown/malformed observations cannot disappear.
    for observation in observations:
        _observation(observation)
    if not candles:
        if (set(raw) != base or markers or len(observations) != 1 or
                set(observations[0]) != {"title", "detail"} or
                observations[0]["title"] != raw["name"] or
                observations[0]["detail"] != "차트 데이터를 가져오지 못했습니다."):
            raise SourceAdmissionError("invalid unavailable journal chart")
        return admit_chart_source({"kind": "unavailable", "reason": "no_market_data"})
    if "period_label" not in raw:
        raise SourceAdmissionError("missing journal chart period")
    return admit_chart_source({"ticker": raw["ticker"], "name": raw["name"],
                               "timeframe": timeframe, "interval": interval, "period": raw["period_label"],
                               "candles": candles, "trade_markers": markers,
                               "rule_based_observations": observations})


def select_chart_candles(chart, indexes):
    """Select a window only from a fully admitted immutable chart."""
    if type(chart) is not CompactChartSource or type(indexes) is not tuple or not indexes:
        raise SourceAdmissionError("invalid admitted chart window")
    if any(type(index) is not int or not 0 <= index < len(chart.candles) for index in indexes):
        raise SourceAdmissionError("invalid candle index")
    return _make(CompactChartSource, ticker=chart.ticker, name=chart.name,
                 timeframe=chart.timeframe, interval=chart.interval, period=chart.period,
                 candles=tuple(chart.candles[index] for index in indexes),
                 trade_markers=chart.trade_markers, rule_based_observations=chart.rule_based_observations)


def compose_review_source(*, review_type, trades, objective, charts=(), analysis_contexts=(),
                          semantic=None, status="missing_key", origin="chart-rules", notice=None):
    """Compose already admitted DTOs; never re-normalize or repair raw inputs."""
    _enum(review_type, ("basic", "advanced"), "review_type")
    _enum(status, ("ready", "error", "missing_key", "empty"), "status")
    _enum(origin, ("openai", "chart-rules", "none"), "origin")
    for values, classes, path in ((trades, (TradeSource,), "trades"),
                                 (charts, (CompactChartSource, UnavailableChartSource), "charts"),
                                 (analysis_contexts, (AnalysisContextSource, AnalysisContextErrorSource), "contexts")):
        if type(values) is not tuple or any(type(item) not in classes for item in values):
            raise SourceAdmissionError("expected admitted tuple at " + path)
    if trades:
        if type(objective) is not ObjectiveSource or objective.result.trade_count != len(trades):
            raise SourceAdmissionError("full episode/objective count mismatch")
    elif type(objective) is not UnavailableObjectiveSource or status not in ("empty", "error"):
        raise SourceAdmissionError("invalid unavailable episode")
    if semantic is not None and type(semantic) is not (AdvancedSemanticSource if review_type == "advanced" else BasicSemanticSource):
        raise SourceAdmissionError("semantic DTO/type mismatch")
    if status == "ready" and semantic is None:
        raise SourceAdmissionError("ready review requires admitted semantics")
    if not trades and status == "error" and (origin != "none" or charts or analysis_contexts or semantic is not None or notice != UNAVAILABLE_REVIEW_TEXT):
        raise SourceAdmissionError("rejected source requires fixed unavailable variant")
    if notice is not None:
        _text(notice, "notice", maximum=MAX_REVIEW_TEXT_CHARS, nonempty=True)
    market = any(type(chart) is CompactChartSource for chart in charts) or any(
        type(context) is AnalysisContextSource for context in analysis_contexts)
    return _make(ValidatedReviewSource, review_type=review_type, status=status, origin=origin,
                 trades=trades, objective=objective, charts=charts, analysis_contexts=analysis_contexts,
                 semantic=semantic, has_market_data=market, notice=notice)


def finish_review_source(source, *, semantic, status, origin, notice=None):
    if type(source) is not ValidatedReviewSource:
        raise SourceAdmissionError("expected admitted review source")
    return compose_review_source(review_type=source.review_type, trades=source.trades,
                                 objective=source.objective, charts=source.charts,
                                 analysis_contexts=source.analysis_contexts, semantic=semantic,
                                 status=status, origin=origin, notice=notice)


def unavailable_review_source(review_type):
    """Terminal source rejection contains no rejected source or model text."""
    return compose_review_source(review_type=review_type, trades=(),
                                 objective=admit_objective_source({"kind": "unavailable", "reason": "no_trades"}),
                                 status="error", origin="none", notice=UNAVAILABLE_REVIEW_TEXT)
