import datetime
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException


PRODUCTS = {
    "basic_review_30": {"kind": "basic", "quantity": 30, "price_krw": 2900},
    "basic_review_100": {"kind": "basic", "quantity": 100, "price_krw": 6900},
    "advanced_review_5": {"kind": "advanced", "quantity": 5, "price_krw": 2900},
    "advanced_review_10": {"kind": "advanced", "quantity": 10, "price_krw": 4900},
}

FREE_SIGNUP_BASIC_CREDITS = 5
FREE_DAILY_BASIC_GRANT = 1
FREE_DAILY_BASIC_MAX = 5
FREE_MONTHLY_BASIC_MAX = 50
FREE_ADS_PER_ADVANCED_TICKET = 5
FREE_WEEKLY_ADVANCED_MAX = 1
ADVANCED_TICKET_HOLD_MAX = 1

PRO_MONTHLY_BASIC = 150
PRO_MONTHLY_ADVANCED = 5


@dataclass
class UsageBucket:
    date_key: str = ""
    month_key: str = ""
    week_key: str = ""
    free_basic_daily_used: int = 0
    free_basic_monthly_used: int = 0
    pro_basic_monthly_used: int = 0
    pro_advanced_monthly_used: int = 0
    weekly_ad_views: int = 0
    weekly_advanced_granted: int = 0


@dataclass
class UserWallet:
    basic_signup_remaining: int = FREE_SIGNUP_BASIC_CREDITS
    purchased_basic: int = 0
    weekly_advanced: int = 0
    purchased_advanced: int = 0
    usage: UsageBucket = field(default_factory=UsageBucket)


@dataclass(frozen=True)
class AiAccessContext:
    user_id: str
    auth_mode: str
    plan: str
    review_type: str
    source: str
    product_balances: dict
    quota: dict


