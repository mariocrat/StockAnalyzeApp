"""Named projections of admitted DTOs for model input and legacy compatibility.

No raw input admission, coercion, arbitrary dictionary walk or missing-field
repair belongs here. Canonical documents use the same structured projection.
"""

import re

from core.review_source_contract import (
    AnalysisContextErrorSource, AdvancedSemanticSource,
    BasicSemanticSource, CompactChartSource, TechnicalObservationSource,
    UnavailableChartSource, UnavailableObjectiveSource, ValidatedReviewSource,
    SourceAdmissionError, admit_semantic_source,
)
from core.trade_review_schema import STRUCTURED_REVIEW_SCHEMA_VERSION


def trade_payload(trade):
    value = {"trade_date": trade.trade_date, "ticker": trade.ticker, "name": trade.name,
             "side": trade.side, "price": trade.price, "quantity": trade.quantity,
             "fee": trade.fee, "tax": trade.tax, "memo": trade.memo, "source": trade.source}
    if trade.variant in ("identified", "stored"):
        value["id"] = trade.id
    if trade.variant == "stored":
        value.update(created_at=trade.created_at, user_id=trade.user_id)
    return value


def observation_payload(item):
    value = {"title": item.title, "detail": item.detail}
    if type(item) is TechnicalObservationSource:
        metrics = item.metrics
        value.update(trade_id=item.trade_id, metrics={
            "price_vs_close_pct": metrics.price_vs_close_pct,
            "after_5_bars": metrics.after_5_bars, "after_later_bars": metrics.after_later_bars,
            "ma5": metrics.ma5, "ma20": metrics.ma20,
        })
    return value


def chart_payload(chart):
    if type(chart) is UnavailableChartSource:
        return {"kind": chart.kind, "reason": chart.reason}
    markers = []
    for marker in chart.trade_markers:
        item = marker.tooltip
        tooltip = {"label": item.label, "count": item.count, "avg_price": item.avg_price,
                   "total_quantity": item.total_quantity, "prices": list(item.prices)}
        if marker.side == "sell":
            tooltip.update(profit_amount=item.profit_amount, return_rate=item.return_rate)
        value = {"time": marker.time, "side": marker.side, "tooltip": tooltip}
        if marker.text is not None:
            value["text"] = marker.text
        markers.append(value)
    return {"ticker": chart.ticker, "name": chart.name, "timeframe": chart.timeframe,
            "interval": chart.interval, "period": chart.period,
            "candles": [{"time": row.time, "t": row.t, "o": row.o, "h": row.h, "l": row.l,
                         "c": row.c, "v": row.v, "ma5": row.ma5, "ma20": row.ma20}
                        for row in chart.candles],
            "trade_markers": markers,
            "rule_based_observations": [observation_payload(item) for item in chart.rule_based_observations]}


def context_payload(context):
    if type(context) is AnalysisContextErrorSource:
        return {"error": context.error, "trade": trade_payload(context.trade)}
    return {"trade_id": context.trade_id, "date": context.date, "market_date": context.market_date,
            "ticker": context.ticker, "name": context.name, "side": context.side,
            "price": context.price, "quantity": context.quantity, "memo": context.memo,
            "close": context.close, "price_vs_close_pct": context.price_vs_close_pct,
            "ma5": context.ma5, "ma20": context.ma20, "ma60": context.ma60,
            "rsi14": context.rsi14, "volume_ratio_20d": context.volume_ratio_20d,
            "return_10d_before": context.return_10d_before,
            "position_in_20d_range": context.position_in_20d_range,
            "next_5d_return": context.next_5d_return, "next_20d_return": context.next_20d_return}


