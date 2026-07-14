import datetime
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

from core.ai_review import _fmt8, _parse_date, _prepare_ohlcv
from core.data_fetcher import get_stock_ohlcv


YF_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "yfinance"
try:
    YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YF_CACHE_DIR))
except Exception:
    pass


def _to_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _trade_day_range(trades: list[dict]):
    dates = [_parse_date(row.get("trade_date")) for row in trades]
    dates = [day for day in dates if day]
    if not dates:
        today = datetime.date.today()
        return today, today
    return min(dates), max(dates)


def _trade_datetime_range(trades: list[dict]):
    values = []
    for row in trades:
        text = str(row.get("trade_date") or "").replace("Z", "")
        try:
            values.append(datetime.datetime.fromisoformat(text))
        except ValueError:
            day = _parse_date(text)
            if day:
                values.append(datetime.datetime.combine(day, datetime.time(9, 0)))
    if not values:
        now = datetime.datetime.now()
        return now, now
    return min(values), max(values)


def _choose_intraday_interval(trades: list[dict]) -> str:
    start_dt, end_dt = _trade_datetime_range(trades)
    minutes = max(0, (end_dt - start_dt).total_seconds() / 60)
    return "1m" if minutes <= 90 else "3m"


def _resample_intraday(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if interval != "3m" or df.empty:
        return df
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    out = df.resample("3min", origin="start_day").agg(agg)
    return out.dropna(subset=["Open", "High", "Low", "Close"])


def _try_intraday(ticker: str, start: datetime.date, end: datetime.date, interval: str) -> pd.DataFrame:
    start_text = start.strftime("%Y-%m-%d")
    end_text = (end + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    for suffix in (".KS", ".KQ"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = yf.download(
                    f"{ticker}{suffix}",
                    start=start_text,
                    end=end_text,
                    interval="1m",
                    progress=False,
                    threads=False,
                    auto_adjust=True,
                )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                df.columns = [str(c).strip().capitalize() for c in df.columns]
                needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                df = df[needed].dropna(subset=["Close"])
                if df.empty:
                    continue
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_convert("Asia/Seoul").tz_localize(None)
                return _prepare_ohlcv(_resample_intraday(df, interval))
        except Exception:
            continue
    return pd.DataFrame()


def _daily_data(ticker: str, start: datetime.date, end: datetime.date) -> pd.DataFrame:
    padded_start = start - datetime.timedelta(days=90)
    padded_end = end + datetime.timedelta(days=30)
    return _prepare_ohlcv(get_stock_ohlcv(ticker, _fmt8(padded_start), _fmt8(padded_end)))


def _weekly_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    weekly = df[["Open", "High", "Low", "Close", "Volume"]].resample("W-FRI").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    })
    return _prepare_ohlcv(weekly.dropna(subset=["Open", "High", "Low", "Close"]))


def _candles_from_df(df: pd.DataFrame, timeframe: str):
    candles = []
    for idx, row in df.iterrows():
        if timeframe == "intraday":
            time_value = int(pd.Timestamp(idx).timestamp())
            label = pd.Timestamp(idx).strftime("%Y-%m-%d %H:%M")
        else:
            time_value = pd.Timestamp(idx).strftime("%Y-%m-%d")
            label = time_value
        candles.append({
            "time": time_value,
            "label": label,
            "open": _to_float(row.get("Open")),
            "high": _to_float(row.get("High")),
            "low": _to_float(row.get("Low")),
            "close": _to_float(row.get("Close")),
            "volume": _to_float(row.get("Volume")),
            "ma5": _to_float(row.get("MA5"), None),
            "ma20": _to_float(row.get("MA20"), None),
        })
    return candles


def _marker_time(trade: dict, candles: list[dict], timeframe: str):
    trade_day = _parse_date(trade.get("trade_date"))
    if not trade_day or not candles:
        return candles[-1]["time"] if candles else None

    if timeframe == "intraday":
        try:
            trade_dt = datetime.datetime.fromisoformat(str(trade.get("trade_date")).replace("Z", ""))
            target_label = trade_dt.strftime("%Y-%m-%d %H:%M")
            exact = next((row for row in candles if row.get("label") == target_label), None)
            if exact:
                return exact["time"]

            def _label_distance(row):
                try:
                    row_dt = datetime.datetime.strptime(row.get("label", ""), "%Y-%m-%d %H:%M")
                    return abs((row_dt - trade_dt).total_seconds())
                except ValueError:
                    return float("inf")

            return min(candles, key=_label_distance)["time"]
        except Exception:
            pass

    target = trade_day.isoformat()
    candidates = [row for row in candles if str(row["time"]) <= target]
    return (candidates[-1] if candidates else candles[0])["time"]


def _trade_outcomes(trades: list[dict]) -> dict:
    position_qty = 0.0
    position_cost = 0.0
    outcomes = {}
    for trade in sorted(trades, key=lambda row: (row.get("trade_date", ""), row.get("id", 0))):
        qty = _to_float(trade.get("quantity"))
        price = _to_float(trade.get("price"))
        costs = _to_float(trade.get("fee")) + _to_float(trade.get("tax"))
        if trade.get("side") == "buy":
            position_qty += qty
            position_cost += price * qty + costs
            continue
        avg_cost = position_cost / position_qty if position_qty > 0 else 0.0
        matched_qty = min(qty, position_qty) if position_qty > 0 else 0.0
        matched_cost = avg_cost * matched_qty
        net_sell = price * qty - costs
        profit = net_sell - matched_cost if matched_qty > 0 else None
        outcomes[str(trade.get("id"))] = {
            "profit_amount": round(profit, 0) if profit is not None else None,
            "return_rate": round((profit / matched_cost) * 100, 2) if profit is not None and matched_cost else None,
            "matched_cost": matched_cost if matched_qty > 0 else None,
        }
        if matched_qty > 0:
            position_qty -= matched_qty
            position_cost -= matched_cost
    return outcomes


def _markers_for_trades(trades: list[dict], candles: list[dict], timeframe: str):
    grouped = {}
    outcomes = _trade_outcomes(trades)
    for trade in trades:
        time_value = _marker_time(trade, candles, timeframe)
        if time_value is None:
            continue
        is_buy = trade.get("side") == "buy"
        key = (time_value, trade.get("side"))
        item = grouped.setdefault(key, {
            "time": time_value,
            "position": "belowBar" if is_buy else "aboveBar",
            "color": "#2962ff" if is_buy else "#ff5252",
            "shape": "arrowUp" if is_buy else "arrowDown",
            "text": "B" if is_buy else "S",
            "size": 2,
            "side": trade.get("side"),
            "trades": [],
        })
        item["trades"].append({
            "id": trade.get("id"),
            "date": trade.get("trade_date"),
            "price": _to_float(trade.get("price")),
            "quantity": _to_float(trade.get("quantity")),
            **outcomes.get(str(trade.get("id")), {}),
        })

    markers = []
    for item in grouped.values():
        count = len(item["trades"])
        if count > 1:
            item["text"] = f"{item['text']}{count}"
        total_qty = sum(row["quantity"] for row in item["trades"])
        avg_price = (
            sum(row["price"] * row["quantity"] for row in item["trades"]) / total_qty
            if total_qty else item["trades"][0]["price"]
        )
        item["tooltip"] = {
            "label": "매수" if item["side"] == "buy" else "매도",
            "count": count,
            "avg_price": round(avg_price, 0),
            "total_quantity": round(total_qty, 4),
            "prices": [row["price"] for row in item["trades"]],
        }
        if item["side"] == "sell":
            profits = [row.get("profit_amount") for row in item["trades"] if row.get("profit_amount") is not None]
            matched_cost = sum(row.get("matched_cost") or 0 for row in item["trades"])
            item["tooltip"]["profit_amount"] = round(sum(profits), 0) if profits else None
            item["tooltip"]["return_rate"] = round((sum(profits) / matched_cost) * 100, 2) if profits and matched_cost else None
            for row in item["trades"]:
                row.pop("matched_cost", None)
        markers.append(item)
    return sorted(markers, key=lambda row: (row["time"], row["side"]))


def _nearest_candle(candles: list[dict], marker_time):
    if marker_time is None or not candles:
        return None
    if isinstance(marker_time, int):
        return min(candles, key=lambda row: abs(row["time"] - marker_time))
    candidates = [row for row in candles if str(row["time"]) <= str(marker_time)]
    return candidates[-1] if candidates else candles[0]


def _movement_after(candles: list[dict], marker_time, bars: int):
    if marker_time is None:
        return None
    index = next((i for i, row in enumerate(candles) if row["time"] == marker_time), None)
    if index is None or index + bars >= len(candles):
        return None
    start = candles[index]["close"]
    end = candles[index + bars]["close"]
    if not start:
        return None
    return round(((end - start) / start) * 100, 2)


def _technical_reviews(trades: list[dict], candles: list[dict], timeframe: str):
    reviews = []
    for trade in trades:
        time_value = _marker_time(trade, candles, timeframe)
        candle = _nearest_candle(candles, time_value)
        if not candle:
            continue
        side = trade.get("side")
        price = _to_float(trade.get("price"))
        close = candle["close"]
        ma5 = candle.get("ma5")
        ma20 = candle.get("ma20")
        after_fast = _movement_after(candles, time_value, 5)
        after_slow = _movement_after(candles, time_value, 8 if timeframe == "weekly" else 20 if timeframe == "daily" else 30)
        price_gap = round(((price - close) / close) * 100, 2) if close else 0

        points = []
        score = 0
        if side == "buy":
            if ma5 and ma20 and close >= ma5 >= ma20:
                score += 1
                points.append("단기 추세가 위로 정렬된 상태에서 매수했습니다.")
            elif ma20 and close < ma20:
                score -= 1
                points.append("20선 아래에서 매수해 반등 실패 시 손절 기준이 중요했습니다.")
            if after_fast is not None and after_fast > 0:
                score += 1
                points.append(f"매수 후 5봉 수익률이 {after_fast}%라 방향 선택은 나쁘지 않았습니다.")
            elif after_fast is not None and after_fast < 0:
                score -= 1
                points.append(f"매수 후 5봉 수익률이 {after_fast}%라 매수 타이밍은 다소 이른 편입니다.")
        else:
            if after_fast is not None and after_fast < 0:
                score += 1
                points.append(f"매도 후 5봉 흐름이 {after_fast}%라 매도 타이밍은 방어적으로 좋았습니다.")
            elif after_fast is not None and after_fast > 0:
                score -= 1
                points.append(f"매도 후 5봉 흐름이 +{after_fast}%라 일부 물량을 남기는 전략을 검토할 만합니다.")
            if ma5 and close < ma5:
                score += 1
                points.append("매도 시점 종가가 5선 아래라 단기 탄력 둔화를 보고 나온 판단으로 해석됩니다.")

        if abs(price_gap) >= 2:
            points.append(f"체결가가 해당 봉 종가와 {price_gap}% 차이납니다. 장중 고점/저점 체결인지 확인이 필요합니다.")
        if not points:
            points.append("차트 지표만으로는 명확한 우위가 약합니다. 매매 이유와 손절 기준 메모가 더 필요합니다.")

        grade = "좋음" if score >= 2 else "보통" if score >= 0 else "아쉬움"
        reviews.append({
            "trade_id": trade.get("id"),
            "title": f"{trade.get('name')} {'매수' if side == 'buy' else '매도'} 시점: {grade}",
            "detail": " ".join(points),
            "metrics": {
                "price_vs_close_pct": price_gap,
                "after_5_bars": after_fast,
                "after_later_bars": after_slow,
                "ma5": ma5,
                "ma20": ma20,
            },
        })
    return reviews


def build_journal_charts(trades: list[dict]) -> dict:
    by_ticker = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").strip()
        if ticker:
            by_ticker.setdefault(ticker, []).append(trade)

    charts = []
    for ticker, rows in by_ticker.items():
        rows = sorted(rows, key=lambda row: (row.get("trade_date", ""), row.get("id", 0)))
        start, end = _trade_day_range(rows)
        same_day = start == end
        holding_days = (end - start).days

        timeframe = "daily"
        source = "daily"
        df = pd.DataFrame()
        interval = "1d"
        if same_day:
            interval = _choose_intraday_interval(rows)
            df = _try_intraday(ticker, start, end, interval)
            if len(df.index) >= 10:
                timeframe = "intraday"
                source = f"{interval} intraday"
            else:
                df = pd.DataFrame()

        if df.empty:
            df = _daily_data(ticker, start, end)
            if holding_days >= 120 and not df.empty:
                df = _weekly_data(df)
                timeframe = "weekly"
                interval = "1wk"
                source = "weekly OHLCV"
            else:
                timeframe = "daily"
                interval = "1d"
                source = "daily OHLCV"

        if df.empty:
            charts.append({
                "ticker": ticker,
                "name": rows[-1].get("name", ticker),
                "timeframe": timeframe,
                "interval": interval,
                "source": source,
                "candles": [],
                "markers": [],
                "reviews": [{"title": rows[-1].get("name", ticker), "detail": "차트 데이터를 가져오지 못했습니다."}],
            })
            continue

        candles = _candles_from_df(df, timeframe)
        markers = _markers_for_trades(rows, candles, timeframe)
        charts.append({
            "ticker": ticker,
            "name": rows[-1].get("name", ticker),
            "timeframe": timeframe,
            "interval": interval,
            "source": source,
            "period_label": start.isoformat() if same_day else f"{start.isoformat()} ~ {end.isoformat()}",
            "candles": candles,
            "markers": markers,
            "reviews": _technical_reviews(rows, candles, timeframe),
        })

    return {"charts": charts}
