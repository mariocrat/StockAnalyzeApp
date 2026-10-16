"""Test-only Python admission -> Node handoff, never a frontend parser.

The coordinator launches a fresh H4 child before importing the pure production
contract. Only synthetic canonical vectors and actual admission results cross
the boundary. Rejections have no summary field for the frontend to consume.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]
VECTOR = "frontend/scripts/fixtures/review-legacy-compatibility-v1.json"
HANDOFF = "scripts/fixtures/generated-review-legacy-admissions.json"


def prepare_legacy_admissions(root, host):
    from tests.module_isolation import protected_paths, sanitized_environment

    runtime = root / "tmp" / "legacy-backend"
    process = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-B", str(Path(__file__).resolve()), str(runtime)],
        cwd=root, env=sanitized_environment(host, runtime),
        input=json.dumps(protected_paths(host).metadata()), capture_output=True, text=True,
        encoding="utf-8", timeout=30,
    )
    if process.returncode:
        raise ValueError("legacy admission child failed")
    report = json.loads(process.stdout)
    raw = (REPOSITORY / VECTOR).read_bytes()
    vectors = json.loads(raw)
    expected_ids = [v["id"] for v in vectors["pass"] + vectors["fail"]]
    if (not isinstance(report, dict) or report.get("contract") != vectors["contract"]
            or report.get("passed") is not True or type(report.get("unexpected")) is not int or report["unexpected"] != 0
            or any(report.get(key) is not True for key in ("restored", "patches_restored"))
            or report.get("vector_sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("legacy admission lifecycle/vector mismatch")
    records = report.get("admissions")
    if (not isinstance(records, list) or any(not isinstance(r, dict) for r in records)
            or [r.get("id") for r in records] != expected_ids
            or any(not (set(r) == {"id", "status", "summary"} and r["status"] == "success" and type(r["summary"]) is str
                        or set(r) == {"id", "status", "code"} and r["status"] == "rejected" and type(r["code"]) is str)
                   for r in records)
            or report.get("counts") != {s: sum(r["status"] == s for r in records) for s in ("success", "rejected")}):
        raise ValueError("legacy admission coverage/record mismatch")
    destination = root / HANDOFF
    if destination.exists():
        raise ValueError("legacy admission handoff collision")
    destination.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return {key: report[key] for key in ("passed", "unexpected", "restored", "patches_restored", "counts", "vector_sha256")}


def child(runtime):
    # -I: only this verified checkout is added; no host CWD/PYTHONPATH imports.
    sys.path.insert(0, str(REPOSITORY))
    from tests.module_isolation import Boundary, ProtectedPaths, isolated_module

    protected = ProtectedPaths(**json.loads(sys.stdin.read()))
    boundary = Boundary(runtime, protected)
    baseline = (Path.cwd(), dict(os.environ), tempfile.tempdir)
    admissions = []
    with isolated_module(runtime, protected, boundary=boundary):
        from core.review_legacy_compatibility import (
            CONTRACT_VERSION, LegacyCompatibilityContractError, admit_legacy_body,
        )

        raw = (REPOSITORY / VECTOR).read_bytes()
        vectors = json.loads(raw)
        for vector in vectors["pass"] + vectors["fail"]:
            # No fixture expected value/status decides admission here.
            try:
                result = admit_legacy_body(vector["document"])
                record = {"id": vector["id"], "status": result.status, "summary": result.summary}
            except LegacyCompatibilityContractError as error:
                record = {"id": vector["id"], "status": "rejected", "code": error.code}
            admissions.append(record)
    restored = (Path.cwd(), dict(os.environ), tempfile.tempdir) == baseline
    report = {"contract": CONTRACT_VERSION, "vector_sha256": hashlib.sha256(raw).hexdigest(),
              "admissions": admissions, "unexpected": boundary.unexpected,
              "restored": restored, "patches_restored": boundary.patches_restored,
              "counts": {status: sum(r["status"] == status for r in admissions) for status in ("success", "rejected")}}
    report["passed"] = restored and boundary.patches_restored and not boundary.unexpected
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(child(Path(sys.argv[1]).resolve()))
