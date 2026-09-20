"""Safety harness for the focused Phase A suite (not the full backend suite)."""

import os
import socket
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch

from backend.core.env import DB_FILES


_active_root = None
_violation_observer = None
_socketpair_setup = ContextVar("phase_a_socketpair_setup", default=None)


@contextmanager
def observe_violations(observer):
    """Record denials before this earlier hook raises; never replay an audit event."""
    global _violation_observer
    previous = _violation_observer
    _violation_observer = observer
    try:
        yield
    finally:
        _violation_observer = previous


def _deny(kind, message):
    if _violation_observer is not None:
        _violation_observer(kind)
    raise AssertionError(message)


def _socketpair_operation(event, args, *, observer):
    """Allow only the ephemeral listener/peer used by Python's socketpair."""
    setup = _socketpair_setup.get()
    if setup is None or observer not in {"phase-a", "a1"}:
        return False
    sock, address = args
    if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
        return False
    if sock.type != socket.SOCK_STREAM:
        return False
    # Two installed hooks inspect one OS operation. Each may approve it once,
    # only for the same socket and endpoint inside this socketpair token.
    approved = setup.get(event)
    if approved is not None:
        owned_socket, owned_address, observers = approved
        if sock is not owned_socket or address != owned_address or observer in observers:
            return False
        observers.add(observer)
        return True
    if event == "socket.bind" and address[1] == 0 and "listener" not in setup:
        setup["listener"] = sock
        setup[event] = (sock, address, {observer})
        return True
    if event == "socket.connect" and "listener" in setup and not setup.get("connected"):
        listener = setup["listener"]
        if address[:2] == listener.getsockname()[:2]:
            setup["connected"] = True
            setup[event] = (sock, address, {observer})
            return True
    return False


def _audit(event, args):
    if _active_root is None:
        return
    if event in {"socket.connect", "socket.bind"}:
        if _socketpair_operation(event, args, observer="phase-a"):
            return
        _deny("network", f"Phase A harness: external/local operation blocked: {event}")
    if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo", "socket.sendto", "socket.sendmsg"}:
        _deny("network", f"Phase A harness: external DNS/datagram blocked: {event}")
    if event in {"subprocess.Popen", "os.system"}:
        _deny("subprocess", "Phase A harness: subprocess blocked")
    paths = []
    kind = "write"
    if event == "sqlite3.connect":
        paths = [args[0]]
    elif event == "open":
        path, mode, flags = args
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        kind = "write" if writing else "sensitive-read"
        if writing or (isinstance(path, (str, bytes)) and str(path).lower().endswith((".db", ".sqlite", ".sqlite3"))):
            paths = [path]
    elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"}:
        paths = [args[0]]
    elif event in {"os.rename", "os.link", "os.symlink"}:
        paths = list(args[:2])
    for raw in paths:
        if isinstance(raw, int):
            continue
        path = Path(os.fsdecode(raw)).resolve()
        if not path.is_relative_to(_active_root):
            _deny(kind, "Phase A harness: filesystem/DB access outside temporary root")


sys.addaudithook(_audit)


@contextmanager
def isolated_runtime():
    global _active_root
    previous_root = _active_root
    # TemporaryDirectory itself initializes tempfile.tempdir on first use.
    with patch.object(tempfile, "tempdir", tempfile.tempdir), tempfile.TemporaryDirectory(prefix="stockboda-phase-a-") as tmp:
        root = Path(tmp).resolve()
        values = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "TMPDIR") if key in os.environ}
        values.update({
            "ALPHAMATE_ENV": "test",
            "ALPHAMATE_TEST_ROOT": str(root),
            "ALPHAMATE_CACHE_DIR": str(root / "cache"),
            "ALPHAMATE_ALLOW_DEV_ACCESS": "false",
        })
        values.update({name: str(root / filename) for name, filename in DB_FILES.items()})
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, values, clear=True))
            # Nested legacy fixtures also remain under the harness root.
            stack.enter_context(patch.object(tempfile, "tempdir", str(root)))
            _active_root = root
            try:
                install_network_patches(stack, _blocked_network)
                yield root
            finally:
                _active_root = previous_root


def _blocked_network():
    _deny("network", "network blocked")


def install_network_patches(stack, blocked):
    """Shared Phase A/A1 transport patches; caller installs its audit guard first."""
    original_socketpair = socket.socketpair
    originals = [(socket, "socketpair", original_socketpair)]

    def internal_socketpair(*args, **kwargs):
        token = _socketpair_setup.set({})
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            _socketpair_setup.reset(token)

    def deny(*args, **kwargs):
        return blocked()

    stack.enter_context(patch.object(socket, "socketpair", internal_socketpair))
    import requests
    originals.append((requests.sessions.Session, "request", requests.sessions.Session.request))
    stack.enter_context(patch.object(requests.sessions.Session, "request", side_effect=deny))
    # yfinance's C transport does not emit Python socket audit events.
    from curl_cffi import requests as curl_requests
    originals.append((curl_requests.Session, "request", curl_requests.Session.request))
    stack.enter_context(patch.object(curl_requests.Session, "request", side_effect=deny))
    return originals
