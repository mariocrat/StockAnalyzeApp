import datetime
import json
import time
import urllib.error
import urllib.request

from core.ai_review import _env_value, _fmt8, _parse_date, _prepare_ohlcv, _chart_context_for_trade
from core.data_fetcher import get_stock_ohlcv
from core.event_log import record_event
from core.journal import build_review
from core.journal_chart import build_journal_charts


OPENAI_TIMEOUT_MAX_SECONDS = 90
OPENAI_MAX_RETRIES_LIMIT = 3
OPENAI_RETRY_BACKOFF_MAX_SECONDS = 5.0
OPENAI_MAX_OUTPUT_TOKENS_LIMIT = 10_000
BASIC_REVIEW_FOCUS_LABELS = {
    "balanced": "매수 시점, 매도 시점, 위험 관리를 균형 있게 점검",
    "entry_timing": "매수 직후 5개 봉과 진입 위치를 우선 점검",
    "exit_timing": "매도 뒤 5개 봉과 청산 효율을 우선 점검",
    "risk_control": "분할 체결, 평균 체결가, 손실 제한 기준을 우선 점검",
}


def _env_int(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        value = int(_env_value(name) or default)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float | None = None) -> float:
    try:
        value = float(_env_value(name) or default)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _is_retryable_openai_error(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 409, 429, 500, 502, 503, 504}
    return isinstance(error, (urllib.error.URLError, TimeoutError))


def _review_max_output_tokens(payload: dict) -> int:
    if str(payload.get("review_type") or "").strip().lower() == "advanced":
        return _env_int("OPENAI_ADVANCED_REVIEW_MAX_OUTPUT_TOKENS", 3000, 256, OPENAI_MAX_OUTPUT_TOKENS_LIMIT)
    return _env_int("OPENAI_BASIC_REVIEW_MAX_OUTPUT_TOKENS", 1000, 256, OPENAI_MAX_OUTPUT_TOKENS_LIMIT)


