"""Explicit module-per-child runner. No target imports in the coordinator.

Usage: APPROVED_PYTHON -I -B tests/run_isolated_tests.py --inventory-only
       APPROVED_PYTHON -I -B tests/run_isolated_tests.py --all
       APPROVED_PYTHON -I -B tests/run_isolated_tests.py tests.test_rate_limit
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
from collections import Counter
from contextvars import ContextVar
import socket
import sqlite3

REPOSITORY = Path(__file__).resolve().parents[1]
# -I excludes the caller's CWD and PYTHONPATH; insert this trusted checkout only.
sys.path.insert(0, str(REPOSITORY))
from tests.module_isolation import Boundary, IsolationViolation, isolated_module, sanitized_environment, protected_paths, ProtectedPaths
from tests.isolation_inventory import COORDINATORS, InventoryError, expected_skips, inventory_summary, load_inventory

# Script and imported runner must share the evidence collector in coordinator children.
if __name__ == "__main__":
    sys.modules["tests.run_isolated_tests"] = sys.modules[__name__]


REPORT_PREFIX = "ISOLATION_RESULT "
_owner = ContextVar("coordinator_test_owner", default=None)
_nested = ContextVar("coordinator_nested_reports", default=None)


class CaseResult(unittest.TextTestResult):
    """One record per direct invocation; subtest/hook errors cannot disappear."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
        self.events = []
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.current = {"id": test.id(), "status": "ERROR", "finished": False}
        self.cases.append(self.current)
        self.owner_token = _owner.set(test.id())

    def stopTest(self, test):
        self.current["finished"] = True
        _owner.reset(self.owner_token)
        self.current = None
        super().stopTest(test)

    def outcome(self, test, status, reason=None):
        if self.current is not None and self.current["id"] == test.id():
            self.current["status"] = status
            if reason is not None:
                self.current["reason"] = reason
        else:
            self.events.append({"id": test.id(), "status": status})

    def addSuccess(self, test):
        self.outcome(test, "PASS")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.outcome(test, "FAIL")
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcome(test, "ERROR")
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.outcome(test, "SKIP", reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.outcome(test, "XFAIL")
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.outcome(test, "XPASS")
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            status = "FAIL" if issubclass(err[0], test.failureException) else "ERROR"
            self.outcome(test, status)
            self.events.append({"id": test.id(), "status": status, "subtest": True})
        super().addSubTest(test, subtest, err)


def result_fields(result):
    return {"tests": result.testsRun if result else 0,
            "failures": len(result.failures) if result else 0,
            "errors": len(result.errors) if result else 0,
            "skipped": len(result.skipped) if result else 0,
            "cases": result.cases if result else [], "events": result.events if result else []}


def run_suite(module):
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    return unittest.TextTestRunner(verbosity=2, resultclass=CaseResult).run(suite)


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
            result = run_suite(target)
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
        "module": module, **result_fields(result),
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
    report = launch_module(module, host)
    if _nested.get() is not None:
        _nested.get().append({"owner": _owner.get(), "report": dict(report)})
    return report


def run_coordinator_module(module, host=None):
    if module not in COORDINATORS:
        raise ValueError("not an approved coordinator self-test")
    return launch_module(module, host, coordinator=True)


def launch_module(module, host=None, *, coordinator=False):
    if not re.fullmatch(r"tests\.[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module):
        raise ValueError("an explicit tests.* module is required")
    if module == "tests.diagnose_phase_a_probe":
        raise ValueError("excluded diagnostic module")
    if coordinator and module not in COORDINATORS:
        raise ValueError("not an approved coordinator self-test")
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
                   "--coordinator-child" if coordinator else "--child", module, "--root", str(root)]
        process = subprocess.run(command, cwd=container, env=sanitized_environment(host, root),
                                 input=json.dumps(protected_paths(host).metadata()),
                                 text=True, encoding="utf-8", capture_output=True, timeout=600 if coordinator else 120)
        report["stderr"] = process.stderr
        report["returncode"] = process.returncode
        reports = [line[len(REPORT_PREFIX):] for line in process.stdout.splitlines()
                   if line.startswith(REPORT_PREFIX)]
        if len(reports) != 1:
            raise ValueError("missing or ambiguous child report")
        payload = json.loads(reports[0])
        if not isinstance(payload, dict) or payload.get("module") != module or type(payload.get("passed")) is not bool:
            raise ValueError("invalid child report")
        if (any(type(payload.get(key)) is not int or payload[key] < 0 for key in ("tests", "failures", "errors", "skipped"))
                or any(not isinstance(payload.get(key), list) for key in ("cases", "events"))
                or any(type(payload.get(key)) is not bool for key in ("restored", "patches_restored"))):
            raise ValueError("incomplete child report")
        # Parent-owned process/cleanup fields cannot be supplied by a child.
        if {"root", "cleanup", "returncode", "stderr", "coordinator_error"} & payload.keys():
            raise ValueError("child supplied parent-owned fields")
        report.update(payload)
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


def coordinator_child(module):
    if module not in COORDINATORS:
        raise ValueError("not an approved coordinator self-test")
    from tests import module_isolation, phase_a_isolation
    # Coordinator tests intentionally install A1 themselves. Never nest a second
    # A1 around them or expose this route as a general target escape hatch.
    tempfile.gettempdir()  # Resolve the sanitized temp base before the snapshot.
    before = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
    targets = ((socket, "socket"), (socket, "socketpair"), (socket, "getaddrinfo"),
               (subprocess, "Popen"), (subprocess, "run"), (sqlite3, "connect"),
               (module_isolation, "_active"), (phase_a_isolation, "_active_root"),
               (phase_a_isolation, "_violation_observer"))
    originals = [getattr(obj, name) for obj, name in targets]
    evidence = []
    token = _nested.set(evidence)
    result = None
    error_kind = None
    try:
        result = run_suite(importlib.import_module(module))
    except BaseException as error:
        error_kind = type(error).__name__
    finally:
        _nested.reset(token)
    restored = before == (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path))
    patches = all(getattr(obj, name) is original for (obj, name), original in zip(targets, originals))
    return {"module": module, **result_fields(result), "nested_reports": evidence,
            "boundary": "coordinator-owned fixtures; nested A1", "module_state": "fresh child process",
            "violations": None, "unexpected": None, "restored": restored, "patches_restored": patches,
            "error_kind": error_kind,
            "passed": bool(result and result.testsRun and result.wasSuccessful() and not error_kind and restored and patches)}


