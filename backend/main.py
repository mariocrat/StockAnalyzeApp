from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
from core.journal import add_trade, list_trades, count_trades, delete_trade, clear_trades, build_review, normalize_trade
from core.ai_review import build_ai_review
from core.ai_review_v2 import build_basic_ai_review, build_advanced_ai_review
from core.journal_chart import build_journal_charts
from core.review_history import add_review_history, list_review_history, get_review_history, delete_review_history
from core.access_control import (
    apply_dev_purchase,
    apply_google_play_purchase,
    handle_google_play_rtdn,
    get_product_catalog,
    get_user_entitlements,
    record_admob_ssv_reward,
    verify_ai_review_access,
)
from core.account_store import login_dev_provider, authenticate_session, revoke_session, update_journal_storage_setting, record_privacy_consent, get_privacy_consent_version, delete_user_account_data
from core.oauth_login import get_oauth_config_status, login_oauth_code, login_oauth_provider
from core.readiness import get_app_readiness
from core.rate_limit import InMemoryRateLimiter
from core.env import env_value
from core.event_log import list_events, purge_configured_retention, purge_events_older_than, record_api_exception, record_api_failure, record_event, summarize_events

from contextlib import asynccontextmanager
import hmac
import threading
import logging
from fastapi import HTTPException

# Suppress yfinance spam at startup
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_theme_refresh_lock = threading.Lock()
_theme_refresh_jobs = set()
_client_event_rate_limiter = InMemoryRateLimiter()
_admin_rate_limiter = InMemoryRateLimiter()


class JournalTradeIn(BaseModel):
    trade_date: str
    ticker: str = ""
    name: str
    side: str
    price: float
    quantity: float
    fee: float = 0
    tax: float = 0
    memo: str = ""
    source: str = "manual"


class JournalBatchIn(BaseModel):
    trades: list[JournalTradeIn]


class JournalAiReviewIn(JournalBatchIn):
    ad_reward_token: str = ""
    entitlement_token: str = ""
    privacy_consent: bool = False
    review_type: str = "basic"
    target_trade_id: Optional[int] = None


class JournalDevPurchaseIn(BaseModel):
    product_id: str
    entitlement_token: str = ""


class JournalGooglePlayPurchaseIn(BaseModel):
    product_id: str
    purchase_token: str
    package_name: str = ""


class GooglePlayRtdnIn(BaseModel):
    message: dict
    subscription: str = ""


class AuthDevLoginIn(BaseModel):
    provider: str
    provider_user_id: str
    display_name: str = ""


class AuthProviderTokenIn(BaseModel):
    access_token: str


class AuthProviderCodeIn(BaseModel):
    code: str
    redirect_uri: str = ""
    state: str = ""


class JournalStorageSettingIn(BaseModel):
    enabled: bool


class ClientEventIn(BaseModel):
    event_type: str = "client_event"
    level: str = "warning"
    message: str = ""
    path: str = ""
    details: dict = {}


def _journal_batch_payload(batch: JournalBatchIn) -> list[dict]:
    return [normalize_trade(trade.model_dump()) for trade in batch.trades]


def _optional_session_user(authorization: Optional[str]):
    if not authorization:
        return None
    try:
        return authenticate_session(authorization)
    except HTTPException:
        return None


def _journal_user_id_if_enabled(authorization: Optional[str]) -> str:
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        raise HTTPException(status_code=403, detail="매매 이력 저장을 먼저 켜야 합니다.")
    return user["id"]


def _save_ai_review_history_if_enabled(
    *,
    authorization: Optional[str],
    batch: JournalAiReviewIn,
    trades: list[dict],
    result: dict,
):
    user = _optional_session_user(authorization)
    if not user or not user.get("journal_storage_enabled"):
        return None

    target_trade = None
    if batch.target_trade_id is not None:
        for trade in trades:
            if str(trade.get("id")) == str(batch.target_trade_id):
                target_trade = trade
                break
    if target_trade is None and trades:
        target_trade = trades[-1]

    try:
        chart_data = build_journal_charts(trades)
    except Exception:
        chart_data = {"charts": []}

    item = add_review_history(
        user_id=user["id"],
        review_type=result.get("review_type") or batch.review_type,
        ticker=str((target_trade or {}).get("ticker") or ""),
        name=str((target_trade or {}).get("name") or ""),
        trade_date=str((target_trade or {}).get("trade_date") or ""),
        target_trade_id=batch.target_trade_id,
        trade_snapshot=target_trade or {},
        recent_trades_snapshot=trades[-10:],
        chart_snapshot={
            "charts": chart_data.get("charts") or [],
            "chart_contexts": result.get("chart_contexts") or [],
            "chart_reviews": result.get("chart_reviews") or [],
        },
        ai_review=result,
        access_snapshot=result.get("access") or {},
        model=str(result.get("model") or ""),
        source=str(result.get("source") or ""),
    )
    return item["id"] if item else None


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


