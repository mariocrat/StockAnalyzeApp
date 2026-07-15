from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
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
    warm_theme_return_caches,
)
from core.metrics import calculate_theme_rankings, get_stocks_in_theme
from core.utils import get_chosung
from core.journal import add_trade, list_trades, count_trades, delete_trade, clear_trades, build_review, normalize_trade
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
    refund_ai_review_access,
    verify_ai_review_access,
)
from core.account_store import login_dev_provider, authenticate_session, revoke_session, update_journal_storage_setting, record_privacy_consent, get_privacy_consent_version, delete_user_account_data
from core.oauth_login import create_oauth_app_error_redirect, create_oauth_app_redirect, consume_oauth_app_ticket, get_oauth_config_status, login_oauth_code, login_oauth_provider
from core.cors import allowed_cors_origins
from core.readiness import get_app_readiness
from core.rate_limit import InMemoryRateLimiter
from core.env import env_value
from core.event_log import list_events, purge_configured_retention, purge_events_older_than, record_api_exception, record_api_failure, record_event, summarize_events

from contextlib import asynccontextmanager
import copy
import hmac
import hashlib
import json
import uuid
import threading
import logging
from fastapi import HTTPException

# Suppress yfinance spam at startup
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_theme_refresh_lock = threading.Lock()
_theme_refresh_jobs = set()
_theme_warm_lock = threading.Lock()
_theme_calculation_lock = threading.Lock()
_client_event_rate_limiter = InMemoryRateLimiter()
_market_rate_limiter = InMemoryRateLimiter()
_admin_rate_limiter = InMemoryRateLimiter()
_auth_rate_limiter = InMemoryRateLimiter()
_billing_rate_limiter = InMemoryRateLimiter()
_callback_rate_limiter = InMemoryRateLimiter()
_ai_review_rate_limiter = InMemoryRateLimiter()
_ai_review_idempotency_lock = threading.Lock()
_ai_review_idempotency_cache = {}
REQUEST_ID_HEADER = "X-Request-ID"
ADMIN_TOKEN_MIN_LENGTH = 32
ADMIN_RATE_LIMIT_MAX_PER_MINUTE = 300
CLIENT_EVENT_RATE_LIMIT_MAX_PER_MINUTE = 600
MARKET_RATE_LIMIT_MAX_PER_MINUTE = 600
AUTH_RATE_LIMIT_MAX_PER_MINUTE = 120
BILLING_RATE_LIMIT_MAX_PER_MINUTE = 120
AI_REVIEW_RATE_LIMIT_MAX_PER_MINUTE = 60
CALLBACK_RATE_LIMIT_MAX_PER_MINUTE = 300
AI_REVIEW_MAX_CONCURRENT_LIMIT = 20
AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE = 1000
AI_REVIEW_IDEMPOTENCY_TTL_MAX_SECONDS = 3600
JOURNAL_ONCE_MAX_TRADES_LIMIT = 1000
AI_REVIEW_MAX_TRADES_LIMIT = 200
PUBLIC_MARKET_RATE_LIMIT_PATHS = {
    "/api/themes",
    "/api/theme_stocks",
    "/api/themes_historical",
    "/api/search",
    "/api/macro",
}
JOURNAL_MEMO_MAX_CHARS_LIMIT = 5000
JOURNAL_QUERY_MAX_LIMIT = 1000
SAVED_JOURNAL_ANALYSIS_MAX_TRADES_LIMIT = 1000


def _env_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = max(minimum, int(env_value(name) or default))
    except ValueError:
        value = default
    if maximum is not None:
        value = min(value, maximum)
    return value


def _ai_review_max_concurrent() -> int:
    return _env_int("ALPHAMATE_AI_REVIEW_MAX_CONCURRENT", 3, 1, AI_REVIEW_MAX_CONCURRENT_LIMIT)


_ai_review_concurrency_guard = threading.BoundedSemaphore(_ai_review_max_concurrent())


def _journal_once_max_trades() -> int:
    return _env_int("ALPHAMATE_JOURNAL_ONCE_MAX_TRADES", 500, 1, JOURNAL_ONCE_MAX_TRADES_LIMIT)


def _ai_review_max_trades() -> int:
    return _env_int("ALPHAMATE_AI_REVIEW_MAX_TRADES", 100, 1, AI_REVIEW_MAX_TRADES_LIMIT)