def objective_payload(objective):
    if type(objective) is UnavailableObjectiveSource:
        # Fixed legacy structured representation; no failed source is recovered.
        return {"symbol": {"ticker": "", "name": ""},
                "period": {"first_trade_date": "", "last_trade_date": ""},
                "result": {"trade_count": 0, "closed_count": 0, "realized_pnl": 0,
                           "realized_return_pct": 0, "win_rate_pct": 0,
                           "weighted_buy_price": None, "weighted_sell_price": None,
                           "total_fee": 0, "total_tax": 0, "buy_fill_count": 0,
                           "sell_fill_count": 0, "open_quantity": 0, "symbol_count": 0}}
    result = objective.result
    return {"symbol": {"ticker": objective.symbol.ticker, "name": objective.symbol.name},
            "period": {"first_trade_date": objective.period.first_trade_date,
                       "last_trade_date": objective.period.last_trade_date},
            "result": {"trade_count": result.trade_count, "closed_count": result.closed_count,
                       "realized_pnl": result.realized_pnl, "realized_return_pct": result.realized_return_pct,
                       "win_rate_pct": result.win_rate_pct, "weighted_buy_price": result.weighted_buy_price,
                       "weighted_sell_price": result.weighted_sell_price, "total_fee": result.total_fee,
                       "total_tax": result.total_tax, "buy_fill_count": result.buy_fill_count,
                       "sell_fill_count": result.sell_fill_count, "open_quantity": result.open_quantity,
                       "symbol_count": result.symbol_count}}


def _quality(item):
    return {"label": item.label, "explanation": item.explanation}


def _card(item):
    return {"title": item.title, "detail": item.detail}


def semantic_payload(semantic):
    lesson = semantic.lesson
    value = {"decision_quality": _quality(semantic.decision_quality), "main_issue": semantic.main_issue,
             "next_action": semantic.next_action,
             "lesson": {"title": lesson.title, "concept": lesson.concept,
                        "applied_to_this_trade": lesson.applied_to_this_trade}}
    if type(semantic) is BasicSemanticSource:
        value.update(good_points=[_card(item) for item in semantic.good_points],
                     main_improvement=_card(semantic.main_improvement),
                     next_trade_checks=[{"phase": item.phase, "text": item.text} for item in semantic.next_trade_checks])
    elif type(semantic) is AdvancedSemanticSource:
        entry, risk, exit_review, playbook = (semantic.entry_review, semantic.risk_review,
                                             semantic.exit_review, semantic.next_trade_playbook)
        value.update(entry_review={"evidence": list(entry.evidence), "uncertainty": list(entry.uncertainty),
                                   "invalidation": entry.invalidation, "assessment": _quality(entry.assessment)},
                     risk_review={"planned_rule": risk.planned_rule, "actual_response": risk.actual_response,
                                  "assessment": _quality(risk.assessment)},
                     exit_review={"profit_taking_assessment": exit_review.profit_taking_assessment,
                                  "trend_exit_assessment": exit_review.trend_exit_assessment,
                                  "explanation": exit_review.explanation},
                     detailed_analysis=[_card(item) for item in semantic.detailed_analysis],
                     next_trade_playbook={"before_entry": list(playbook.before_entry),
                                          "while_holding": list(playbook.while_holding),
                                          "before_exit": list(playbook.before_exit)},
                     reflection_questions=list(semantic.reflection_questions))
        value["lesson"]["next_trade_application"] = lesson.next_trade_application
    else:
        raise SourceAdmissionError("expected semantic DTO")
    return value


def cost_completeness_payload(trades):
    return {"missing_fee_count": sum(trade.fee is None for trade in trades),
            "missing_tax_count": sum(trade.tax is None for trade in trades),
            "calculation": "exclude_unknown"}


def review_cost_warning(trades):
    costs = cost_completeness_payload(trades)
    fee, tax = costs["missing_fee_count"], costs["missing_tax_count"]
    if not fee and not tax:
        return ""
    missing = "수수료와 세금" if fee and tax else "수수료" if fee else "세금"
    return f"{missing} 미반영: 확인된 비용만 계산에 반영했습니다. 손익·수익률은 비용 일부 미반영 값입니다."