def _period_date_range(period: str):
    base_date = _last_completed_market_date()
    period_days = {"1D": 1, "1W": 7, "1M": 30, "1Y": 365}
    if period not in period_days:
        return None, None
    if period == "1D":
        start_dt = _previous_weekday(base_date)
    else:
        start_dt = base_date - datetime.timedelta(days=period_days[period])
    return start_dt.strftime("%Y%m%d"), base_date.strftime("%Y%m%d")


def _fallback_span(period: str):
    return {
        "1D": (None, 3),
        "1W": (4, 10),
        "1M": (20, 45),
        "1Y": (300, 420),
    }.get(period)


def _schedule_theme_cache_refresh(start_date: str, end_date: str):
    key = (start_date, end_date)
    with _theme_refresh_lock:
        if key in _theme_refresh_jobs:
            return
        _theme_refresh_jobs.add(key)

    def _worker():
        try:
            get_theme_returns_historical(start_date, end_date)
        except Exception as e:
            print(f"[cache] Theme refresh failed {start_date}-{end_date}: {e}")
        finally:
            with _theme_refresh_lock:
                _theme_refresh_jobs.discard(key)

    threading.Thread(target=_worker, daemon=True).start()

def _warm_cache():
    """Pre-warm theme caches in the background."""
    try:
        cleanup_result = purge_configured_retention()
        if not cleanup_result.get("skipped"):
            print(f"[startup] Operational event log cleanup: {cleanup_result}")

        base_date = _last_completed_market_date()
        print("[startup] Warming theme caches...")

        try:
            _get_stock_search_index()
        except Exception as e:
            print(f"[startup] Search index warm-up failed (non-fatal): {e}")

        for days in (365, 30, 7, 1):
            start = (base_date - datetime.timedelta(days=days)).strftime('%Y%m%d')
            end = base_date.strftime('%Y%m%d')
            get_theme_returns_historical(start, end)
        print("[startup] Theme cache ready.")
    except Exception as e:
        print(f"[startup] Cache warm-up failed (non-fatal): {e}")

@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_warm_cache, daemon=True).start()
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


