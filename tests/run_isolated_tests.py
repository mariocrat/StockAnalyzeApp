"""Explicit module-per-child runner. No target imports in the coordinator.

Usage: python -B tests/run_isolated_tests.py tests.test_rate_limit
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import traceback

REPOSITORY = Path(__file__).resolve().parents[1]
# -I excludes the caller's CWD and PYTHONPATH; insert this trusted checkout only.
sys.path.insert(0, str(REPOSITORY))
from tests.module_isolation import Boundary, IsolationViolation, isolated_module, sanitized_environment, protected_paths, ProtectedPaths


REPORT_PREFIX = "ISOLATION_RESULT "


def execute_child(module, root, protected):
    result = None
    boundary = Boundary(root, protected)
    completed = False
    stage = "bootstrap"
    error_kind = None
    old_cwd, old_env, old_temp = Path.cwd(), dict(os.environ), tempfile.tempdir
    try:
        with isolated_module(root, protected, boundary=boundary):
            stage = "import"
            target = importlib.import_module(module)
            stage = "test"
            suite = unittest.defaultTestLoader.loadTestsFromModule(target)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            stage = "cleanup"
        completed = True
    except BaseException as error:
        error_kind = type(error).__name__
        print("isolation child error: " + error_kind, file=sys.stderr)
        if isinstance(error, IsolationViolation):
            print(str(error), file=sys.stderr)
        # No source lines, exception values or filesystem arguments in diagnostics.
        for frame in traceback.extract_tb(error.__traceback__):
            print(f"  {frame.filename}:{frame.lineno} in {frame.name}", file=sys.stderr)
    restored = Path.cwd() == old_cwd and dict(os.environ) == old_env and tempfile.tempdir == old_temp
    return {
        "module": module, "tests": result.testsRun if result else 0,
        "failures": len(result.failures) if result else 0,
        "errors": len(result.errors) if result else 0,
        "violations": len(boundary.violations), "unexpected": boundary.unexpected,
        "violation_kinds": boundary.violations,
        "restored": restored, "patches_restored": boundary.patches_restored,
        "error_stage": stage if error_kind else None, "error_kind": error_kind,
        "passed": bool(completed and result is not None and result.wasSuccessful() and result.testsRun
                       and not boundary.unexpected and restored and boundary.patches_restored),
    }


def child(module, root, protected):
    report = execute_child(module, root, protected)
    print(REPORT_PREFIX + json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


def run_module(module, host=None):
    if not re.fullmatch(r"tests\.[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module):
        raise ValueError("an explicit tests.* module is required")
    host = dict(os.environ if host is None else host)
    report = {"module": module, "tests": 0, "violations": 0, "unexpected": 0,
              "restored": False, "patches_restored": False, "passed": False,
              "returncode": None, "stderr": "", "cleanup": False}
    owned = None
    container = None
    try:
        # Only coordinator-owned synthetic storage is created/removed here.
        owned = tempfile.TemporaryDirectory(prefix="stockboda-h4-a1-")
        container = Path(owned.name).resolve()
        root = container / "runtime"
        report["root"] = str(root)
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                   "--child", module, "--root", str(root)]
        process = subprocess.run(command, cwd=container, env=sanitized_environment(host, root),
                                 input=json.dumps(protected_paths(host).metadata()),
                                 text=True, encoding="utf-8", capture_output=True, timeout=120)
        report["stderr"] = process.stderr
        report["returncode"] = process.returncode
        reports = [line[len(REPORT_PREFIX):] for line in process.stdout.splitlines()
                   if line.startswith(REPORT_PREFIX)]
        if len(reports) != 1:
            raise ValueError("missing or ambiguous child report")
        report.update(json.loads(reports[0]))
        report["passed"] = report["passed"] and process.returncode == 0
    except Exception as error:
        report.update(passed=False, coordinator_error=type(error).__name__)
    finally:
        if owned is not None:
            try:
                owned.cleanup()
                report["cleanup"] = not container.exists()
            except Exception as error:
                report.update(cleanup=False, cleanup_error=type(error).__name__)
        report["passed"] = report["passed"] and report["cleanup"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="+")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if len(args.modules) != 1 or args.root is None:
            parser.error("child requires one module and a root")
        return child(args.modules[0], args.root, ProtectedPaths(**json.loads(sys.stdin.read())))
    passed = True
    for module in args.modules:
        report = run_module(module)
        print(report.pop("stderr"), file=sys.stderr, end="")
        print(REPORT_PREFIX + json.dumps(report))
        passed = passed and report["passed"]
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
