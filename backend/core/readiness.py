import os

from .access_control import get_product_catalog
from .oauth_login import get_oauth_config_status


def _env_value(name: str) -> str:
    return os.getenv(name, "").strip()


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


def get_app_readiness() -> dict:
    catalog = get_product_catalog()
    sections = {
        "ai": _ai_status(),
        "login": _login_status(),
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
