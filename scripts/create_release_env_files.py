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
        print(f"생성됨: {item}")
    for item in result["skipped_files"]:
        print(f"이미 있어서 유지함: {item}")
    for item in result["missing_template_files"]:
        print(f"템플릿 파일 없음: {item}")

    if result["created"]:
        print("")
        print("다음: 만들어진 .env.release 파일을 열고 실제 운영용 값을 채우세요.")
        print("채운 .env.release 파일은 GitHub에 올리지 마세요.")
    elif result["skipped"] and not result["missing_templates"]:
        print("")
        print("출시용 .env.release 파일이 이미 있습니다. 기존 파일은 덮어쓰지 않았습니다.")

    return 1 if result["missing_templates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