_WALLET_LOCK = threading.Lock()
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()

    roots = [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for path in roots:
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, val = raw.split("=", 1)
                if key.strip() == name:
                    return val.strip().strip("\"'")
        except Exception:
            continue
    return ""


def _access_db_path() -> Path:
    configured = _env_value("ALPHAMATE_ACCESS_DB_PATH")
    if configured:
        return Path(configured)
    return DATA_DIR / "access.sqlite3"


def _connect_access_db():
    path = _access_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS access_wallets (
            user_id TEXT PRIMARY KEY,
            basic_signup_remaining INTEGER NOT NULL DEFAULT 5,
            purchased_basic INTEGER NOT NULL DEFAULT 0,
            weekly_advanced INTEGER NOT NULL DEFAULT 0,
            purchased_advanced INTEGER NOT NULL DEFAULT 0,
            date_key TEXT NOT NULL DEFAULT '',
            month_key TEXT NOT NULL DEFAULT '',
            week_key TEXT NOT NULL DEFAULT '',
            free_basic_daily_used INTEGER NOT NULL DEFAULT 0,
            free_basic_monthly_used INTEGER NOT NULL DEFAULT 0,
            pro_basic_monthly_used INTEGER NOT NULL DEFAULT 0,
            pro_advanced_monthly_used INTEGER NOT NULL DEFAULT 0,
            weekly_ad_views INTEGER NOT NULL DEFAULT 0,
            weekly_advanced_granted INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def _wallet_from_row(row) -> UserWallet:
    if row is None:
        return UserWallet()
    usage = UsageBucket(
        date_key=row["date_key"],
        month_key=row["month_key"],
        week_key=row["week_key"],
        free_basic_daily_used=int(row["free_basic_daily_used"]),
        free_basic_monthly_used=int(row["free_basic_monthly_used"]),
        pro_basic_monthly_used=int(row["pro_basic_monthly_used"]),
        pro_advanced_monthly_used=int(row["pro_advanced_monthly_used"]),
        weekly_ad_views=int(row["weekly_ad_views"]),
        weekly_advanced_granted=int(row["weekly_advanced_granted"]),
    )
    return UserWallet(
        basic_signup_remaining=int(row["basic_signup_remaining"]),
        purchased_basic=int(row["purchased_basic"]),
        weekly_advanced=int(row["weekly_advanced"]),
        purchased_advanced=int(row["purchased_advanced"]),
        usage=usage,
    )


def _load_wallet(user_id: str) -> UserWallet:
    conn = _connect_access_db()
    try:
        row = conn.execute(
            "SELECT * FROM access_wallets WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return _wallet_from_row(row)
    finally:
        conn.close()


def _save_wallet(user_id: str, wallet: UserWallet):
    usage = wallet.usage
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = _connect_access_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO access_wallets (
                user_id,
                basic_signup_remaining,
                purchased_basic,
                weekly_advanced,
                purchased_advanced,
                date_key,
                month_key,
                week_key,
                free_basic_daily_used,
                free_basic_monthly_used,
                pro_basic_monthly_used,
                pro_advanced_monthly_used,
                weekly_ad_views,
                weekly_advanced_granted,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                wallet.basic_signup_remaining,
                wallet.purchased_basic,
                wallet.weekly_advanced,
                wallet.purchased_advanced,
                usage.date_key,
                usage.month_key,
                usage.week_key,
                usage.free_basic_daily_used,
                usage.free_basic_monthly_used,
                usage.pro_basic_monthly_used,
                usage.pro_advanced_monthly_used,
                usage.weekly_ad_views,
                usage.weekly_advanced_granted,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _is_production() -> bool:
    return _env_value("ALPHAMATE_ENV").lower() == "production"


def _dev_access_enabled() -> bool:
    if _is_production():
        return False
    return _env_value("ALPHAMATE_ALLOW_DEV_ACCESS").lower() not in {"0", "false", "no"}


def _allow_advanced_for_basic() -> bool:
    return _env_value("ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC").lower() in {"1", "true", "yes"}


def _bearer_token(authorization: str | None) -> str:
    text = str(authorization or "").strip()
    if text.lower().startswith("bearer "):
        return text[7:].strip()
    return text


def _today_keys():
    today = datetime.date.today()
    return (
        today.isoformat(),
        today.strftime("%Y-%m"),
        f"{today.isocalendar().year}-W{today.isocalendar().week:02d}",
    )


def _wallet_for(user_id: str) -> UserWallet:
    wallet = _load_wallet(user_id)
    date_key, month_key, week_key = _today_keys()
    usage = wallet.usage
    if usage.date_key != date_key:
        usage.date_key = date_key
        usage.free_basic_daily_used = 0
    if usage.month_key != month_key:
        usage.month_key = month_key
        usage.free_basic_monthly_used = 0
        usage.pro_basic_monthly_used = 0
        usage.pro_advanced_monthly_used = 0
    if usage.week_key != week_key:
        usage.week_key = week_key
        usage.weekly_ad_views = 0
        usage.weekly_advanced_granted = 0
        wallet.weekly_advanced = 0
    return wallet


def _authenticate(authorization: str | None) -> tuple[str, str]:
    token = _bearer_token(authorization)
    dev_auth_token = _env_value("ALPHAMATE_DEV_AUTH_TOKEN") or "dev-token"
    if _dev_access_enabled() and token == dev_auth_token:
        return "dev-user", "dev"
    try:
        from core.account_store import authenticate_session
    except ModuleNotFoundError:
        from backend.core.account_store import authenticate_session

    user = authenticate_session(authorization)
    return user["id"], "session"


def _plan_for(entitlement_token: str | None) -> str:
    dev_pro_token = _env_value("ALPHAMATE_DEV_PRO_ENTITLEMENT_TOKEN") or "dev-pro-entitlement"
    if _dev_access_enabled() and str(entitlement_token or "").strip() == dev_pro_token:
        return "pro"
    return "free"


def _verify_ad(ad_reward_token: str | None) -> bool:
    dev_ad_token = _env_value("ALPHAMATE_DEV_AD_REWARD_TOKEN") or "dev-ad-reward"
    return _dev_access_enabled() and str(ad_reward_token or "").strip() == dev_ad_token


def _grant_weekly_advanced_if_earned(wallet: UserWallet):
    usage = wallet.usage
    if usage.weekly_ad_views < FREE_ADS_PER_ADVANCED_TICKET:
        return
    if usage.weekly_advanced_granted >= FREE_WEEKLY_ADVANCED_MAX:
        return
    if wallet.weekly_advanced >= ADVANCED_TICKET_HOLD_MAX:
        return
    wallet.weekly_advanced += 1
    usage.weekly_advanced_granted += 1


def _consume_basic(wallet: UserWallet, plan: str, ad_verified: bool) -> str:
    usage = wallet.usage
    if plan == "pro":
        if usage.pro_basic_monthly_used < PRO_MONTHLY_BASIC:
            usage.pro_basic_monthly_used += 1
            return "pro_monthly_basic"
        if wallet.purchased_basic > 0:
            wallet.purchased_basic -= 1
            return "purchased_basic"
        raise HTTPException(status_code=402, detail="Basic review quota exhausted. Please buy review credits.")

    if wallet.basic_signup_remaining > 0:
        wallet.basic_signup_remaining -= 1
        return "signup_basic"
    if usage.free_basic_daily_used < FREE_DAILY_BASIC_GRANT and usage.free_basic_monthly_used < FREE_MONTHLY_BASIC_MAX:
        usage.free_basic_daily_used += 1
        usage.free_basic_monthly_used += 1
        return "free_daily_basic"
    if wallet.purchased_basic > 0:
        wallet.purchased_basic -= 1
        return "purchased_basic"
    if ad_verified and usage.free_basic_daily_used < FREE_DAILY_BASIC_MAX and usage.free_basic_monthly_used < FREE_MONTHLY_BASIC_MAX:
        usage.free_basic_daily_used += 1
        usage.free_basic_monthly_used += 1
        usage.weekly_ad_views += 1
        _grant_weekly_advanced_if_earned(wallet)
        return "rewarded_ad_basic"
    if _allow_advanced_for_basic() and wallet.purchased_advanced > 0:
        wallet.purchased_advanced -= 1
        return "purchased_advanced_as_basic"
    raise HTTPException(status_code=402, detail="Basic review quota exhausted. Watch an ad or buy review credits.")


def _consume_advanced(wallet: UserWallet, plan: str) -> str:
    usage = wallet.usage
    if plan == "pro" and usage.pro_advanced_monthly_used < PRO_MONTHLY_ADVANCED:
        usage.pro_advanced_monthly_used += 1
        return "pro_monthly_advanced"
    if wallet.weekly_advanced > 0:
        wallet.weekly_advanced -= 1
        return "weekly_ad_advanced"
    if wallet.purchased_advanced > 0:
        wallet.purchased_advanced -= 1
        return "purchased_advanced"
    raise HTTPException(status_code=402, detail="Advanced review ticket required. Please buy an advanced review pack.")


def _wallet_snapshot(wallet: UserWallet, plan: str) -> dict:
    usage = wallet.usage
    return {
        "plan": plan,
        "basic": {
            "signup_remaining": wallet.basic_signup_remaining,
            "free_daily_remaining": max(0, FREE_DAILY_BASIC_GRANT - usage.free_basic_daily_used),
            "free_daily_max_remaining": max(0, FREE_DAILY_BASIC_MAX - usage.free_basic_daily_used),
            "free_monthly_remaining": max(0, FREE_MONTHLY_BASIC_MAX - usage.free_basic_monthly_used),
            "pro_monthly_remaining": max(0, PRO_MONTHLY_BASIC - usage.pro_basic_monthly_used) if plan == "pro" else 0,
            "purchased_remaining": wallet.purchased_basic,
        },
        "advanced": {
            "pro_monthly_remaining": max(0, PRO_MONTHLY_ADVANCED - usage.pro_advanced_monthly_used) if plan == "pro" else 0,
            "weekly_reward_remaining": wallet.weekly_advanced,
            "weekly_ad_views": usage.weekly_ad_views,
            "weekly_ad_views_needed": max(0, FREE_ADS_PER_ADVANCED_TICKET - usage.weekly_ad_views),
            "purchased_remaining": wallet.purchased_advanced,
            "max_hold": ADVANCED_TICKET_HOLD_MAX,
        },
        "products": PRODUCTS,
        "settings": {
            "allow_advanced_ticket_for_basic": _allow_advanced_for_basic(),
        },
    }


def get_user_entitlements(*, authorization: str | None, entitlement_token: str | None) -> dict:
    user_id, auth_mode = _authenticate(authorization)
    plan = _plan_for(entitlement_token)
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        _save_wallet(user_id, wallet)
        data = _wallet_snapshot(wallet, plan)
    data["user"] = {"id": user_id, "auth_mode": auth_mode}
    return data


def apply_dev_purchase(*, authorization: str | None, entitlement_token: str | None, product_id: str) -> dict:
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=400, detail="Unknown product id.")
    user_id, _ = _authenticate(authorization)
    plan = _plan_for(entitlement_token)
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        product = PRODUCTS[product_id]
        if product["kind"] == "basic":
            wallet.purchased_basic += product["quantity"]
        else:
            wallet.purchased_advanced += product["quantity"]
        _save_wallet(user_id, wallet)
        return _wallet_snapshot(wallet, plan)


def verify_ai_review_access(
    *,
    authorization: str | None,
    ad_reward_token: str | None,
    entitlement_token: str | None,
    privacy_consent: bool,
    review_type: str,
) -> AiAccessContext:
    if not privacy_consent:
        raise HTTPException(status_code=400, detail="Privacy consent is required before AI analysis.")

    user_id, auth_mode = _authenticate(authorization)
    plan = _plan_for(entitlement_token)
    normalized_type = "advanced" if review_type == "advanced" else "basic"
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        if normalized_type == "advanced":
            source = _consume_advanced(wallet, plan)
        else:
            source = _consume_basic(wallet, plan, _verify_ad(ad_reward_token))
        _save_wallet(user_id, wallet)
        snapshot = _wallet_snapshot(wallet, plan)
    return AiAccessContext(
        user_id=user_id,
        auth_mode=auth_mode,
        plan=plan,
        review_type=normalized_type,
        source=source,
        product_balances=snapshot,
        quota={
            "basic": snapshot["basic"],
            "advanced": snapshot["advanced"],
        },
    )
