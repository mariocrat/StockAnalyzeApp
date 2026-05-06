import pandas as pd
from .data_fetcher import get_krx_themes, get_stock_ohlcv, get_market_cap_yf
from pykrx import stock

from cachetools.func import ttl_cache

@ttl_cache(maxsize=100, ttl=3600)
def calculate_theme_rankings(start_date: str, end_date: str):
    """
    Calculate average return for each theme in the given period.
    Returns a sorted DataFrame of themes.
    """
    import yfinance as yf
    import datetime
    
    themes, names = get_krx_themes()
    theme_data = []
    
    # Bypass broken pykrx APIs by requesting BOTH .KS and .KQ for every ticker
    unique_tickers = list(set([t for t_list in themes.values() for t in t_list]))
    yf_tickers = []
    ticker_map = {}
    
    for t in unique_tickers:
        ks_t = f"{t}.KS"
        kq_t = f"{t}.KQ"
        yf_tickers.extend([ks_t, kq_t])
        ticker_map[ks_t] = t
        ticker_map[kq_t] = t
        
    start_dt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    # Add 1 day to end_date to include it in yfinance
    end_dt_obj = datetime.datetime.strptime(end_date, "%Y%m%d") + datetime.timedelta(days=1)
    end_dt = end_dt_obj.strftime("%Y-%m-%d")
    
    # 2. Bulk download using yfinance
    return_dict = {}
    if yf_tickers:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = yf.download(yf_tickers, start=start_dt, end=end_dt, group_by="ticker", progress=False, threads=False)
        
        for yf_t in yf_tickers:
            # yfinance returns MultiIndex columns when requesting multiple tickers
            if yf_t in data.columns.levels[0]:
                df = data[yf_t].dropna()
                if not df.empty and len(df) >= 2:
                    start_price = df['Open'].iloc[0] if df['Open'].iloc[0] > 0 else df['Close'].iloc[0]
                    end_price = df['Close'].iloc[-1]
                    if start_price > 0:
                        return_dict[ticker_map[yf_t]] = ((end_price / start_price) - 1) * 100
                            
    # 3. Calculate theme averages
    for theme_name, tickers in themes.items():
        theme_returns = []
        valid_tickers = []
        for ticker in tickers:
            if ticker in return_dict:
                theme_returns.append(return_dict[ticker])
                valid_tickers.append({"ticker": ticker, "name": names.get(ticker, ticker)})
                    
        if theme_returns:
            avg_return = sum(theme_returns) / len(theme_returns)
            theme_data.append({
                "Theme": theme_name,
                "Avg Return (%)": round(avg_return, 2),
                "Num Stocks": len(valid_tickers),
                "Tickers": valid_tickers
            })
            
    theme_df = pd.DataFrame(theme_data)
    if not theme_df.empty:
        theme_df = theme_df.sort_values(by="Avg Return (%)", ascending=False).reset_index(drop=True)
        theme_df.insert(0, 'Rank', range(1, len(theme_df) + 1))
        
    return theme_df

@ttl_cache(maxsize=100, ttl=3600)
def get_stocks_in_theme(theme_tickers: list, start_date: str, end_date: str):
    """
    Get detailed dataframe for stocks in a selected theme.
    Returns: Ticker, Name, Price(Close), Return(%), Volume, Market Cap.
    """
    themes, names_dict = get_krx_themes()
    stock_data = []
    
    for ticker in theme_tickers:
        df = get_stock_ohlcv(ticker, start_date, end_date)
        name = names_dict.get(ticker, ticker)
        
        if not df.empty and len(df) >= 2:
            start_price = df['Open'].iloc[0] if df['Open'].iloc[0] > 0 else df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            ret = ((end_price / start_price) - 1) * 100 if start_price > 0 else 0
            vol = int(df['Volume'].iloc[-1]) # latest volume
            mcap = get_market_cap_yf(ticker)
            
            stock_data.append({
                "Ticker": ticker,
                "Name": name,
                "Price(KRW)": end_price,
                "Return(%)": round(ret, 2),
                "Volume": vol,
                "Market Cap(KRW)": mcap
            })
        else:
            # Fallback if no data
            stock_data.append({
                "Ticker": ticker,
                "Name": name,
                "Price(KRW)": 0,
                "Return(%)": 0.0,
                "Volume": 0,
                "Market Cap(KRW)": get_market_cap_yf(ticker)
            })
            
    theme_stocks = pd.DataFrame(stock_data)
    if not theme_stocks.empty:
        theme_stocks = theme_stocks.sort_values(by="Return(%)", ascending=False).reset_index(drop=True)
        
    return theme_stocks
