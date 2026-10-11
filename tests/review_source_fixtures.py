"""Complete synthetic producer fixtures for DTO-connected review tests.

Legacy tests used prompt-only candle/observation shorthands. Expand those
explicit test fixtures here; production admission never uses this helper.
Unknown supplied fields are retained so negative fixtures still reject.
"""

from backend.core.review_source_contract import (
    admit_trade_sources, admit_chart_source, compose_review_source,
)


def compact_chart_fixture(value=None):
    if not value:
        return {"kind": "unavailable", "reason": "no_market_data"}
    if "kind" in value:
        return dict(value)
    value = dict(value)
    value.setdefault("ticker", "005930")
    value.setdefault("name", "삼성전자")
    value.setdefault("timeframe", "daily")
    value.setdefault("interval", "1d")
    value.setdefault("period", "2026-07-10")
    value.setdefault("trade_markers", [])
    value.setdefault("candles", [{"time": "2026-07-10", "close": 70400}])
    candles = []
    for row in value["candles"]:
        row = dict(row)
        close = row.pop("close", row.get("c", 70400))
        row.setdefault("t", row["time"])
        row.setdefault("o", close)
        row.setdefault("h", close)
        row.setdefault("l", close)
        row.setdefault("c", close)
        row.setdefault("v", 1000)
        row.setdefault("ma5", None)
        row.setdefault("ma20", None)
        candles.append(row)
    value["candles"] = candles
    observations = []
    for row in value.get("rule_based_observations", []):
        row = dict(row)
        row.setdefault("title", "과거 체결")
        if "metrics" in row or "trade_id" in row:
            row.setdefault("trade_id", None)
            row["metrics"] = {"price_vs_close_pct": 0, "after_5_bars": None,
                              "after_later_bars": None, "ma5": None, "ma20": None,
                              **row.get("metrics", {})}
        observations.append(row)
    value["rule_based_observations"] = observations
    return value


def review_input_fixture(trades, chart=None, *, review_type="basic", charts=None):
    # Deferred import keeps standalone source contract tests free of storage.
    from core.ai_review_v2 import _objective_review_snapshot
    trades = admit_trade_sources(trades)
    chart_values = charts if charts is not None else [compact_chart_fixture(chart)]
    return compose_review_source(review_type=review_type, trades=trades,
                                 objective=_objective_review_snapshot(trades),
                                 charts=tuple(admit_chart_source(value) for value in chart_values))


def approved_chart_fixture():
    """Different from the independent general/history-metadata chart fixture."""
    return compact_chart_fixture({
        "name": "합성 승인 종목", "period": "2026-07-10",
        "candles": [{"time": "2026-07-10", "close": 71234}],
        "trade_markers": [
            {"time": "2026-07-10", "side": "buy", "tooltip": {
                "label": "매수", "count": 2, "avg_price": 70200,
                "total_quantity": 2, "prices": [70000, 70400]}},
            {"time": "2026-07-10", "side": "sell", "tooltip": {
                "label": "매도", "count": 1, "avg_price": 70900,
                "total_quantity": 1, "prices": [70900], "profit_amount": 700, "return_rate": 1}},
        ],
        "rule_based_observations": [{"title": "과거 체결", "detail": "승인된 과거 차트 기록을 확인했습니다."}],
    })


def history_chart_fixture(trades, *, available=True):
    """Run the general chart producer against owned synthetic market data."""
    from tests.storage_fixture import require_storage_boundary
    require_storage_boundary()
    from unittest.mock import patch
    import pandas as pd
    from core import journal_chart

    days = sorted({trade["trade_date"][:10] for trade in trades})
    frame = pd.DataFrame(
        {"Open": 70000.0, "High": 71000.0, "Low": 69000.0,
         "Close": 70400.0, "Volume": 1000.0},
        index=pd.to_datetime(days),
    )
    frame = journal_chart._prepare_ohlcv(frame) if available else pd.DataFrame()
    with patch.object(journal_chart, "_try_intraday", return_value=pd.DataFrame()), patch.object(
            journal_chart, "_daily_data", return_value=frame):
        return journal_chart.build_journal_charts(trades)


def fallback_model_fixture(payload):
    from core.ai_review_v2 import _default_basic_semantics, _default_advanced_semantics
    from backend.core.review_source_projection import semantic_payload
    advanced = payload["review_type"] == "advanced"
    source = review_input_fixture(payload["recent_trades"] if advanced else payload["trade_episode"],
                                 payload.get("trade_chart_snapshot"), review_type=payload["review_type"],
                                 charts=payload["trade_chart_snapshots"] if advanced else None)
    return semantic_payload(_default_advanced_semantics(source) if advanced else _default_basic_semantics(source))


def approved_route_fixture(summary, *, approval_state, review_type="basic", status="ready",
                           source="openai", model=None, **extras):
    """Route-operation stubs carry a real seal; production requires that approval."""
    from backend.core.review_display_contract import compile_literal_text
    from backend.core.review_envelope_compiler import compile_review_envelope, seal_review_envelope
    from backend.core.review_legacy_compatibility import admit_legacy_body
    from backend.core.review_source_contract import unavailable_review_source
    body = compile_literal_text(str(summary))
    candidate = compile_review_envelope(unavailable_review_source(review_type))
    candidate.update(status=status, source=source, body=body)
    approval_state["snapshot"] = seal_review_envelope(candidate)
    return {"status": status, "source": source, "review_type": review_type, "model": model,
            "summary": admit_legacy_body(body).summary, "display_snapshot": body, **extras}
