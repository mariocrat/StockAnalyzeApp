import datetime

import pandas as pd

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
