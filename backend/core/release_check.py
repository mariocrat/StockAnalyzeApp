from .env import env_value
from .readiness import get_app_readiness


def _env_value(name: str) -> str:
    return env_value(name)


def _collect_section_errors(section_name: str, section: dict) -> list[str]:
    errors = []
    for item in section.get("missing_server_settings", []):
        errors.append(f"{section_name}: {item}")

    providers = section.get("providers", {})
    for provider_name, provider in providers.items():
        for item in provider.get("missing_server_settings", []):
            errors.append(f"{section_name}.{provider_name}: {item}")
    return errors


def validate_backend_release_env() -> dict:
    errors = []
    if _env_value("ALPHAMATE_ENV").lower() != "production":
        errors.append("ALPHAMATE_ENV must be production")

    readiness = get_app_readiness()
    for section_name, section in readiness.get("sections", {}).items():
        if not section.get("ready"):
            errors.extend(_collect_section_errors(section_name, section))

    return {
        "ok": not errors,
        "errors": errors,
        "readiness": readiness,
    }


def format_backend_release_check(result: dict) -> str:
    if result.get("ok"):
        return "Backend release environment check passed."

    lines = ["Backend release environment check failed:"]
    for error in result.get("errors", []):
        lines.append(f"- {error}")
    return "\n".join(lines)
