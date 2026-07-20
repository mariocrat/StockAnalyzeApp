import pandas as pd
import yfinance as yf
from cachetools.func import ttl_cache
import datetime
import json
import os
import re
import threading
import time
from pathlib import Path


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
THEME_RETURN_CACHE_VERSION = "v4"
CORPORATE_ACTION_FACTORS = (2, 3, 4, 5, 10, 20, 50, 100)


def _cache_dir() -> Path:
    configured = os.environ.get("ALPHAMATE_CACHE_DIR", "").strip()
    path = Path(configured) if configured else DEFAULT_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _theme_fetch_workers(ticker_count: int) -> int:
    try:
        configured = int(os.environ.get("ALPHAMATE_THEME_FETCH_WORKERS", "8"))
    except ValueError:
        configured = 8
    return min(max(2, configured), 16, max(2, ticker_count))


def _read_json_cache(name: str, ttl_seconds: int):
    path = _cache_dir() / name
    try:
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload == []:
            return None
        return payload
    except Exception:
        return None


def _write_json_cache(name: str, payload):
    path = _cache_dir() / name
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _theme_return_cache_name(start_date: str, end_date: str, period: str = "custom") -> str:
    namespace = re.sub(r"[^a-zA-Z0-9]", "", str(period or "custom")) or "custom"
    return f"theme_returns_{THEME_RETURN_CACHE_VERSION}_{namespace}_{start_date}_{end_date}.json"


def get_cached_theme_returns(start_date: str, end_date: str, period: str = "custom"):
    cache_name = _theme_return_cache_name(start_date, end_date, period)
    cached = _read_json_cache(cache_name, ttl_seconds=3600*24*30)
    if cached:
        return pd.DataFrame(cached)
    return pd.DataFrame()


def get_latest_cached_theme_returns(
    period: str = "",
    min_span_days: int | None = None,
    max_span_days: int | None = None,
):
    candidates = []
    prefix = f"theme_returns_{THEME_RETURN_CACHE_VERSION}_"
    for path in _cache_dir().glob(f"{prefix}*.json"):
        stem = path.stem.replace(prefix, "", 1)
        try:
            namespace, start_text, end_text = stem.rsplit("_", 2)
            if period and namespace.lower() != str(period).lower():
                continue
            start_dt = datetime.datetime.strptime(start_text, "%Y%m%d").date()
            end_dt = datetime.datetime.strptime(end_text, "%Y%m%d").date()
        except ValueError:
            continue

        span_days = (end_dt - start_dt).days
        if min_span_days is not None and span_days < min_span_days:
            continue
        if max_span_days is not None and span_days > max_span_days:
            continue
        candidates.append((end_dt, path.stat().st_mtime, path.name))

    for _, _, name in sorted(candidates, reverse=True):
        cached = _read_json_cache(name, ttl_seconds=3600*24*14)
        if cached:
            return pd.DataFrame(cached)
    return pd.DataFrame()


def get_cached_naver_themes():
    cached = _read_json_cache("naver_themes_v3.json", ttl_seconds=3600*24*7)
    if cached:
        return cached["themes"], cached["names"], cached["returns"]
    return None


def _read_covering_close_cache(start_date: str, end_date: str):
    candidates = []
    for path in _cache_dir().glob(f"naver_closes_*_{end_date}.json"):
        stem = path.stem.replace("naver_closes_", "")
        try:
            cache_start, cache_end = stem.split("_", 1)
        except ValueError:
            continue
        if cache_start <= start_date and cache_end == end_date:
            candidates.append((cache_start, path.name))

    for _, name in sorted(candidates):
        cached = _read_json_cache(name, ttl_seconds=3600*24*30)
        if cached:
            return cached
    return None


def _corporate_action_scale(previous_close: float, next_reference_price: float) -> float | None:
    """Return the historical-price scale for a likely split or consolidation."""
    if previous_close <= 0 or next_reference_price <= 0:
        return None
    raw_ratio = next_reference_price / previous_close
    if 0.65 <= raw_ratio <= 1.35:
        return None

    candidates = list(CORPORATE_ACTION_FACTORS)
    scales = candidates if raw_ratio > 1 else [1 / factor for factor in candidates]
    best_scale = min(
        scales,
        key=lambda scale: abs((next_reference_price / (previous_close * scale)) - 1),
    )
    adjusted_ratio = next_reference_price / (previous_close * best_scale)
    return float(best_scale) if 0.65 <= adjusted_ratio <= 1.35 else None


