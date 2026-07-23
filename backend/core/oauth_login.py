import requests
import secrets
import threading
import time
from fastapi import HTTPException
from urllib.parse import urlencode, urlparse

try:
    from core.account_store import _env_value, login_provider_identity
    from core.access_control import grant_first_login_advanced_review
except ModuleNotFoundError:
    from backend.core.account_store import _env_value, login_provider_identity
    from backend.core.access_control import grant_first_login_advanced_review


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"
OAUTH_TIMEOUT_DEFAULT_SECONDS = 8
OAUTH_TIMEOUT_MAX_SECONDS = 20
PLACEHOLDER_URL_PARTS = ("example.com", "your-api", "your-app", "your-domain", "your-site")
LOCAL_REDIRECT_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
OAUTH_APP_TICKET_DEFAULT_SECONDS = 180
OAUTH_APP_TICKET_MAX_SECONDS = 600
OAUTH_APP_TICKETS = {}
OAUTH_APP_TICKET_LOCK = threading.Lock()


def _env_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(_env_value(name))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _oauth_timeout_seconds() -> int:
    return _env_int("ALPHAMATE_OAUTH_TIMEOUT_SECONDS", OAUTH_TIMEOUT_DEFAULT_SECONDS, 2, OAUTH_TIMEOUT_MAX_SECONDS)


def _is_placeholder_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and any(part in text for part in PLACEHOLDER_URL_PARTS)


