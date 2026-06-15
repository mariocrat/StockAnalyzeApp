import requests
from fastapi import HTTPException

try:
    from core.account_store import _env_value, login_provider_identity
except ModuleNotFoundError:
    from backend.core.account_store import _env_value, login_provider_identity


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"


def _exchange_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    try:
        response = requests.post(
            url,
            data=payload,
            headers=headers or {},
            timeout=8,
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
            timeout=8,
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

    return login_provider_identity(**profile)


def _configured_redirect_uri(provider: str, redirect_uri: str) -> str:
    configured = _env_value(f"{provider.upper()}_REDIRECT_URI")
    value = str(redirect_uri or configured or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="redirect_uri is required.")
    return value


def _require_config(name: str) -> str:
    value = _env_value(name)
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured.")
    return value


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
