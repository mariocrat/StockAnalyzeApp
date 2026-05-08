from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import pandas as pd
import datetime
from cachetools.func import ttl_cache

from core.data_fetcher import get_all_theme_stocks, get_stock_ohlcv, get_macro_data, get_krx_themes, get_stock_names, get_theme_returns_historical
from core.metrics import calculate_theme_rankings, get_stocks_in_theme
from core.utils import get_chosung

from contextlib import asynccontextmanager
import threading

def _warm_cache():
    """Pre-warm the theme cache so the first user request is instant."""
    try:
        today = datetime.date.today()
        start = (today - datetime.timedelta(days=7)).strftime('%Y%m%d')
        end = today.strftime('%Y%m%d')
        print("[startup] Warming theme cache...")
        calculate_theme_rankings(start, end)
        print("[startup] Theme cache ready.")
    except Exception as e:
        print(f"[startup] Cache warm-up failed (non-fatal): {e}")

@asynccontextmanager
async def lifespan(app):
    # Warm cache in a background thread so server starts instantly
    threading.Thread(target=_warm_cache, daemon=True).start()
    yield

app = FastAPI(title="Stock Analysis API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
def get_themes(start_date: str, end_date: str):
    df = calculate_theme_rankings(start_date, end_date)
    return df.to_dict(orient="records")

@app.get("/api/theme_stocks")
@ttl_cache(maxsize=1000, ttl=3600)
def get_theme_stocks(tickers: str, start_date: str, end_date: str):
    # tickers is comma separated
    ticker_list = tickers.split(',')
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
        if is_match(name):
            matches.append({"Ticker": ticker, "Name": name})
            if len(matches) > 50:
                break
            
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
def get_stock_data(ticker: str, start_date: str, end_date: str, indicators: Optional[str] = None):
    # Pad backwards by 365 days to ensure enough candles for MA-120
    dt_start = datetime.datetime.strptime(start_date, "%Y%m%d")
    padded_start = (dt_start - datetime.timedelta(days=365)).strftime("%Y%m%d")

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

    if indicators:
        df = calculate_indicators(df, indicators.split(','))

    # 3. Slice back to the requested start date
    df = df[df.index >= dt_start]
    if df.empty:
        return {"data": []}

    # 4. Fill NaN: forward-fill then back-fill (fixes MA gaps at edges)
    df = df.ffill().bfill()

    # 5. Drop any rows still missing core OHLC values
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])

    # 6. Strict YYYY-MM-DD date strings (no time component, no timezone)
    df['Date'] = df.index.strftime('%Y-%m-%d')

    # 7. Replace inf and residual NaN with None for clean JSON
    df = df.replace([float('inf'), float('-inf')], None)
    df = df.where(pd.notnull(df), None)

    return {"data": df.to_dict(orient="records")}

@app.get("/api/macro")
def get_macro(start_date: str, end_date: str):
    df = get_macro_data(start_date, end_date)
    if df.empty:
        return {"data": []}
    
    df['Date'] = df.index.tz_localize(None).strftime('%Y-%m-%d')
    # Fill NaN
    df = df.where(pd.notnull(df), None)
    return {"data": df.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