def _normalize_ai_review_type(review_type: str | None) -> str:
    normalized = str(review_type or "basic").strip().lower()
    if normalized not in {"basic", "advanced"}:
        raise HTTPException(status_code=400, detail="review_type must be basic or advanced.")
    return normalized


def _journal_memo_max_chars() -> int:
    return _env_int("ALPHAMATE_JOURNAL_MEMO_MAX_CHARS", 2000, 1, JOURNAL_MEMO_MAX_CHARS_LIMIT)


def _journal_query_max_limit() -> int:
    return _env_int("ALPHAMATE_JOURNAL_QUERY_MAX_LIMIT", 500, 1, JOURNAL_QUERY_MAX_LIMIT)


def _saved_journal_analysis_max_trades() -> int:
    return _env_int("ALPHAMATE_SAVED_JOURNAL_ANALYSIS_MAX_TRADES", 500, 1, SAVED_JOURNAL_ANALYSIS_MAX_TRADES_LIMIT)


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


class AuthOAuthTicketIn(BaseModel):
    ticket: str


class JournalStorageSettingIn(BaseModel):
    enabled: bool


class ClientEventIn(BaseModel):
    event_type: str = "client_event"
    level: str = "warning"
    message: str = ""
    path: str = ""
    details: dict = {}


def _journal_batch_payload(batch: JournalBatchIn) -> list[dict]:
    try:
        return [normalize_trade(trade.model_dump()) for trade in batch.trades]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _add_journal_trade(payload: dict, *, user_id: str = "") -> dict:
    try:
        return add_trade(payload, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _enforce_journal_batch_limit(batch: JournalBatchIn, *, max_trades: int, label: str = "매매 기록"):
    trade_count = len(batch.trades or [])
    if trade_count > max_trades:
        raise HTTPException(
            status_code=413,
            detail=f"{label}는 한 번에 최대 {max_trades}건까지 처리할 수 있습니다. 현재 {trade_count}건입니다.",
        )
    _enforce_trade_text_limits(batch.trades or [])


def _enforce_trade_text_limits(trades: list[JournalTradeIn]):
    max_memo_chars = _journal_memo_max_chars()
    for index, trade in enumerate(trades, start=1):
        memo = str(trade.memo or "")
        if len(memo) > max_memo_chars:
            raise HTTPException(
                status_code=413,
                detail=f"{index}번째 매매 메모는 최대 {max_memo_chars}자까지 입력할 수 있습니다.",
            )


def _safe_journal_query_limit(limit: int, *, default: int = 100) -> int:
    try:
        requested = int(limit or default)
    except (TypeError, ValueError):
        requested = default
    return max(1, min(requested, _journal_query_max_limit()))


def _optional_session_user(authorization: Optional[str]):
    if not authorization:
        return None
    try:
        return authenticate_session(authorization)
    except HTTPException:
        return None


def _persistent_journal_user(authorization: Optional[str]):
    if str(env_value("ALPHAMATE_ENV") or "").strip().lower() == "production":
        return authenticate_session(authorization)
    return _optional_session_user(authorization)


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


KST = datetime.timezone(datetime.timedelta(hours=9))
THEME_MARKET_DATA_READY_HOUR = 15
THEME_MARKET_DATA_READY_MINUTE = 40


def _kst_now(now: Optional[datetime.datetime] = None) -> datetime.datetime:
    if now is None:
        return datetime.datetime.now(KST)
    if now.tzinfo is None:
        return now.replace(tzinfo=KST)
    return now.astimezone(KST)


def _last_completed_market_date(now: Optional[datetime.datetime] = None) -> datetime.date:
    current = _kst_now(now)
    today = current.date()
    data_ready_at = current.replace(
        hour=THEME_MARKET_DATA_READY_HOUR,
        minute=THEME_MARKET_DATA_READY_MINUTE,
        second=0,
        microsecond=0,
    )
    if today.weekday() < 5 and current >= data_ready_at:
        return today
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


def _schedule_theme_cache_refresh(start_date: str = "", end_date: str = ""):
    if _theme_warm_lock.locked():
        return
    threading.Thread(target=_warm_cache, daemon=True).start()


def _schedule_custom_theme_cache_refresh(start_date: str, end_date: str):
    key = (start_date, end_date)
    with _theme_refresh_lock:
        if key in _theme_refresh_jobs:
            return
        _theme_refresh_jobs.add(key)

    def _worker():
        try:
            with _theme_calculation_lock:
                get_theme_returns_historical(start_date, end_date)
        except Exception as e:
            print(f"[cache] Theme refresh failed {start_date}-{end_date}: {e}")
        finally:
            with _theme_refresh_lock:
                _theme_refresh_jobs.discard(key)

    threading.Thread(target=_worker, daemon=True).start()

def _env_bool_flag(name: str, default: bool = False) -> bool:
    raw = env_value(name).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _warm_cache_on_startup() -> bool:
    # Render health checks are strict; expensive market-data warmup should be opt-in there.
    return _env_bool_flag("ALPHAMATE_WARM_CACHE_ON_STARTUP", False)

def _warm_cache():
    """Pre-warm theme caches in the background."""
    if not _theme_warm_lock.acquire(blocking=False):
        return
    try:
        cleanup_result = purge_configured_retention()
        if not cleanup_result.get("skipped"):
            print(f"[startup] Operational event log cleanup: {cleanup_result}")

        print("[startup] Warming theme caches...")

        try:
            _get_stock_search_index()
        except Exception as e:
            print(f"[startup] Search index warm-up failed (non-fatal): {e}")

        period_ranges = {
            period: _period_date_range(period)
            for period in ("1D", "1W", "1M", "1Y")
        }
        with _theme_calculation_lock:
            counts = warm_theme_return_caches(period_ranges)
        get_themes.cache_clear()
        print(f"[startup] Theme cache ready: {counts}")
    except Exception as e:
        print(f"[startup] Cache warm-up failed (non-fatal): {e}")
    finally:
        _theme_warm_lock.release()


def _seconds_until_next_theme_refresh(now: Optional[datetime.datetime] = None) -> float:
    current = _kst_now(now)
    target = current.replace(
        hour=THEME_MARKET_DATA_READY_HOUR,
        minute=THEME_MARKET_DATA_READY_MINUTE,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += datetime.timedelta(days=1)
    return max(1.0, (target - current).total_seconds())


def _theme_cache_scheduler(stop_event: threading.Event):
    while not stop_event.wait(_seconds_until_next_theme_refresh()):
        _warm_cache()

@asynccontextmanager
async def lifespan(app):
    scheduler_stop = threading.Event()
    if _warm_cache_on_startup():
        threading.Thread(target=_warm_cache, daemon=True).start()
    else:
        print("[startup] Theme cache warm-up skipped. Set ALPHAMATE_WARM_CACHE_ON_STARTUP=true to enable it.")
    scheduler = threading.Thread(target=lambda: _theme_cache_scheduler(scheduler_stop), daemon=True)
    scheduler.start()
    try:
        yield
    finally:
        scheduler_stop.set()

app = FastAPI(title="Stock Analysis API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_cors_origins(),
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
    return _env_int(
        "ALPHAMATE_CLIENT_EVENT_RATE_LIMIT_PER_MINUTE",
        60,
        1,
        CLIENT_EVENT_RATE_LIMIT_MAX_PER_MINUTE,
    )


def _market_rate_limit() -> int:
    return _env_int(
        "ALPHAMATE_MARKET_RATE_LIMIT_PER_MINUTE",
        120,
        1,
        MARKET_RATE_LIMIT_MAX_PER_MINUTE,
    )

def _admin_rate_limit() -> int:
    return _env_int("ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE", 30, 1, ADMIN_RATE_LIMIT_MAX_PER_MINUTE)


def _auth_rate_limit() -> int:
    return _env_int(
        "ALPHAMATE_AUTH_RATE_LIMIT_PER_MINUTE",
        30,
        1,
        AUTH_RATE_LIMIT_MAX_PER_MINUTE,
    )


def _billing_rate_limit() -> int:
    return _env_int(
        "ALPHAMATE_BILLING_RATE_LIMIT_PER_MINUTE",
        20,
        1,
        BILLING_RATE_LIMIT_MAX_PER_MINUTE,
    )


def _callback_rate_limit() -> int:
    return _env_int(
        "ALPHAMATE_CALLBACK_RATE_LIMIT_PER_MINUTE",
        60,
        1,
        CALLBACK_RATE_LIMIT_MAX_PER_MINUTE,
    )


def _ai_review_rate_limit() -> int:
    return _env_int("ALPHAMATE_AI_REVIEW_RATE_LIMIT_PER_MINUTE", 10, 1, AI_REVIEW_RATE_LIMIT_MAX_PER_MINUTE)


def _ai_review_idempotency_ttl_seconds() -> int:
    return _env_int(
        "ALPHAMATE_AI_REVIEW_IDEMPOTENCY_TTL_SECONDS",
        300,
        60,
        AI_REVIEW_IDEMPOTENCY_TTL_MAX_SECONDS,
    )


def _billing_rate_key(authorization: str | None, client_key: str) -> str:
    text = str(authorization or "").strip()
    if text:
        return "auth:" + uuid.uuid5(uuid.NAMESPACE_URL, text).hex
    return "client:" + str(client_key or "unknown")

def _ai_review_rate_key(authorization: str | None) -> str:
    text = str(authorization or "").strip()
    if not text:
        return "anonymous"
    return "auth:" + uuid.uuid5(uuid.NAMESPACE_URL, text).hex


def _clean_ai_review_idempotency_key(value: str | None) -> str:
    text = str(value or "").strip()
    if not 8 <= len(text) <= 120:
        return ""
    safe = "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})
    return safe if safe == text else ""


def _ai_review_idempotency_cache_key(authorization: str | None, key: str) -> str:
    key_hash = hashlib.sha256(str(key or "").encode("utf-8")).hexdigest()
    return f"{_ai_review_rate_key(authorization)}:idem:{key_hash}"


def _ai_review_payload_fingerprint(batch: JournalAiReviewIn) -> str:
    payload = batch.model_dump(exclude={"ad_reward_token", "entitlement_token"})
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prune_ai_review_idempotency_cache(now: datetime.datetime):
    expired = [
        key for key, item in _ai_review_idempotency_cache.items()
        if item.get("expires_at") and item["expires_at"] <= now
    ]
    for key in expired:
        _ai_review_idempotency_cache.pop(key, None)


def _trim_ai_review_idempotency_cache(protected_keys: set[str] | None = None):
    protected_keys = protected_keys or set()
    overflow = len(_ai_review_idempotency_cache) - max(1, int(AI_REVIEW_IDEMPOTENCY_CACHE_MAX_SIZE))
    if overflow <= 0:
        return
    ordered = sorted(
        _ai_review_idempotency_cache.items(),
        key=lambda item: item[1].get("expires_at") or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
    )
    removed = 0
    for key, _ in ordered:
        if key in protected_keys:
            continue
        _ai_review_idempotency_cache.pop(key, None)
        removed += 1
        if removed >= overflow:
            break


def _begin_ai_review_idempotency(
    authorization: str | None,
    raw_key: str | None,
    payload_fingerprint: str,
) -> tuple[str, dict | None]:
    key = _clean_ai_review_idempotency_key(raw_key)
    if not key:
        return "", None
    cache_key = _ai_review_idempotency_cache_key(authorization, key)
    now = datetime.datetime.now(datetime.timezone.utc)
    with _ai_review_idempotency_lock:
        _prune_ai_review_idempotency_cache(now)
        _trim_ai_review_idempotency_cache()
        cached = _ai_review_idempotency_cache.get(cache_key)
        if cached and cached.get("payload_fingerprint") != payload_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was reused with a different AI review request.",
            )
        if cached and cached.get("status") == "done":
            result = copy.deepcopy(cached["result"])
            result.setdefault("access", {})["idempotent_replay"] = True
            return "", result
        if cached and cached.get("status") == "pending":
            raise HTTPException(
                status_code=409,
                detail="AI review request is already running. Please retry shortly.",
                headers={"Retry-After": "5"},
            )
        _ai_review_idempotency_cache[cache_key] = {
            "status": "pending",
            "payload_fingerprint": payload_fingerprint,
            "expires_at": now + datetime.timedelta(seconds=_ai_review_idempotency_ttl_seconds()),
        }
        _trim_ai_review_idempotency_cache({cache_key})
    return cache_key, None


def _finish_ai_review_idempotency(cache_key: str, result: dict | None):
    if not cache_key:
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    with _ai_review_idempotency_lock:
        if result is None:
            _ai_review_idempotency_cache.pop(cache_key, None)
            return
        stored = copy.deepcopy(result)
        stored.setdefault("access", {})["idempotent_replay"] = False
        previous = _ai_review_idempotency_cache.get(cache_key) or {}
        _ai_review_idempotency_cache[cache_key] = {
            "status": "done",
            "result": stored,
            "payload_fingerprint": previous.get("payload_fingerprint"),
            "expires_at": now + datetime.timedelta(seconds=_ai_review_idempotency_ttl_seconds()),
        }
        _trim_ai_review_idempotency_cache({cache_key})


def _enforce_ai_review_rate_limit(authorization: str | None) -> bool:
    rate_limit = _ai_review_rate_limiter.check(
        _ai_review_rate_key(authorization),
        limit=_ai_review_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many AI review requests. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )
    return True


def _acquire_ai_review_capacity() -> bool:
    if not _ai_review_concurrency_guard.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="AI review service is busy. Please try again shortly.",
            headers={"Retry-After": "10"},
        )
    return True


def _release_ai_review_capacity():
    _ai_review_concurrency_guard.release()


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


def _enforce_auth_rate_limit(client_key: str) -> bool:
    rate_limit = _auth_rate_limiter.check(
        client_key or "unknown",
        limit=_auth_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many login requests. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )
    return True


def _enforce_billing_rate_limit(authorization: str | None, client_key: str) -> bool:
    rate_limit = _billing_rate_limiter.check(
        _billing_rate_key(authorization, client_key),
        limit=_billing_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many billing requests. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )
    return True


def _enforce_callback_rate_limit(callback_name: str, client_key: str) -> bool:
    rate_limit = _callback_rate_limiter.check(
        f"{callback_name}:{client_key or 'unknown'}",
        limit=_callback_rate_limit(),
        window_seconds=60,
    )
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many callback requests. Retry after {rate_limit['retry_after_seconds']} seconds.",
            headers={"Retry-After": str(rate_limit["retry_after_seconds"])},
        )
    return True