def check_report(entry, report, *, probe=False):
    """Fail closed on identity, skips, cardinality, outcome and lifecycle evidence."""
    if not isinstance(report, dict):
        return ["malformed report"]
    issues = []
    expected = {entry["module"] + "." + case for case in entry["cases"]}
    cases = report.get("cases", [])
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        return ["malformed cases"]
    ids = [case.get("id") for case in cases]
    if any(not isinstance(identifier, str) for identifier in ids):
        return ["malformed testcase identity"]
    if any(not isinstance(case.get("status"), str) for case in cases):
        return ["malformed testcase outcome"]
    if len(ids) != len(set(ids)):
        issues.append("duplicate testcase")
    if set(ids) != expected:
        issues.append("missing/extra testcase")
    if not cases or report.get("tests") != len(cases):
        issues.append("zero-test/count mismatch")
    if report.get("module") != entry["module"]:
        issues.append("module identity mismatch")
    allowed = expected_skips(entry)
    actual = {case.get("id"): case.get("reason") for case in cases if case.get("status") == "SKIP"}
    if actual != allowed or report.get("skipped") != len(actual):
        issues.append("unexpected/missing skip")
    if any(case.get("status") not in {"PASS", "FAIL", "ERROR", "SKIP"} or case.get("finished") is not True for case in cases):
        issues.append("unsupported/incomplete testcase outcome")
    if report.get("events") or report.get("failures") != 0 or report.get("errors") != 0:
        issues.append("test/hook failure")
    if any(case.get("status") in {"FAIL", "ERROR"} for case in cases):
        issues.append("failed testcase")
    if any(report.get(key) is not True for key in ("restored", "patches_restored", "cleanup")):
        issues.append("restoration/cleanup failure")
    if report.get("coordinator_error") or report.get("error_kind"):
        issues.append("child/coordinator error")
    if entry["execution_role"] != "coordinator":
        violations, unexpected = report.get("violations"), report.get("unexpected")
        kinds = report.get("violation_kinds")
        if (type(violations) is not int or type(unexpected) is not int
                or not isinstance(kinds, list) or violations != len(kinds)
                or not 0 <= unexpected <= violations):
            issues.append("invalid isolation ledger")
    records = report.get("nested_reports", [])
    if (not isinstance(records, list) or any(not isinstance(record, dict)
            or not isinstance(record.get("owner"), str) or not isinstance(record.get("report"), dict)
            for record in records)):
        issues.append("malformed nested reports")
    outcome = entry["expected"] if probe else {"passed": True, "returncode": 0}
    if any(type(report.get(key)) is not type(value) or report.get(key) != value for key, value in outcome.items()):
        issues.append("unexpected child outcome")
    if not probe and entry["execution_role"] == "guarded" and report.get("unexpected") != 0:
        issues.append("unexpected isolation violation")
    return issues


