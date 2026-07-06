import secrets
import sys
from pathlib import Path


SECRET_NAMES = [
    "ALPHAMATE_ADMIN_TOKEN",
    "GOOGLE_PLAY_RTDN_SHARED_TOKEN",
]


def generate_release_secrets() -> dict[str, str]:
    return {name: secrets.token_urlsafe(48) for name in SECRET_NAMES}


def format_release_secrets(values: dict[str, str]) -> str:
    lines = [
        "서버용 개인 토큰 후보를 만들었지만 터미널에는 실제 값을 표시하지 않습니다.",
        "",
        "generate_release_secrets.bat 또는 --fill-empty 옵션을 사용하면 서버용 .env.release의 빈 값만 채웁니다.",
        "이 값은 frontend/.env.release 또는 VITE_* 설정에 넣지 마세요.",
        "",
        "확인한 서버 전용 설정:",
    ]
    for name in SECRET_NAMES:
        lines.append(f"{name}=<hidden>")
    return "\n".join(lines)

def _replace_empty_env_value(line: str, name: str, value: str) -> tuple[str, bool, bool]:
    prefix = f"{name}="
    if not line.startswith(prefix):
        return line, False, False
    current = line[len(prefix):].strip()
    if current:
        return line, True, False
    return f"{prefix}{value}", True, True


def fill_empty_release_secret_values(root: Path | str, values: dict[str, str]) -> dict:
    env_path = Path(root) / ".env.release"
    if not env_path.exists():
        return {
            "filled": [],
            "skipped_existing": [],
            "missing_file": str(env_path),
        }

    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = set()
    filled = []
    skipped_existing = []
    updated_lines = []

    for line in lines:
        updated = line
        for name in SECRET_NAMES:
            updated, matched, changed = _replace_empty_env_value(updated, name, values[name])
            if matched:
                found.add(name)
                if changed and name not in filled:
                    filled.append(name)
                elif not changed and name not in skipped_existing:
                    skipped_existing.append(name)
        updated_lines.append(updated)

    for name in SECRET_NAMES:
        if name not in found:
            updated_lines.append(f"{name}={values[name]}")
            filled.append(name)

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return {
        "filled": filled,
        "skipped_existing": skipped_existing,
        "missing_file": "",
    }


def format_fill_result(result: dict) -> str:
    lines = ["서버용 개인 토큰 빈칸을 확인했습니다."]
    for item in result.get("filled", []):
        lines.append(f"채움: {item}")
    for item in result.get("skipped_existing", []):
        lines.append(f"이미 값이 있어서 유지함: {item}")
    if result.get("missing_file"):
        lines.append(f"파일 없음: {result['missing_file']}")
        lines.append("prepare_release_env_files.bat를 먼저 실행하세요.")
    lines.extend([
        "",
        ".env.release 파일은 GitHub에 올리지 마세요.",
    ])
    return "\n".join(lines)


def main() -> int:
    values = generate_release_secrets()
    if "--fill-empty" in sys.argv[1:]:
        root = Path(__file__).resolve().parents[1]
        result = fill_empty_release_secret_values(root, values)
        print(format_fill_result(result))
        return 1 if result.get("missing_file") else 0

    print(format_release_secrets(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
