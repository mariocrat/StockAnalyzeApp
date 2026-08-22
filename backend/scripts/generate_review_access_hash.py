import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.account_store import hash_review_password


def main() -> int:
    password = getpass.getpass("Review access password: ")
    print(hash_review_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
