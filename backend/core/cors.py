try:
    from core.env import env_value
except ModuleNotFoundError:
    from backend.core.env import env_value


DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "capacitor://localhost",
    "ionic://localhost",
]


def allowed_cors_origins() -> list[str]:
    configured = env_value("ALPHAMATE_CORS_ORIGINS")
    if not configured:
        return list(DEFAULT_CORS_ORIGINS)

    origins = []
    seen = set()
    for item in configured.split(","):
        origin = item.strip().rstrip("/")
        if not origin or origin in seen:
            continue
        seen.add(origin)
        origins.append(origin)
    return origins or list(DEFAULT_CORS_ORIGINS)
