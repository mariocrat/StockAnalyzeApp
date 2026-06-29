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


OWNER_SECTION_LABELS = {
    "ai": "AI 복기",
    "login": "카카오/네이버 로그인",
    "data_storage": "운영 데이터 저장소",
    "admin": "운영 로그 관리자",
    "privacy_policy": "개인정보처리방침",
    "google_play": "Google Play 결제",
    "admob": "AdMob 광고",
}


def _section_missing_items(section: dict) -> list[str]:
    missing = [str(item) for item in section.get("missing_server_settings", [])]
    providers = section.get("providers", {})
    for provider_name, provider in providers.items():
        for item in provider.get("missing_server_settings", []):
            missing.append(f"{provider_name}: {item}")
    return missing


def format_owner_release_readiness_report(result: dict) -> str:
    readiness = result.get("readiness", {})
    sections = readiness.get("sections", {})
    total_sections = len(sections)
    ready_sections = sum(1 for section in sections.values() if section.get("ready"))
    ready_percent = round((ready_sections / total_sections) * 100) if total_sections else 0
    lines = [
        "AlphaMate 출시 준비 보고서",
        "",
        f"전체 상태: {'준비됨' if result.get('ok') else '준비 필요'}",
        f"준비율: {ready_sections}/{total_sections} ({ready_percent}%)",
        "",
        "항목별 상태:",
    ]

    next_actions = []
    for section_name, section in sections.items():
        label = OWNER_SECTION_LABELS.get(section_name, section_name)
        ready = bool(section.get("ready"))
        lines.append(f"- [{'준비됨' if ready else '필요'}] {label}")
        missing_items = _section_missing_items(section)
        if not ready and missing_items:
            next_actions.extend(missing_items)
            for item in missing_items[:5]:
                lines.append(f"  - 필요한 설정: {item}")
            if len(missing_items) > 5:
                lines.append(f"  - 추가 누락 설정 {len(missing_items) - 5}개")

    lines.extend(["", "다음에 할 일:"])
    if next_actions:
        for index, item in enumerate(next_actions[:10], start=1):
            lines.append(f"{index}. {item}")
        if len(next_actions) > 10:
            lines.append(f"- 그 외 누락 항목 {len(next_actions) - 10}개")
    else:
        lines.append("1. 출시 전 실제 기기 로그인, 결제, 광고, AI 복기를 수동으로 확인하세요.")

    lines.extend([
        "",
        "주의: 이 보고서는 필요한 설정 이름만 보여주고 API Key, 토큰, 서비스 계정 원문은 출력하지 않습니다.",
    ])
    return "\n".join(lines)