def coordinate(entries, *, guarded=run_module, coordinator=run_coordinator_module):
    """One primary run per direct module; registered owner reports cover probes."""
    reports, probes, issues = {}, {}, {}
    ordered = sorted(entries.values(), key=lambda item: (item["execution_role"] != "coordinator", item["module"]))
    for entry in ordered:
        if entry["execution_role"] == "probe":
            continue
        launch = coordinator if entry["execution_role"] == "coordinator" else guarded
        report = launch(entry["module"])
        reports[entry["module"]] = report
        faults = check_report(entry, report)
        if faults:
            issues[entry["module"]] = faults
    evidence = []
    for report in reports.values():
        records = report.get("nested_reports", []) if isinstance(report, dict) else []
        if isinstance(records, list):
            evidence.extend(record for record in records if isinstance(record, dict)
                            and isinstance(record.get("report"), dict))
    for entry in ordered:
        if entry["execution_role"] != "probe":
            continue
        module = entry["module"]
        if entry["owner"] is None:
            report = guarded(module)
        else:
            matches = [record["report"] for record in evidence if record.get("owner") == entry["owner"]
                       and record["report"].get("module") == module]
            if len(matches) != 1:
                issues[module] = ["missing/duplicate primary probe invocation"]
                continue
            report = matches[0]
        probes[module] = report
        faults = check_report(entry, report, probe=True)
        if faults:
            issues[module] = faults
    def observed(group):
        return [case for report in group.values() if isinstance(report, dict)
                for case in (report.get("cases") if isinstance(report.get("cases"), list) else [])
                if isinstance(case, dict) and isinstance(case.get("id"), str) and isinstance(case.get("status"), str)]

    def counts(cases):
        return {status: sum(case["status"] == status for case in cases) for status in ("PASS", "FAIL", "ERROR", "SKIP")}

    def coverage(cases, probe):
        expected = {entry["module"] + "." + case for entry in entries.values()
                    if (entry["execution_role"] == "probe") == probe for case in entry["cases"]}
        actual = Counter(case["id"] for case in cases)
        return {"expected": len(expected), "observed": sum(actual.values()),
                "missing": sorted(expected - actual.keys()), "extra": sorted(actual.keys() - expected),
                "duplicates": sorted(case for case, count in actual.items() if count > 1)}

    direct_cases, probe_cases = observed(reports), observed(probes)
    guarded_reports = [report for module, report in reports.items()
                       if entries[module]["execution_role"] == "guarded" and isinstance(report, dict)]
    lifecycle = [*reports.values(), *probes.values()]
    complete = len(probes) == sum(entry["execution_role"] == "probe" for entry in entries.values())
    def total(group, key):
        return sum(report[key] for report in group if type(report.get(key)) is int)

    return {"scope": "Python only", "inventory": inventory_summary(entries), "counts": counts(direct_cases),
            "probe_counts": counts(probe_cases), "coverage": coverage(direct_cases, False),
            "probe_coverage": coverage(probe_cases, True), "actual_skips": counts(direct_cases)["SKIP"],
            "reports": reports, "probes": probes, "issues": issues,
            "violations": total(guarded_reports, "violations"), "unexpected": total(guarded_reports, "unexpected"),
            "probe_violations": total([r for r in probes.values() if isinstance(r, dict)], "violations"),
            "probe_unexpected": total([r for r in probes.values() if isinstance(r, dict)], "unexpected"),
            **{key: bool(reports) and complete and all(isinstance(report, dict) and report.get(key) is True for report in lifecycle)
               for key in ("restored", "patches_restored", "cleanup")},
            "passed": bool(reports) and not issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--coordinator-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="run the complete Python inventory (no Node/build)")
    parser.add_argument("--inventory-only", action="store_true", help="validate source/manifest without importing targets")
    args = parser.parse_args()
    if sum((args.child, args.coordinator_child, args.all, args.inventory_only)) > 1:
        parser.error("choose one execution mode")
    if "tests.diagnose_phase_a_probe" in args.modules:
        parser.error("excluded diagnostic module")
    if args.child or args.coordinator_child:
        if len(args.modules) != 1 or args.root is None:
            parser.error("child requires one module and a root")
        if args.coordinator_child:
            report = coordinator_child(args.modules[0])
            print(REPORT_PREFIX + json.dumps(report), flush=True)
            return 0 if report["passed"] else 1
        return child(args.modules[0], args.root, ProtectedPaths(**json.loads(sys.stdin.read())))
    if args.root is not None or ((args.all or args.inventory_only) and args.modules):
        parser.error("invalid mode arguments")
    try:
        entries = load_inventory()
    except (InventoryError, ValueError, KeyError, TypeError, OSError, SyntaxError) as error:
        print("Inventory validation failed: " + type(error).__name__, file=sys.stderr)
        return 2
    if args.inventory_only:
        print(json.dumps(inventory_summary(entries), sort_keys=True))
        return 0
    if args.all:
        report = coordinate(entries)
        print("PYTHON_SUITE_RESULT " + json.dumps(report))
        return 0 if report["passed"] else 1
    if not args.modules or len(args.modules) != len(set(args.modules)):
        parser.error("explicit, unique module names are required")
    if any(module not in entries for module in args.modules):
        parser.error("module is not in the reviewed inventory")
    if any(entries[module]["execution_role"] == "probe" and entries[module]["owner"] for module in args.modules):
        parser.error("run these probes through their registered coordinator owners")
    passed = True
    for module in args.modules:
        entry = entries[module]
        report = run_coordinator_module(module) if entry["execution_role"] == "coordinator" else run_module(module)
        report["inventory_issues"] = check_report(entry, report, probe=entry["execution_role"] == "probe")
        report["passed"] = report["passed"] and not report["inventory_issues"]
        print(report.pop("stderr"), file=sys.stderr, end="")
        print(REPORT_PREFIX + json.dumps(report))
        passed = passed and report["passed"]
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
