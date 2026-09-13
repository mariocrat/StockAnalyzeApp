"""H4-A1 cooperative Python test boundary, installed before target imports.

Not an OS sandbox: arbitrary native code and full lifecycle ownership are deferred.
"""

import os
import socket
import sqlite3
import _sqlite3
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch

from backend.core import env as configuration
from backend.core.env import DB_FILES, REPOSITORY_ROOT, validate_configuration
from scripts.create_release_env_files import RELEASE_ENV_FILES
from tests.phase_a_isolation import _socketpair_operation, install_network_patches


_active = None
_sqlite_opening = ContextVar("isolation_sqlite_opening", default=None)


def sanitized_environment(host, root):
    """Do not inherit application/provider values, Python hooks, PATH or proxies."""
    values = {key: value for key, value in host.items()
              if key.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE"}}
    values.update({
        "ALPHAMATE_ENV": "test",
        "ALPHAMATE_TEST_ROOT": str(root),
        "ALPHAMATE_CACHE_DIR": str(root / "cache"),
        "ALPHAMATE_ALLOW_DEV_ACCESS": "false",
        "TEMP": str(root.parent), "TMP": str(root.parent), "TMPDIR": str(root.parent),
        "HOME": str(root), "USERPROFILE": str(root),
        "APPDATA": str(root / "config"), "LOCALAPPDATA": str(root / "config"),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
    })
    values.update({name: str(root / filename) for name, filename in DB_FILES.items()})
    return values


class ProtectedPaths:
    """Canonical directory containment and exact files, without filename heuristics."""
    def __init__(self, roots=(), files=()):
        self.roots = {Path(path).resolve() for path in roots}
        self.files = {Path(path).resolve() for path in files}

    def add_root(self, path):
        self.roots.add(Path(path).resolve())

    def add_file(self, path):
        self.files.add(Path(path).resolve())

    def add_database(self, path):
        path = Path(path).resolve()
        # Exact companions of a registered database; never extension-based classification.
        for suffix in ("", "-wal", "-shm", "-journal"):
            self.add_file(str(path) + suffix)

    def contains(self, path):
        path = Path(path).resolve()
        return path in self.files or any(path.is_relative_to(root) for root in self.roots)

    def metadata(self):
        return {"roots": sorted(map(str, self.roots)), "files": sorted(map(str, self.files))}


def checkout_roots():
    """Include the owning checkout using Git metadata only; never inspect private data."""
    roots = {REPOSITORY_ROOT}
    git_pointer = REPOSITORY_ROOT / ".git"
    if git_pointer.is_file():
        pointer = git_pointer.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir: "):
            raise ValueError("invalid worktree metadata")
        git_dir = (REPOSITORY_ROOT / pointer.removeprefix("gitdir: ")).resolve()
        common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
        roots.add((git_dir / common).resolve().parent)
    return roots


def protected_paths(host):
    """Reuse pure resolver calculations: no _settings(), env/DB/credential file reads."""
    protected = ProtectedPaths()
    for repository in checkout_roots():
        for environment in ("production", "development"):
            # Explicit settings bypass _settings(), which may read a selected private env.
            defaults = configuration._validated_paths({"ALPHAMATE_ENV": environment})
            for name, path in defaults.items():
                mapped = repository / path.relative_to(REPOSITORY_ROOT)
                protected.add_root(mapped if name == "ALPHAMATE_CACHE_DIR" else mapped.parent)
        for _, target in RELEASE_ENV_FILES:
            protected.add_file(repository / target)
        # frontend/scripts/validate-release-env.js defaults to frontend CWD/.env.
        protected.add_file(repository / "frontend" / ".env")
    for name in (*DB_FILES, "ALPHAMATE_CACHE_DIR", "ALPHAMATE_ENV_FILE"):
        value = host.get(name, "").strip()
        if value:
            path = configuration._resolve_path(value, name)
            if name in DB_FILES:
                protected.add_database(path)
            elif name == "ALPHAMATE_CACHE_DIR":
                protected.add_root(path)
            else:
                protected.add_file(path)
    # These callers use Path(value) relative to process CWD, unlike env._resolve_path.
    # access_control.py and backend/scripts/validate_release_alignment.py are the sources.
    for name in ("GOOGLE_PLAY_SERVICE_ACCOUNT_FILE", "ALPHAMATE_FRONTEND_ENV_FILE"):
        value = host.get(name, "").strip()
        if value:
            protected.add_file(Path(value))
    return protected


class IsolationViolation(AssertionError):
    pass


class Boundary:
    def __init__(self, root, protected=None):
        self.root = Path(root).resolve()
        self.protected = protected if protected is not None else ProtectedPaths()
        self.violations = []
        self.acknowledged = set()
        self.patches_restored = False

    def deny(self, kind):
        # Never record path/URL/environment contents: category is sufficient evidence.
        self.violations.append(kind)
        raise IsolationViolation("isolation blocked: " + kind)

    @property
    def unexpected(self):
        return len(self.violations) - len(self.acknowledged)

    @contextmanager
    def expect_violation(self, kind):
        """Acknowledge exactly one matching negative probe, never clear the ledger."""
        start = len(self.violations)
        try:
            yield
        except IsolationViolation:
            pass
        if self.violations[start:] != [kind]:
            raise AssertionError("expected exactly one isolation violation: " + kind)
        self.acknowledged.add(start)

    def path(self, raw, writing=False):
        if isinstance(raw, int):
            # Runtime stdin/stdout/stderr remain inherited; opening arbitrary FDs is not allowed.
            self.deny("file-descriptor")
        path = Path(os.fsdecode(raw)).resolve()
        inside = path.is_relative_to(self.root)
        if writing and not inside:
            self.deny("write")
        # Owned fixtures take precedence, even when an ancestor is registered.
        if not inside and not writing and self.protected.contains(path):
            self.deny("sensitive-read")

    def sqlite_authorizer(self, action, _arg1, _arg2, _database, _trigger):
        # SQLite opens ATTACH/VACUUM INTO files internally, without Python open
        # events. Record before returning DENY; callers may catch DatabaseError.
        if action == sqlite3.SQLITE_ATTACH:
            self.violations.append("sqlite-attach")
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def audit(self, event, args):
        if event in {"socket.connect", "socket.bind"}:
            if not _socketpair_operation(event, args):
                self.deny("network")
        elif event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                       "socket.getnameinfo", "socket.sendto", "socket.sendmsg"}:
            self.deny("network")
        elif event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork"}:
            self.deny("subprocess")
        elif event == "sqlite3.connect":
            # Unwrapped/pre-bootstrap aliases and direct constructors fail before
            # opening a file. Each guarded call authorizes exactly one creation.
            if _sqlite_opening.get() is not self:
                self.deny("sqlite-connect")
            _sqlite_opening.set(None)
            self.path(args[0], writing=True)
        elif event == "open":
            raw, mode, flags = args
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            self.path(raw, writing=writing)
        elif event in {"os.symlink", "os.link"}:
            # No runtime link creation; avoids aliases to persistent data.
            self.deny("link")
        elif event == "os.rename":
            if any(fd not in {-1, None} for fd in args[2:]):
                self.deny("dir-fd")
            for raw in args[:2]:
                self.path(raw, writing=True)
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.chown", "os.truncate", "os.utime"}:
            fd_index = {"os.mkdir": 2, "os.remove": 1, "os.rmdir": 1,
                        "os.chmod": 2, "os.chown": 3, "os.utime": 3}.get(event)
            if fd_index is not None and len(args) > fd_index and args[fd_index] not in {-1, None}:
                self.deny("dir-fd")
            self.path(args[0], writing=True)