def _record_openai_usage(data: dict, *, payload: dict, model: str) -> None:
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    details = {
        "review_type": str(payload.get("review_type") or "unknown"),
        "model": model,
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(input_details.get("cached_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    try:
        record_event(
            level="info",
            event_type="openai_review_usage",
            method="POST",
            path="/v1/responses",
            status_code=200,
            message="OpenAI review token usage recorded.",
            details=details,
        )
    except Exception:
        # Usage telemetry must never turn a successful review into a user-facing failure.
        return


def _record_openai_failure(error: BaseException, *, payload: dict, model: str, attempt: int) -> None:
    status_code = error.code if isinstance(error, urllib.error.HTTPError) else 0
    details = {
        "review_type": str(payload.get("review_type") or "unknown"),
        "model": model,
        "attempt": attempt,
        "error_type": type(error).__name__,
        "retryable": _is_retryable_openai_error(error),
    }
    try:
        record_event(
            level="error",
            event_type="openai_review_request_failed",
            method="POST",
            path="/v1/responses",
            status_code=status_code,
            message="OpenAI review request failed without storing prompt or response content.",
            details=details,
        )
    except Exception:
        return


def _call_openai_review(payload: dict, *, model: str, instructions: str) -> str:
    api_key = _env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY")
    if not api_key:
        return ""

    body = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": _review_max_output_tokens(payload),
        "store": False,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout_seconds = _env_int("ALPHAMATE_OPENAI_TIMEOUT_SECONDS", 45, 5, OPENAI_TIMEOUT_MAX_SECONDS)
    max_retries = _env_int("ALPHAMATE_OPENAI_MAX_RETRIES", 1, 0, OPENAI_MAX_RETRIES_LIMIT)
    retry_backoff_seconds = _env_float(
        "ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS",
        0.5,
        0.0,
        OPENAI_RETRY_BACKOFF_MAX_SECONDS,
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as res:
                data = json.loads(res.read().decode("utf-8"))
            _record_openai_usage(data, payload=payload, model=model)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt >= max_retries or not _is_retryable_openai_error(e):
                _record_openai_failure(e, payload=payload, model=model, attempt=attempt + 1)
                raise RuntimeError(str(e)) from e
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds)
        except json.JSONDecodeError as e:
            _record_openai_failure(e, payload=payload, model=model, attempt=attempt + 1)
            raise RuntimeError(str(e)) from e
    else:
        raise RuntimeError(str(last_error))

    if data.get("output_text"):
        output_text = str(data["output_text"]).strip()
        if output_text:
            return output_text

    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    output_text = "\n".join(chunks).strip()
    if output_text:
        return output_text

    incomplete = data.get("incomplete_details") if isinstance(data, dict) else None
    try:
        record_event(
            level="error",
            event_type="openai_review_empty_output",
            method="POST",
            path="/v1/responses",
            status_code=502,
            message="OpenAI review response did not contain user-visible text.",
            details={
                "review_type": str(payload.get("review_type") or "unknown"),
                "model": model,
                "response_status": str(data.get("status") or "unknown"),
                "incomplete_reason": str((incomplete or {}).get("reason") or ""),
            },
        )
    except Exception:
        pass
    raise RuntimeError("OpenAI response did not include output text.")


def _target_trade(trades: list[dict], target_trade_id=None) -> dict | None:
    ordered = sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
    if target_trade_id is not None:
        for trade in ordered:
            if str(trade.get("id")) == str(target_trade_id):
                return trade
    return ordered[-1] if ordered else None


def _contexts_for_trades(trades: list[dict]) -> list[dict]:
    by_ticker = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").strip()
        if ticker:
            by_ticker.setdefault(ticker, []).append(trade)

    contexts = []
    for ticker, ticker_trades in by_ticker.items():
        dates = [_parse_date(t.get("trade_date")) for t in ticker_trades]
        dates = [d for d in dates if d]
        if not dates:
            continue
        start = min(dates) - datetime.timedelta(days=140)
        end = max(dates) + datetime.timedelta(days=45)
        df = _prepare_ohlcv(get_stock_ohlcv(ticker, _fmt8(start), _fmt8(end)))
        for trade in ticker_trades:
            contexts.append(_chart_context_for_trade(trade, df))
    return contexts


def _trade_episode(trades: list[dict], target: dict) -> list[dict]:
    ticker = str(target.get("ticker") or "").strip()
    name = str(target.get("name") or "").strip()
    episode = [
        row for row in trades
        if (ticker and str(row.get("ticker") or "").strip() == ticker)
        or (not ticker and name and str(row.get("name") or "").strip() == name)
    ]
    return sorted(episode, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))[-20:]


def _compact_chart_snapshot(trades: list[dict]) -> dict:
    try:
        chart = (build_journal_charts(trades).get("charts") or [None])[0]
    except Exception:
        chart = None
    if not chart:
        return {}

    candles = chart.get("candles") or []
    markers = chart.get("markers") or []
    marker_times = {str(item.get("time")) for item in markers}
    marker_indexes = [index for index, row in enumerate(candles) if str(row.get("time")) in marker_times]
    if marker_indexes:
        start = max(0, min(marker_indexes) - 25)
        end = min(len(candles), max(marker_indexes) + 36)
        candles = candles[start:end]
    else:
        candles = candles[-100:]
    if len(candles) > 140:
        step = max(1, len(candles) // 120)
        candles = candles[::step][-140:]

    return {
        "ticker": chart.get("ticker"),
        "name": chart.get("name"),
        "timeframe": chart.get("timeframe"),
        "interval": chart.get("interval"),
        "period": chart.get("period_label"),
        "candles": [
            {
                "t": row.get("label") or row.get("time"),
                "o": row.get("open"), "h": row.get("high"), "l": row.get("low"), "c": row.get("close"),
                "v": row.get("volume"), "ma5": row.get("ma5"), "ma20": row.get("ma20"),
            }
            for row in candles
        ],
        "trade_markers": [
            {"time": row.get("time"), "side": row.get("side"), "tooltip": row.get("tooltip")}
            for row in markers
        ],
        "rule_based_observations": chart.get("reviews") or [],
    }


def _weighted_average(trades: list[dict], side: str) -> float | None:
    rows = [row for row in trades if row.get("side") == side]
    total_quantity = sum(float(row.get("quantity") or 0) for row in rows)
    if total_quantity <= 0:
        return None
    return sum(float(row.get("price") or 0) * float(row.get("quantity") or 0) for row in rows) / total_quantity


def _safe_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_basic_review_focus(value: str | None) -> str:
    focus = str(value or "").strip().lower()
    return focus if focus in BASIC_REVIEW_FOCUS_LABELS else "balanced"


def _observation_for_side(trades: list[dict], chart_snapshot: dict, side: str) -> dict:
    trade_ids = {
        str(row.get("id"))
        for row in trades
        if row.get("side") == side and row.get("id") is not None
    }
    observations = chart_snapshot.get("rule_based_observations") or []
    for observation in reversed(observations):
        if str(observation.get("trade_id")) in trade_ids:
            return observation
    return {}


def _basic_evaluation_anchor(trades: list[dict], chart_snapshot: dict) -> dict:
    review = build_review(trades)
    summary = review.get("summary") or {}
    buy_average = _weighted_average(trades, "buy")
    sell_average = _weighted_average(trades, "sell")
    pnl = float(summary.get("realized_pnl") or 0)
    return_pct = float(summary.get("realized_return_pct") or 0)
    trade_by_id = {str(row.get("id")): row for row in trades if row.get("id") is not None}
    execution_evidence = []
    for observation in chart_snapshot.get("rule_based_observations") or []:
        trade = trade_by_id.get(str(observation.get("trade_id"))) or {}
        metrics = observation.get("metrics") or {}
        execution_evidence.append({
            "trade_id": observation.get("trade_id"),
            "side": trade.get("side") or "unknown",
            "trade_date": trade.get("trade_date"),
            "trade_price": trade.get("price"),
            "rule_grade": observation.get("title"),
            "rule_detail": observation.get("detail"),
            "price_vs_candle_close_pct": _safe_float(metrics.get("price_vs_close_pct")),
            "after_5_bars_pct": _safe_float(metrics.get("after_5_bars")),
            "after_later_bars_pct": _safe_float(metrics.get("after_later_bars")),
            "ma5": _safe_float(metrics.get("ma5")),
            "ma20": _safe_float(metrics.get("ma20")),
        })

    if buy_average is None or sell_average is None:
        outcome_direction = "open_or_incomplete"
    elif pnl > 0:
        outcome_direction = "profit"
    elif pnl < 0:
        outcome_direction = "loss"
    else:
        outcome_direction = "flat"

    return {
        "symbol": {
            "ticker": str((trades[-1] if trades else {}).get("ticker") or ""),
            "name": str((trades[-1] if trades else {}).get("name") or ""),
        },
        "outcome": {
            "direction": outcome_direction,
            "realized_pnl": pnl,
            "realized_return_pct": return_pct,
            "weighted_buy_price": buy_average,
            "weighted_sell_price": sell_average,
            "buy_fill_count": sum(1 for row in trades if row.get("side") == "buy"),
            "sell_fill_count": sum(1 for row in trades if row.get("side") == "sell"),
        },
        "execution_evidence": execution_evidence,
    }


def _basic_checklist_items(trades: list[dict], chart_snapshot: dict) -> list[str]:
    buy_average = _weighted_average(trades, "buy")
    sell_average = _weighted_average(trades, "sell")
    buy_count = sum(1 for row in trades if row.get("side") == "buy")
    buy_observation = _observation_for_side(trades, chart_snapshot, "buy")
    sell_observation = _observation_for_side(trades, chart_snapshot, "sell")
    buy_after_five = _safe_float((buy_observation.get("metrics") or {}).get("after_5_bars"))
    sell_after_five = _safe_float((sell_observation.get("metrics") or {}).get("after_5_bars"))

    if buy_average is not None:
        first = f"평균 매수가 {buy_average:,.0f}원을 기준으로 무효화 가격과 허용 손실액을 체결 전에 함께 적기"
    else:
        first = "첫 체결 전에 무효화 가격과 허용 손실액을 숫자로 함께 적기"

    if buy_after_five is not None:
        second = (
            f"이번 매수 뒤 5개 봉 수익률 {buy_after_five:+.2f}%를 기준으로 "
            "5번째 봉에서 가설 유지 또는 철회 여부를 기록하기"
        )
    else:
        second = f"이번 {max(1, buy_count)}회 매수 체결마다 분할 진입 목적과 중단 조건을 한 줄씩 남기기"

    if sell_average is not None and sell_after_five is not None:
        third = (
            f"평균 매도가 {sell_average:,.0f}원 이후 5개 봉 수익률 {sell_after_five:+.2f}%를 "
            "다음 복기에서도 같은 기준으로 비교하기"
        )
    elif sell_average is not None:
        third = f"평균 매도가 {sell_average:,.0f}원 뒤 같은 시간 단위의 5개 봉 흐름을 확인해 청산 효율을 비교하기"
    else:
        third = "매도 체결 전 일부 청산과 전량 청산 조건을 각각 숫자로 정하기"
    return [first, second, third]


def _fallback_basic_text(trades: list[dict], chart_snapshot: dict) -> str:
    target = trades[-1]
    name = target.get("name") or target.get("ticker") or "선택 종목"
    review = build_review(trades)
    summary = review.get("summary") or {}
    pnl = float(summary.get("realized_pnl") or 0)
    return_pct = float(summary.get("realized_return_pct") or 0)
    buy_avg = _weighted_average(trades, "buy")
    sell_avg = _weighted_average(trades, "sell")
    buy_observation = _observation_for_side(trades, chart_snapshot, "buy").get("detail") or ""
    sell_observation = _observation_for_side(trades, chart_snapshot, "sell").get("detail") or ""
    checklist = _basic_checklist_items(trades, chart_snapshot)

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

    return (
        f"총평: {verdict}\n"
        f"잘한 점: {good}\n"
        f"아쉬운 점: {weak}\n"
        f"다음 체크리스트: 1) {checklist[0]} 2) {checklist[1]} 3) {checklist[2]}"
    )


def _fallback_advanced_text(trades: list[dict], chart_snapshots: list[dict]) -> str:
    review = build_review(trades)
    summary = review.get("summary") or {}
    symbols = review.get("by_symbol") or []
    losses = [row for row in symbols if float(row.get("realized_pnl") or 0) < 0]
    open_positions = [row for row in symbols if float(row.get("open_quantity") or 0) > 0]
    observations = [
        item
        for snapshot in chart_snapshots
        for item in (snapshot.get("rule_based_observations") or [])
    ]
    weak_entries = [item.get("detail") for item in observations if "매수 시점: 아쉬움" in str(item.get("title"))]
    weak_exits = [item.get("detail") for item in observations if "매도 시점: 아쉬움" in str(item.get("title"))]
    repeated_issue = weak_entries[0] if weak_entries else weak_exits[0] if weak_exits else "체결 전후 봉에서 반복되는 명확한 약점은 아직 표본이 부족합니다."
    loss_text = ", ".join(f"{row.get('name')} {float(row.get('realized_pnl') or 0):+,.0f}원" for row in losses[:3]) or "확정 손실 종목 없음"
    return (
        f"최근 패턴: {len(trades)}건, 실현손익 {float(summary.get('realized_pnl') or 0):+,.0f}원, 승률 {float(summary.get('win_rate_pct') or 0):.1f}%입니다.\n"
        f"반복 문제: {repeated_issue}\n"
        f"손실 관리: {loss_text}. 미청산 종목은 {len(open_positions)}개입니다.\n"
        "다음 규칙: 첫 매수 전에 손절 가격과 최대 손실액을 숫자로 정하고, 추가 매수는 첫 체결 뒤 최소 3개 봉에서 저점이 높아질 때만 검토하며, 매도 후 5개 봉 흐름과 비교해 청산이 너무 빨랐는지 점검하세요."
    )


def build_basic_ai_review(trades: list[dict], target_trade_id=None, analysis_focus: str = "balanced") -> dict:
    target = _target_trade(trades, target_trade_id)
    if not target:
        return {"status": "empty", "source": "none", "review_type": "basic", "summary": "매매 기록을 먼저 입력하세요."}

    episode = _trade_episode(trades, target)
    chart_snapshot = _compact_chart_snapshot(episode)
    contexts = [] if chart_snapshot else _contexts_for_trades(episode)
    focus = _normalize_basic_review_focus(analysis_focus)
    evaluation_anchor = _basic_evaluation_anchor(episode, chart_snapshot)
    payload = {
        "review_type": "basic",
        "analysis_version": "basic-review-v2",
        "analysis_focus": {
            "key": focus,
            "priority": BASIC_REVIEW_FOCUS_LABELS[focus],
        },
        "trade_episode": episode,
        "daily_chart_contexts": contexts,
        "trade_chart_snapshot": chart_snapshot,
        "evaluation_anchor": evaluation_anchor,
        "consistency_policy": {
            "stable_dimensions": ["매수 시점", "매도 시점", "위험 관리", "실현 결과"],
            "rule": "동일한 evaluation_anchor라면 평가 방향과 근거가 서로 모순되면 안 된다.",
            "focus_rule": "analysis_focus는 강조 근거만 바꾸며 잘함과 아쉬움의 판정을 뒤집지 않는다.",
        },
        "output_contract": {
            "format": "plain text",
            "sections": ["총평 1줄", "잘한 점 1줄", "아쉬운 점 1줄", "다음 체크리스트 3개"],
            "length": "짧고 실전적으로",
        },
    }
    model = _env_value("OPENAI_BASIC_REVIEW_MODEL") or _env_value("OPENAI_MODEL") or "gpt-5.4-mini"
    instructions = (
        "<role>너는 한국 주식 매매 복기 코치다. 같은 종목의 여러 분할 체결은 하나의 매매 에피소드로 평가한다.</role>\n"
        "<evidence_rules>evaluation_anchor와 trade_chart_snapshot의 실제 봉, 매수·매도 마커, 평균 체결가, "
        "실현손익을 우선 근거로 사용한다. 메모가 없어도 가격과 차트로 평가하고, 기록을 남긴 사실 자체를 칭찬하지 않는다. "
        "서로 다른 숫자 근거를 2개 이상 포함하며 근거가 없으면 추측하지 않는다.</evidence_rules>\n"
        "<consistency_rules>동일한 evaluation_anchor에는 매수 시점, 매도 시점, 위험 관리의 평가 방향을 동일하게 유지한다. "
        "analysis_focus는 이번 답변에서 우선 설명할 관점일 뿐 잘함과 아쉬움의 판정을 뒤집는 근거가 아니다. "
        "표현을 새롭게 보이게 하려고 결론을 바꾸거나 모순되는 평가를 만들지 않는다.</consistency_rules>\n"
        "<quality_rules>잘한 점을 억지로 만들지 말고, 확인된 강점이 없으면 그렇게 쓴다. 아쉬운 점과 체크리스트는 이번 거래의 "
        "가격, 수익률, 체결 횟수, 5개 봉 또는 이동평균 근거에 직접 연결한다. 어느 거래에도 붙일 수 있는 상투적인 문구만 쓰지 않는다.</quality_rules>\n"
        "<output_contract>투자 추천이나 매수·매도 지시는 하지 않는다. 총평 1줄, 잘한 점 1줄, 아쉬운 점 1줄, "
        "다음 체크리스트 3개로만 짧고 구체적으로 답한다.</output_contract>"
    )
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError:
        return {
            "status": "error",
            "source": "chart-rules",
            "review_type": "basic",
            "summary": _fallback_basic_text(episode, chart_snapshot),
            "chart_contexts": contexts,
            "chart_snapshot": chart_snapshot,
            "chart_reviews": chart_snapshot.get("rule_based_observations") or [],
        }

    return {
        "status": "ready" if ai_text else "missing_key",
        "source": "openai" if ai_text else "chart-rules",
        "review_type": "basic",
        "model": model if ai_text else None,
        "summary": ai_text or _fallback_basic_text(episode, chart_snapshot),
        "chart_contexts": contexts,
        "chart_snapshot": chart_snapshot,
        "chart_reviews": chart_snapshot.get("rule_based_observations") or [],
    }


def build_advanced_ai_review(
    trades: list[dict],
    target_trade_id=None,
    *,
    model_override: str = "",
    allow_fallback: bool = True,
) -> dict:
    ordered = sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
    target = _target_trade(ordered, target_trade_id)
    if not target:
        return {"status": "empty", "source": "none", "review_type": "advanced", "summary": "매매 기록을 먼저 입력하세요."}

    recent = ordered[-10:]
    chart_snapshots = []
    by_ticker = {}
    for trade in recent:
        by_ticker.setdefault(str(trade.get("ticker") or trade.get("name") or ""), []).append(trade)
    for ticker_trades in by_ticker.values():
        snapshot = _compact_chart_snapshot(ticker_trades)
        if snapshot:
            chart_snapshots.append(snapshot)
    contexts = [] if chart_snapshots else _contexts_for_trades(recent)
    payload = {
        "review_type": "advanced",
        "target_trade": target,
        "recent_trades": recent,
        "chart_contexts": contexts,
        "trade_chart_snapshots": chart_snapshots,
        "output_contract": {
            "format": "structured markdown",
            "must_cover": ["반복 실수", "손절 기준", "진입 가설", "대응 문제", "다음 매매 규칙"],
            "sections": ["이번 매매 판단", "반복 패턴", "손절 기준", "매수·매도 대응", "다음 매매 규칙"],
            "length": "핵심 근거 중심으로 간결하게",
        },
    }
    model = str(model_override or "").strip() or _env_value("OPENAI_ADVANCED_REVIEW_MODEL") or "gpt-5.6-terra"
    fallback_model = (
        _env_value("OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL")
        or _env_value("OPENAI_BASIC_REVIEW_MODEL")
        or "gpt-5.4-mini"
    )
    instructions = (
        "너는 한국 주식 매매 복기 코치다. 이번 매매와 최근 5~10건의 실제 체결·차트 스냅샷을 비교해 반복 실수, 손절 기준, "
        "매수 가설, 매도 대응 문제를 분석한다. 메모가 없어도 체결가와 전후 봉 흐름으로 판단하고, 기록 자체를 칭찬하지 않는다. "
        "각 판단에는 종목명, 가격, 수익률, 이동평균선 또는 전후 봉 흐름 중 구체 근거를 붙인다. 확인된 사실과 해석을 구분하고, "
        "최고가를 사후적으로 맞혔어야 한다는 식으로 평가하지 않는다. 손절 기준은 서로 다른 대안을 여러 개 나열하기보다 이번 진입 "
        "가설과 가장 논리적으로 연결되는 한 가지 기본 기준을 먼저 제시한다. 근거 없이 모든 종목에 적용할 고정 비율을 만들지 않는다. "
        "MA5, MA10 같은 영문 약어는 쓰지 않는다. 1분봉이면 5분 이동평균선, 일봉이면 5일 이동평균선처럼 차트 주기에 맞는 "
        "한국어 명칭을 쓴다. '이번 매매 판단', '반복 패턴', '손절 기준', '매수·매도 대응', '다음 매매 규칙' 순서의 마크다운 제목을 "
        "사용하고, 각 항목은 짧은 문단과 목록으로 정리한다. 투자 추천이나 종목 추천은 금지한다. 마지막 규칙은 실제 근거가 있는 "
        "숫자 기준만 3개 이내로 제시한다."
    )
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError:
        if allow_fallback and fallback_model and fallback_model != model:
            try:
                ai_text = _call_openai_review(payload, model=fallback_model, instructions=instructions)
                model = fallback_model
            except RuntimeError:
                ai_text = ""
        else:
            ai_text = ""
        if not ai_text:
            return {
                "status": "error",
                "source": "chart-rules",
                "review_type": "advanced",
                "summary": _fallback_advanced_text(recent, chart_snapshots),
                "chart_contexts": contexts,
                "chart_snapshots": chart_snapshots,
                "chart_reviews": [item for snapshot in chart_snapshots for item in (snapshot.get("rule_based_observations") or [])],
            }

    return {
        "status": "ready" if ai_text else "missing_key",
        "source": "openai" if ai_text else "chart-rules",
        "review_type": "advanced",
        "model": model if ai_text else None,
        "summary": ai_text or _fallback_advanced_text(recent, chart_snapshots),
        "chart_contexts": contexts,
        "chart_snapshots": chart_snapshots,
        "chart_reviews": [item for snapshot in chart_snapshots for item in (snapshot.get("rule_based_observations") or [])],
    }
