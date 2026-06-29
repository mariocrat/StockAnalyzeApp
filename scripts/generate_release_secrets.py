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
        "Generated release secret candidates.",
        "",
        "Copy these lines into your private server .env.release file only:",
    ]
    for name in SECRET_NAMES:
        lines.append(f"{name}={values[name]}")
    lines.extend([
        "",
        "Do not commit these values to GitHub.",
        "Do not paste them into frontend/.env.release or any VITE_* setting.",
        "Run this again if any value may have been exposed.",
    ])
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
    lines = ["Updated private server .env.release secret placeholders."]
    for item in result.get("filled", []):
        lines.append(f"Filled: {item}")
    for item in result.get("skipped_existing", []):
        lines.append(f"Skipped existing value: {item}")
    if result.get("missing_file"):
        lines.append(f"Missing file: {result['missing_file']}")
        lines.append("Run prepare_release_env_files.bat first.")
    lines.extend([
        "",
        "Do not commit .env.release to GitHub.",
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
