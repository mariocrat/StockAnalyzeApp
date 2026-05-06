import pandas as pd
import yfinance as yf
from pykrx import stock
from cachetools.func import ttl_cache
import datetime

@ttl_cache(maxsize=100, ttl=3600)
def get_stock_names(market="ALL"):
    """Get mapping of ticker to stock name."""
    today = datetime.datetime.today().strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market=market)
    names = {ticker: stock.get_market_ticker_name(ticker) for ticker in tickers}
    return names

@ttl_cache(maxsize=100, ttl=3600*24)
def get_krx_themes():
    """
    Scrape top themes and their top stocks dynamically from Naver Finance.
    Returns a dictionary of {ThemeName: [Ticker1, Ticker2, ...]}.
    """
    import requests
    from bs4 import BeautifulSoup
    
    url = 'https://finance.naver.com/sise/theme.naver'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        links = soup.select('a[href^="/sise/sise_group_detail.naver?type=theme"]')
        themes = {}
        names = {}
        
        # Limit to top 30 themes to keep performance reasonable for MVP
        for a in links[:30]:
            theme_name = a.text.strip()
            if not theme_name: continue
            
            detail_url = 'https://finance.naver.com' + a['href']
            detail_res = requests.get(detail_url, headers=headers)
            detail_res.encoding = 'euc-kr'
            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
            
            stock_links = detail_soup.select('div.name_area a[href^="/item/main.naver?code="]')
            tickers = []
            for sa in stock_links:
                ticker = sa['href'].split('code=')[1]
                name = sa.text.strip()
                if ticker not in tickers:
                    tickers.append(ticker)
                    names[ticker] = name
                    if len(tickers) >= 10: # Top 10 stocks per theme
                        break
                        
            if tickers:
                themes[theme_name] = tickers
                
        return themes, names
    except Exception as e:
        # Fallback dictionary if scraping fails
        return {
            "반도체(에러 폴백)": ["005930", "000660"],
            "이차전지(에러 폴백)": ["373220", "006400"]
        }, {
            "005930": "삼성전자", "000660": "SK하이닉스",
            "373220": "LG에너지솔루션", "006400": "삼성SDI"
        }

@ttl_cache(maxsize=100, ttl=3600*24)
def get_all_theme_stocks():
    """
    Returns a dataframe of all unique stocks present in the current themes.
    Useful for global searching.
    """
    themes, names = get_krx_themes()
    
    stocks = []
    for ticker, name in names.items():
        stocks.append({'Ticker': ticker, 'Name': name})
    
    df = pd.DataFrame(stocks)
    if not df.empty:
        df = df.sort_values(by='Name').reset_index(drop=True)
    return df

@ttl_cache(maxsize=100, ttl=3600)
def get_returns_for_period(start_date: str, end_date: str, market="ALL"):
    """
    Get stock returns for the entire market between start_date and end_date.
    start_date, end_date format: YYYYMMDD
    Returns a DataFrame.
    """
    df = stock.get_market_price_change_by_ticker(start_date, end_date, market=market)
    # The pykrx dataframe has index as ticker. We need to reset index.
    df = df.reset_index()
    # Rename columns to english for easier handling
    df = df.rename(columns={
        "티커": "Ticker",
        "종목명": "Name",
        "시가": "Open",
        "종가": "Close",
        "변동폭": "Change",
        "등락률": "Return",
        "거래량": "Volume",
        "거래대금": "Value"
    })
    return df

@ttl_cache(maxsize=100, ttl=3600)
def get_market_cap(date: str):
    """
    Get market cap for all stocks on a specific date.
    """
    df_kospi = stock.get_market_cap(date, market="KOSPI").reset_index()
    df_kosdaq = stock.get_market_cap(date, market="KOSDAQ").reset_index()
    df = pd.concat([df_kospi, df_kosdaq], ignore_index=True)
    df = df.rename(columns={
        "티커": "Ticker",
        "시가총액": "MarketCap",
        "상장주식수": "Shares",
        "거래량": "Volume",
        "거래대금": "Value"
    })
    return df[['Ticker', 'MarketCap']]

@ttl_cache(maxsize=100, ttl=3600)
def get_stock_ohlcv(ticker: str, start_date: str, end_date: str):
    """
    Get OHLCV data for a specific stock for charts using yfinance.
    """
    import datetime
    start_dt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_dt_obj = datetime.datetime.strptime(end_date, "%Y%m%d") + datetime.timedelta(days=1)
    end_dt = end_dt_obj.strftime("%Y-%m-%d")
    
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = yf.download(f"{ticker}.KS", start=start_dt, end=end_dt, progress=False, threads=False)
        if df.empty:
            df = yf.download(f"{ticker}.KQ", start=start_dt, end=end_dt, progress=False, threads=False)
            
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
    
    return df

@ttl_cache(maxsize=100, ttl=3600)
def get_macro_data(start_date: str, end_date: str):
    """
    Get Macro data using yfinance.
    USDKRW=X, CL=F (WTI), GC=F (Gold)
    Dates should be in YYYY-MM-DD for yfinance.
    """
    # format pykrx dates YYYYMMDD to YYYY-MM-DD
    start_dt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_dt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    tickers = ["USDKRW=X", "CL=F", "GC=F"]
    data = yf.download(tickers, start=start_dt, end=end_dt)['Close']
    if not data.empty:
        data.columns = ['WTI', 'Gold', 'USD/KRW']
    return data

@ttl_cache(maxsize=100, ttl=3600*24)
def get_market_cap_yf(ticker: str):
    """
    Fetch market cap using yfinance as pykrx's endpoint is currently unstable.
    """
    try:
        # Check KOSPI first
        t = yf.Ticker(f"{ticker}.KS")
        mcap = t.info.get('marketCap')
        if mcap: return mcap
        
        # Check KOSDAQ if KOSPI fails
        t = yf.Ticker(f"{ticker}.KQ")
        mcap = t.info.get('marketCap')
        if mcap: return mcap
    except:
        pass
    return 0
