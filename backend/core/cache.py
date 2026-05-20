import yfinance as yf
import pandas as pd
import datetime
import warnings
import threading
import logging

# Set yfinance logger to ERROR to prevent spam
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Global dictionary to hold 1-year OHLCV data for all tickers
# Format: { '005930': DataFrame(Open, High, Low, Close, Volume) }
GLOBAL_OHLCV_CACHE = {}
_CACHE_READY = False
_CACHE_LOCK = threading.Lock()

def init_global_ohlcv_cache(unique_tickers=None):
    """
    Downloads 1-year OHLCV data for all given tickers in the background
    and stores it in GLOBAL_OHLCV_CACHE.
    """
    global GLOBAL_OHLCV_CACHE, _CACHE_READY
    
    if not unique_tickers:
        # If no specific tickers provided, fallback to getting all themes' tickers
        # To avoid circular import, we import locally
        from core.data_fetcher import get_krx_themes
        themes, _, _ = get_krx_themes()
        unique_tickers = list({t for tlist in themes.values() for t in tlist})
    
    # Filter strictly 6-digit tickers
    valid_tickers = [t for t in unique_tickers if isinstance(t, str) and t.isdigit() and len(t) == 6]
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = (end_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[cache] Fetching 1-year OHLCV for {len(valid_tickers)} valid tickers in background...")

    temp_cache = {}

    def _extract_returns(df_bulk, tickers, suffix):
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
                
                # Keep standard OHLCV if available
                if not df_t.empty and 'Close' in df_t.columns and 'Open' in df_t.columns:
                    # tz-naive index
                    df_t.index = pd.to_datetime(df_t.index).normalize().tz_localize(None)
                    temp_cache[ticker] = df_t
            except Exception:
                pass

    # 1. Bulk .KS
    try:
        ks_list = [f"{t}.KS" for t in valid_tickers]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df_ks = yf.download(ks_list, start=start_str, end=end_str,
                                progress=False, auto_adjust=True,
                                group_by='ticker', threads=True)
        _extract_returns(df_ks, valid_tickers, '.KS')
    except Exception as e:
        print(f"[cache] .KS bulk failed: {e}")

    # 2. Bulk .KQ for missing
    missing = [t for t in valid_tickers if t not in temp_cache]
    if missing:
        try:
            kq_list = [f"{t}.KQ" for t in missing]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df_kq = yf.download(kq_list, start=start_str, end=end_str,
                                    progress=False, auto_adjust=True,
                                    group_by='ticker', threads=True)
            _extract_returns(df_kq, missing, '.KQ')
        except Exception as e:
            print(f"[cache] .KQ bulk failed: {e}")

    with _CACHE_LOCK:
        GLOBAL_OHLCV_CACHE.update(temp_cache)
        _CACHE_READY = True

    print(f"[cache] 1-year OHLCV cache populated with {len(GLOBAL_OHLCV_CACHE)} stocks.")

def get_cached_ohlcv(ticker: str) -> pd.DataFrame:
    """Return the cached OHLCV dataframe for the ticker, or None if not found."""
    with _CACHE_LOCK:
        return GLOBAL_OHLCV_CACHE.get(ticker)

def is_cache_ready() -> bool:
    with _CACHE_LOCK:
        return _CACHE_READY
