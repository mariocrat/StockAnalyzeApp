import secrets
import shutil
import subprocess
import sys
from pathlib import Path


SIGNING_NAMES = [
    "ALPHAMATE_ANDROID_KEYSTORE_FILE",
    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD",
    "ALPHAMATE_ANDROID_KEY_ALIAS",
    "ALPHAMATE_ANDROID_KEY_PASSWORD",
]

TEMPLATE_KEYSTORE_PATHS = {
    "D:/secure/alphamate/alphamate-upload.jks",
    "D:\\secure\\alphamate\\alphamate-upload.jks",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _secret_token() -> str:
    return secrets.token_urlsafe(36)


def default_android_signing_values(root: Path | str) -> dict[str, str]:
    root = Path(root)
    keystore_path = root / "release-private" / "android" / "alphamate-upload.jks"
    return {
        "ALPHAMATE_ANDROID_KEYSTORE_FILE": str(keystore_path).replace("\\", "/"),
        "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD": _secret_token(),
        "ALPHAMATE_ANDROID_KEY_ALIAS": "alphamate-upload",
        "ALPHAMATE_ANDROID_KEY_PASSWORD": _secret_token(),
    }


def _normalize_env_path(value: str) -> str:
    return value.strip().strip("'\"")


def _is_template_keystore_path(value: str) -> bool:
    normalized = _normalize_env_path(value)
    return normalized in TEMPLATE_KEYSTORE_PATHS


def _is_stale_project_keystore_path(current: str, default_value: str) -> bool:
    normalized = _normalize_env_path(current)
    default_normalized = _normalize_env_path(default_value)
    if not normalized or normalized == default_normalized:
        return False
    normalized_slash = normalized.replace("\\", "/")
    if not normalized_slash.lower().endswith("/release-private/android/alphamate-upload.jks"):
        return False
    return not Path(normalized).exists()


def _replace_release_signing_value(line: str, name: str, value: str) -> tuple[str, bool, bool]:
    prefix = f"{name}="
    if not line.startswith(prefix):
        return line, False, False

    current = line[len(prefix):].strip()
    if not current:
        return f"{prefix}{value}", True, True
    if name == "ALPHAMATE_ANDROID_KEYSTORE_FILE" and (
        _is_template_keystore_path(current)
        or _is_stale_project_keystore_path(current, value)
    ):
        return f"{prefix}{value}", True, True

    return line, True, False


def _parse_env_file(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_android_signing_values(root: Path | str) -> dict[str, str]:
    env_path = Path(root) / "frontend" / ".env.release"
    env = _parse_env_file(env_path)
    return {name: env.get(name, "") for name in SIGNING_NAMES}


def fill_empty_android_signing_values(root: Path | str, values: dict[str, str]) -> dict:
    env_path = Path(root) / "frontend" / ".env.release"
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
        for name in SIGNING_NAMES:
            updated, matched, changed = _replace_release_signing_value(updated, name, values[name])
            if matched:
                found.add(name)
                if changed and name not in filled:
                    filled.append(name)
                elif not changed and name not in skipped_existing:
                    skipped_existing.append(name)
        updated_lines.append(updated)

    for name in SIGNING_NAMES:
        if name not in found:
            updated_lines.append(f"{name}={values[name]}")
            filled.append(name)

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return {
        "filled": filled,
        "skipped_existing": skipped_existing,
        "missing_file": "",
    }


def find_keytool(root: Path | str) -> Path | None:
    path_keytool = shutil.which("keytool")
    if path_keytool:
        return Path(path_keytool)
    root = Path(root)
    candidates = sorted((root / ".tools").glob("jdk/**/bin/keytool.exe"))
    return candidates[0] if candidates else None


def build_keytool_command(*, keytool_path: Path, values: dict[str, str]) -> list[str]:
    return [
        str(keytool_path),
        "-genkeypair",
        "-v",
        "-keystore",
        values["ALPHAMATE_ANDROID_KEYSTORE_FILE"],
        "-storepass",
        values["ALPHAMATE_ANDROID_KEYSTORE_PASSWORD"],
        "-alias",
        values["ALPHAMATE_ANDROID_KEY_ALIAS"],
        "-keypass",
        values["ALPHAMATE_ANDROID_KEY_PASSWORD"],
        "-keyalg",
        "RSA",
        "-keysize",
        "2048",
        "-validity",
        "10000",
        "-dname",
        "CN=AlphaMate, OU=Mobile, O=Mariocrat, L=Seoul, ST=Seoul, C=KR",
    ]


def create_upload_key(*, root: Path | str, values: dict[str, str]) -> dict:
    keytool = find_keytool(root)
    if keytool is None:
        return {"created": False, "skipped_existing": False, "error": "keytool을 찾을 수 없습니다. Android Studio 또는 JDK 설치가 필요합니다."}

    keystore_path = Path(values["ALPHAMATE_ANDROID_KEYSTORE_FILE"])
    if keystore_path.exists():
        return {"created": False, "skipped_existing": True, "error": ""}

    try:
        keystore_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return {"created": False, "skipped_existing": False, "error": f"키스토어 폴더를 만들 수 없습니다. 경로: {keystore_path.parent}"}

    command = build_keytool_command(keytool_path=keytool, values=values)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return {"created": False, "skipped_existing": False, "error": "keytool 실행에 실패해 Android 업로드 키를 만들지 못했습니다."}
    return {"created": True, "skipped_existing": False, "error": ""}


def format_result(fill_result: dict, key_result: dict | None) -> str:
    lines = ["Android 서명 설정 빈 값을 확인했습니다."]
    for item in fill_result.get("filled", []):
        lines.append(f"채움: {item}")
    for item in fill_result.get("skipped_existing", []):
        lines.append(f"이미 값이 있어서 유지함: {item}")
    if fill_result.get("missing_file"):
        lines.append(f"파일 없음: {fill_result['missing_file']}")
        lines.append("prepare_release_env_files.bat를 먼저 실행하세요.")
    if key_result:
        if key_result.get("created"):
            lines.append("Android 업로드 키스토어 파일을 만들었습니다.")
        elif key_result.get("skipped_existing"):
            lines.append("기존 Android 업로드 키스토어 파일을 유지했습니다.")
        elif key_result.get("error"):
            lines.append(key_result["error"])
    lines.extend([
        "",
        "frontend/.env.release와 Android 키스토어 파일은 GitHub에 올리지 마세요.",
    ])
    return "\n".join(lines)


def main() -> int:
    root = _repo_root()
    values = default_android_signing_values(root)
    fill_result = fill_empty_android_signing_values(root, values)
    if fill_result.get("missing_file"):
        print(format_result(fill_result, None))
        return 1

    actual_values = load_android_signing_values(root)
    key_result = None
    if "--create-key" in sys.argv[1:]:
        key_result = create_upload_key(root=root, values=actual_values)

    print(format_result(fill_result, key_result))
    return 1 if key_result and key_result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
