import pandas as pd
import yfinance as yf
from pykrx import stock
from cachetools.func import ttl_cache
import datetime


@ttl_cache(maxsize=1, ttl=3600*6)
def get_stock_names(market="ALL"):
    """
    Get mapping of ticker -> stock name for all KRX listed stocks.
    Chain: pykrx → FinanceDataReader → Naver theme names (fallback)
    """
    # 1. Try pykrx
    try:
        today = datetime.datetime.today().strftime("%Y%m%d")
        tickers = stock.get_market_ticker_list(today, market=market)
        if not tickers:
            raise ValueError("pykrx returned empty ticker list")
        names = {ticker: stock.get_market_ticker_name(ticker) for ticker in tickers}
        print(f"[get_stock_names] pykrx OK: {len(names)} stocks")
        return names
    except Exception as e:
        print(f"[get_stock_names] pykrx failed ({e})")

    # 2. Try FinanceDataReader
    try:
        import FinanceDataReader as fdr
        kospi  = fdr.StockListing('KOSPI')[['Code', 'Name']].dropna()
        kosdaq = fdr.StockListing('KOSDAQ')[['Code', 'Name']].dropna()
        combined = pd.concat([kospi, kosdaq], ignore_index=True)
        names = {str(row.Code).zfill(6): row.Name for row in combined.itertuples()}
        print(f"[get_stock_names] FDR OK: {len(names)} stocks")
        return names
    except Exception as e:
        print(f"[get_stock_names] FDR failed ({e})")

    # 3. Last resort: Naver theme names (~200 stocks)
    print("[get_stock_names] falling back to Naver theme names")
    _, names_from_themes, _ = get_krx_themes()
    return names_from_themes


@ttl_cache(maxsize=100, ttl=3600*24)
def get_krx_themes():
    """
    Scrape top themes and their top stocks dynamically from Naver Finance.
    Also scrapes per-stock return rates from the theme detail page,
    eliminating the need for yfinance bulk downloads for ranking.

    Returns: (themes_dict, names_dict, theme_returns_map)
      - themes_dict:       {ThemeName: [ticker, ...]}
      - names_dict:        {ticker: name}
      - theme_returns_map: {ThemeName: {ticker: return_pct}}
    """
    import requests
    from bs4 import BeautifulSoup
    import concurrent.futures

    url = 'https://finance.naver.com/sise/theme.naver'
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')

        links = soup.select('a[href^="/sise/sise_group_detail.naver?type=theme"]')
        themes = {}
        names = {}
        theme_returns_map = {}

        # Limit to top 30 themes for performance
        theme_links = links[:30]

        def fetch_theme_detail(a):
            theme_name = a.text.strip()
            if not theme_name:
                return None

            detail_url = 'https://finance.naver.com' + a['href']
            detail_res = requests.get(detail_url, headers=headers)
            detail_res.encoding = 'euc-kr'
            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')

            rows = detail_soup.select('tr')
            tickers_list = []
            local_names = {}
            local_returns = {}

            for row in rows:
                link_tag = row.select_one('div.name_area a[href^="/item/main.naver?code="]')
                if not link_tag:
                    continue
                ticker = link_tag['href'].split('code=')[1]
                name = link_tag.text.strip()

                # The 3rd td.number contains the rate: <span class="tah p11 red01">+18.69%</span>
                # We find all td.number spans and look for the one with '%'
                rate = None
                td_numbers = row.select('td.number')
                for td in td_numbers:
                    span = td.select_one('span.tah')
                    if span and '%' in span.text:
                        try:
                            rate = float(
                                span.text.strip()
                                .replace('%', '').replace(',', '').replace('+', '')
                            )
                        except ValueError:
                            rate = None
                        break

                if ticker not in tickers_list:
                    tickers_list.append(ticker)
                    local_names[ticker] = name
                    if rate is not None:
                        local_returns[ticker] = rate
                    if len(tickers_list) >= 10:  # Top 10 stocks per theme
                        break

            return theme_name, tickers_list, local_names, local_returns

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch_theme_detail, theme_links))

        for result in results:
            if result:
                t_name, t_tickers, l_names, l_returns = result
                if t_tickers:
                    themes[t_name] = t_tickers
                    names.update(l_names)
                    theme_returns_map[t_name] = l_returns

        return themes, names, theme_returns_map

    except Exception as e:
        print(f"[get_krx_themes] Error: {e}")
        return (
            {
                "반도체(에러 폴백)": ["005930", "000660"],
                "이차전지(에러 폴백)": ["373220", "006400"]
            },
            {
                "005930": "삼성전자", "000660": "SK하이닉스",
                "373220": "LG에너지솔루션", "006400": "삼성SDI"
            },
            {}
        )


