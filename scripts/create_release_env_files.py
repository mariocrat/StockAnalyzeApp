import shutil
from pathlib import Path


RELEASE_ENV_FILES = [
    (Path(".env.release.example"), Path(".env.release")),
    (Path("frontend") / ".env.release.example", Path("frontend") / ".env.release"),
]


def _env_key(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return ""
    return stripped.split("=", 1)[0].strip()


def _append_missing_template_keys(source: Path, target: Path) -> list[str]:
    template_lines = source.read_text(encoding="utf-8").splitlines()
    target_text = target.read_text(encoding="utf-8")
    target_lines = target_text.splitlines()
    existing_keys = {_env_key(line) for line in target_lines}
    missing_lines = []
    missing_keys = []

    for line in template_lines:
        key = _env_key(line)
        if key and key not in existing_keys:
            missing_lines.append(line)
            missing_keys.append(key)
            existing_keys.add(key)

    if missing_lines:
        output_lines = target_lines[:]
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.append("# Added from the latest release template. Fill real values before production.")
        output_lines.extend(missing_lines)
        target.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    return missing_keys


def create_release_env_files(root: Path | str) -> dict:
    root = Path(root)
    created = []
    skipped = []
    updated = []
    missing_keys_by_file = {}
    missing_templates = []

    for source_relative, target_relative in RELEASE_ENV_FILES:
        source = root / source_relative
        target = root / target_relative
        if not source.exists():
            missing_templates.append(str(source_relative))
            continue
        if target.exists():
            missing_keys = _append_missing_template_keys(source, target)
            if missing_keys:
                updated.append(str(target_relative))
                missing_keys_by_file[str(target_relative)] = missing_keys
            else:
                skipped.append(str(target_relative))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        created.append(str(target_relative))

    return {
        "created": len(created),
        "skipped": len(skipped),
        "updated": len(updated),
        "missing_templates": len(missing_templates),
        "created_files": created,
        "skipped_files": skipped,
        "updated_files": updated,
        "missing_keys_by_file": missing_keys_by_file,
        "missing_template_files": missing_templates,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = create_release_env_files(root)

    for item in result["created_files"]:
        print(f"생성함: {item}")
    for item in result["updated_files"]:
        keys = ", ".join(result["missing_keys_by_file"].get(item, []))
        print(f"추가함: {item} ({keys})")
    for item in result["skipped_files"]:
        print(f"이미 최신 상태라 유지함: {item}")
    for item in result["missing_template_files"]:
        print(f"템플릿 파일 없음: {item}")

    if result["created"] or result["updated"]:
        print("")
        print("다음: .env.release 파일을 열고 실제 운영용 값을 채우세요.")
        print("채운 .env.release 파일은 GitHub에 올리지 마세요.")
    elif result["skipped"] and not result["missing_templates"]:
        print("")
        print("출시용 .env.release 파일이 이미 있고 최신 템플릿 키도 들어 있습니다.")

    return 1 if result["missing_templates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
