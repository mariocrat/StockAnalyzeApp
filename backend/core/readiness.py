from .access_control import get_product_catalog
from .env import env_value
from .oauth_login import get_oauth_config_status

REQUIRED_DATA_STORAGE_SETTINGS = [
    "ALPHAMATE_ACCOUNT_DB_PATH",
    "ALPHAMATE_JOURNAL_DB_PATH",
    "ALPHAMATE_ACCESS_DB_PATH",
    "ALPHAMATE_REVIEW_HISTORY_DB_PATH",
    "ALPHAMATE_EVENT_LOG_DB_PATH",
]
PRIVACY_POLICY_URL_SETTING = "ALPHAMATE_PRIVACY_POLICY_URL"
ADMIN_TOKEN_SETTING = "ALPHAMATE_ADMIN_TOKEN"
ADMIN_TOKEN_MIN_LENGTH = 32
PLACEHOLDER_URL_PARTS = ("example.com", "your-api", "your-app", "your-domain", "your-site")


def _env_value(name: str) -> str:
    return env_value(name)


def _ai_status() -> dict:
    configured = bool(_env_value("OPENAI_API_KEY") or _env_value("ALPHAMATE_OPENAI_API_KEY"))
    missing = [] if configured else ["OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY"]
    return {
        "ready": configured,
        "missing_server_settings": missing,
        "required_server_settings": ["OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY"],
    }


def _login_status() -> dict:
    status = get_oauth_config_status()
    providers = status.get("providers", {})
    ready = all(provider.get("server_ready") for provider in providers.values())
    return {
        "ready": ready,
        "providers": providers,
        "frontend_public_settings": {
            "kakao": ["VITE_KAKAO_REST_API_KEY", "VITE_KAKAO_REDIRECT_URI"],
            "naver": ["VITE_NAVER_CLIENT_ID", "VITE_NAVER_REDIRECT_URI"],
        },
    }


def _data_storage_status() -> dict:
    missing = [name for name in REQUIRED_DATA_STORAGE_SETTINGS if not _env_value(name)]
    return {
        "ready": not missing,
        "missing_server_settings": missing,
        "required_server_settings": REQUIRED_DATA_STORAGE_SETTINGS,
        "note": "Production deployments should use explicit persistent server-side database paths or managed volumes.",
    }


def _privacy_policy_status() -> dict:
    url = _env_value(PRIVACY_POLICY_URL_SETTING).strip()
    valid_url = url.startswith("https://")
    placeholder = any(part in url for part in PLACEHOLDER_URL_PARTS)
    missing = []
    if not valid_url:
        missing.append(PRIVACY_POLICY_URL_SETTING)
    elif placeholder:
        missing.append(f"{PRIVACY_POLICY_URL_SETTING}_PLACEHOLDER")
    return {
        "ready": valid_url and not placeholder,
        "url": url if valid_url and not placeholder else "",
        "missing_server_settings": missing,
        "required_server_settings": [PRIVACY_POLICY_URL_SETTING],
        "note": "Google Play release should point to a public HTTPS privacy policy URL.",
    }


def _admin_status() -> dict:
    token = _env_value(ADMIN_TOKEN_SETTING)
    configured = bool(token)
    strong_enough = len(token) >= ADMIN_TOKEN_MIN_LENGTH
    missing = []
    if not configured:
        missing.append(ADMIN_TOKEN_SETTING)
    elif not strong_enough:
        missing.append(f"{ADMIN_TOKEN_SETTING}_MIN_LENGTH_{ADMIN_TOKEN_MIN_LENGTH}")
    return {
        "ready": configured and strong_enough,
        "missing_server_settings": missing,
        "required_server_settings": [ADMIN_TOKEN_SETTING],
        "note": f"Required for protected operational event log lookup. Use at least {ADMIN_TOKEN_MIN_LENGTH} random characters.",
    }


def get_app_readiness() -> dict:
    catalog = get_product_catalog()
    sections = {
        "ai": _ai_status(),
        "login": _login_status(),
        "data_storage": _data_storage_status(),
        "admin": _admin_status(),
        "privacy_policy": _privacy_policy_status(),
        "google_play": catalog["google_play"],
        "admob": catalog["admob"],
    }
    return {
        "overall_ready": all(section.get("ready") for section in sections.values()),
        "sections": sections,
        "notes": [
            "Secret values are never returned by this endpoint.",
            "Frontend VITE_* settings must be checked in the app build environment.",
        ],
    }
