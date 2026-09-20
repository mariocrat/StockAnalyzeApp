"""Coordinator regressions using disposable private files and Git metadata only."""

from contextlib import closing, redirect_stderr
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from backend.core import env
from tests import module_isolation as isolation
from tests import phase_a_isolation as phase
from tests import run_isolated_tests as runner


def synthetic_worktrees(base):
    main = base / "main"
    common = main / ".git"
    common.mkdir(parents=True)
    roots = [main]
    for name in ("current", "sibling with spaces"):
        root = base / name
        root.mkdir()
        registration = common / "worktrees" / name
        registration.mkdir(parents=True)
        (root / ".git").write_text("gitdir: " + os.path.relpath(registration, root), encoding="utf-8")
        (registration / "commondir").write_text("../..", encoding="utf-8")
        (registration / "gitdir").write_text(os.path.relpath(root / ".git", registration), encoding="utf-8")
        roots.append(root)
    return roots


class FoundationIsolationTest(unittest.TestCase):
    def execute(self, container, protected, body, *, passed=True, bootstrap=None):
        module = types.ModuleType("tests.synthetic_foundation_target")
        module.Case = type("SyntheticCase", (unittest.TestCase,), {"test_body": body})
        original_import = runner.importlib.import_module
        observer = phase._violation_observer

        def imported(name, *args, **kwargs):
            return module if name == module.__name__ else original_import(name, *args, **kwargs)

        with patch.object(runner.importlib, "import_module", side_effect=imported), redirect_stderr(io.StringIO()):
            if bootstrap is None:
                report = runner.execute_child(module.__name__, container / "runtime", protected)
            else:
                with patch.object(isolation, "install_network_patches", bootstrap):
                    report = runner.execute_child(module.__name__, container / "runtime", protected)
        self.assertEqual(report["passed"], passed, report)
        self.assertTrue(report["restored"], report)
        self.assertTrue(report["patches_restored"], report)
        self.assertIs(phase._violation_observer, observer)
        self.assertIsNone(phase._active_root)
        self.assertIsNone(phase._socketpair_setup.get())
        return report

    def test_worktree_discovery_from_main_and_linked_metadata_only(self):
        with tempfile.TemporaryDirectory(prefix="foundation-git-") as temp:
            roots = synthetic_worktrees(Path(temp))
            read_text = Path.read_text
            reads = []

            def metadata_only(path, *args, **kwargs):
                self.assertIn(path.name, {".git", "gitdir", "commondir"})
                reads.append(path)
                return read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", metadata_only):
                for root in roots:
                    self.assertEqual(isolation.checkout_roots(root), set(roots))
            self.assertTrue(reads)
        self.assertFalse(Path(temp).exists())

    def test_invalid_worktree_metadata_fails_closed_without_private_reads(self):
        for fault in ("missing", "wrong-backlink", "wrong-common", "non-git-target", "empty"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix="foundation-git-invalid-") as temp:
                roots = synthetic_worktrees(Path(temp))
                entry = roots[0] / ".git" / "worktrees" / roots[2].name
                if fault == "missing":
                    (entry / "gitdir").unlink()
                elif fault == "wrong-backlink":
                    (roots[2] / ".git").write_text("gitdir: synthetic-wrong", encoding="utf-8")
                elif fault == "wrong-common":
                    (entry / "commondir").write_text("../../synthetic-wrong", encoding="utf-8")
                elif fault == "non-git-target":
                    (entry / "gitdir").write_text(str(Path(temp) / "private-do-not-open"), encoding="utf-8")
                else:
                    (entry / "gitdir").write_text("", encoding="utf-8")
                read_text = Path.read_text

                def metadata_only(path, *args, **kwargs):
                    self.assertIn(path.name, {".git", "gitdir", "commondir"})
                    return read_text(path, *args, **kwargs)

                with patch.object(Path, "read_text", metadata_only):
                    with self.assertRaisesRegex(ValueError, "^invalid worktree metadata$"):
                        isolation.checkout_roots(roots[1])
            self.assertFalse(Path(temp).exists())

    def test_registered_defaults_signing_credentials_and_owned_files(self):
        with tempfile.TemporaryDirectory(prefix="foundation-private-") as temp:
            container = Path(temp).resolve()
            roots = synthetic_worktrees(container)
            host = {name: str(container / "configured" / name) for name in env.DB_FILES}
            for name in ("ALPHAMATE_CACHE_DIR", "ALPHAMATE_ENV_FILE", "ALPHAMATE_FRONTEND_ENV_FILE",
                         "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS",
                         "ALPHAMATE_ANDROID_KEYSTORE_FILE"):
                host[name] = str(container / "configured" / name)
            targets = []
            for root in roots:
                targets.extend(root / relative for relative in (
                    "backend/data/opaque", "backend/data/development/opaque",
                    "backend/.cache/opaque", "backend/.cache/development/opaque",
                    "release-private/android/alphamate-upload.jks", "release-private/signing/opaque.key"))
                for directory in (root, root / "backend", root / "frontend"):
                    targets.extend(directory / name for name in (
                        ".env", ".env.local", ".env.release", ".env.release.local",
                        ".env.production", ".env.production.local"))
            for name, value in host.items():
                if name in env.DB_FILES:
                    targets.extend(Path(value + suffix) for suffix in ("", "-wal", "-shm", "-journal"))
                else:
                    targets.append(Path(value) / "opaque" if name == "ALPHAMATE_CACHE_DIR" else Path(value))
            explicit_file = container / "registered-private"
            explicit_root = container / "registered-persistent"
            targets.extend((explicit_file, explicit_root / "opaque"))
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"synthetic-private")
            ordinary = roots[2] / "release-private-neighbor" / ".env"
            ordinary.parent.mkdir()
            ordinary.write_bytes(b"ordinary-source")
            discover = isolation.checkout_roots
            with patch.object(isolation, "checkout_roots", side_effect=lambda: discover(roots[1])), \
                    patch.object(env, "_settings", side_effect=AssertionError("must not load private env")):
                protected = isolation.protected_paths(host)
            protected.add_file(explicit_file)
            protected.add_root(explicit_root)
            for root in roots:
                self.assertFalse(protected.contains(root / ".env.release.example"))
                self.assertFalse(protected.contains(root / "frontend/android/app/build.gradle"))
            self.assertFalse(protected.contains(Path(str(explicit_file) + "-neighbor")))
            self.assertFalse(protected.contains(explicit_file / "child"))

            def exercise(case):
                boundary = isolation.current_boundary()
                aliases = [targets[0].parent / ".." / "data" / "opaque"]
                if os.name == "nt":
                    aliases.append(Path(str(targets[-1]).upper().replace("\\", "/")))
                for target in targets + aliases:
                    with case.subTest(path=target.relative_to(container) if target.is_relative_to(container) else "alias"):
                        with boundary.expect_violation("sensitive-read"):
                            target.read_bytes()
                case.assertEqual(ordinary.read_bytes(), b"ordinary-source")
                # Explicitly protected ancestors still cannot block test-owned fixtures.
                protected.add_root(container)
                try:
                    for relative in ("release-private/android/owned.jks", "backend/data/opaque",
                                     "backend/.cache/opaque", ".env.release", "credentials.json"):
                        owned = boundary.root / relative
                        owned.parent.mkdir(parents=True, exist_ok=True)
                        owned.write_bytes(b"owned")
                        case.assertEqual(owned.read_bytes(), b"owned")
                finally:
                    protected.roots.remove(container)

            report = self.execute(container, protected, exercise)
            self.assertEqual(report["unexpected"], 0)
            self.assertEqual(report["violations"], len(targets) + 1 + int(os.name == "nt"))
            self.assertTrue(all(target.read_bytes() == b"synthetic-private" for target in targets))
        self.assertFalse(container.exists())

    def test_relative_credential_and_keystore_paths_match_consumers(self):
        with tempfile.TemporaryDirectory(prefix="foundation-relative-") as temp:
            container = Path(temp).resolve()
            roots = synthetic_worktrees(container)
            previous = Path.cwd()
            discover = isolation.checkout_roots
            try:
                os.chdir(container)
                with patch.object(isolation, "checkout_roots", side_effect=lambda: discover(roots[1])):
                    protected = isolation.protected_paths({
                        "GOOGLE_APPLICATION_CREDENTIALS": "configured/adc.json",
                        "ALPHAMATE_ANDROID_KEYSTORE_FILE": "configured/upload.jks",
                    })
            finally:
                os.chdir(previous)
            targets = [container / "configured/adc.json", container / "configured/upload.jks"]
            targets.extend(root / "frontend/android/app/configured/upload.jks" for root in roots)

            def exercise(case):
                boundary = isolation.current_boundary()
                for target in targets:
                    case.assertTrue(protected.contains(target))
                    with boundary.expect_violation("sensitive-read"):
                        target.read_bytes()  # All nonexistent; denial must precede OS open.

            report = self.execute(container, protected, exercise)
            self.assertEqual(report["violations"], len(targets))
            self.assertEqual(report["unexpected"], 0)
        self.assertFalse(container.exists())

    def test_nested_phase_denials_are_recorded_once_before_the_original_assertion(self):
        with tempfile.TemporaryDirectory(prefix="foundation-ledger-") as temp:
            container = Path(temp).resolve()
            private = container / "private.sqlite3"
            private.write_bytes(b"synthetic-private")

            def exercise(case):
                boundary = isolation.current_boundary()
                with phase.isolated_runtime() as root:
                    operations = (
                        ("network", lambda: sys.audit("socket.getaddrinfo", "synthetic.invalid", 443, 0, 0, 0)),
                        ("subprocess", lambda: sys.audit("subprocess.Popen", "synthetic-never-launched")),
                        ("write", lambda: (root.parent / "synthetic-outside").write_bytes(b"blocked")),
                        ("sensitive-read", private.read_bytes),
                        ("write", lambda: sqlite3.connect(container / "synthetic-outside.sqlite3")),
                    )
                    for kind, operation in operations:
                        before = len(boundary.violations)
                        with boundary.expect_violation(kind):
                            try:
                                operation()
                            except AssertionError as error:
                                case.assertIs(type(error), AssertionError)
                                case.assertIn("Phase A harness:", str(error))
                                case.assertEqual(boundary.violations[before:], [kind])
                            else:
                                case.fail("expected Phase A denial")
                    # A1-only denials still reach A1 when Phase A permits the event.
                    opaque = container / "opaque-private"
                    boundary.protected.add_file(opaque)
                    with boundary.expect_violation("sensitive-read"):
                        opaque.read_bytes()
                    with closing(sqlite3.connect(root / "owned.sqlite3")) as connection:
                        case.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
                    owned = root / "ordinary"
                    owned.write_bytes(b"owned")
                    case.assertEqual(owned.read_bytes(), b"owned")

            report = self.execute(container, isolation.ProtectedPaths(files=[private]), exercise)
            self.assertEqual(report["violations"], 6)
            self.assertEqual(report["unexpected"], 0)
            self.assertEqual(private.read_bytes(), b"synthetic-private")
            self.assertFalse((container / "synthetic-outside.sqlite3").exists())
        self.assertFalse(container.exists())

    def test_swallowed_phase_denials_fail_the_real_child(self):
        report = runner.run_module("tests.isolation_phase_a_swallowed_probe")
        self.assertFalse(report["passed"], report)
        self.assertEqual(report["returncode"], 1)
        self.assertEqual((report["tests"], report["failures"], report["errors"]), (1, 0, 0))
        self.assertEqual(report["violation_kinds"], ["network", "subprocess", "write", "network"])
        self.assertEqual(report["unexpected"], 4)
        for field in ("restored", "patches_restored", "cleanup"):
            self.assertTrue(report[field], report)
        self.assertFalse(Path(report["root"]).parent.exists())

    def test_observer_restores_after_body_and_bootstrap_failure(self):
        def fail_body(case):
            case.assertIsNotNone(phase._violation_observer)
            raise RuntimeError("synthetic body failure")

        def fail_bootstrap(stack, blocked):
            self.assertIsNotNone(phase._violation_observer)
            raise RuntimeError("synthetic bootstrap failure")

        for bootstrap in (None, fail_bootstrap):
            with self.subTest(bootstrap=bootstrap is not None), tempfile.TemporaryDirectory(prefix="foundation-restore-") as temp:
                report = self.execute(Path(temp), isolation.ProtectedPaths(), fail_body,
                                      passed=False, bootstrap=bootstrap)
                self.assertEqual(report["violations"], 0)
                self.assertEqual(report["tests"], 1 if bootstrap is None else 0)
            self.assertFalse(Path(temp).exists())

    def test_standalone_phase_a_keeps_assertion_without_an_a1_observer(self):
        self.assertIsNone(phase._violation_observer)
        # Preload transports under A1 first; standalone bootstrap need not probe IPv6.
        with tempfile.TemporaryDirectory(prefix="foundation-standalone-") as temp:
            self.execute(Path(temp), isolation.ProtectedPaths(), lambda case: None)
        with phase.isolated_runtime():
            with self.assertRaisesRegex(AssertionError, "Phase A harness: subprocess blocked") as caught:
                sys.audit("subprocess.Popen", "synthetic-never-launched")
            self.assertIs(type(caught.exception), AssertionError)
        self.assertIsNone(phase._violation_observer)
        self.assertIsNone(phase._active_root)
        self.assertFalse(Path(temp).exists())