@ttl_cache(maxsize=50, ttl=1800)
def get_theme_returns_historical(start_date: str, end_date: str):
    """
    Vectorized theme return calculation.
    Uses 2 bulk yfinance downloads (.KS + .KQ) instead of 200+ sequential FDR calls.
    Falls back to FDR in parallel for any still-missing tickers.
    Theme averages computed via pandas groupby (vectorized).
    """
    themes, names, _ = get_krx_themes()
    
    # Filter only 6-digit tickers
    unique_tickers = list({t for tlist in themes.values() for t in tlist if isinstance(t, str) and t.isdigit() and len(t) == 6})

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    return_dict: dict = {}

    from core.cache import get_cached_ohlcv, is_cache_ready
    
    if is_cache_ready():
        # FAST PATH: Use global memory cache
        for ticker in unique_tickers:
            df_t = get_cached_ohlcv(ticker)
            if df_t is not None and not df_t.empty:
                try:
                    df_filled = df_t.ffill().bfill()
                    open_row = df_filled.loc[df_filled.index <= start_dt]
                    close_row = df_filled.loc[df_filled.index <= end_dt]
                    if not open_row.empty and not close_row.empty:
                        open_p = open_row['Close'].iloc[-1]
                        close_p = close_row['Close'].iloc[-1]
                        if pd.notna(open_p) and pd.notna(close_p) and open_p != 0:
                            return_dict[ticker] = round(((close_p - open_p) / open_p) * 100, 2)
                except Exception as e:
                    pass
    else:
        # SLOW PATH / FALLBACK: Fallback to pykrx or yfinance if cache not ready yet
        # Since this happens only during the first 10-20 seconds of server startup,
        # we can just use the existing logic but with `show_errors=False`.
        start_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_str   = (datetime.datetime.strptime(end_date, "%Y%m%d")
                     + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        def _extract_returns(df_bulk, tickers, suffix):
            """Extract open→close returns from a multi-ticker yfinance DataFrame."""
            if df_bulk is None or df_bulk.empty:
                return
            cols = df_bulk.columns
            for ticker in tickers:
                sym = f"{ticker}{suffix}"
                try:
                    if isinstance(cols, pd.MultiIndex):
                        if sym not in cols.get_level_values(0):
                            continue
                        df_t = df_bulk[sym].dropna(how='all')
                    else:
                        df_t = df_bulk.dropna(how='all')
                    close = df_t['Close'].dropna()
                    if len(close) < 2:
                        continue
                    open_p = df_t['Open'].dropna().iloc[0]
                    close_p = close.iloc[-1]
                    if pd.notna(open_p) and open_p != 0:
                        return_dict[ticker] = round(((close_p - open_p) / open_p) * 100, 2)
                except Exception:
                    pass

        # ── 1. Bulk .KS download ──────────────────────────────────────────
        import warnings
        try:
            ks_list = [f"{t}.KS" for t in unique_tickers]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df_ks = yf.download(ks_list, start=start_str, end=end_str,
                                    progress=False, auto_adjust=True,
                                    group_by='ticker', threads=True)
            _extract_returns(df_ks, unique_tickers, '.KS')
            print(f"[historical] .KS bulk: {len(return_dict)} returns")
        except Exception as e:
            print(f"[historical] .KS bulk failed: {e}")

        # ── 2. Bulk .KQ for tickers not found ────────────────────────────
        missing = [t for t in unique_tickers if t not in return_dict]
        if missing:
            try:
                kq_list = [f"{t}.KQ" for t in missing]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    df_kq = yf.download(kq_list, start=start_str, end=end_str,
                                        progress=False, auto_adjust=True,
                                        group_by='ticker', threads=True)
                _extract_returns(df_kq, missing, '.KQ')
                print(f"[historical] .KQ bulk: {len(return_dict)} total returns")
            except Exception as e:
                print(f"[historical] .KQ bulk failed: {e}")

        # ── 3. FDR fallback for any still-missing tickers ─────────────────
        still_missing = [t for t in unique_tickers if t not in return_dict]
        if still_missing:
            import FinanceDataReader as fdr
            import concurrent.futures
            def _fdr_fetch(ticker):
                try:
                    df = fdr.DataReader(ticker, start=start_str, end=end_str)
                    if df is None or df.empty or len(df) < 2:
                        return ticker, None
                    df.columns = [str(c).strip().capitalize() for c in df.columns]
                    op = df['Open'].iloc[0]
                    cl = df['Close'].iloc[-1]
                    if pd.notna(op) and pd.notna(cl) and op != 0:
                        return ticker, round(((cl - op) / op) * 100, 2)
                except Exception:
                    pass
                return ticker, None
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                for t, r in ex.map(_fdr_fetch, still_missing):
                    if r is not None:
                        return_dict[t] = r
            print(f"[historical] FDR fallback: {len(return_dict)} total returns")

    # ── 4. Vectorized theme averages via pandas groupby ───────────────
    rows = [{'Theme': tn, 'Ticker': t} for tn, tl in themes.items() for t in tl]
    df_map = pd.DataFrame(rows)
    df_map['Return'] = df_map['Ticker'].map(return_dict)
    df_map['Name']   = df_map['Ticker'].map(names)

    # 1. 주가가 없는(NaN) 종목 버리기 (과감히 버림)
    valid_df = df_map.dropna(subset=['Return']).copy()

    # 2. 테마에 유효한 종목이 단 1개라도 있다면 평균 계산
    stats = (valid_df.groupby('Theme')['Return']
               .mean()
               .round(2)
               .reset_index()
               .rename(columns={'Return': 'Avg Return (%)'}))

    # 3. 테마 목록에도 유효한 종목들만 포함시킴
    def _build_ticker_list(g):
        items = []
        for r in g.itertuples():
            items.append({
                'ticker':      r.Ticker,
                'name':        r.Name if pd.notna(r.Name) else r.Ticker,
                'return_rate': round(r.Return, 2)
            })
        items.sort(key=lambda x: -(x['return_rate'] or 0))
        return items

    if not valid_df.empty:
        ticker_lists = valid_df.groupby('Theme').apply(_build_ticker_list).to_dict()
        stats['Tickers'] = stats['Theme'].map(ticker_lists)
        stats['Num Stocks'] = stats['Tickers'].apply(len)
    else:
        stats['Tickers'] = []
        stats['Num Stocks'] = 0

    stats = stats.sort_values('Avg Return (%)', ascending=False).reset_index(drop=True)
    stats.insert(0, 'Rank', range(1, len(stats) + 1))
    return stats


@ttl_cache(maxsize=100, ttl=3600*24)
def get_all_theme_stocks():
    """
    Returns a dataframe of all unique stocks present in the current themes.
    Useful for theme-scoped searching.
    """
    themes, names, _ = get_krx_themes()
    stocks = [{'Ticker': t, 'Name': n} for t, n in names.items()]
    df = pd.DataFrame(stocks)
    if not df.empty:
        df = df.drop_duplicates(subset='Ticker').sort_values(by='Name').reset_index(drop=True)
    return df


@ttl_cache(maxsize=100, ttl=3600)
def get_returns_for_period(start_date: str, end_date: str, market="ALL"):
    """
    Get stock returns for the entire market between start_date and end_date.
    start_date, end_date format: YYYYMMDD
    Returns a DataFrame with columns: Ticker, Return.
    """
    try:
        df = stock.get_market_price_change_by_ticker(start_date, end_date, market=market)
        df = df.reset_index()
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
    except Exception as e:
        print(f"[get_returns_for_period] pykrx error: {e}")
        return pd.DataFrame()


@ttl_cache(maxsize=100, ttl=3600)
def get_market_cap(date: str):
    """Get market cap for all stocks on a specific date."""
    try:
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
    except Exception as e:
        print(f"[get_market_cap] pykrx error: {e}")
        return pd.DataFrame()


@ttl_cache(maxsize=500, ttl=3600)
def get_stock_ohlcv(ticker: str, start_date: str, end_date: str):
    """
    Get OHLCV data for a specific Korean stock.
    Primary: FinanceDataReader (handles 6-digit KRX code natively).
    Fallback: yfinance with .KS / .KQ suffix detection.
    Returns a DataFrame with columns: Open, High, Low, Close, Volume.
    Index is DatetimeIndex (date only, no time/tz).
    """
    start_dt_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_dt_obj = datetime.datetime.strptime(end_date, "%Y%m%d") + datetime.timedelta(days=1)
    end_dt_str = end_dt_obj.strftime("%Y-%m-%d")

    # ── 1. FinanceDataReader (preferred: no suffix needed) ─────────
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, start=start_dt_str, end=end_dt_str)
        if df is not None and not df.empty:
            # Normalize column names (FDR uses title-case)
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            # Keep only standard OHLCV columns
            needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
            df = df[needed]
            # Drop rows where Close is missing
            df = df.dropna(subset=['Close'])
            # Strip time/tz from index → pure date
            df.index = pd.to_datetime(df.index).normalize().tz_localize(None)
            if not df.empty:
                print(f"[get_stock_ohlcv] FDR OK {ticker}: {len(df)} rows")
                return df
    except Exception as e:
        print(f"[get_stock_ohlcv] FDR failed for {ticker}: {e}")

    # ── 2. yfinance fallback (.KS then .KQ) ───────────────────────
    import warnings
    for suffix in ('.KS', '.KQ'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = yf.download(
                    f"{ticker}{suffix}", start=start_dt_str, end=end_dt_str,
                    progress=False, show_errors=False, threads=False, auto_adjust=True
                )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                df.columns = [str(c).strip().capitalize() for c in df.columns]
                needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
                df = df[needed]
                df = df.dropna(subset=['Close'])
                df.index = pd.to_datetime(df.index).normalize().tz_localize(None)
                if not df.empty:
                    print(f"[get_stock_ohlcv] yfinance OK {ticker}{suffix}: {len(df)} rows")
                    return df
        except Exception as e:
            print(f"[get_stock_ohlcv] yfinance {suffix} failed for {ticker}: {e}")

    print(f"[get_stock_ohlcv] ALL sources failed for {ticker}")
    return pd.DataFrame()


@ttl_cache(maxsize=100, ttl=3600)
def get_macro_data(start_date: str, end_date: str):
    """
    Get Macro data using yfinance.
    USDKRW=X, CL=F (WTI), GC=F (Gold)
    """
    start_dt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_dt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

    tickers = ["USDKRW=X", "CL=F", "GC=F"]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = yf.download(tickers, start=start_dt, end=end_dt, progress=False, show_errors=False)['Close']
    if not data.empty:
        data.columns = ['WTI', 'Gold', 'USD/KRW']
    return data


@ttl_cache(maxsize=100, ttl=3600*24)
def get_market_cap_yf(ticker: str):
    """
    Fetch market cap using yfinance as pykrx's endpoint is currently unstable.
    """
    try:
        t = yf.Ticker(f"{ticker}.KS")
        mcap = t.info.get('marketCap')
        if mcap:
            return mcap
        t = yf.Ticker(f"{ticker}.KQ")
        mcap = t.info.get('marketCap')
        if mcap:
            return mcap
    except Exception:
        pass
    return 0
