import base64
import datetime
import hashlib
import json
import os
import requests
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

SUBSCRIPTIONS = {
    "pro_monthly_launch": {"kind": "pro", "monthly_basic": 150, "monthly_advanced": 5, "price_krw": 3900},
    "pro_monthly": {"kind": "pro", "monthly_basic": 150, "monthly_advanced": 5, "price_krw": 4900},
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS google_play_purchases (
            purchase_token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            local_product_id TEXT NOT NULL,
            google_play_product_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            order_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            granted_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS google_play_subscriptions (
            user_id TEXT PRIMARY KEY,
            purchase_token_hash TEXT NOT NULL,
            local_product_id TEXT NOT NULL,
            google_play_product_id TEXT NOT NULL,
            status TEXT NOT NULL,
            expiry_time TEXT NOT NULL DEFAULT '',
            auto_renewing INTEGER NOT NULL DEFAULT 0,
            latest_order_id TEXT NOT NULL DEFAULT '',
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


def _write_wallet(conn, user_id: str, wallet: UserWallet):
    usage = wallet.usage
    now = datetime.datetime.now().isoformat(timespec="seconds")
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


def _save_wallet(user_id: str, wallet: UserWallet):
    conn = _connect_access_db()
    try:
        _write_wallet(conn, user_id, wallet)
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


def _google_play_id(default_id: str) -> str:
    env_key = "GOOGLE_PLAY_" + default_id.upper() + "_ID"
    return _env_value(env_key) or default_id


def _google_play_status() -> dict:
    package_name = _env_value("GOOGLE_PLAY_PACKAGE_NAME")
    service_account_configured = bool(
        _env_value("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
        or _env_value("GOOGLE_PLAY_SERVICE_ACCOUNT_FILE")
    )
    missing = []
    if not package_name:
        missing.append("GOOGLE_PLAY_PACKAGE_NAME")
    if not service_account_configured:
        missing.append("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON or GOOGLE_PLAY_SERVICE_ACCOUNT_FILE")
    return {
        "ready": not missing,
        "package_name_configured": bool(package_name),
        "service_account_configured": service_account_configured,
        "missing_server_settings": missing,
    }


def _hash_purchase_token(token: str) -> str:
    return hashlib.sha256(str(token or "").strip().encode("utf-8")).hexdigest()


def _parse_google_time(value: str | None):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _subscription_is_active(*, status: str, expiry_time: str) -> bool:
    if status not in {
        "SUBSCRIPTION_STATE_ACTIVE",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
        "SUBSCRIPTION_STATE_CANCELED",
    }:
        return False
    expires_at = _parse_google_time(expiry_time)
    if expires_at is None:
        return status in {"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"}
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    return expires_at > datetime.datetime.now(datetime.timezone.utc)


def _google_play_service_account_info() -> dict:
    raw_json = _env_value("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=503, detail="Google Play service account JSON is invalid.")

    file_path = _env_value("GOOGLE_PLAY_SERVICE_ACCOUNT_FILE")
    if file_path:
        try:
            return json.loads(Path(file_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="Google Play service account file was not found.")
        except json.JSONDecodeError:
            raise HTTPException(status_code=503, detail="Google Play service account file is invalid.")

    raise HTTPException(status_code=503, detail="Google Play service account is not configured.")


def _google_play_access_token() -> str:
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ModuleNotFoundError:
        raise HTTPException(status_code=503, detail="google-auth package is required for Google Play verification.")

    info = _google_play_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    credentials.refresh(Request())
    return credentials.token


def _google_play_headers() -> dict:
    return {"Authorization": f"Bearer {_google_play_access_token()}"}


def _verify_google_play_purchase(
    *,
    package_name: str,
    google_product_id: str,
    purchase_token: str,
    kind: str,
) -> dict:
    if kind != "consumable":
        raise HTTPException(status_code=501, detail="Google Play subscription verification is not implemented yet.")

    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{package_name}/purchases/products/{google_product_id}/tokens/{purchase_token}"
    )
    try:
        response = requests.get(url, headers=_google_play_headers(), timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Google Play purchase verification request failed.")

    if response.status_code == 404:
        raise HTTPException(status_code=402, detail="Google Play purchase token was not found.")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Google Play purchase verification failed.")

    data = response.json()
    purchase_state = "purchased" if int(data.get("purchaseState", -1)) == 0 else "not_purchased"
    return {
        "package_name": package_name,
        "product_id": google_product_id,
        "purchase_state": purchase_state,
        "order_id": str(data.get("orderId") or ""),
        "acknowledgement_state": "acknowledged" if int(data.get("acknowledgementState", 0)) == 1 else "unacknowledged",
        "raw": data,
    }


def _verify_google_play_subscription(
    *,
    package_name: str,
    google_product_id: str,
    purchase_token: str,
) -> dict:
    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{package_name}/purchases/subscriptionsv2/tokens/{purchase_token}"
    )
    try:
        response = requests.get(url, headers=_google_play_headers(), timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Google Play subscription verification request failed.")

    if response.status_code == 404:
        raise HTTPException(status_code=402, detail="Google Play subscription token was not found.")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Google Play subscription verification failed.")

    data = response.json()
    matching_item = None
    for item in data.get("lineItems") or []:
        if item.get("productId") == google_product_id:
            matching_item = item
            break
    if not matching_item:
        raise HTTPException(status_code=400, detail="Google Play subscription product id does not match.")

    auto_renewing = bool((matching_item.get("autoRenewingPlan") or {}).get("autoRenewEnabled"))
    return {
        "package_name": package_name,
        "product_id": google_product_id,
        "subscription_state": str(data.get("subscriptionState") or ""),
        "expiry_time": str(matching_item.get("expiryTime") or ""),
        "latest_order_id": str(matching_item.get("latestSuccessfulOrderId") or data.get("latestOrderId") or ""),
        "auto_renewing": auto_renewing,
        "raw": data,
    }


def _consume_google_play_product(*, package_name: str, google_product_id: str, purchase_token: str) -> bool:
    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{package_name}/purchases/products/{google_product_id}/tokens/{purchase_token}:consume"
    )
    try:
        response = requests.post(url, headers=_google_play_headers(), timeout=10)
    except requests.RequestException:
        return False
    return response.status_code < 400


def _load_google_purchase(token_hash: str):
    conn = _connect_access_db()
    try:
        return conn.execute(
            "SELECT * FROM google_play_purchases WHERE purchase_token_hash = ?",
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()


def _load_google_subscription(user_id: str):
    conn = _connect_access_db()
    try:
        return conn.execute(
            "SELECT * FROM google_play_subscriptions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _load_google_subscription_by_token_hash(token_hash: str):
    conn = _connect_access_db()
    try:
        return conn.execute(
            "SELECT * FROM google_play_subscriptions WHERE purchase_token_hash = ?",
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()


def _user_has_active_subscription(user_id: str) -> bool:
    row = _load_google_subscription(user_id)
    if not row:
        return False
    return _subscription_is_active(
        status=row["status"],
        expiry_time=row["expiry_time"],
    )


def _write_google_purchase(
    conn,
    *,
    token_hash: str,
    user_id: str,
    local_product_id: str,
    google_product_id: str,
    kind: str,
    order_id: str,
):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO google_play_purchases (
            purchase_token_hash,
            user_id,
            local_product_id,
            google_play_product_id,
            kind,
            order_id,
            status,
            granted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_hash,
            user_id,
            local_product_id,
            google_product_id,
            kind,
            str(order_id or ""),
            "applied",
            now,
        ),
    )


def _save_google_subscription(
    *,
    user_id: str,
    token_hash: str,
    local_product_id: str,
    google_product_id: str,
    status: str,
    expiry_time: str,
    auto_renewing: bool,
    latest_order_id: str,
):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = _connect_access_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO google_play_subscriptions (
                user_id,
                purchase_token_hash,
                local_product_id,
                google_play_product_id,
                status,
                expiry_time,
                auto_renewing,
                latest_order_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                token_hash,
                local_product_id,
                google_product_id,
                status,
                expiry_time,
                1 if auto_renewing else 0,
                latest_order_id,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _save_wallet_and_record_google_purchase(
    *,
    wallet: UserWallet,
    token_hash: str,
    user_id: str,
    local_product_id: str,
    google_product_id: str,
    kind: str,
    order_id: str,
):
    conn = _connect_access_db()
    try:
        _write_google_purchase(
            conn,
            token_hash=token_hash,
            user_id=user_id,
            local_product_id=local_product_id,
            google_product_id=google_product_id,
            kind=kind,
            order_id=order_id,
        )
        _write_wallet(conn, user_id, wallet)
        conn.commit()
    finally:
        conn.close()


def sync_google_play_subscription_token(
    *,
    package_name: str,
    purchase_token: str,
    google_product_id: str | None = None,
) -> dict:
    if not str(purchase_token or "").strip():
        raise HTTPException(status_code=400, detail="purchase_token is required.")

    configured_package = _env_value("GOOGLE_PLAY_PACKAGE_NAME")
    normalized_package = str(package_name or configured_package or "").strip()
    if configured_package and normalized_package != configured_package:
        raise HTTPException(status_code=400, detail="Google Play package name does not match server configuration.")

    token_hash = _hash_purchase_token(purchase_token)
    row = _load_google_subscription_by_token_hash(token_hash)
    if not row:
        return {"status": "ignored", "reason": "unknown_subscription_token"}

    expected_google_product_id = row["google_play_product_id"]
    if google_product_id and google_product_id != expected_google_product_id:
        raise HTTPException(status_code=400, detail="Google Play subscription product id does not match stored subscription.")

    verification = _verify_google_play_subscription(
        package_name=normalized_package,
        google_product_id=expected_google_product_id,
        purchase_token=purchase_token,
    )
    status_text = str(verification.get("subscription_state") or "")
    expiry_time = str(verification.get("expiry_time") or "")
    _save_google_subscription(
        user_id=row["user_id"],
        token_hash=token_hash,
        local_product_id=row["local_product_id"],
        google_product_id=expected_google_product_id,
        status=status_text,
        expiry_time=expiry_time,
        auto_renewing=bool(verification.get("auto_renewing")),
        latest_order_id=str(verification.get("latest_order_id") or ""),
    )
    return {
        "status": "active" if _subscription_is_active(status=status_text, expiry_time=expiry_time) else "inactive",
        "user_id": row["user_id"],
        "product_id": row["local_product_id"],
        "subscription_state": status_text,
        "expiry_time": expiry_time,
    }


def _verify_rtdn_oidc_token(authorization: str | None) -> dict:
    audience = _env_value("GOOGLE_PLAY_RTDN_OIDC_AUDIENCE")
    expected_email = _env_value("GOOGLE_PLAY_RTDN_OIDC_EMAIL")
    if not audience and not expected_email:
        return {}

    text = str(authorization or "").strip()
    if not text.lower().startswith("bearer "):
        raise HTTPException(status_code=403, detail="Google Play RTDN OIDC token is required.")
    token = text[7:].strip()
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(token, Request(), audience=audience or None)
    except Exception:
        raise HTTPException(status_code=403, detail="Google Play RTDN OIDC token is invalid.")

    if expected_email and claims.get("email") != expected_email:
        raise HTTPException(status_code=403, detail="Google Play RTDN OIDC email is invalid.")
    if expected_email and claims.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail="Google Play RTDN OIDC email is not verified.")
    return claims


def handle_google_play_rtdn(
    *,
    pubsub_payload: dict,
    shared_token: str | None,
    authorization: str | None = None,
) -> dict:
    configured_token = _env_value("GOOGLE_PLAY_RTDN_SHARED_TOKEN")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Google Play RTDN shared token is not configured.")
    if str(shared_token or "") != configured_token:
        raise HTTPException(status_code=403, detail="Google Play RTDN token is invalid.")
    oidc_claims = _verify_rtdn_oidc_token(authorization)

    message = (pubsub_payload or {}).get("message") or {}
    encoded_data = message.get("data")
    if not encoded_data:
        raise HTTPException(status_code=400, detail="Pub/Sub message data is required.")
    try:
        decoded = base64.b64decode(encoded_data).decode("utf-8")
        notification = json.loads(decoded)
    except Exception:
        raise HTTPException(status_code=400, detail="Pub/Sub message data is invalid.")

    subscription_notification = notification.get("subscriptionNotification")
    if subscription_notification:
        result = sync_google_play_subscription_token(
            package_name=str(notification.get("packageName") or ""),
            purchase_token=subscription_notification.get("purchaseToken") or "",
        )
        result["notification_type"] = subscription_notification.get("notificationType")
        result["message_id"] = message.get("messageId") or message.get("message_id") or ""
        if oidc_claims:
            result["oidc_verified"] = True
        return result

    if notification.get("testNotification") is not None:
        result = {"status": "test", "message_id": message.get("messageId") or message.get("message_id") or ""}
        if oidc_claims:
            result["oidc_verified"] = True
        return result

    return {"status": "ignored", "reason": "unsupported_notification"}


def get_product_catalog() -> dict:
    return {
        "consumables": {
            product_id: {
                **product,
                "google_play_product_id": _google_play_id(product_id),
            }
            for product_id, product in PRODUCTS.items()
        },
        "subscriptions": {
            product_id: {
                **product,
                "google_play_product_id": _google_play_id(product_id),
            }
            for product_id, product in SUBSCRIPTIONS.items()
        },
        "google_play": _google_play_status(),
        "settings": {
            "allow_advanced_ticket_for_basic": _allow_advanced_for_basic(),
        },
    }


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


def _plan_for(user_id: str, entitlement_token: str | None) -> str:
    dev_pro_token = _env_value("ALPHAMATE_DEV_PRO_ENTITLEMENT_TOKEN") or "dev-pro-entitlement"
    if _dev_access_enabled() and str(entitlement_token or "").strip() == dev_pro_token:
        return "pro"
    if _user_has_active_subscription(user_id):
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
    plan = _plan_for(user_id, entitlement_token)
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        _save_wallet(user_id, wallet)
        data = _wallet_snapshot(wallet, plan)
    data["user"] = {"id": user_id, "auth_mode": auth_mode}
    return data


def apply_dev_purchase(*, authorization: str | None, entitlement_token: str | None, product_id: str) -> dict:
    if not _dev_access_enabled():
        raise HTTPException(status_code=403, detail="Development purchase is disabled.")
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=400, detail="Unknown product id.")
    user_id, _ = _authenticate(authorization)
    plan = _plan_for(user_id, entitlement_token)
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        product = PRODUCTS[product_id]
        if product["kind"] == "basic":
            wallet.purchased_basic += product["quantity"]
        else:
            wallet.purchased_advanced += product["quantity"]
        _save_wallet(user_id, wallet)
        return _wallet_snapshot(wallet, plan)


def apply_google_play_purchase(
    *,
    authorization: str | None,
    product_id: str,
    purchase_token: str,
    package_name: str | None = None,
) -> dict:
    if product_id not in PRODUCTS and product_id not in SUBSCRIPTIONS:
        raise HTTPException(status_code=400, detail="Unknown product id.")
    if not str(purchase_token or "").strip():
        raise HTTPException(status_code=400, detail="purchase_token is required.")

    user_id, _ = _authenticate(authorization)
    status = _google_play_status()
    if not status["ready"]:
        raise HTTPException(status_code=503, detail="Google Play Billing verification is not configured.")

    configured_package = _env_value("GOOGLE_PLAY_PACKAGE_NAME")
    if package_name and configured_package and package_name != configured_package:
        raise HTTPException(status_code=400, detail="Google Play package name does not match server configuration.")

    google_product_id = _google_play_id(product_id)
    normalized_package = package_name or configured_package
    token_hash = _hash_purchase_token(purchase_token)
    plan = _plan_for(user_id, None)

    if product_id in SUBSCRIPTIONS:
        verification = _verify_google_play_subscription(
            package_name=normalized_package,
            google_product_id=google_product_id,
            purchase_token=purchase_token,
        )
        if str(verification.get("product_id") or "") != google_product_id:
            raise HTTPException(status_code=400, detail="Google Play product id does not match the requested product.")
        if str(verification.get("package_name") or normalized_package) != normalized_package:
            raise HTTPException(status_code=400, detail="Google Play package name does not match the requested package.")

        status_text = str(verification.get("subscription_state") or "")
        expiry_time = str(verification.get("expiry_time") or "")
        if not _subscription_is_active(status=status_text, expiry_time=expiry_time):
            _save_google_subscription(
                user_id=user_id,
                token_hash=token_hash,
                local_product_id=product_id,
                google_product_id=google_product_id,
                status=status_text,
                expiry_time=expiry_time,
                auto_renewing=bool(verification.get("auto_renewing")),
                latest_order_id=str(verification.get("latest_order_id") or ""),
            )
            raise HTTPException(status_code=402, detail="Google Play subscription is not active.")

        _save_google_subscription(
            user_id=user_id,
            token_hash=token_hash,
            local_product_id=product_id,
            google_product_id=google_product_id,
            status=status_text,
            expiry_time=expiry_time,
            auto_renewing=bool(verification.get("auto_renewing")),
            latest_order_id=str(verification.get("latest_order_id") or ""),
        )
        with _WALLET_LOCK:
            wallet = _wallet_for(user_id)
            snapshot = _wallet_snapshot(wallet, "pro")
        snapshot["purchase"] = {
            "status": "active",
            "product_id": product_id,
            "kind": "pro",
            "expiry_time": expiry_time,
            "auto_renewing": bool(verification.get("auto_renewing")),
        }
        return snapshot

    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        existing = _load_google_purchase(token_hash)
        if existing:
            snapshot = _wallet_snapshot(wallet, plan)
            snapshot["purchase"] = {
                "status": "already_applied",
                "product_id": existing["local_product_id"],
                "kind": existing["kind"],
            }
            return snapshot

    verification = _verify_google_play_purchase(
        package_name=normalized_package,
        google_product_id=google_product_id,
        purchase_token=purchase_token,
        kind="consumable",
    )
    if str(verification.get("product_id") or "") != google_product_id:
        raise HTTPException(status_code=400, detail="Google Play product id does not match the requested product.")
    if str(verification.get("package_name") or normalized_package) != normalized_package:
        raise HTTPException(status_code=400, detail="Google Play package name does not match the requested package.")
    if verification.get("purchase_state") != "purchased":
        raise HTTPException(status_code=402, detail="Google Play purchase is not completed.")

    product = PRODUCTS[product_id]
    with _WALLET_LOCK:
        wallet = _wallet_for(user_id)
        existing = _load_google_purchase(token_hash)
        if existing:
            snapshot = _wallet_snapshot(wallet, plan)
            snapshot["purchase"] = {
                "status": "already_applied",
                "product_id": existing["local_product_id"],
                "kind": existing["kind"],
            }
            return snapshot
        if product["kind"] == "basic":
            wallet.purchased_basic += product["quantity"]
        else:
            wallet.purchased_advanced += product["quantity"]
        _save_wallet_and_record_google_purchase(
            wallet=wallet,
            token_hash=token_hash,
            user_id=user_id,
            local_product_id=product_id,
            google_product_id=google_product_id,
            kind=product["kind"],
            order_id=str(verification.get("order_id") or ""),
        )
        snapshot = _wallet_snapshot(wallet, plan)

    consumed = _consume_google_play_product(
        package_name=normalized_package,
        google_product_id=google_product_id,
        purchase_token=purchase_token,
    )
    snapshot["purchase"] = {
        "status": "applied",
        "product_id": product_id,
        "kind": product["kind"],
        "quantity": product["quantity"],
        "consumed": consumed,
    }
    return snapshot


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
    plan = _plan_for(user_id, entitlement_token)
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