def _adjust_price_rows_for_corporate_actions(rows: list[dict]) -> list[dict]:
    """Normalize older OHLC prices to the latest share basis."""
    adjusted = [dict(row) for row in sorted(rows, key=lambda item: item["date"])]
    price_fields = ("open", "high", "low", "close")
    for index in range(1, len(adjusted)):
        previous_close = float(adjusted[index - 1].get("close") or 0)
        reference_price = float(adjusted[index].get("open") or adjusted[index].get("close") or 0)
        scale = _corporate_action_scale(previous_close, reference_price)
        if scale is None:
            continue
        for older_index in range(index):
            for field in price_fields:
                value = float(adjusted[older_index].get(field) or 0)
                if value > 0:
                    adjusted[older_index][field] = value * scale
    return adjusted


def _clean_price_jumps(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize split/consolidation gaps before return calculations."""
    if df is None or df.empty or 'Close' not in df.columns:
        return pd.DataFrame()

    out = df.copy().sort_index()
    needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in out.columns]
    out = out[needed]
    out = out[pd.to_numeric(out['Close'], errors='coerce') > 0]
    if out.empty:
        return out

    for col in ['Open', 'High', 'Low', 'Close']:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')

    rows = []
    for row_index, row in out.iterrows():
        rows.append({
            "date": pd.Timestamp(row_index).strftime("%Y%m%d"),
            "open": float(row.get("Open") or 0),
            "high": float(row.get("High") or 0),
            "low": float(row.get("Low") or 0),
            "close": float(row.get("Close") or 0),
            "volume": float(row.get("Volume") or 0),
        })
    adjusted_rows = _adjust_price_rows_for_corporate_actions(rows)
    for adjusted, row_index in zip(adjusted_rows, out.index):
        for source, target in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
            if target in out.columns and adjusted[source] > 0:
                out.at[row_index, target] = adjusted[source]
    return out


@ttl_cache(maxsize=1, ttl=3600*24)
def get_yfinance_suffix_map():
    """Map KRX tickers to the yfinance suffix that usually resolves fastest."""
    suffix_map = {}
    try:
        import FinanceDataReader as fdr
        kospi = fdr.StockListing('KOSPI')[['Code']].dropna()
        kosdaq = fdr.StockListing('KOSDAQ')[['Code']].dropna()
        for code in kospi['Code']:
            suffix_map[str(code).zfill(6)] = '.KS'
        for code in kosdaq['Code']:
            suffix_map[str(code).zfill(6)] = '.KQ'
    except Exception:
        pass
    return suffix_map


@ttl_cache(maxsize=1, ttl=3600*24)
def get_naver_market_stock_names():
    cached = _read_json_cache("naver_market_stocks_v2.json", ttl_seconds=3600*24)
    if cached:
        return cached

    import requests
    from bs4 import BeautifulSoup

    headers = {'User-Agent': 'Mozilla/5.0'}
    names = {}

    for sosok in (0, 1):
        first_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
        first_res = requests.get(first_url, headers=headers, timeout=8)
        first_res.encoding = 'euc-kr'
        first_soup = BeautifulSoup(first_res.text, 'html.parser')
        pages = [1]
        for a in first_soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'sise_market_sum.naver' in href and 'page=' in href:
                try:
                    pages.append(int(href.split('page=')[-1].split('&')[0]))
                except ValueError:
                    pass

        for page in range(1, max(pages) + 1):
            if page == 1:
                soup = first_soup
            else:
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers=headers, timeout=8)
                res.encoding = 'euc-kr'
                soup = BeautifulSoup(res.text, 'html.parser')

            for a in soup.find_all('a', href=lambda h: h and h.startswith('/item/main.naver?code=')):
                ticker = a.get('href').split('code=')[1]
                name = a.text.strip()
                if ticker and ticker.isdigit() and len(ticker) == 6 and name:
                    names[ticker] = name

    _write_json_cache("naver_market_stocks_v2.json", names)
    return names


@ttl_cache(maxsize=1, ttl=3600*6)
def get_stock_names(market="ALL"):
    """
    Get mapping of ticker -> stock name for all KRX listed stocks.
    Chain: FinanceDataReader → pykrx → Naver theme names (fallback)
    """
    # 1. Try FinanceDataReader first. pykrx can print KRX login warnings in
    # this environment even when we only need public ticker names.
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

    # 2. Try Naver market cap lists, which do not require KRX credentials.
    try:
        names = get_naver_market_stock_names()
        if names:
            print(f"[get_stock_names] Naver market OK: {len(names)} stocks")
            return names
    except Exception as e:
        print(f"[get_stock_names] Naver market failed ({e})")

    # 3. Try pykrx
    try:
        from pykrx import stock
        today = datetime.datetime.today().strftime("%Y%m%d")
        tickers = stock.get_market_ticker_list(today, market=market)
        if not tickers:
            raise ValueError("pykrx returned empty ticker list")
        names = {ticker: stock.get_market_ticker_name(ticker) for ticker in tickers}
        print(f"[get_stock_names] pykrx OK: {len(names)} stocks")
        return names
    except Exception as e:
        print(f"[get_stock_names] pykrx failed ({e})")

    # 4. Last resort: Naver theme names
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

    cached = _read_json_cache("naver_themes_v3.json", ttl_seconds=3600*24*7)
    if cached:
        return cached["themes"], cached["names"], cached["returns"]

    url = 'https://finance.naver.com/sise/theme.naver'
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        first_res = requests.get(url, headers=headers, timeout=8)
        first_res.encoding = 'euc-kr'
        first_soup = BeautifulSoup(first_res.text, 'html.parser')
        page_numbers = [1]
        for href in [a.get('href', '') for a in first_soup.find_all('a')]:
            if 'theme.naver' in href and 'page=' in href:
                try:
                    page_numbers.append(int(href.split('page=')[-1].split('&')[0]))
                except ValueError:
                    pass
        last_page = max(page_numbers)

        links = []
        seen_hrefs = set()
        for page in range(1, last_page + 1):
            page_url = f"{url}?&page={page}"
            page_res = first_res if page == 1 else requests.get(page_url, headers=headers, timeout=8)
            page_res.encoding = 'euc-kr'
            page_soup = first_soup if page == 1 else BeautifulSoup(page_res.text, 'html.parser')
            for a in page_soup.find_all('a', href=lambda h: h and h.startswith('/sise/sise_group_detail.naver?type=theme')):
                href = a.get('href')
                if href in seen_hrefs:
                    continue
                if not a.text.strip():
                    continue
                seen_hrefs.add(href)
                links.append(a)

        themes = {}
        names = {}
        theme_returns_map = {}

        theme_links = links

        def fetch_theme_detail(a):
            theme_name = a.text.strip()
            if not theme_name:
                return None

            detail_url = 'https://finance.naver.com' + a['href']
            detail_res = requests.get(detail_url, headers=headers, timeout=8)
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
            return theme_name, tickers_list, local_names, local_returns

        with concurrent.futures.ThreadPoolExecutor(max_workers=_theme_fetch_workers(len(theme_links))) as executor:
            results = list(executor.map(fetch_theme_detail, theme_links))

        for result in results:
            if result:
                t_name, t_tickers, l_names, l_returns = result
                if t_tickers:
                    themes[t_name] = t_tickers
                    names.update(l_names)
                    theme_returns_map[t_name] = l_returns

        payload = {"themes": themes, "names": names, "returns": theme_returns_map}
        _write_json_cache("naver_themes_v3.json", payload)
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


def get_theme_returns_historical(start_date: str, end_date: str, period: str = "custom"):
    """
    Calculate theme returns from Naver chart close prices.
    The exact start/end cache is reused, but stale caches for other dates are
    not treated as current values.
    """
    cache_name = _theme_return_cache_name(start_date, end_date, period)
    cached = _read_json_cache(cache_name, ttl_seconds=3600*24*30)
    if cached:
        return pd.DataFrame(cached)

    calculation_key = period if period in {"1D", "1W", "1M", "1Y"} else "requested"
    results = _calculate_theme_return_ranges({calculation_key: (start_date, end_date)})
    stats = results.get(calculation_key, pd.DataFrame())
    if not stats.empty:
        _write_json_cache(cache_name, stats.to_dict(orient="records"))
    return stats


def warm_theme_return_caches(period_ranges: dict[str, tuple[str, str]]) -> dict[str, int]:
    """Build all missing standard-period caches with one bounded market-data pass."""
    missing = {
        period: date_range
        for period, date_range in period_ranges.items()
        if get_cached_theme_returns(*date_range, period=period).empty
    }
    if not missing:
        return {
            period: len(get_cached_theme_returns(*date_range, period=period))
            for period, date_range in period_ranges.items()
        }

    calculated = _calculate_theme_return_ranges(missing)
    counts = {}
    for period, date_range in period_ranges.items():
        stats = calculated.get(period)
        if stats is not None and not stats.empty:
            cache_name = _theme_return_cache_name(date_range[0], date_range[1], period)
            _write_json_cache(cache_name, stats.to_dict(orient="records"))
        cached = get_cached_theme_returns(*date_range, period=period)
        counts[period] = int(len(cached))
    return counts


def _calculate_theme_return_ranges(period_ranges: dict[str, tuple[str, str]]) -> dict[str, pd.DataFrame]:
    """Fetch closes once and retain only per-period returns, not every daily row."""
    if not period_ranges:
        return {}

    import concurrent.futures
    import requests

    themes, names, _ = get_krx_themes()
    unique_tickers = sorted({
        ticker
        for ticker_list in themes.values()
        for ticker in ticker_list
        if isinstance(ticker, str) and ticker.isdigit() and len(ticker) == 6
    })
    earliest_start = min(start for start, _ in period_ranges.values())
    latest_end = max(end for _, end in period_ranges.values())
    row_re = re.compile(
        r'\["(\d{8})"\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)'
        r'\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)'
    )
    headers = {'User-Agent': 'Mozilla/5.0'}
    request_state = threading.local()

    def _session() -> requests.Session:
        session = getattr(request_state, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(headers)
            request_state.session = session
        return session

    def _fetch_closes(ticker: str):
        url = (
            "https://api.finance.naver.com/siseJson.naver"
            f"?symbol={ticker}&requestType=1&startTime={earliest_start}"
            f"&endTime={latest_end}&timeframe=day"
        )
        try:
            # A session per worker keeps the Naver HTTPS connection alive.
            # Render otherwise pays a TLS handshake for every ticker.
            response = _session().get(url, timeout=8)
            if response.status_code != 200:
                return ticker, []
            rows = []
            for date_text, open_text, high_text, low_text, close_text, volume_text in row_re.findall(response.text):
                try:
                    row = {
                        "date": date_text,
                        "open": float(open_text),
                        "high": float(high_text),
                        "low": float(low_text),
                        "close": float(close_text),
                        "volume": float(volume_text),
                    }
                except ValueError:
                    continue
                if row["close"] > 0:
                    rows.append(row)
            return ticker, _adjust_price_rows_for_corporate_actions(rows)
        except Exception:
            return ticker, []

    returns_by_period = {period: {} for period in period_ranges}
    effective_dates = {
        period: {"starts": [], "ends": []}
        for period in period_ranges
    }
    max_workers = _theme_fetch_workers(len(unique_tickers))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch_closes, ticker) for ticker in unique_tickers]
        for future in concurrent.futures.as_completed(futures):
            ticker, close_rows = future.result()
            if len(close_rows) < 2:
                continue
            for period, (start_date, end_date) in period_ranges.items():
                period_rows = [row for row in close_rows if start_date <= row["date"] <= end_date]
                if len(period_rows) < 2:
                    continue
                if period == "1D":
                    period_rows = period_rows[-2:]
                start_price = period_rows[0]["close"]
                end_price = period_rows[-1]["close"]
                if start_price > 0:
                    returns_by_period[period][ticker] = round(
                        ((end_price - start_price) / start_price) * 100,
                        2,
                    )
                    effective_dates[period]["starts"].append(period_rows[0]["date"])
                    effective_dates[period]["ends"].append(period_rows[-1]["date"])

    return {
        period: _build_theme_return_stats(
            themes=themes,
            names=names,
            ticker_returns=ticker_returns,
            start_date=(
                min(effective_dates[period]["starts"])
                if effective_dates[period]["starts"]
                else period_ranges[period][0]
            ),
            end_date=(
                max(effective_dates[period]["ends"])
                if effective_dates[period]["ends"]
                else period_ranges[period][1]
            ),
        )
        for period, ticker_returns in returns_by_period.items()
    }


def _build_theme_return_stats(
    *,
    themes: dict,
    names: dict,
    ticker_returns: dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    rows = [{'Theme': theme, 'Ticker': ticker} for theme, tickers in themes.items() for ticker in tickers]
    df_map = pd.DataFrame(rows)
    if df_map.empty:
        return pd.DataFrame()
    df_map['Return'] = df_map['Ticker'].map(ticker_returns)
    df_map['Name'] = df_map['Ticker'].map(names)
    valid_df = df_map.dropna(subset=['Return']).copy()
    if valid_df.empty:
        return pd.DataFrame()

    stats = (valid_df.groupby('Theme')['Return']
             .mean()
             .round(2)
             .reset_index()
             .rename(columns={'Return': 'Avg Return (%)'}))

    def _build_ticker_list(group):
        items = [
            {
                'ticker': row.Ticker,
                'name': row.Name if pd.notna(row.Name) else row.Ticker,
                'return_rate': round(row.Return, 2),
            }
            for row in group.itertuples()
        ]
        items.sort(key=lambda item: -(item['return_rate'] or 0))
        return items

    ticker_lists = {
        theme: _build_ticker_list(group)
        for theme, group in valid_df.groupby('Theme')
    }
    stats['Tickers'] = stats['Theme'].map(ticker_lists)
    stats['Num Stocks'] = stats['Tickers'].apply(len)
    stats = stats.sort_values('Avg Return (%)', ascending=False).reset_index(drop=True)
    stats.insert(0, 'Rank', range(1, len(stats) + 1))
    stats['Start Date'] = start_date
    stats['End Date'] = end_date
    stats['Data Source'] = 'Naver chart close'
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
        from pykrx import stock
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
        from pykrx import stock
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
