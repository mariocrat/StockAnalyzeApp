import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2_000_000
SECRET_PATTERNS = [
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Google private key block", re.compile(r"-----BEGIN (?:RSA |EC |)PRIVATE KEY-----")),
    ("hard-coded password assignment", re.compile(r"(?m)^\s*[A-Z0-9_]*(?:PASSWORD|SECRET|PRIVATE_KEY)\s*=\s*[^#\s]+")),
    ("Google service account JSON", re.compile(r"(?im)^\s*GOOGLE_PLAY_SERVICE_ACCOUNT_JSON\s*=\s*\{")),
]
ALLOWED_ASSIGNMENT_FILES = {
    ".env.example",
    "frontend/.env.example",
    "docs/manual_test_guide.md",
    "docs/security_deployment_plan.md",
    "tests/test_backend_release_check.py",
    "tests/test_billing_readiness.py",
    "frontend/scripts/validate-release-env.test.js",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def read_text(path: Path) -> str | None:
    if path.stat().st_size > MAX_TEXT_BYTES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None


def main() -> int:
    findings = []
    for relative in tracked_files():
        path = ROOT / relative
        if not path.is_file():
            continue
        text = read_text(path)
        if text is None:
            continue
        normalized = relative.replace("\\", "/")
        for label, pattern in SECRET_PATTERNS:
            if label == "hard-coded password assignment" and normalized in ALLOWED_ASSIGNMENT_FILES:
                continue
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{normalized}:{line}: {label}")

    if findings:
        print("Potential tracked secrets found:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("No tracked secret patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
