from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn
import pandas as pd
import datetime
from cachetools.func import ttl_cache

from core.data_fetcher import (
    get_stock_ohlcv,
    get_macro_data,
    get_krx_themes,
    get_stock_names,
    get_theme_returns_historical,
    get_cached_theme_returns,
    get_latest_cached_theme_returns,
)
from core.metrics import calculate_theme_rankings, get_stocks_in_theme
from core.utils import get_chosung

from contextlib import asynccontextmanager
import threading
import logging

# Suppress yfinance spam at startup
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

def _previous_weekday(day: datetime.date) -> datetime.date:
    day = day - datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day = day - datetime.timedelta(days=1)
    return day

def _last_completed_market_date(now: Optional[datetime.datetime] = None) -> datetime.date:
    now = now or datetime.datetime.now()
    today = now.date()
    # Rankings are updated by the nightly cache cycle, so intraday and
    # post-close sessions both keep using the previous trading day.
    return _previous_weekday(today)

def _warm_cache():
    """Pre-warm theme caches in the background."""
    try:
        base_date = _last_completed_market_date()
        print("[startup] Warming theme caches...")

        for days in (1, 7, 30, 365):
            start = (base_date - datetime.timedelta(days=days)).strftime('%Y%m%d')
            end = base_date.strftime('%Y%m%d')
            get_theme_returns_historical(start, end)
        print("[startup] Theme cache ready.")
    except Exception as e:
        print(f"[startup] Cache warm-up failed (non-fatal): {e}")

@asynccontextmanager
async def lifespan(app):
    yield

