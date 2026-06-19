import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.release_check import format_backend_release_check, validate_backend_release_env


def main() -> int:
    result = validate_backend_release_env()
    print(format_backend_release_check(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
