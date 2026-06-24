import datetime
import json
import time
import urllib.error
import urllib.request

from core.ai_review import _env_value, _fmt8, _parse_date, _prepare_ohlcv, _chart_context_for_trade
from core.data_fetcher import get_stock_ohlcv


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(_env_value(name) or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        value = float(_env_value(name) or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _is_retryable_openai_error(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 409, 429, 500, 502, 503, 504}
    return isinstance(error, (urllib.error.URLError, TimeoutError))


def _call_openai_review(payload: dict, *, model: str, instructions: str) -> str:
    api_key = _env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY")
    if not api_key:
        return ""

    body = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
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
    timeout_seconds = _env_int("ALPHAMATE_OPENAI_TIMEOUT_SECONDS", 45, 5)
    max_retries = _env_int("ALPHAMATE_OPENAI_MAX_RETRIES", 1, 0)
    retry_backoff_seconds = _env_float("ALPHAMATE_OPENAI_RETRY_BACKOFF_SECONDS", 0.5, 0.0)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as res:
                data = json.loads(res.read().decode("utf-8"))
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


def _fallback_basic_text(trade: dict) -> str:
    side = "매수" if trade.get("side") == "buy" else "매도"
    name = trade.get("name") or trade.get("ticker") or "선택 종목"
    return (
        f"총평: {name} {side} 기록을 기준으로 차트와 매매 이유를 함께 점검하세요.\n"
        "잘한 점: 체결 가격과 수량을 기록해 복기 가능한 상태로 만들었습니다.\n"
        "아쉬운 점: 매매 전 가설, 손절 기준, 목표가가 메모에 충분히 남아있는지 확인이 필요합니다.\n"
        "다음 체크리스트: 1) 진입 가설을 한 문장으로 적기 2) 손절 기준을 가격으로 적기 3) 매도 후 대응 규칙을 남기기"
    )


def build_basic_ai_review(trades: list[dict], target_trade_id=None) -> dict:
    target = _target_trade(trades, target_trade_id)
    if not target:
        return {"status": "empty", "source": "none", "review_type": "basic", "summary": "매매 기록을 먼저 입력하세요."}

    contexts = _contexts_for_trades([target])
    payload = {
        "review_type": "basic",
        "trade": target,
        "chart_context": contexts[0] if contexts else {},
        "output_contract": {
            "format": "plain text",
            "sections": ["총평 1줄", "잘한 점 1줄", "아쉬운 점 1줄", "다음 체크리스트 3개"],
            "length": "짧고 실전적으로",
        },
    }
    model = _env_value("OPENAI_BASIC_REVIEW_MODEL") or _env_value("OPENAI_MODEL") or "gpt-5.4-mini"
    instructions = (
        "너는 한국 주식 매매 복기 코치다. 단건 매매 하나만 짧게 평가한다. "
        "투자 추천이나 매수/매도 지시는 하지 않는다. 반드시 총평, 잘한 점, 아쉬운 점, 다음 체크리스트 3개로만 답한다."
    )
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError as e:
        return {
            "status": "error",
            "source": "chart-rules",
            "review_type": "basic",
            "summary": f"{_fallback_basic_text(target)}\n\nAI 호출 실패: {e}",
            "chart_contexts": contexts,
        }

    return {
        "status": "ready" if ai_text else "missing_key",
        "source": "openai" if ai_text else "chart-rules",
        "review_type": "basic",
        "model": model if ai_text else None,
        "summary": ai_text or _fallback_basic_text(target),
        "chart_contexts": contexts,
    }


def build_advanced_ai_review(trades: list[dict], target_trade_id=None) -> dict:
    ordered = sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
    target = _target_trade(ordered, target_trade_id)
    if not target:
        return {"status": "empty", "source": "none", "review_type": "advanced", "summary": "매매 기록을 먼저 입력하세요."}

    recent = ordered[-10:]
    contexts = _contexts_for_trades(recent)
    payload = {
        "review_type": "advanced",
        "target_trade": target,
        "recent_trades": recent,
        "chart_contexts": contexts,
        "output_contract": {
            "format": "plain text",
            "must_cover": ["반복 실수", "손절 기준", "진입 가설", "대응 문제", "다음 매매 규칙"],
        },
    }
    model = _env_value("OPENAI_ADVANCED_REVIEW_MODEL") or "gpt-5.5"
    instructions = (
        "너는 한국 주식 매매 복기 코치다. 이번 매매와 최근 5~10건을 비교해 반복 실수, 손절 기준, "
        "진입 가설, 대응 문제를 분석한다. 투자 추천이나 종목 추천은 금지한다. 다음 매매에서 지킬 규칙 중심으로 답한다."
    )
    try:
        ai_text = _call_openai_review(payload, model=model, instructions=instructions)
    except RuntimeError as e:
        return {
            "status": "error",
            "source": "chart-rules",
            "review_type": "advanced",
            "summary": f"최근 매매 {len(recent)}건을 기준으로 반복 패턴을 확인하세요. AI 호출 실패: {e}",
            "chart_contexts": contexts,
        }

    return {
        "status": "ready" if ai_text else "missing_key",
        "source": "openai" if ai_text else "chart-rules",
        "review_type": "advanced",
        "model": model if ai_text else None,
        "summary": ai_text or "OPENAI_API_KEY가 설정되지 않아 고급 복기는 기본 안내로 표시됩니다. 최근 매매의 반복 실수, 손절 기준, 진입 가설을 메모와 함께 점검하세요.",
        "chart_contexts": contexts,
    }