def _is_public_market_rate_limited_path(path: str) -> bool:
    text = str(path or "")
    return text in PUBLIC_MARKET_RATE_LIMIT_PATHS or text.startswith("/api/stock/")


def _market_rate_limit_response(rate_limit: dict):
    retry_after = str(rate_limit["retry_after_seconds"])
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Too many market data requests. Retry after {retry_after} seconds."
        },
        headers={"Retry-After": retry_after},
    )

def _request_id_from_header(value: str | None) -> str:
    text = str(value or "").strip()
    safe = "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})
    if safe == text and 8 <= len(safe) <= 80:
        return safe
    return uuid.uuid4().hex


@app.middleware("http")
async def limit_public_market_requests(request: Request, call_next):
    path = request.url.path
    if _is_public_market_rate_limited_path(path):
        rate_limit = _market_rate_limiter.check(
            _request_client_key(request),
            limit=_market_rate_limit(),
            window_seconds=60,
        )
        if not rate_limit["allowed"]:
            return _market_rate_limit_response(rate_limit)
    return await call_next(request)

@app.middleware("http")
async def log_failed_api_requests(request: Request, call_next):
    path = request.url.path
    request_id = _request_id_from_header(request.headers.get(REQUEST_ID_HEADER))
    if not path.startswith("/api/"):
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    user_id = _request_user_id_for_log(request)
    try:
        response = await call_next(request)
    except Exception as exc:
        record_api_exception(
            method=request.method,
            path=path,
            exc=exc,
            user_id=user_id,
            details={"request_id": request_id},
        )
        raise
    response.headers[REQUEST_ID_HEADER] = request_id

    if response.status_code >= 400:
        record_api_failure(
            method=request.method,
            path=path,
            status_code=response.status_code,
            user_id=user_id,
            message=f"HTTP {response.status_code}",
            details={
                "request_id": request_id,
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
    return response


@app.get("/healthz")
@app.get("/api/healthz")
def healthz():
    return {"ok": True, "service": "alphamate-api"}


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
    if env_value("ALPHAMATE_ENV").lower() == "production" and len(configured) < ADMIN_TOKEN_MIN_LENGTH:
        raise HTTPException(status_code=503, detail="Admin token must be at least 32 characters in production.")
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
    offset: int = 0,
    level: str = "",
    event_type: str = "",
    request_id: str = "",
    user_id: str = "",
    path: str = "",
    status_code: Optional[int] = None,
    event_id: str = "",
    created_after: str = "",
    created_before: str = "",
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    safe_limit = max(1, min(int(limit or 100), 1000))
    safe_offset = max(0, int(offset or 0))
    events = list_events(
        limit=safe_limit,
        offset=safe_offset,
        level=level,
        event_type=event_type,
        request_id=request_id,
        user_id=user_id,
        path=path,
        status_code=status_code,
        event_id=event_id,
        created_after=created_after,
        created_before=created_before,
    )
    return {"events": events, "count": len(events), "limit": safe_limit, "offset": safe_offset}


@app.get("/api/admin/operational-events/summary")
def get_admin_operational_event_summary(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    limit: int = 500,
    offset: int = 0,
    level: str = "",
    event_type: str = "",
    request_id: str = "",
    user_id: str = "",
    path: str = "",
    status_code: Optional[int] = None,
    event_id: str = "",
    created_after: str = "",
    created_before: str = "",
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    return summarize_events(
        limit=limit,
        offset=offset,
        level=level,
        event_type=event_type,
        request_id=request_id,
        user_id=user_id,
        path=path,
        status_code=status_code,
        event_id=event_id,
        created_after=created_after,
        created_before=created_before,
    )


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


def _theme_cache_status_payload() -> dict:
    periods = {}
    for period in ("1D", "1W", "1M", "1Y"):
        start_date, end_date = _period_date_range(period)
        cached = get_cached_theme_returns(start_date, end_date)
        periods[period] = {
            "ready": not cached.empty,
            "start_date": start_date,
            "end_date": end_date,
            "theme_count": int(len(cached)),
        }
    return {
        "refreshing": _theme_warm_lock.locked(),
        "periods": periods,
    }


@app.get("/api/admin/theme-cache/status")
def get_admin_theme_cache_status(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    return _theme_cache_status_payload()


@app.post("/api/admin/theme-cache/refresh")
def post_admin_theme_cache_refresh(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _enforce_admin_rate_limit(_request_client_key(request))
    _require_admin_token(authorization)
    if _theme_warm_lock.locked():
        return {"started": False, "status": "already_running", **_theme_cache_status_payload()}
    threading.Thread(target=_warm_cache, daemon=True).start()
    return {"started": True, "status": "started"}


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
                    records = fallback.to_dict(orient="records")
                    for record in records:
                        record["Data Status"] = "updating"
                        record["Expected End Date"] = end_date
                    return records
                if env_value("ALPHAMATE_ENV").lower() == "production":
                    _schedule_theme_cache_refresh(start_date, end_date)
                    raise HTTPException(
                        status_code=503,
                        detail="최신 기간 수익률을 업데이트 중입니다. 잠시 후 자동으로 다시 확인합니다.",
                    )
                df = get_theme_returns_historical(start_date, end_date)
        else:
            df = get_cached_theme_returns(start_date, end_date)
            if df.empty and env_value("ALPHAMATE_ENV").lower() == "production":
                _schedule_custom_theme_cache_refresh(start_date, end_date)
                raise HTTPException(
                    status_code=503,
                    detail="요청한 기간 수익률을 준비 중입니다. 잠시 후 자동으로 다시 확인합니다.",
                )
            if df.empty:
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
def post_auth_dev_login(login: AuthDevLoginIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    return login_dev_provider(
        provider=login.provider,
        provider_user_id=login.provider_user_id,
        display_name=login.display_name,
    )


@app.post("/api/auth/login/kakao")
def post_auth_login_kakao(login: AuthProviderTokenIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    return login_oauth_provider(provider="kakao", access_token=login.access_token)


@app.post("/api/auth/login/naver")
def post_auth_login_naver(login: AuthProviderTokenIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    return login_oauth_provider(provider="naver", access_token=login.access_token)


@app.post("/api/auth/login/kakao/code")
def post_auth_login_kakao_code(login: AuthProviderCodeIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    return login_oauth_code(
        provider="kakao",
        code=login.code,
        redirect_uri=login.redirect_uri,
        state=login.state,
    )


@app.post("/api/auth/login/naver/code")
def post_auth_login_naver_code(login: AuthProviderCodeIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    return login_oauth_code(
        provider="naver",
        code=login.code,
        redirect_uri=login.redirect_uri,
        state=login.state,
    )



@app.post("/api/auth/login/oauth-ticket")
def post_auth_login_oauth_ticket(login: AuthOAuthTicketIn, request: Request):
    _enforce_auth_rate_limit(_request_client_key(request))
    session = consume_oauth_app_ticket(login.ticket)
    record_event(
        level="info",
        event_type="oauth_app_ticket_consumed",
        method="POST",
        path="/api/auth/login/oauth-ticket",
        status_code=200,
        user_id=str(session.get("user", {}).get("id") or ""),
        message="OAuth app login completed.",
        details={"provider": session.get("user", {}).get("provider") or ""},
    )
    return session


@app.get("/api/auth/kakao/callback")
def get_auth_kakao_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    _enforce_auth_rate_limit(_request_client_key(request))
    if error:
        return RedirectResponse(create_oauth_app_error_redirect(provider="kakao", state=state, error=error))
    redirect_url = create_oauth_app_redirect(provider="kakao", code=code, state=state)
    record_event(
        level="info",
        event_type="oauth_callback_completed",
        method="GET",
        path="/api/auth/kakao/callback",
        status_code=302,
        message="OAuth provider callback completed.",
        details={"provider": "kakao"},
    )
    return RedirectResponse(redirect_url)


@app.get("/api/auth/naver/callback")
def get_auth_naver_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    _enforce_auth_rate_limit(_request_client_key(request))
    if error:
        return RedirectResponse(create_oauth_app_error_redirect(provider="naver", state=state, error=error))
    redirect_url = create_oauth_app_redirect(provider="naver", code=code, state=state)
    record_event(
        level="info",
        event_type="oauth_callback_completed",
        method="GET",
        path="/api/auth/naver/callback",
        status_code=302,
        message="OAuth provider callback completed.",
        details={"provider": "naver"},
    )
    return RedirectResponse(redirect_url)


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
    safe_limit = _safe_journal_query_limit(limit, default=500)
    user = _persistent_journal_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            return []
        return list_trades(limit=safe_limit, user_id=user["id"])
    return list_trades(limit=safe_limit)


@app.post("/api/journal/trades")
def create_journal_trade(
    trade: JournalTradeIn,
    authorization: Optional[str] = Header(default=None),
):
    _enforce_trade_text_limits([trade])
    user = _persistent_journal_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            raise HTTPException(status_code=403, detail="매매 이력 저장을 먼저 켜야 합니다.")
        return _add_journal_trade(trade.model_dump(), user_id=user["id"])
    return _add_journal_trade(trade.model_dump())


@app.delete("/api/journal/trades/{trade_id}")
def remove_journal_trade(
    trade_id: int,
    authorization: Optional[str] = Header(default=None),
):
    user = _persistent_journal_user(authorization)
    if user:
        deleted_count = delete_trade(trade_id, user_id=user["id"])
    else:
        deleted_count = delete_trade(trade_id)
    return {"ok": True, "deleted_count": deleted_count}


@app.delete("/api/journal/trades")
def remove_all_journal_trades(authorization: Optional[str] = Header(default=None)):
    user = _persistent_journal_user(authorization)
    if user:
        deleted_count = clear_trades(user_id=user["id"])
    else:
        deleted_count = clear_trades()
    return {"ok": True, "deleted_count": deleted_count}


@app.get("/api/journal/review")
def get_journal_review(authorization: Optional[str] = Header(default=None)):
    user = _persistent_journal_user(authorization)
    if user:
        if not user.get("journal_storage_enabled"):
            return build_review([])
        return build_review(list_trades(limit=_saved_journal_analysis_max_trades(), user_id=user["id"]))
    return build_review()


@app.post("/api/journal/review-once")
def get_journal_review_once(batch: JournalBatchIn):
    _enforce_journal_batch_limit(batch, max_trades=_journal_once_max_trades())
    return build_review(_journal_batch_payload(batch))


@app.get("/api/journal/ai-review")
def get_journal_ai_review(authorization: Optional[str] = Header(default=None)):
    raise HTTPException(
        status_code=410,
        detail="이전 AI 복기 경로는 더 이상 사용하지 않습니다. /api/journal/ai-review-once를 사용하세요.",
    )


@app.get("/api/journal/review-history")
def get_journal_review_history(
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
):
    user = authenticate_session(authorization)
    if not user.get("journal_storage_enabled"):
        return []
    return list_review_history(user_id=user["id"], limit=_safe_journal_query_limit(limit, default=100))


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
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _enforce_billing_rate_limit(authorization, _request_client_key(request))
    return apply_dev_purchase(
        authorization=authorization,
        entitlement_token=purchase.entitlement_token,
        product_id=purchase.product_id,
    )


@app.post("/api/journal/google-play-purchase")
def post_journal_google_play_purchase(
    purchase: JournalGooglePlayPurchaseIn,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _enforce_billing_rate_limit(authorization, _request_client_key(request))
    return apply_google_play_purchase(
        authorization=authorization,
        product_id=purchase.product_id,
        purchase_token=purchase.purchase_token,
        package_name=purchase.package_name,
    )


@app.post("/api/journal/google-play-rtdn")
def post_journal_google_play_rtdn(
    payload: GooglePlayRtdnIn,
    request: Request,
    x_alphamate_rtdn_token: Optional[str] = Header(default=None, alias="X-AlphaMate-RTDN-Token"),
    authorization: Optional[str] = Header(default=None),
):
    _enforce_callback_rate_limit("google-play-rtdn", _request_client_key(request))
    return handle_google_play_rtdn(
        pubsub_payload=payload.model_dump(),
        shared_token=x_alphamate_rtdn_token,
        authorization=authorization,
    )


@app.get("/api/journal/admob-ssv")
def get_journal_admob_ssv(request: Request):
    _enforce_callback_rate_limit("admob-ssv", _request_client_key(request))
    return record_admob_ssv_reward(str(request.url.query))


@app.post("/api/journal/ai-review-once")
def get_journal_ai_review_once(
    batch: JournalAiReviewIn,
    authorization: Optional[str] = Header(default=None),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    _enforce_journal_batch_limit(batch, max_trades=_ai_review_max_trades(), label="AI 복기")
    batch.review_type = _normalize_ai_review_type(batch.review_type)
    idempotency_cache_key, idempotent_result = _begin_ai_review_idempotency(
        authorization,
        x_idempotency_key,
        _ai_review_payload_fingerprint(batch),
    )
    if idempotent_result is not None:
        return idempotent_result

    _enforce_ai_review_rate_limit(authorization)
    _acquire_ai_review_capacity()
    access = None
    result = None
    try:
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
    except Exception:
        _finish_ai_review_idempotency(idempotency_cache_key, None)
        if access is not None:
            refund_ai_review_access(access)
        raise
    finally:
        _release_ai_review_capacity()

    refunded = False
    if result.get("status") == "error":
        refunded = True
        refunded_wallet = refund_ai_review_access(access)
    else:
        refunded_wallet = access.product_balances
    access_quota = {
        "basic": refunded_wallet["basic"],
        "advanced": refunded_wallet["advanced"],
    }
    result["access"] = {
        "auth_mode": access.auth_mode,
        "plan": access.plan,
        "review_type": access.review_type,
        "source": access.source,
        "quota": access_quota,
        "wallet": refunded_wallet,
        "refunded": refunded,
        "idempotent_replay": False,
    }
    review_history_id = _save_ai_review_history_if_enabled(
        authorization=authorization,
        batch=batch,
        trades=trades,
        result=result,
    )
    if review_history_id:
        result["review_history_id"] = review_history_id
    _finish_ai_review_idempotency(idempotency_cache_key, result)
    return result


@app.get("/api/journal/charts")
def get_journal_charts(authorization: Optional[str] = Header(default=None)):
    user = _persistent_journal_user(authorization)
    limit = _saved_journal_analysis_max_trades()
    if user:
        trades = list_trades(limit=limit, user_id=user["id"]) if user.get("journal_storage_enabled") else []
    else:
        trades = list_trades(limit=limit)
    return build_journal_charts(trades)


@app.post("/api/journal/charts-once")
def get_journal_charts_once(batch: JournalBatchIn):
    _enforce_journal_batch_limit(batch, max_trades=_journal_once_max_trades())
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
