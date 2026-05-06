from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import pandas as pd
import datetime

from core.data_fetcher import get_all_theme_stocks, get_stock_ohlcv, get_macro_data, get_krx_themes
from core.metrics import calculate_theme_rankings, get_stocks_in_theme
from core.utils import get_chosung

app = FastAPI(title="Stock Analysis API")

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
def get_themes(start_date: str, end_date: str):
    df = calculate_theme_rankings(start_date, end_date)
    return df.to_dict(orient="records")

@app.get("/api/theme_stocks")
def get_theme_stocks(tickers: str, start_date: str, end_date: str):
    # tickers is comma separated
    ticker_list = tickers.split(',')
    df = get_stocks_in_theme(ticker_list, start_date, end_date)
    return df.to_dict(orient="records")

@app.get("/api/search")
def search_stocks(q: str):
    df = get_all_theme_stocks()
    q = q.strip().lower()
    
    # Simple search
    def is_match(name):
        return q in name.lower() or q in get_chosung(name)
        
    matches = []
    for _, row in df.iterrows():
        if is_match(row['Name']):
            matches.append({"Ticker": row["Ticker"], "Name": row["Name"]})
            
    # Which themes contain these matches?
    themes, _ = get_krx_themes()
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
    # indicators: comma separated
    dt_start = datetime.datetime.strptime(start_date, "%Y%m%d")
    padded_start = (dt_start - datetime.timedelta(days=180)).strftime("%Y%m%d")
    
    df = get_stock_ohlcv(ticker, padded_start, end_date)
    if df.empty:
        return {"data": []}
        
    if indicators:
        ind_list = indicators.split(',')
        df = calculate_indicators(df, ind_list)
        
    df = df[df.index >= dt_start]
    
    # Explicitly set Date column
    df['Date'] = df.index.strftime('%Y-%m-%d')
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
