import datetime
import json
import urllib.error
import urllib.request

import pandas as pd

from core.data_fetcher import get_stock_ohlcv

try:
    from core.env import env_value
except ModuleNotFoundError:
    from backend.core.env import env_value


def _parse_date(value: str) -> datetime.date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "")).date()
    except ValueError:
        pass
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _fmt8(day: datetime.date) -> str:
    return day.strftime("%Y%m%d")


def _env_value(name: str) -> str:
    return env_value(name)


def _prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy().sort_index()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Close"])
    if out.empty:
        return out

    out["MA5"] = out["Close"].rolling(5).mean()
    out["MA20"] = out["Close"].rolling(20).mean()
    out["MA60"] = out["Close"].rolling(60).mean()
    out["VOL20"] = out["Volume"].rolling(20).mean() if "Volume" in out.columns else 0

    delta = out["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["RSI14"] = 100 - (100 / (1 + rs))
    out["RET10"] = out["Close"].pct_change(10) * 100
    out["HIGH20"] = out["Close"].rolling(20).max()
    out["LOW20"] = out["Close"].rolling(20).min()
    return out


def _nearest_row(df: pd.DataFrame, day: datetime.date):
    if df.empty:
        return None, None
    target = pd.Timestamp(day)
    available = df[df.index <= target]
    if available.empty:
        return None, None
    row = available.iloc[-1]
    return available.index[-1].date(), row


def _future_return(df: pd.DataFrame, day: datetime.date, trading_days: int):
    target = pd.Timestamp(day)
    rows = df[df.index >= target]
    if len(rows) <= trading_days:
        return None
    start = float(rows.iloc[0]["Close"])
    end = float(rows.iloc[trading_days]["Close"])
    if start <= 0:
        return None
    return round(((end - start) / start) * 100, 2)


def _round(value, digits=2):
    try:
        if pd.isna(value):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _chart_context_for_trade(trade: dict, df: pd.DataFrame) -> dict:
    trade_day = _parse_date(trade.get("trade_date"))
    if not trade_day:
        return {"error": "날짜를 해석하지 못했습니다.", "trade": trade}

    market_day, row = _nearest_row(df, trade_day)
    if row is None:
        return {"error": "매매일 이전 차트 데이터가 없습니다.", "trade": trade}

    close = float(row["Close"])
    price = float(trade.get("price") or 0)
    volume = float(row.get("Volume") or 0)
    vol20 = float(row.get("VOL20") or 0)
    ma20 = _round(row.get("MA20"))
    ma60 = _round(row.get("MA60"))
    high20 = _round(row.get("HIGH20"))
    low20 = _round(row.get("LOW20"))

    return {
        "trade_id": trade.get("id"),
        "date": str(trade.get("trade_date", "")),
        "market_date": market_day.isoformat(),
        "ticker": trade.get("ticker", ""),
        "name": trade.get("name", ""),
        "side": trade.get("side", ""),
        "price": _round(price, 0),
        "quantity": _round(trade.get("quantity"), 4),
        "memo": trade.get("memo", ""),
        "close": _round(close, 0),
        "price_vs_close_pct": _round(((price - close) / close) * 100 if close else None),
        "ma5": _round(row.get("MA5")),
        "ma20": ma20,
        "ma60": ma60,
        "rsi14": _round(row.get("RSI14")),
        "volume_ratio_20d": _round(volume / vol20 if vol20 else None),
        "return_10d_before": _round(row.get("RET10")),
        "position_in_20d_range": _round(
            ((close - low20) / (high20 - low20)) * 100
            if high20 is not None and low20 is not None and high20 != low20
            else None
        ),
        "next_5d_return": _future_return(df, trade_day, 5),
        "next_20d_return": _future_return(df, trade_day, 20),
    }


def _rule_notes(contexts: list[dict]) -> list[dict]:
    notes = []
    for ctx in contexts:
        if ctx.get("error"):
            notes.append({
                "title": f"{ctx.get('trade', {}).get('name', '종목')} 데이터 부족",
                "detail": ctx["error"],
            })
            continue

        side = "매수" if ctx.get("side") == "buy" else "매도"
        title = f"{ctx.get('name')} {side} 복기"
        details = []
        rsi = ctx.get("rsi14")
        ret10 = ctx.get("return_10d_before")
        range_pos = ctx.get("position_in_20d_range")
        vol_ratio = ctx.get("volume_ratio_20d")
        next5 = ctx.get("next_5d_return")
        next20 = ctx.get("next_20d_return")

        if ctx.get("side") == "buy":
            if rsi is not None and rsi >= 70 and ret10 is not None and ret10 >= 12:
                details.append("매수 시점은 단기 급등과 과열이 겹친 자리입니다. 추격 진입이었다면 분할 매수보다 눌림 확인 기준이 필요합니다.")
            elif ctx.get("ma20") and ctx.get("ma60") and ctx["close"] < ctx["ma20"] < ctx["ma60"]:
                details.append("매수 시점은 20일선과 60일선 아래의 약세 구간입니다. 반등 매매라면 손절 기준이 먼저 정해져야 합니다.")
            elif range_pos is not None and range_pos >= 80:
                details.append("20거래일 가격 범위의 상단부에서 매수했습니다. 돌파 매매라면 거래량 동반 여부와 실패 시 이탈선을 함께 봐야 합니다.")
            else:
                details.append("매수 시점은 과열 또는 약세 신호가 극단적으로 겹치지는 않았습니다. 진입 사유가 차트 신호였는지 재료 기대였는지 메모가 중요합니다.")
        else:
            if next5 is not None and next5 >= 5:
                details.append("매도 후 5거래일 수익률이 높았습니다. 너무 빠른 익절이었는지, 분할 매도로 일부를 남길 수 있었는지 확인해볼 만합니다.")
            elif next20 is not None and next20 <= -8:
                details.append("매도 후 20거래일 흐름이 크게 약했습니다. 위험 회피 또는 손절 판단은 비교적 잘 작동한 구간입니다.")
            else:
                details.append("매도 후 단기 흐름이 극단적으로 한쪽으로 치우치지는 않았습니다. 매도 이유가 목표가, 손절, 시간 제한 중 무엇이었는지 분류하면 좋아요.")

        if vol_ratio is not None and vol_ratio >= 2:
            details.append("거래량이 20일 평균의 2배 이상이라 수급 이벤트가 있었던 날입니다. 이런 날은 다음날 갭과 장중 변동성이 커질 수 있습니다.")
        if ctx.get("price_vs_close_pct") is not None and abs(ctx["price_vs_close_pct"]) >= 2:
            details.append(f"입력한 체결가가 해당일 종가와 {ctx['price_vs_close_pct']}% 차이납니다. 장중 고점/저점 부근 체결인지 확인하면 복기 정확도가 올라갑니다.")

        notes.append({
            "title": title,
            "detail": " ".join(details),
            "metrics": {
                "rsi14": rsi,
                "return_10d_before": ret10,
                "volume_ratio_20d": vol_ratio,
                "next_5d_return": next5,
                "next_20d_return": next20,
            },
        })
    return notes


def _call_openai(payload: dict) -> str:
    api_key = _env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY")
    if not api_key:
        return ""

    model = _env_value("OPENAI_MODEL") or "gpt-5.4-mini"
    body = {
        "model": model,
        "instructions": (
            "너는 한국 주식 매매 복기 코치다. 사용자의 매매 기록과 매매일 전후 차트 지표를 근거로 "
            "구체적이고 실전적인 복기 조언을 한국어로 작성한다. 단정적인 매수/매도 추천은 하지 말고, "
            "진입 품질, 청산 품질, 리스크 관리, 다음 매매 규칙을 중심으로 말한다."
        ),
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
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            data = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise RuntimeError(str(e)) from e

    if data.get("output_text"):
        return str(data["output_text"]).strip()

    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def build_ai_review(trades: list[dict]) -> dict:
    ordered = sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
    if not ordered:
        return {
            "status": "empty",
            "source": "none",
            "summary": "매매 기록을 입력하면 매매 시점의 차트 흐름을 함께 분석합니다.",
            "chart_reviews": [],
        }

    by_ticker = {}
    for trade in ordered:
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
        for trade in ticker_trades[-12:]:
            contexts.append(_chart_context_for_trade(trade, df))

    rule_reviews = _rule_notes(contexts)
    payload = {
        "purpose": "매매복기. 투자 추천이 아니라 사용자의 의사결정 품질 점검.",
        "trades": ordered[-20:],
        "chart_contexts": contexts[-20:],
        "rule_reviews": rule_reviews[-20:],
        "requested_output": [
            "전체 요약 2~3문장",
            "좋았던 판단과 아쉬운 판단",
            "다음 매매에서 지킬 규칙 3개",
            "종목별로 중요한 차트 근거",
        ],
    }

    try:
        ai_text = _call_openai(payload)
    except RuntimeError as e:
        return {
            "status": "error",
            "source": "chart-rules",
            "summary": f"AI 호출에 실패해 기본 차트 복기로 표시합니다. ({e})",
            "chart_reviews": rule_reviews,
            "chart_contexts": contexts,
        }

    if ai_text:
        return {
            "status": "ready",
            "source": "openai",
            "summary": ai_text,
            "chart_reviews": rule_reviews,
            "chart_contexts": contexts,
        }

    return {
        "status": "missing_key",
        "source": "chart-rules",
        "summary": "OPENAI_API_KEY가 설정되지 않아 기본 차트 복기로 표시합니다. 키를 설정하면 AI가 아래 차트 지표와 매매 기록을 함께 읽고 더 깊게 분석합니다.",
        "chart_reviews": rule_reviews,
        "chart_contexts": contexts,
    }
