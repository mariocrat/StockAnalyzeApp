"""Compile canonical display documents from one admitted source DTO only."""

from __future__ import annotations

from core.review_body_compiler import compile_review_body
from core.review_display_contract import (
    SCHEMA_VERSION as DISPLAY_VERSION,
    parse_inline_strong, validate_document,
)
from core.review_envelope_contract import (
    SCHEMA_VERSION as ENVELOPE_VERSION, ApprovedReviewSnapshot, validate_envelope,
)
from core.review_source_contract import (
    CompactChartSource, ObjectiveSource, TechnicalObservationSource,
    UnavailableChartSource, UnavailableObjectiveSource, ValidatedReviewSource,
)


class ReviewEnvelopeCompileError(ValueError):
    """An input is not an admitted review source."""


def _surface(surface, lines):
    blocks = [{"type": "paragraph", "runs": parse_inline_strong(line), "separator_after": "\n"}
              for line in lines]
    blocks[-1]["separator_after"] = ""
    document = {
        "schema_version": DISPLAY_VERSION, "surface": surface, "blocks": blocks,
        "canonical_text": "".join("".join(run["text"] for run in block["runs"])
                                  + block["separator_after"] for block in blocks),
    }
    validate_document(document, expected_surface=surface)
    return document


def _card(item):
    return {
        "trade_id": item.trade_id if type(item) is TechnicalObservationSource else None,
        "display": _surface("chart_card", [f"{item.title}: {item.detail}"]),
        # These outbound analysis metrics are unavailable in the technical
        # observation variant. No other source field is a substitute for them.
        "metrics": {"rsi14": None, "return_10d_before": None, "volume_ratio_20d": None,
                    "next_5d_return": None, "next_20d_return": None},
    }


def _marker(marker):
    tooltip = marker.tooltip
    lines = [f"{tooltip.label} {tooltip.count}건",
             f"평균 {tooltip.avg_price:,.0f}원 · 수량 {tooltip.total_quantity}",
             ", ".join(f"{price:,.0f}" for price in tooltip.prices) + "원"]
    if marker.side == "sell" and tooltip.profit_amount is not None:
        rate = "확인 불가" if tooltip.return_rate is None else f"{tooltip.return_rate:+}%"
        lines.append(f"실현 {tooltip.profit_amount:+,.0f}원 · {rate}")
    label = ("B" if marker.side == "buy" else "S") + (str(tooltip.count) if tooltip.count > 1 else "")
    return {"time": marker.time, "side": marker.side,
            "label": _surface("marker_label", [label]), "tooltip": _surface("marker_tooltip", lines)}


def _chart(chart):
    header = {"intraday": "분봉", "daily": "일봉", "weekly": "주봉"}[chart.timeframe]
    return {
        "ticker": chart.ticker, "timeframe": chart.timeframe, "interval": chart.interval,
        "header": _surface("chart_header", [f"{header} · {chart.interval} · {chart.period}"]),
        "tab": _surface("chart_tab", [chart.name]),
        "candles": [{"time": row.time, "open": row.o, "high": row.h, "low": row.l,
                     "close": row.c, "volume": row.v, "ma5": row.ma5, "ma20": row.ma20}
                    for row in chart.candles],
        "markers": [_marker(marker) for marker in chart.trade_markers],
    }


def compile_review_envelope(source: ValidatedReviewSource):
    """A named projection of DTO attributes; raw sources never enter here."""
    if type(source) is not ValidatedReviewSource:
        raise ReviewEnvelopeCompileError("expected ValidatedReviewSource")
    try:
        body = compile_review_body(source)
        if type(source.objective) is ObjectiveSource:
            result = source.objective.result
            objective = {"trade_count": result.trade_count, "realized_pnl": result.realized_pnl,
                         "realized_return_pct": result.realized_return_pct, "win_rate_pct": result.win_rate_pct,
                         "weighted_buy_price": result.weighted_buy_price, "has_market_data": source.has_market_data}
        elif type(source.objective) is UnavailableObjectiveSource:
            objective = {"trade_count": 0, "realized_pnl": 0, "realized_return_pct": 0,
                         "win_rate_pct": 0, "weighted_buy_price": None, "has_market_data": False}
        else:
            raise ReviewEnvelopeCompileError("unexpected objective DTO variant")
        charts, cards = [], []
        for chart in source.charts:
            if type(chart) is UnavailableChartSource:
                continue  # Explicit unavailable variant has no chart display surface.
            if type(chart) is not CompactChartSource:
                raise ReviewEnvelopeCompileError("unexpected chart DTO variant")
            charts.append(_chart(chart))
            cards.extend(_card(item) for item in chart.rule_based_observations)
        trades = [{"id": trade.id, "trade_date": trade.trade_date[:10], "ticker": trade.ticker,
                   "side": trade.side, "name": _surface("trade_name", [trade.name]),
                   "price": trade.price, "quantity": trade.quantity}
                  for trade in source.trades[-20:] if trade.id is not None and trade.symbol_kind == "krx"]
        return {
            "schema_version": ENVELOPE_VERSION, "review_type": source.review_type,
            "status": source.status, "source": source.origin, "body": body, "objective": objective,
            "chart_cards": cards, "charts": charts, "trades": trades, "history": None,
            "notice": _surface("notice", [source.notice]) if source.notice is not None else None,
        }
    except AttributeError as error:
        raise ReviewEnvelopeCompileError("uninitialized source DTO") from error


def seal_review_envelope(candidate):
    validate_envelope(candidate)
    return ApprovedReviewSnapshot(candidate)
