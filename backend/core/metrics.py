import pandas as pd
from .data_fetcher import get_krx_themes, get_stock_ohlcv, get_market_cap_yf, _clean_price_jumps
from cachetools.func import ttl_cache


@ttl_cache(maxsize=100, ttl=3600)
def calculate_theme_rankings(start_date: str, end_date: str):
    """
    Calculate average return for each theme.
    Uses return data already embedded in get_krx_themes() scrape result.
    Each ticker entry includes return_rate and is sorted descending.
    """
    themes, names, theme_returns_map = get_krx_themes()
    theme_data = []

    for theme_name, tickers in themes.items():
        ticker_returns = theme_returns_map.get(theme_name, {})
        theme_return_vals = []
        valid_tickers = []

        for ticker in tickers:
            ret = ticker_returns.get(ticker)
            valid_tickers.append({
                "ticker": ticker,
                "name": names.get(ticker, ticker),
                "return_rate": round(ret, 2) if ret is not None else None,
            })
            if ret is not None:
                theme_return_vals.append(ret)

        # Sort stocks by return descending (None last)
        valid_tickers.sort(key=lambda x: (x['return_rate'] is None, -(x['return_rate'] or 0)))

        avg_return = round(sum(theme_return_vals) / len(theme_return_vals), 2) if theme_return_vals else 0.0
        theme_data.append({
            "Theme": theme_name,
            "Avg Return (%)": avg_return,
            "Num Stocks": len(valid_tickers),
            "Tickers": valid_tickers
        })

    theme_df = pd.DataFrame(theme_data)
    if not theme_df.empty:
        theme_df = theme_df.sort_values(by="Avg Return (%)", ascending=False).reset_index(drop=True)
        theme_df.insert(0, 'Rank', range(1, len(theme_df) + 1))

    return theme_df


@ttl_cache(maxsize=100, ttl=3600)
def get_stocks_in_theme(theme_tickers: tuple, start_date: str, end_date: str):
    """
    Get detailed dataframe for stocks in a selected theme.
    Returns: Ticker, Name, Price(Close), Return(%), Volume, Market Cap.
    Note: theme_tickers must be a tuple (not list) for ttl_cache compatibility.
    """
    _, names_dict, _ = get_krx_themes()
    stock_data = []

    for ticker in theme_tickers:
        df = get_stock_ohlcv(ticker, start_date, end_date)
        df = _clean_price_jumps(df)
        name = names_dict.get(ticker, ticker)

        if not df.empty and len(df) >= 2:
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            ret = ((end_price / start_price) - 1) * 100 if start_price > 0 else 0
            vol = int(df['Volume'].iloc[-1])
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
            stock_data.append({
                "Ticker": ticker,
                "Name": name,
                "Price(KRW)": 0,
                "Return(%)": 0.0,
                "Volume": 0,
                "Market Cap(KRW)": 0
            })

    theme_stocks = pd.DataFrame(stock_data)
    if not theme_stocks.empty:
        theme_stocks = theme_stocks.sort_values(by="Return(%)", ascending=False).reset_index(drop=True)

    return theme_stocks
