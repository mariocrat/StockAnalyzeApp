import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.env import env_value


FRONTEND_ENV_DEFAULT = ROOT / "frontend" / ".env.release"
EXPECTED_RELEASE_PACKAGE_NAME = "com.mariocrat.stockanalyze"

ALIGNMENT_PAIRS = [
    ("GOOGLE_PLAY_PACKAGE_NAME", "VITE_GOOGLE_PLAY_PACKAGE_NAME"),
    ("ALPHAMATE_OAUTH_APP_SCHEME", "VITE_GOOGLE_PLAY_PACKAGE_NAME"),
    ("KAKAO_CLIENT_ID", "VITE_KAKAO_REST_API_KEY"),
    ("KAKAO_REDIRECT_URI", "VITE_KAKAO_REDIRECT_URI"),
    ("NAVER_CLIENT_ID", "VITE_NAVER_CLIENT_ID"),
    ("NAVER_REDIRECT_URI", "VITE_NAVER_REDIRECT_URI"),
    ("ADMOB_REWARDED_AD_UNIT_ID", "VITE_ADMOB_REWARDED_AD_UNIT_ID"),
]


def _read_env_file(path: Path) -> dict:
    values = {}
    try:
        if not path.exists():
            return values
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    except Exception:
        return {}
    return values


def _frontend_env_values() -> dict:
    configured = os.environ.get("ALPHAMATE_FRONTEND_ENV_FILE", "").strip()
    env_file = Path(configured) if configured else FRONTEND_ENV_DEFAULT
    values = _read_env_file(env_file)
    for key in [frontend_key for _, frontend_key in ALIGNMENT_PAIRS]:
        if os.environ.get(key):
            values[key] = os.environ[key].strip()
    return values


def validate_release_alignment() -> dict:
    frontend_env = _frontend_env_values()
    errors = []
    checked = []
    for backend_key, frontend_key in ALIGNMENT_PAIRS:
        backend_value = env_value(backend_key)
        frontend_value = str(frontend_env.get(frontend_key) or "").strip()
        if not backend_value or not frontend_value:
            continue
        checked.append({"backend": backend_key, "frontend": frontend_key})
        if backend_value != frontend_value:
            errors.append(f"{backend_key} must match {frontend_key}")
    backend_package = env_value("GOOGLE_PLAY_PACKAGE_NAME")
    backend_oauth_app_scheme = env_value("ALPHAMATE_OAUTH_APP_SCHEME")
    frontend_package = str(frontend_env.get("VITE_GOOGLE_PLAY_PACKAGE_NAME") or "").strip()
    if backend_package and backend_oauth_app_scheme and backend_package != backend_oauth_app_scheme:
        checked.append({"backend": "ALPHAMATE_OAUTH_APP_SCHEME", "frontend": "GOOGLE_PLAY_PACKAGE_NAME"})
        errors.append("ALPHAMATE_OAUTH_APP_SCHEME must match GOOGLE_PLAY_PACKAGE_NAME")
    if backend_package and backend_package != EXPECTED_RELEASE_PACKAGE_NAME:
        errors.append("GOOGLE_PLAY_PACKAGE_NAME must be com.mariocrat.stockanalyze")
    if frontend_package and frontend_package != EXPECTED_RELEASE_PACKAGE_NAME:
        errors.append("VITE_GOOGLE_PLAY_PACKAGE_NAME must be com.mariocrat.stockanalyze")
    if not checked:
        errors.append("No comparable server/app release settings were found")
    return {
        "ok": not errors,
        "errors": errors,
        "checked": checked,
    }


def format_release_alignment_report(result: dict) -> str:
    lines = [
        "AlphaMate 서버/앱 설정 일치 보고서",
        "",
        f"전체 상태: {'준비됨' if result.get('ok') else '준비 필요'}",
    ]
    if result.get("ok"):
        lines.append("- 서버와 앱의 출시 설정이 서로 맞습니다.")
        lines.append("- Google Play 패키지명, 카카오/네이버 공개 Client ID와 Redirect URI, AdMob 보상형 광고 단위가 일치합니다.")
        lines.append("- 이 보고서는 서버와 앱 설정이 서로 같은지만 확인합니다. 운영 값 준비 여부는 위의 Backend/Frontend 출시 준비 보고서를 기준으로 보세요.")
    else:
        lines.extend([
            "",
            "다음 작업:",
            "1. 서버와 앱 출시 설정 파일을 먼저 채우기 (.env.release, frontend/.env.release)",
            "2. 서버 설정과 앱 설정을 같은 값으로 맞추기",
            "",
            "확인할 항목:",
        ])
        for error in result.get("errors", []):
            lines.append(f"- {error}")
    lines.extend([
        "",
        "주의: 이 보고서는 설정 이름만 보여주고 실제 URL, 패키지명, Key 값은 출력하지 않습니다.",
    ])
    return "\n".join(lines)

def main() -> int:
    result = validate_release_alignment()
    print(format_release_alignment_report(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