def review_data_quality(source):
    if type(source) is not ValidatedReviewSource:
        raise SourceAdmissionError("quality requires admitted review source")
    observations = [item for chart in source.charts if type(chart) is CompactChartSource
                    for item in chart.rule_based_observations]
    gaps = [item.metrics.price_vs_close_pct for item in observations if type(item) is TechnicalObservationSource]
    context_errors = [item.error for item in source.analysis_contexts if type(item) is AnalysisContextErrorSource]
    cost_warning = review_cost_warning(source.trades)
    reasons = [cost_warning] if cost_warning else []
    if not source.has_market_data:
        reasons.append("차트 데이터가 없어 기술적 비교를 제한합니다.")
    reasons.extend(context_errors[:2])
    max_gap = max((abs(gap) for gap in gaps), default=0)
    if max_gap >= 2:
        reasons.append(f"체결가와 해당 차트 기준 가격의 최대 차이가 {max_gap:.2f}%입니다.")
    memos = [trade.memo.strip() for trade in source.trades]
    missing = []
    if cost_warning:
        missing.append(cost_warning)
    if not any(memos):
        missing.append("실제 매매 이유")
    if any(trade.side == "buy" for trade in source.trades) and not any(
            re.search(r"손절|무효화|무효|위험|철회|리스크|기준", memo) for memo in memos):
        missing.append("사전 위험/무효화 기준")
    if any(trade.side == "sell" for trade in source.trades) and not any(
            re.search(r"매도|청산|수익|추세|기준", memo) for memo in memos):
        missing.append("사전 매도 기준")
    if any("T" not in trade.trade_date for trade in source.trades):
        missing.append("체결 시각")
    level, label = (("low", "낮음") if max_gap >= 10 or not source.has_market_data else
                    ("medium", "보통") if max_gap >= 2 or missing or context_errors else ("high", "높음"))
    return {"level": level, "label": label, "reasons": reasons[:5]}, missing


def fixed_semantic_source(review_type):
    safe = "복기 내용을 안전하게 표시할 수 없습니다."
    quality = {"label": "판단 보류", "explanation": safe}
    value = {"decision_quality": quality, "main_issue": safe,
             "next_action": "거래 기록을 직접 확인해 주세요.",
             "lesson": {"title": "판단 보류", "concept": safe, "applied_to_this_trade": safe}}
    if review_type == "basic":
        value.update(good_points=[{"title": "판단 보류", "detail": safe}],
                     main_improvement={"title": "판단 보류", "detail": safe},
                     next_trade_checks=[{"phase": phase, "text": "거래 기록을 직접 확인하기"}
                                        for phase in ("before_entry", "while_holding", "before_exit")])
    else:
        value.update(entry_review={"evidence": [safe], "uncertainty": [], "invalidation": "기록 없음", "assessment": quality},
                     risk_review={"planned_rule": "기록 없음", "actual_response": safe, "assessment": quality},
                     exit_review={"profit_taking_assessment": "판단 보류", "trend_exit_assessment": "판단 보류", "explanation": safe},
                     detailed_analysis=[], next_trade_playbook={phase: ["거래 기록을 직접 확인하기"]
                                                                for phase in ("before_entry", "while_holding", "before_exit")},
                     reflection_questions=["당시 거래 기록에 어떤 근거가 남아 있나요?"])
        value["lesson"]["next_trade_application"] = safe
    return admit_semantic_source(value, review_type)


def structured_review_payload(source):
    if type(source) is not ValidatedReviewSource:
        raise SourceAdmissionError("expected admitted review source")
    fixed = not source.trades and source.status == "error" and source.origin == "none"
    semantic = fixed_semantic_source(source.review_type) if fixed else source.semantic
    if semantic is None:
        raise SourceAdmissionError("structured projection requires admitted semantics")
    value = semantic_payload(semantic)
    confidence, missing = ({"level": "low", "label": "낮음", "reasons": []}, []) if fixed else review_data_quality(source)
    summary = {"decision_quality": value.pop("decision_quality"), "main_issue": value.pop("main_issue"),
               "next_action": value.pop("next_action"), "data_confidence": confidence, "missing_information": missing}
    return {"schema_version": STRUCTURED_REVIEW_SCHEMA_VERSION, "review_type": source.review_type,
            "objective": objective_payload(source.objective), "summary": summary, source.review_type: value}