def _request_user_id_for_log(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if not authorization:
        return ""
    try:
        user = authenticate_session(authorization)
        return str(user.get("id") or "")
    except Exception:
        return ""


def _request_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _client_event_rate_limit() -> int:
    try:
        return int(env_value("ALPHAMATE_CLIENT_EVENT_RATE_LIMIT_PER_MINUTE") or 60)
    except ValueError:
        return 60


def _admin_rate_limit() -> int:
    try:
        return int(env_value("ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE") or 30)
    except ValueError:
        return 30


def _enforce_admin_rate_limit(client_key: str) -> bool:
    rate_limit = _admin_rate_limiter.check(
        client_key or "unknown",
        limit=_admin_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many admin requests. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )
    return True


@app.middleware("http")
async def log_failed_api_requests(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)

    user_id = _request_user_id_for_log(request)
    try:
        response = await call_next(request)
    except Exception as exc:
        record_api_exception(
            method=request.method,
            path=path,
            exc=exc,
            user_id=user_id,
        )
        raise

    if response.status_code >= 400:
        record_api_failure(
            method=request.method,
            path=path,
            status_code=response.status_code,
            user_id=user_id,
            message=f"HTTP {response.status_code}",
            details={
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
    return response


def _clean_client_event_text(value: str, fallback: str, *, limit: int = 120) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in {"_", "-", ".", "/", ":"}).strip()
    return (text or fallback)[:limit]


def _bearer_value(authorization: Optional[str]) -> str:
    text = str(authorization or "").strip()
    if text.lower().startswith("bearer "):
        return text[7:].strip()
    return text


def _require_admin_token(authorization: Optional[str]) -> bool:
    configured = env_value("ALPHAMATE_ADMIN_TOKEN")
    if not configured:
        raise HTTPException(status_code=503, detail="Admin event log access is not configured.")
    token = _bearer_value(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Admin token is required.")
    if not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=403, detail="Admin token is invalid.")
    return True


@app.get("/api/admin/operational-events")
def get_admin_operational_events(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    limit: int = 100,
    level: str = "",
    event_type: str = "",
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    events = list_events(limit=limit, level=level, event_type=event_type)
    return {"events": events, "count": len(events)}


@app.get("/api/admin/operational-events/summary")
def get_admin_operational_event_summary(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    limit: int = 500,
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    return summarize_events(limit=limit)


@app.delete("/api/admin/operational-events/retention")
def delete_old_admin_operational_events(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    retention_days: int = 90,
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    try:
        return purge_events_older_than(retention_days=retention_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/client-events")
def create_client_event(
    event: ClientEventIn,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    rate_limit = _client_event_rate_limiter.check(
        _request_client_key(request),
        limit=_client_event_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many client event reports. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )

    user = _optional_session_user(authorization)
    level = _clean_client_event_text(event.level, "warning", limit=20)
    if level not in {"debug", "info", "warning", "error"}:
        level = "warning"
    record_event(
        level=level,
        event_type=_clean_client_event_text(event.event_type, "client_event"),
        method="CLIENT",
        path=_clean_client_event_text(event.path, "/client", limit=200),
        status_code=0,
        user_id=str(user.get("id") or "") if user else "",
        message=str(event.message or "")[:500],
        details=event.details if isinstance(event.details, dict) else {},
    )
    return {"ok": True}


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
    if period in {"1D", "1W", "1M", "1Y"}:
        start_date, end_date = _period_date_range(period)

    if start_date and end_date:
        if period in {"1D", "1W", "1M", "1Y"}:
            df = get_cached_theme_returns(start_date, end_date)
            if df.empty:
                span = _fallback_span(period)
                fallback = pd.DataFrame()
                if span:
                    min_span, max_span = span
                    fallback = get_latest_cached_theme_returns(
                        min_span_days=min_span,
                        max_span_days=max_span,
                    )
                if not fallback.empty:
                    _schedule_theme_cache_refresh(start_date, end_date)
                    return fallback.to_dict(orient="records")
                df = get_theme_returns_historical(start_date, end_date)
        else:
            df = get_theme_returns_historical(start_date, end_date)
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

@ttl_cache(maxsize=1, ttl=3600)
def _get_stock_search_index():
    names_dict = get_stock_names("ALL")
    themes, _, _ = get_krx_themes()

    ticker_themes = {}
    for theme_name, tickers in themes.items():
        for ticker in tickers:
            ticker_themes.setdefault(ticker, []).append(theme_name)

    index = []
    for ticker, name in names_dict.items():
        name_text = str(name)
        index.append({
            "Ticker": ticker,
            "Name": name_text,
            "Themes": ticker_themes.get(ticker, []),
            "_name_lower": name_text.lower(),
            "_chosung": get_chosung(name_text).lower(),
            "_ticker_lower": ticker.lower(),
        })
    return index


@app.get("/api/search")
@ttl_cache(maxsize=1000, ttl=3600)
def search_stocks(q: str):
    query = q.strip().lower()
    if not query:
        return []

    matches = []
    for item in _get_stock_search_index():
        if (
            query in item["_ticker_lower"]
            or query in item["_name_lower"]
            or query in item["_chosung"]
        ):
            rank = 3
            if query == item["_ticker_lower"] or query == item["_name_lower"]:
                rank = 0
            elif item["_ticker_lower"].startswith(query) or item["_name_lower"].startswith(query):
                rank = 1
            elif item["_chosung"].startswith(query):
                rank = 2
            matches.append((rank, item))

    def sort_key(pair):
        rank, item = pair
        name = item["Name"]
        starts_with_hangul = bool(name) and '가' <= name[0] <= '힣'
        return (rank, not starts_with_hangul, name, item["Ticker"])

    matches.sort(key=sort_key)
    result = []
    for _, m in matches[:50]:
        result.append({
            "Ticker": m["Ticker"],
            "Name": m["Name"],
            "Themes": m["Themes"]
        })
    return result


@app.post("/api/auth/dev-login")
def post_auth_dev_login(login: AuthDevLoginIn):
    return login_dev_provider(
        provider=login.provider,
        provider_user_id=login.provider_user_id,
        display_name=login.display_name,
    )


@app.post("/api/auth/login/kakao")
def post_auth_login_kakao(login: AuthProviderTokenIn):
    return login_oauth_provider(provider="kakao", access_token=login.access_token)


@app.post("/api/auth/login/naver")
def post_auth_login_naver(login: AuthProviderTokenIn):
    return login_oauth_provider(provider="naver", access_token=login.access_token)


@app.post("/api/auth/login/kakao/code")
def post_auth_login_kakao_code(login: AuthProviderCodeIn):
    return login_oauth_code(
        provider="kakao",
        code=login.code,
        redirect_uri=login.redirect_uri,
        state=login.state,
    )


@app.post("/api/auth/login/naver/code")
def post_auth_login_naver_code(login: AuthProviderCodeIn):
    return login_oauth_code(
        provider="naver",
        code=login.code,
        redirect_uri=login.redirect_uri,
        state=login.state,
    )


@app.get("/api/auth/oauth-config")
def get_auth_oauth_config():
    return get_oauth_config_status()


@app.get("/api/app/readiness")
def get_app_readiness_status():
    return get_app_readiness()


@app.get("/api/me")
def get_me(authorization: Optional[str] = Header(default=None)):
    return authenticate_session(authorization)


@app.patch("/api/me/journal-storage")
def patch_me_journal_storage(
    setting: JournalStorageSettingIn,
    authorization: Optional[str] = Header(default=None),
):
    return update_journal_storage_setting(
        authorization=authorization,
        enabled=setting.enabled,
    )


@app.get("/api/me/data-summary")
def get_me_data_summary(authorization: Optional[str] = Header(default=None)):
    user = authenticate_session(authorization)
    return {
        "journal_storage_enabled": bool(user.get("journal_storage_enabled")),
        "saved_trade_count": count_trades(user_id=user["id"]),
        "connected_providers": [
            identity["provider"] for identity in user.get("identities", [])
        ],
        "delete_scope": "current_user_only",
        "server_keeps_ai_review_history": bool(user.get("journal_storage_enabled")),
        "privacy_consent_current_version": get_privacy_consent_version(),
        "privacy_consent_version": user.get("privacy_consent_version", ""),
        "privacy_consented_at": user.get("privacy_consented_at", ""),
    }


@app.get("/api/me/export-data")
def export_me_data(authorization: Optional[str] = Header(default=None)):
    user = authenticate_session(authorization)
    entitlements = get_user_entitlements(
        authorization=authorization,
        entitlement_token="",
    )
    return {
        "type": "alphamate_user_data_export",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "user": user,
        "saved_trades": list_trades(limit=5000, user_id=user["id"]),
        "entitlements": entitlements,
        "review_history": [
            get_review_history(row["id"], user_id=user["id"])
            for row in list_review_history(user_id=user["id"], limit=5000)
        ],
        "server_keeps_ai_review_history": bool(user.get("journal_storage_enabled")),
    }


@app.delete("/api/me/account-data")
def delete_me_account_data(authorization: Optional[str] = Header(default=None)):
    return delete_user_account_data(authorization)


@app.post("/api/auth/logout")
def post_auth_logout(authorization: Optional[str] = Header(default=None)):
    return revoke_session(authorization)


@app.get("/api/journal/trades")
def get_journal_trades(
    limit: int = 500,
    authorization: Optional[str] = Header(default=None),
):
    user = _optional_session_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            return []
        return list_trades(limit=limit, user_id=user["id"])
    return list_trades(limit=limit)


@app.post("/api/journal/trades")
def create_journal_trade(
    trade: JournalTradeIn,
    authorization: Optional[str] = Header(default=None),
):
    user = _optional_session_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            raise HTTPException(status_code=403, detail="매매 이력 저장을 먼저 켜야 합니다.")
        return add_trade(trade.model_dump(), user_id=user["id"])
    return add_trade(trade.model_dump())


@app.delete("/api/journal/trades/{trade_id}")
def remove_journal_trade(
    trade_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = _optional_session_user(authorization)
    if user:
        deleted_count = delete_trade(trade_id, user_id=user["id"])
    else:
        deleted_count = delete_trade(trade_id)
    return {"ok": True, "deleted_count": deleted_count}


@app.delete("/api/journal/trades")
def remove_all_journal_trades(authorization: Optional[str] = Header(default=None)):
    user = _optional_session_user(authorization)
    if user:
        deleted_count = clear_trades(user_id=user["id"])
    else:
        deleted_count = clear_trades()
    return {"ok": True, "deleted_count": deleted_count}


@app.get("/api/journal/review")
def get_journal_review(authorization: Optional[str] = Header(default=None)):
    user = _optional_session_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            return build_review([])
        return build_review(list_trades(limit=5000, user_id=user["id"]))
    return build_review()


@app.post("/api/journal/review-once")
def get_journal_review_once(batch: JournalBatchIn):
    return build_review(_journal_batch_payload(batch))


@app.get("/api/journal/ai-review")
def get_journal_ai_review(authorization: Optional[str] = Header(default=None)):
    user = _optional_session_user(authorization)
    trades = list_trades(limit=5000, user_id=user["id"]) if user and user.get("journal_storage_enabled") else list_trades(limit=5000)
    return build_ai_review(trades)


@app.get("/api/journal/review-history")
def get_journal_review_history(
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        return []
    return list_review_history(user_id=user["id"], limit=limit)


@app.get("/api/journal/review-history/{review_id}")
def get_journal_review_history_detail(
    review_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        raise HTTPException(status_code=403, detail="매매 이력 저장을 켠 계정만 복기 보관함을 사용할 수 있습니다.")
    item = get_review_history(review_id, user_id=user["id"])
    if not item:
        raise HTTPException(status_code=404, detail="복기 이력을 찾을 수 없습니다.")
    return item


@app.delete("/api/journal/review-history/{review_id}")
def remove_journal_review_history(
    review_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    deleted_count = delete_review_history(review_id, user_id=user["id"])
    return {"ok": True, "deleted_count": deleted_count}


@app.get("/api/journal/entitlements")
def get_journal_entitlements(
    authorization: Optional[str] = Header(default=None),
    entitlement_token: Optional[str] = None,
):
    return get_user_entitlements(
        authorization=authorization,
        entitlement_token=entitlement_token,
    )


@app.get("/api/journal/products")
def get_journal_products():
    return get_product_catalog()


@app.post("/api/journal/dev-purchase")
def post_journal_dev_purchase(
    purchase: JournalDevPurchaseIn,
    authorization: Optional[str] = Header(default=None),
):
    return apply_dev_purchase(
        authorization=authorization,
        entitlement_token=purchase.entitlement_token,
        product_id=purchase.product_id,
    )


@app.post("/api/journal/google-play-purchase")
def post_journal_google_play_purchase(
    purchase: JournalGooglePlayPurchaseIn,
    authorization: Optional[str] = Header(default=None),
):
    return apply_google_play_purchase(
        authorization=authorization,
        product_id=purchase.product_id,
        purchase_token=purchase.purchase_token,
        package_name=purchase.package_name,
    )


@app.post("/api/journal/google-play-rtdn")
def post_journal_google_play_rtdn(
    payload: GooglePlayRtdnIn,
    x_alphamate_rtdn_token: Optional[str] = Header(default=None, alias="X-AlphaMate-RTDN-Token"),
    authorization: Optional[str] = Header(default=None),
):
    return handle_google_play_rtdn(
        pubsub_payload=payload.model_dump(),
        shared_token=x_alphamate_rtdn_token,
        authorization=authorization,
    )


@app.get("/api/journal/admob-ssv")
def get_journal_admob_ssv(request: Request):
    return record_admob_ssv_reward(str(request.url.query))


@app.post("/api/journal/ai-review-once")
def get_journal_ai_review_once(
    batch: JournalAiReviewIn,
    authorization: Optional[str] = Header(default=None),
):
    access = verify_ai_review_access(
        authorization=authorization,
        ad_reward_token=batch.ad_reward_token,
        entitlement_token=batch.entitlement_token,
        privacy_consent=batch.privacy_consent,
        review_type=batch.review_type,
    )
    if batch.privacy_consent and authorization:
        record_privacy_consent(authorization=authorization)
    trades = _journal_batch_payload(batch)
    if access.review_type == "advanced":
        result = build_advanced_ai_review(trades, target_trade_id=batch.target_trade_id)
    else:
        result = build_basic_ai_review(trades, target_trade_id=batch.target_trade_id)
    result["access"] = {
        "auth_mode": access.auth_mode,
        "plan": access.plan,
        "review_type": access.review_type,
        "source": access.source,
        "quota": access.quota,
        "wallet": access.product_balances,
    }
    review_history_id = _save_ai_review_history_if_enabled(
        authorization=authorization,
        batch=batch,
        trades=trades,
        result=result,
    )
    if review_history_id:
        result["review_history_id"] = review_history_id
    return result


@app.get("/api/journal/charts")
def get_journal_charts(authorization: Optional[str] = Header(default=None)):
    user = _optional_session_user(authorization)
    trades = list_trades(limit=5000, user_id=user["id"]) if user and user.get("journal_storage_enabled") else list_trades(limit=5000)
    return build_journal_charts(trades)


@app.post("/api/journal/charts-once")
def get_journal_charts_once(batch: JournalBatchIn):
    return build_journal_charts(_journal_batch_payload(batch))

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
