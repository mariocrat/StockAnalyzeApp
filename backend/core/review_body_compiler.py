"""Canonical body templates. Compatibility strings never enter this compiler."""

from core.journal import build_review
from core.review_display_contract import (
    SCHEMA_VERSION, compile_literal_text, compile_structured_review,
    parse_inline_strong, validate_document,
)
from core.review_source_contract import (
    ValidatedReviewSource, CompactChartSource, TechnicalObservationSource, EMPTY_REVIEW_TEXT,
)
from core.review_source_projection import trade_payload, structured_review_payload, review_cost_warning


def compile_review_body(source):
    """Select the canonical body from the admitted source, before approval."""
    if type(source) is not ValidatedReviewSource:
        raise TypeError("expected ValidatedReviewSource")
    if source.status == "empty":
        return compile_literal_text(EMPTY_REVIEW_TEXT)
    if source.origin == "chart-rules" and source.status in ("error", "missing_key"):
        return (compile_advanced_fallback_body(source) if source.review_type == "advanced"
                else compile_basic_fallback_body(source))
    return compile_structured_review(structured_review_payload(source))[0]


def _observation_for_side(source: ValidatedReviewSource, side: str):
    ids = {trade.id for trade in source.trades if trade.side == side and trade.id is not None}
    observations = [item for chart in source.charts if type(chart) is CompactChartSource
                    for item in chart.rule_based_observations if type(item) is TechnicalObservationSource]
    return next((item for item in reversed(observations) if item.trade_id in ids), None)


def _fallback_body(lines, *, separator="\n\n"):
    """Compile safe paragraphs once; their text and separators are owned here."""
    blocks = [{"type": "paragraph", "runs": parse_inline_strong(line), "separator_after": separator}
              for line in lines]
    blocks[-1]["separator_after"] = ""
    document = {"schema_version": SCHEMA_VERSION, "surface": "body", "blocks": blocks,
                "canonical_text": "".join("".join(run["text"] for run in block["runs"])
                                          + block["separator_after"] for block in blocks)}
    validate_document(document)
    return document


def _basic_checklist_items(source: ValidatedReviewSource) -> list[str]:
    buy_count = sum(trade.side == "buy" for trade in source.trades)
    buy_observation = _observation_for_side(source, "buy")
    sell_observation = _observation_for_side(source, "sell")
    buy_after_five = buy_observation.metrics.after_5_bars if buy_observation is not None else None
    sell_after_five = sell_observation.metrics.after_5_bars if sell_observation is not None else None

    first = "이번 매수 전에 진입 이유와 가설이 틀렸다고 판단할 기준을 기록했는지 확인하기"

    if buy_after_five is not None:
        second = (
            f"이번 매수 뒤 5개 봉 수익률 {buy_after_five:+.2f}%를 기준으로 "
            "실제 흐름이 처음 가설과 일치했는지 기록하기"
        )
    else:
        second = f"이번 {max(1, buy_count)}회 매수 체결마다 분할 진입의 목적이 서로 달랐는지 확인하기"

    if sell_after_five is not None:
        third = (
            f"이번 매도 뒤 5개 봉 수익률 {sell_after_five:+.2f}%와 비교해 "
            "매도 이유가 사전에 정한 기준과 일치했는지 기록하기"
        )
    else:
        third = "이번 매도 이유가 매매 중의 불안감인지 사전에 정한 기준인지 구분해 기록하기"
    return [first, second, third]


def compile_basic_fallback_body(source: ValidatedReviewSource):
    name = source.trades[-1].name
    result = source.objective.result
    pnl, return_pct = result.realized_pnl, result.realized_return_pct
    buy_avg, sell_avg = result.weighted_buy_price, result.weighted_sell_price
    buy = _observation_for_side(source, "buy")
    sell = _observation_for_side(source, "sell")
    buy_observation = buy.detail if buy is not None else ""
    sell_observation = sell.detail if sell is not None else ""
    checklist = _basic_checklist_items(source)

    if buy_avg is not None and sell_avg is not None:
        verdict = f"{name} 매매는 평균 {buy_avg:,.0f}원 매수, {sell_avg:,.0f}원 매도로 실현손익 {pnl:+,.0f}원({return_pct:+.2f}%)입니다."
    else:
        verdict = f"{name} 매매는 아직 매수·매도가 모두 확인되지 않아 체결 시점의 위험 관리 중심으로 봐야 합니다."

    if pnl >= 0:
        good = sell_observation or "손실 포지션을 남기지 않고 수익을 실현한 점은 대응 측면에서 유효했습니다."
        weak = buy_observation or "수익 여부와 별개로 매수 직후 불리한 움직임을 견딜 가격 기준이 숫자로 정해져 있었는지 확인해야 합니다."
    else:
        good = sell_observation or "손실을 확정해 미청산 위험을 더 키우지 않은 점은 대응 측면에서 의미가 있습니다."
        weak = buy_observation or "평균 매수가 대비 매도가가 낮았습니다. 첫 매수 뒤 가격이 가설과 반대로 움직였을 때 추가 매수보다 철회 기준이 먼저 필요했습니다."

    return _fallback_body([
        *([review_cost_warning(source.trades)] if review_cost_warning(source.trades) else []),
        f"이번 매매 판단: {verdict}",
        f"확인된 강점: {good}",
        f"개선할 점: {weak}",
        f"다음 매매 점검: {checklist[0]} / {checklist[1]} / {checklist[2]}"
    ])


def compile_advanced_fallback_body(source: ValidatedReviewSource):
    review = build_review([trade_payload(trade) for trade in source.trades])
    result = source.objective.result
    symbols = review["by_symbol"]
    losses = [row for row in symbols if row["realized_pnl"] < 0]
    open_positions = [row for row in symbols if row["open_quantity"] > 0]
    observations = [item for chart in source.charts if type(chart) is CompactChartSource
                    for item in chart.rule_based_observations]
    weak_entries = [item.detail for item in observations if "매수 시점: 아쉬움" in item.title]
    weak_exits = [item.detail for item in observations if "매도 시점: 아쉬움" in item.title]
    repeated_issue = weak_entries[0] if weak_entries else weak_exits[0] if weak_exits else "체결 전후 봉에서 반복되는 명확한 약점은 아직 표본이 부족합니다."
    loss_text = ", ".join(f"{row['name']} {row['realized_pnl']:+,.0f}원" for row in losses[:3]) or "확정 손실 종목 없음"
    return _fallback_body([
        *([review_cost_warning(source.trades)] if review_cost_warning(source.trades) else []),
        f"최근 패턴: {len(source.trades)}건, 실현손익 {result.realized_pnl:+,.0f}원, 승률 {result.win_rate_pct:.1f}%입니다.",
        f"반복 문제: {repeated_issue}",
        f"손실 관리: {loss_text}. 미청산 종목은 {len(open_positions)}개입니다.",
        "다음 복기 질문: 매수 이유가 체결 전에 기록됐는지, 당시 위험 허용 범위를 정했는지, 매도 이유가 그 기준과 일치했는지 확인하세요."
    ], separator="\n\n")
