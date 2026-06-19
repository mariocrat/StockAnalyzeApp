import os
from pathlib import Path


DEFAULT_ENV_ROOTS = [
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[1] / ".env",
]


def _read_env_file(path: Path, name: str) -> str:
    try:
        if not path.exists():
            return ""
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, val = raw.lstrip("\ufeff").split("=", 1)
            if key.strip() == name:
                return val.strip().strip("\"'")
    except Exception:
        return ""
    return ""


def env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()

    configured_file = os.environ.get("ALPHAMATE_ENV_FILE", "").strip()
    roots = [Path(configured_file)] if configured_file else []
    roots.extend(DEFAULT_ENV_ROOTS)

    for path in roots:
        value = _read_env_file(path, name)
        if value:
            return value
    return ""
