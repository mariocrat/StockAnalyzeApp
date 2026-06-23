import shutil
from pathlib import Path


RELEASE_ENV_FILES = [
    (Path(".env.release.example"), Path(".env.release")),
    (Path("frontend") / ".env.release.example", Path("frontend") / ".env.release"),
]


def create_release_env_files(root: Path | str) -> dict:
    root = Path(root)
    created = []
    skipped = []
    missing_templates = []

    for source_relative, target_relative in RELEASE_ENV_FILES:
        source = root / source_relative
        target = root / target_relative
        if not source.exists():
            missing_templates.append(str(source_relative))
            continue
        if target.exists():
            skipped.append(str(target_relative))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        created.append(str(target_relative))

    return {
        "created": len(created),
        "skipped": len(skipped),
        "missing_templates": len(missing_templates),
        "created_files": created,
        "skipped_files": skipped,
        "missing_template_files": missing_templates,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = create_release_env_files(root)

    for item in result["created_files"]:
        print(f"Created: {item}")
    for item in result["skipped_files"]:
        print(f"Skipped existing file: {item}")
    for item in result["missing_template_files"]:
        print(f"Missing template: {item}")

    if result["created"]:
        print("")
        print("Next: open the created .env.release files and fill the real private values.")
        print("Do not commit the filled files to GitHub.")
    elif result["skipped"] and not result["missing_templates"]:
        print("")
        print("Release env files already exist. No file was overwritten.")

    return 1 if result["missing_templates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