app = FastAPI(title="Stock Analysis API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_indicators(df: pd.DataFrame, indicators: list):
    df = df.copy()
    if 'Moving Averages' in indicators:
        for ma in [5, 20, 60, 120]:
            df[f'MA_{ma}'] = df['Close'].rolling(window=ma).mean()
    if 'Bollinger Bands' in indicators:
        df['BB_MA20'] = df['Close'].rolling(window=20).mean()
        df['BB_STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_MA20'] + (df['BB_STD20'] * 2)
        df['BB_Lower'] = df['BB_MA20'] - (df['BB_STD20'] * 2)
    if 'MACD' in indicators:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    if 'RSI' in indicators:
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
    
    # Fill NA with None for JSON serialization
    return df.where(pd.notnull(df), None)

@app.get("/api/themes")
@ttl_cache(maxsize=100, ttl=3600)
def get_themes(period: str = "1D", start_date: Optional[str] = None, end_date: Optional[str] = None):
    base_date = _last_completed_market_date()
    period_days = {"1D": 1, "1W": 7, "1M": 30, "1Y": 365}
    if period in period_days:
        if period == "1D":
            start_dt = _previous_weekday(base_date)
        else:
            start_dt = base_date - datetime.timedelta(days=period_days[period])
        start_date = start_dt.strftime("%Y%m%d")
        end_date = base_date.strftime("%Y%m%d")

    if start_date and end_date:
        fallback_spans = {
            "1W": (4, 10),
            "1M": (20, 45),
            "1Y": (300, 420),
        }
        if period == "1D":
            df = get_cached_theme_returns(start_date, end_date)
            if df.empty:
                df = get_theme_returns_historical(start_date, end_date)
        elif period in fallback_spans:
            df = get_cached_theme_returns(start_date, end_date)
            if df.empty:
                df = get_theme_returns_historical(start_date, end_date)
        else:
            df = pd.DataFrame()
        if df.empty:
            if period in fallback_spans:
                min_span, max_span = fallback_spans[period]
                df = get_latest_cached_theme_returns(
                    min_span_days=min_span,
                    max_span_days=max_span,
                )
            elif period == "1D":
                df = get_latest_cached_theme_returns(max_span_days=3)
        return df.to_dict(orient="records")
    return []

@app.get("/api/theme_stocks")
@ttl_cache(maxsize=1000, ttl=3600)
def get_theme_stocks(tickers: str, start_date: str, end_date: str):
    # tickers is comma separated
    ticker_list = tuple(t.strip() for t in tickers.split(',') if t.strip())
    df = get_stocks_in_theme(ticker_list, start_date, end_date)
    return df.to_dict(orient="records")

@app.get("/api/themes_historical")
@ttl_cache(maxsize=50, ttl=1800)
def get_themes_historical(start_date: str, end_date: str):
    """Theme rankings using actual OHLCV returns for any given period (1W/1M/1Y/custom)."""
    df = get_theme_returns_historical(start_date, end_date)
    return df.to_dict(orient="records")

@app.get("/api/search")
@ttl_cache(maxsize=1000, ttl=3600)
def search_stocks(q: str):
    names_dict = get_stock_names("ALL")
    q = q.strip().lower()
    
    # Simple search
    def is_match(name):
        return q in name.lower() or q in get_chosung(name)
        
    matches = []
    for ticker, name in names_dict.items():
        if q in ticker.lower() or is_match(name):
            matches.append({"Ticker": ticker, "Name": name})
    def sort_key(item):
        name = item["Name"]
        starts_with_hangul = bool(name) and '가' <= name[0] <= '힣'
        return (not starts_with_hangul, name, item["Ticker"])

    matches.sort(key=sort_key)
    matches = matches[:50]
            
    # Which themes contain these matches?
    themes, _, _ = get_krx_themes()   # 3-tuple now
    result = []
    for m in matches:
        matched_themes = [t for t, t_list in themes.items() if m["Ticker"] in t_list]
        result.append({
            "Ticker": m["Ticker"],
            "Name": m["Name"],
            "Themes": matched_themes
        })
    return result

@app.get("/api/stock/{ticker}")
def get_stock_data(ticker: str, start_date: str, end_date: str, indicators: Optional[str] = None, interval: str = "1d"):
    # Always fetch 10 years of data to prevent viewport clipping
    padded_start = "20150101"

    df = get_stock_ohlcv(ticker, padded_start, end_date)
    if df.empty:
        return {"data": []}

    df = df.copy()

    # 1. Sort ascending (Lightweight Charts strict requirement)
    df = df.sort_index(ascending=True)

    # 2-a. Block zero-price rows (data errors, pre-listing placeholders)
    df = df[(df['Open'] > 0) & (df['High'] > 0) & (df['Low'] > 0) & (df['Close'] > 0)]
    if df.empty:
        return {"data": []}

    # 2-b. Noise killer: Korean market daily limit is ±30%.
    #      Rows where any of High/Low/Close moved >35% vs previous Close → ffill
    _prev_close = df['Close'].shift(1)
    _noise = (
        (df['Close'].sub(_prev_close).div(_prev_close).abs() > 0.35) |
        (df['High'].sub(_prev_close).div(_prev_close).abs()  > 0.35) |
        (df['Low'].sub(_prev_close).div(_prev_close).abs()   > 0.35)
    )
    # First row has no previous close → never flag it as noise
    _noise.iloc[0] = False
    if _noise.any():
        df.loc[_noise, ['Open', 'High', 'Low', 'Close']] = float('nan')
        df = df.ffill()


    # 3. Apply Resampling based on interval BEFORE calculating indicators
    if interval.lower() == '1w':
        df = df.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
    elif interval.lower() == '1m':
        df = df.resample('ME').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
    elif interval.lower() == '1y':
        df = df.resample('YE').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

    # Append 26 future periods for Ichimoku Cloud projection
    if not df.empty:
        # Determine the frequency of the index (business days, weeks, months)
        # We will just append 26 standard periods.
        if interval.lower() == '1w':
            freq = 'W-FRI'
        elif interval.lower() == '1m':
            freq = 'ME'
        elif interval.lower() == '1y':
            freq = 'YE'
        else:
            freq = 'B' # Business days
        last_date = df.index[-1]
        future_dates = pd.date_range(start=last_date, periods=27, freq=freq)[1:]
        future_df = pd.DataFrame(index=future_dates)
        df = pd.concat([df, future_df])

    # MA 5/10/20/60/120 on full padded history
    for ma in [5, 10, 20, 60, 120]:
        df[f'MA_{ma}'] = df['Close'].rolling(window=ma).mean()

    # Bollinger Bands (20, 2)
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Basis'] = df['Close'].rolling(window=20).mean()
    df['BB_Upper'] = df['BB_Basis'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Basis'] - 2 * bb_std

    # RSI(14) — Wilder's smoothing via EWM (com = period-1)
    _delta    = df['Close'].diff()
    _gain     = _delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    _loss     = (-_delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    df['RSI_14'] = (100 - 100 / (1 + _gain / _loss.replace(0, float('nan')))).round(2)

    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Stochastic (14, 3, 3)
    L14 = df['Low'].rolling(window=14).min()
    H14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = ((df['Close'] - L14) / (H14 - L14)) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

    # Ichimoku Cloud (9, 26, 52)
    nine_high = df['High'].rolling(window=9).max()
    nine_low = df['Low'].rolling(window=9).min()
    df['Ichi_Tenkan'] = (nine_high + nine_low) / 2

    twentysix_high = df['High'].rolling(window=26).max()
    twentysix_low = df['Low'].rolling(window=26).min()
    df['Ichi_Kijun'] = (twentysix_high + twentysix_low) / 2

    fiftytwo_high = df['High'].rolling(window=52).max()
    fiftytwo_low = df['Low'].rolling(window=52).min()

    df['Ichi_Senkou_A'] = ((df['Ichi_Tenkan'] + df['Ichi_Kijun']) / 2).shift(26)
    df['Ichi_Senkou_B'] = ((fiftytwo_high + fiftytwo_low) / 2).shift(26)

    if indicators:
        df = calculate_indicators(df, indicators.split(','))

    # Do not slice back to start_date, return the full 10-year dataset
    # so the frontend can zoom out indefinitely.
    if df.empty:
        return {"data": []}

    # 4. Fill NaN: forward-fill then back-fill (fixes MA gaps at edges)
    # Actually, DO NOT ffill/bfill the whole dataframe, otherwise future OHLC rows get filled!
    # We only want to fill MA/indicators where appropriate, or leave them as NaN.
    # The frontend handles None seamlessly.
    # df = df.ffill().bfill()  <-- REMOVED to preserve future blank rows for Ichimoku

    # 5. Drop any rows still missing core OHLC values ONLY IF they are not future rows.
    # Future rows have NaN Close but valid Senkou Spans.
    # We'll just keep all rows and let the frontend ignore empty candles.
    df = df[df['Close'] > 0]
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])

    # 6. Strict YYYY-MM-DD date strings (no time component, no timezone)
    df['Date'] = df.index.strftime('%Y-%m-%d')

    # 7. Replace inf and residual NaN with None for clean JSON
    df = df.replace([float('inf'), float('-inf')], float('nan'))
    df = df.astype(object).where(pd.notnull(df), None)

    return {"data": df.to_dict(orient="records")}

@app.get("/api/macro")
def get_macro(start_date: str, end_date: str):
    df = get_macro_data(start_date, end_date)
    if df.empty:
        return {"data": []}
    
    df['Date'] = df.index.tz_localize(None).strftime('%Y-%m-%d')
    # Fill NaN
    df = df.replace([float('inf'), float('-inf')], float('nan'))
    df = df.astype(object).where(pd.notnull(df), None)
    return {"data": df.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
