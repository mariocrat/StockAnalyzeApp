import requests
from fastapi import HTTPException

try:
    from core.account_store import login_provider_identity
except ModuleNotFoundError:
    from backend.core.account_store import login_provider_identity


KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"


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
