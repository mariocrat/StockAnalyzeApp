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


def _call_openai_review(payload: dict, *, model: str, instructions: str) -> str:
    api_key = _env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY")
    if not api_key:
        return ""

    body = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": _review_max_output_tokens(payload),
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
                raise RuntimeError(str(e)) from e
            if retry_backoff_seconds:
                time.sleep(retry_backoff_seconds)
        except json.JSONDecodeError as e:
            raise RuntimeError(str(e)) from e
    else:
        raise RuntimeError(str(last_error))

    if data.get("output_text"):
        return str(data["output_text"]).strip()

    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


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


def _fallback_basic_text(trades: list[dict], chart_snapshot: dict) -> str:
    target = trades[-1]
    name = target.get("name") or target.get("ticker") or "선택 종목"
    review = build_review(trades)
    summary = review.get("summary") or {}
    pnl = float(summary.get("realized_pnl") or 0)
    return_pct = float(summary.get("realized_return_pct") or 0)
    buy_avg = _weighted_average(trades, "buy")
    sell_avg = _weighted_average(trades, "sell")
    observations = chart_snapshot.get("rule_based_observations") or []
    buy_observation = next((row.get("detail") for row in observations if "매수" in str(row.get("title"))), "")
    sell_observation = next((row.get("detail") for row in observations if "매도" in str(row.get("title"))), "")

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
        "다음 체크리스트: 1) 매수 전 무효화 가격을 먼저 정하기 2) 첫 체결 후 3~5개 봉의 반응을 확인하고 추가 매수 결정하기 3) 매도 후 같은 시간대 주가 흐름과 비교해 너무 이른 매도인지 확인하기"
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


def build_basic_ai_review(trades: list[dict], target_trade_id=None) -> dict:
    target = _target_trade(trades, target_trade_id)
    if not target:
        return {"status": "empty", "source": "none", "review_type": "basic", "summary": "매매 기록을 먼저 입력하세요."}

    episode = _trade_episode(trades, target)
    chart_snapshot = _compact_chart_snapshot(episode)
    contexts = [] if chart_snapshot else _contexts_for_trades(episode)
    payload = {
        "review_type": "basic",
        "trade_episode": episode,
        "daily_chart_contexts": contexts,
        "trade_chart_snapshot": chart_snapshot,
        "output_contract": {
            "format": "plain text",
            "sections": ["총평 1줄", "잘한 점 1줄", "아쉬운 점 1줄", "다음 체크리스트 3개"],
            "length": "짧고 실전적으로",
        },
    }
    model = _env_value("OPENAI_BASIC_REVIEW_MODEL") or _env_value("OPENAI_MODEL") or "gpt-5.4-mini"
    instructions = (
        "너는 한국 주식 매매 복기 코치다. 같은 종목의 여러 분할 체결은 하나의 매매 에피소드로 묶어 평가한다. "
        "trade_chart_snapshot의 실제 봉, 매수·매도 마커, 평균 체결가, 실현손익을 우선 근거로 사용한다. "
        "메모가 없어도 가격과 차트만으로 매수 시점, 매도 시점, 대응을 평가한다. 기록을 남겼다는 사실 자체를 잘한 점으로 쓰지 말고, "
        "메모가 없다는 이유만으로 핵심 평가를 회피하지 않는다. 반드시 서로 다른 숫자 근거를 2개 이상 포함한다. "
        "투자 추천이나 매수·매도 지시는 하지 않는다. 반드시 총평 1줄, 잘한 점 1줄, 아쉬운 점 1줄, 다음 체크리스트 3개로만 짧고 구체적으로 답한다."
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


def build_advanced_ai_review(trades: list[dict], target_trade_id=None) -> dict:
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
            "format": "plain text",
            "must_cover": ["반복 실수", "손절 기준", "진입 가설", "대응 문제", "다음 매매 규칙"],
        },
    }
    model = _env_value("OPENAI_ADVANCED_REVIEW_MODEL") or "gpt-5.6-terra"
    instructions = (
        "너는 한국 주식 매매 복기 코치다. 이번 매매와 최근 5~10건의 실제 체결·차트 스냅샷을 비교해 반복 실수, 손절 기준, "
        "매수 가설, 매도 대응 문제를 분석한다. 메모가 없어도 체결가와 전후 봉 흐름으로 판단하고, 기록 자체를 칭찬하지 않는다. "
        "각 판단에는 종목명, 가격, 수익률, 이동평균선 또는 전후 봉 흐름 중 구체 근거를 붙인다. 투자 추천이나 종목 추천은 금지한다. "
        "마지막에는 다음 매매에서 바로 지킬 수 있는 숫자 기준의 규칙을 제시한다."
    )
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError:
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