def _audit(event, args):
    if _active is not None:
        _active.audit(event, args)


sys.addaudithook(_audit)


def current_boundary():
    if _active is None:
        raise RuntimeError("isolation is not installed")
    return _active


def install_sqlite_patches(stack, boundary):
    original_connect = sqlite3.connect
    original_connection = sqlite3.Connection

    def guarded_connect(*args, **kwargs):
        # A custom factory could execute SQL before the authorizer is installed.
        # The repository uses only the default factory; reject both API spellings.
        factory = kwargs.get("factory", args[5] if len(args) > 5 else original_connection)
        if factory is not original_connection:
            boundary.deny("sqlite-factory")
        token = _sqlite_opening.set(boundary)
        try:
            connection = original_connect(*args, **kwargs)
        finally:
            _sqlite_opening.reset(token)
        try:
            # connect/handle fires before __init__ finishes on this Python runtime.
            # Install on the fully initialized connection before returning it.
            original_connection.set_authorizer(connection, boundary.sqlite_authorizer)
        except Exception:
            if isinstance(connection, original_connection):
                connection.close()
            boundary.deny("sqlite-authorizer")
        return connection

    targets = (sqlite3, sqlite3.dbapi2, _sqlite3)
    originals = [(target, "connect", target.connect) for target in targets]
    for target in targets:
        stack.enter_context(patch.object(target, "connect", guarded_connect))
    return originals


@contextmanager
def isolated_module(root, protected=None, *, boundary=None):
    """Restore CWD/environment/patches even on import, test or cleanup failure."""
    global _active
    if _active is not None:
        raise RuntimeError("nested module isolation is not supported")
    boundary = boundary if boundary is not None else Boundary(root, protected)
    old_cwd = Path.cwd()
    originals = [(socket, "socketpair", socket.socketpair), (socket, "has_ipv6", socket.has_ipv6)]
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, sanitized_environment(os.environ, boundary.root), clear=True))
        stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
        stack.enter_context(patch.object(tempfile, "tempdir", str(boundary.root / "temp")))
        _active = boundary
        try:
            for directory in (boundary.root, boundary.root / "temp", boundary.root / "cache", boundary.root / "config"):
                directory.mkdir(exist_ok=True)
            os.chdir(boundary.root)
            validate_configuration()
            originals.extend(install_sqlite_patches(stack, boundary))
            # urllib3.util.connection probes IPv6 by binding ::1 during import and
            # catches every Exception. Advertise no IPv6 for this import only, so
            # capability detection needs no live socket and no violation is consumed.
            with patch("socket.has_ipv6", False):
                originals.extend(install_network_patches(stack, lambda: boundary.deny("network")))
            import urllib.request
            originals.append((urllib.request.OpenerDirector, "open", urllib.request.OpenerDirector.open))
            stack.enter_context(patch.object(urllib.request.OpenerDirector, "open", side_effect=lambda *a, **k: boundary.deny("network")))
            yield boundary
        finally:
            try:
                os.chdir(old_cwd)
                stack.close()
            finally:
                # Audit hooks cannot be removed; this child-only hook becomes inert.
                _active = None
                boundary.patches_restored = all(getattr(target, name) is original for target, name, original in originals)
