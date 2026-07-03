import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.env import env_value


FRONTEND_ENV_DEFAULT = ROOT / "frontend" / ".env.release"
ALIGNMENT_PAIRS = [
    ("GOOGLE_PLAY_PACKAGE_NAME", "VITE_GOOGLE_PLAY_PACKAGE_NAME"),
    ("KAKAO_REDIRECT_URI", "VITE_KAKAO_REDIRECT_URI"),
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
        lines.append("- 서버와 앱의 Google Play 패키지명, 카카오 Redirect URI, 네이버 Redirect URI가 서로 맞습니다.")
    else:
        lines.extend([
            "",
            "다음에 할 일:",
            "1. 서버 설정과 앱 설정을 같은 값으로 맞추기",
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
