"""Backend configuration: explicit source, environment and storage boundaries."""

import os
from enum import Enum
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
DB_FILES = {
    "ALPHAMATE_ACCOUNT_DB_PATH": "accounts.sqlite3",
    "ALPHAMATE_ACCESS_DB_PATH": "access.sqlite3",
    "ALPHAMATE_JOURNAL_DB_PATH": "trades.sqlite3",
    "ALPHAMATE_REVIEW_HISTORY_DB_PATH": "review_history.sqlite3",
    "ALPHAMATE_EVENT_LOG_DB_PATH": "event_log.sqlite3",
}


class ConfigurationError(ValueError):
    """Messages contain setting names and error kinds, never supplied values."""


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


def _resolve_path(value: str, name: str) -> Path:
    try:
        if "\x00" in value:
            raise ValueError()
        path = Path(value)
        if path.drive and not path.is_absolute():
            raise ValueError()
        return (path if path.is_absolute() else REPOSITORY_ROOT / path).resolve()
    except (OSError, ValueError, RuntimeError):
        raise ConfigurationError(f"{name}: invalid path") from None


def _settings() -> dict[str, str]:
    selected = os.environ.get("ALPHAMATE_ENV_FILE")
    if selected is None:
        return {key: value.strip() for key, value in os.environ.items()}
    if not selected.strip():
        raise ConfigurationError("ALPHAMATE_ENV_FILE: empty selection")
    path = _resolve_path(selected.strip(), "ALPHAMATE_ENV_FILE")
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise ConfigurationError("ALPHAMATE_ENV_FILE: unreadable file") from None
    values = {}
    for line in content.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def env_value(name: str) -> str:
    return _settings().get(name, "")


def _environment(settings: dict[str, str]) -> Environment:
    try:
        return Environment(settings.get("ALPHAMATE_ENV", "").strip().lower())
    except ValueError:
        raise ConfigurationError("ALPHAMATE_ENV: expected development, test or production") from None


def runtime_environment() -> Environment:
    return _environment(_settings())


def is_production() -> bool:
    return runtime_environment() is Environment.PRODUCTION


def _dev_access(settings: dict[str, str], environment: Environment) -> bool:
    value = settings.get("ALPHAMATE_ALLOW_DEV_ACCESS", "").strip().lower()
    if value not in {"", "0", "false", "no", "off", "1", "true", "yes", "on"}:
        raise ConfigurationError("ALPHAMATE_ALLOW_DEV_ACCESS: invalid boolean")
    enabled = value in {"1", "true", "yes", "on"}
    if environment is Environment.PRODUCTION and enabled:
        raise ConfigurationError("ALPHAMATE_ALLOW_DEV_ACCESS: forbidden in production")
    return enabled


def dev_access_enabled() -> bool:
    settings = _settings()
    environment = _environment(settings)
    enabled = _dev_access(settings, environment)
    if enabled and environment is Environment.TEST:
        _validated_paths(settings)
    return enabled


def _validated_paths(settings: dict[str, str]) -> dict[str, Path]:
    """Resolve and validate before callers create directories or open databases."""
    environment = _environment(settings)
    _dev_access(settings, environment)
    test_root = None
    if environment is Environment.TEST:
        configured_root = settings.get("ALPHAMATE_TEST_ROOT", "")
        if not configured_root:
            raise ConfigurationError("ALPHAMATE_TEST_ROOT: explicit temporary root required")
        test_root = _resolve_path(configured_root, "ALPHAMATE_TEST_ROOT")
        # Do not call gettempdir(): its first call can probe the filesystem by writing.
        temporary_base = next((os.environ[key] for key in ("TMPDIR", "TEMP", "TMP") if os.environ.get(key)), "/tmp" if os.name != "nt" else "")
        if not temporary_base:
            raise ConfigurationError("ALPHAMATE_TEST_ROOT: system temporary directory unavailable")
        temporary_root = _resolve_path(temporary_base, "system temporary directory")
        if test_root == temporary_root or not test_root.is_relative_to(temporary_root):
            raise ConfigurationError("ALPHAMATE_TEST_ROOT: must be inside temporary directory")

    data_root = BACKEND_ROOT / "data"
    cache_default = BACKEND_ROOT / ".cache"
    if environment is Environment.DEVELOPMENT:
        data_root = data_root / "development"
        cache_default = cache_default / "development"
    paths = {}
    for name, filename in DB_FILES.items():
        value = settings.get(name, "")
        if test_root is not None and not value:
            raise ConfigurationError(f"{name}: explicit test path required")
        paths[name] = _resolve_path(value, name) if value else data_root / filename
    cache_value = settings.get("ALPHAMATE_CACHE_DIR", "")
    if test_root is not None and not cache_value:
        raise ConfigurationError("ALPHAMATE_CACHE_DIR: explicit test path required")
    cache = _resolve_path(cache_value, "ALPHAMATE_CACHE_DIR") if cache_value else cache_default
    if len(set(paths.values())) != len(paths):
        raise ConfigurationError("DB paths: collision")
    if any(path == cache or cache.is_relative_to(path) or path.is_relative_to(cache) for path in paths.values()):
        raise ConfigurationError("DB/cache paths: collision")
    if any(left != right and left.is_relative_to(right) for left in paths.values() for right in paths.values()):
        raise ConfigurationError("DB paths: overlapping paths")
    paths["ALPHAMATE_CACHE_DIR"] = cache
    if test_root is not None:
        for name, path in paths.items():
            if path == test_root or not path.is_relative_to(test_root):
                raise ConfigurationError(f"{name}: outside test root")
    return paths


def validate_configuration() -> dict[str, Path]:
    return _validated_paths(_settings())


def database_path(name: str) -> Path:
    return validate_configuration()[name]


def cache_directory() -> Path:
    return validate_configuration()["ALPHAMATE_CACHE_DIR"]
