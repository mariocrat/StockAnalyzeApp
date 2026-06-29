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


OWNER_NEXT_ACTION_HINTS = {
    "OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY": "OpenAI API Key를 발급해서 서버 설정에 넣기",
    "ALPHAMATE_ADMIN_TOKEN": "generate_release_secrets.bat를 실행해서 운영 로그 관리자 토큰 빈 값을 채우기",
    "ALPHAMATE_ADMIN_TOKEN_MIN_LENGTH_32": "generate_release_secrets.bat를 실행해서 운영 로그 관리자 토큰 빈 값을 채우기",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE existing JSON file": "Google Play 서비스 계정 JSON 파일을 서버에 저장하고 경로 연결하기",
    "GOOGLE_PLAY_RTDN_SHARED_TOKEN": "generate_release_secrets.bat를 실행해서 Google Play 결제 알림용 공유 토큰 빈 값을 채우기",
    "KAKAO_CLIENT_ID": "카카오 개발자 콘솔에서 REST API Key를 확인해 서버 설정에 넣기",
    "KAKAO_CLIENT_SECRET": "카카오 Client Secret 사용 여부를 정하고 서버 설정에 넣기",
    "NAVER_CLIENT_ID": "네이버 개발자 센터에서 Client ID를 확인해 서버 설정에 넣기",
    "NAVER_CLIENT_SECRET": "네이버 Client Secret을 확인해 서버 설정에 넣기",
}

OWNER_NEXT_ACTION_LINKS = {
    "OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY": "https://platform.openai.com/api-keys",
    "KAKAO_CLIENT_ID": "https://developers.kakao.com/console/app",
    "KAKAO_CLIENT_SECRET": "https://developers.kakao.com/console/app",
    "NAVER_CLIENT_ID": "https://developers.naver.com/apps/",
    "NAVER_CLIENT_SECRET": "https://developers.naver.com/apps/",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE existing JSON file": "https://console.cloud.google.com/iam-admin/serviceaccounts",
}

OWNER_REQUIRED_INPUTS = {
    "OPENAI_API_KEY or ALPHAMATE_OPENAI_API_KEY": "OpenAI API Key 값",
    "KAKAO_CLIENT_ID": "카카오 REST API Key 값",
    "KAKAO_CLIENT_SECRET": "카카오 Client Secret 값 또는 미사용 결정",
    "NAVER_CLIENT_ID": "네이버 Client ID 값",
    "NAVER_CLIENT_SECRET": "네이버 Client Secret 값",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE existing JSON file": "Google Play 서비스 계정 JSON 파일",
}


def _owner_next_action_text(item: str) -> str:
    provider = ""
    setting = item
    if ": " in item:
        provider, setting = item.split(": ", 1)

    hint = OWNER_NEXT_ACTION_HINTS.get(setting)
    if not hint:
        return item

    provider_labels = {
        "kakao": "카카오",
        "naver": "네이버",
    }
    provider_label = provider_labels.get(provider)
    prefix = f"{provider_label}: " if provider_label else ""
    link = OWNER_NEXT_ACTION_LINKS.get(setting)
    suffix = f" - {link}" if link else ""
    return f"{prefix}{hint} ({item}){suffix}"


def _owner_required_inputs(items: list[str]) -> list[str]:
    inputs = []
    for item in items:
        setting = item.split(": ", 1)[1] if ": " in item else item
        if setting in OWNER_REQUIRED_INPUTS:
            inputs.append(OWNER_REQUIRED_INPUTS[setting])
    return list(dict.fromkeys(inputs))


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
            lines.append(f"{index}. {_owner_next_action_text(item)}")
        if len(next_actions) > 10:
            lines.append(f"- 그 외 누락 항목 {len(next_actions) - 10}개")
    else:
        lines.append("1. 출시 전 실제 기기 로그인, 결제, 광고, AI 복기를 수동으로 확인하세요.")

    required_inputs = _owner_required_inputs(next_actions)
    if required_inputs:
        lines.extend(["", "내가 나중에 받아야 하는 정보/파일:"])
        for index, item in enumerate(required_inputs, start=1):
            lines.append(f"{index}. {item}")

    lines.extend([
        "",
        "주의: 이 보고서는 필요한 설정 이름만 보여주고 API Key, 토큰, 서비스 계정 원문은 출력하지 않습니다.",
    ])
    return "\n".join(lines)