def _redirect_uri_problem(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except Exception:
        return "INVALID"
    if not parsed.scheme or not parsed.netloc:
        return "INVALID"
    host = (parsed.hostname or "").lower()
    if host in LOCAL_REDIRECT_HOSTS or host.startswith("127."):
        return "LOCALHOST"
    if parsed.scheme != "https":
        return "NOT_HTTPS"
    if _is_placeholder_url(text):
        return "PLACEHOLDER"
    return ""


def _is_production() -> bool:
    return _env_value("ALPHAMATE_ENV").lower() == "production"


def _exchange_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    try:
        response = requests.post(
            url,
            data=payload,
            headers=headers or {},
            timeout=_oauth_timeout_seconds(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Login provider token endpoint did not respond.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login provider authorization code exchange failed.")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Login provider returned an invalid token response.") from exc


def _request_json(url: str, access_token: str) -> dict:
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_oauth_timeout_seconds(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Login provider did not respond.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login provider token verification failed.")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Login provider returned an invalid response.") from exc


def _kakao_profile(access_token: str) -> dict:
    data = _request_json(KAKAO_USER_INFO_URL, access_token)
    provider_user_id = str(data.get("id") or "").strip()
    account = data.get("kakao_account") or {}
    profile = account.get("profile") or {}
    if not provider_user_id:
        raise HTTPException(status_code=401, detail="Kakao profile did not include a user id.")
    return {
        "provider": "kakao",
        "provider_user_id": provider_user_id,
        "display_name": profile.get("nickname") or "",
        "email": account.get("email") or "",
    }


def _naver_profile(access_token: str) -> dict:
    data = _request_json(NAVER_PROFILE_URL, access_token)
    profile = data.get("response") or {}
    provider_user_id = str(profile.get("id") or "").strip()
    if not provider_user_id:
        raise HTTPException(status_code=401, detail="Naver profile did not include a user id.")
    return {
        "provider": "naver",
        "provider_user_id": provider_user_id,
        "display_name": profile.get("nickname") or profile.get("name") or "",
        "email": profile.get("email") or "",
    }


def login_oauth_provider(*, provider: str, access_token: str) -> dict:
    token = str(access_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="access_token is required.")

    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "kakao":
        profile = _kakao_profile(token)
    elif normalized_provider == "naver":
        profile = _naver_profile(token)
    else:
        raise HTTPException(status_code=400, detail="Unsupported login provider.")

    session = login_provider_identity(**profile)
    grant_first_login_advanced_review(session["user"]["id"])
    return session


def _configured_redirect_uri(provider: str, redirect_uri: str) -> str:
    configured = _env_value(f"{provider.upper()}_REDIRECT_URI")
    requested = str(redirect_uri or "").strip()
    configured = str(configured or "").strip()
    if _is_production():
        if not configured or _redirect_uri_problem(configured):
            raise HTTPException(status_code=503, detail=f"{provider.upper()}_REDIRECT_URI is not configured.")
        if requested and requested != configured:
            raise HTTPException(status_code=400, detail="redirect_uri does not match the server configuration.")
        return configured

    value = str(requested or configured or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="redirect_uri is required.")
    return value


def _require_config(name: str) -> str:
    value = _env_value(name)
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured.")
    return value


def get_oauth_config_status() -> dict:
    kakao_required = ["KAKAO_CLIENT_ID"]
    naver_required = ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"]

    def provider_status(required: list[str], optional: list[str], placeholder_checks: dict[str, str]) -> dict:
        effective_required = list(required)
        effective_optional = list(optional)
        if _is_production():
            for setting_name in placeholder_checks:
                if setting_name not in effective_required:
                    effective_required.append(setting_name)
                if setting_name in effective_optional:
                    effective_optional.remove(setting_name)

        missing = [name for name in effective_required if not _env_value(name)]
        for setting_name, placeholder_key in placeholder_checks.items():
            problem = _redirect_uri_problem(_env_value(setting_name))
            if problem == "PLACEHOLDER":
                missing.append(placeholder_key)
            elif problem:
                missing.append(f"{setting_name}_{problem}")
        return {
            "server_ready": not missing,
            "missing_server_settings": missing,
            "required_server_settings": effective_required,
            "optional_server_settings": effective_optional,
        }

    return {
        "providers": {
            "kakao": provider_status(
                kakao_required,
                ["KAKAO_CLIENT_SECRET", "KAKAO_REDIRECT_URI"],
                {"KAKAO_REDIRECT_URI": "KAKAO_REDIRECT_URI_PLACEHOLDER"},
            ),
            "naver": provider_status(
                naver_required,
                ["NAVER_REDIRECT_URI"],
                {"NAVER_REDIRECT_URI": "NAVER_REDIRECT_URI_PLACEHOLDER"},
            ),
        }
    }


def _exchange_kakao_code(*, code: str, redirect_uri: str) -> str:
    payload = {
        "grant_type": "authorization_code",
        "client_id": _require_config("KAKAO_CLIENT_ID"),
        "redirect_uri": _configured_redirect_uri("kakao", redirect_uri),
        "code": code,
    }
    client_secret = _env_value("KAKAO_CLIENT_SECRET")
    if client_secret:
        payload["client_secret"] = client_secret
    token_data = _exchange_json(
        KAKAO_TOKEN_URL,
        payload,
        {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
    )
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=502, detail="Kakao token response did not include access_token.")
    return access_token


def _exchange_naver_code(*, code: str, redirect_uri: str, state: str) -> str:
    payload = {
        "grant_type": "authorization_code",
        "client_id": _require_config("NAVER_CLIENT_ID"),
        "client_secret": _require_config("NAVER_CLIENT_SECRET"),
        "redirect_uri": _configured_redirect_uri("naver", redirect_uri),
        "code": code,
        "state": str(state or "").strip(),
    }
    if not payload["state"]:
        raise HTTPException(status_code=400, detail="state is required for Naver login.")
    token_data = _exchange_json(NAVER_TOKEN_URL, payload)
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=502, detail="Naver token response did not include access_token.")
    return access_token



def _oauth_app_scheme() -> str:
    return (_env_value("ALPHAMATE_OAUTH_APP_SCHEME") or "com.mariocrat.stockanalyze").strip()


def _oauth_app_ticket_ttl_seconds() -> int:
    return _env_int("ALPHAMATE_OAUTH_APP_TICKET_TTL_SECONDS", OAUTH_APP_TICKET_DEFAULT_SECONDS, 30, OAUTH_APP_TICKET_MAX_SECONDS)


def _normalize_oauth_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in {"kakao", "naver"}:
        raise HTTPException(status_code=400, detail="Unsupported login provider.")
    return normalized


def _purge_expired_oauth_app_tickets(now: float) -> None:
    expired = [ticket for ticket, payload in OAUTH_APP_TICKETS.items() if payload["expires_at"] <= now]
    for ticket in expired:
        OAUTH_APP_TICKETS.pop(ticket, None)


def _issue_oauth_app_ticket(session: dict) -> tuple[str, int]:
    ttl = _oauth_app_ticket_ttl_seconds()
    now = time.time()
    ticket = secrets.token_urlsafe(32)
    with OAUTH_APP_TICKET_LOCK:
        _purge_expired_oauth_app_tickets(now)
        OAUTH_APP_TICKETS[ticket] = {
            "session": session,
            "expires_at": now + ttl,
        }
    return ticket, ttl


def create_oauth_app_redirect(*, provider: str, code: str, state: str = "") -> str:
    normalized_provider = _normalize_oauth_provider(provider)
    auth_code = str(code or "").strip()
    if not auth_code:
        raise HTTPException(status_code=400, detail="code is required.")
    session = login_oauth_code(
        provider=normalized_provider,
        code=auth_code,
        redirect_uri="",
        state=state,
    )
    ticket, ttl = _issue_oauth_app_ticket(session)
    query = urlencode({
        "ticket": ticket,
        "state": str(state or "").strip(),
        "expires_in": str(ttl),
    })
    return f"{_oauth_app_scheme()}://oauth/{normalized_provider}?{query}"


def create_oauth_app_error_redirect(*, provider: str, state: str = "", error: str = "oauth_cancelled") -> str:
    normalized_provider = _normalize_oauth_provider(provider)
    query = urlencode({
        "error": str(error or "oauth_cancelled").strip(),
        "state": str(state or "").strip(),
    })
    return f"{_oauth_app_scheme()}://oauth/{normalized_provider}?{query}"


def consume_oauth_app_ticket(ticket: str) -> dict:
    token = str(ticket or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="ticket is required.")
    now = time.time()
    with OAUTH_APP_TICKET_LOCK:
        _purge_expired_oauth_app_tickets(now)
        payload = OAUTH_APP_TICKETS.pop(token, None)
    if not payload:
        raise HTTPException(status_code=401, detail="OAuth app login ticket is invalid or expired.")
    if payload["expires_at"] <= now:
        raise HTTPException(status_code=401, detail="OAuth app login ticket is invalid or expired.")
    return payload["session"]

def login_oauth_code(*, provider: str, code: str, redirect_uri: str = "", state: str = "") -> dict:
    normalized_provider = str(provider or "").strip().lower()
    auth_code = str(code or "").strip()
    if not auth_code:
        raise HTTPException(status_code=400, detail="code is required.")

    if normalized_provider == "kakao":
        access_token = _exchange_kakao_code(code=auth_code, redirect_uri=redirect_uri)
    elif normalized_provider == "naver":
        access_token = _exchange_naver_code(code=auth_code, redirect_uri=redirect_uri, state=state)
    else:
        raise HTTPException(status_code=400, detail="Unsupported login provider.")
    return login_oauth_provider(provider=normalized_provider, access_token=access_token)
