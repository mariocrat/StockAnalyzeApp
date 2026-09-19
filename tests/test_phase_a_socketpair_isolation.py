"""Focused foundation checks; no application or legacy testcase imports."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

BOUNDARY = require_storage_boundary()

import os
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import requests
from curl_cffi import requests as curl_requests
from tests import phase_a_isolation as phase


class SocketpairCompositionTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir,
                    socket.socketpair, phase._active_root, phase._socketpair_setup.get())
        self.addCleanup(self._restored, baseline)
        self.enterContext(storage_fixture())

    def _restored(self, baseline):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir,
                          socket.socketpair, phase._active_root,
                          phase._socketpair_setup.get()), baseline)

    def test_owned_socketpair_and_exception_restore_token(self):
        for fail in (False, True):
            try:
                with phase.isolated_runtime():
                    left, right = socket.socketpair()
                    with left, right:
                        left.sendall(b"owned")
                        self.assertEqual(right.recv(5), b"owned")
                        self.assertIsNone(phase._socketpair_setup.get())
                        if fail:
                            raise RuntimeError("synthetic body failure")
            except RuntimeError as error:
                self.assertTrue(fail)
                self.assertEqual(str(error), "synthetic body failure")
            self.assertEqual((left.fileno(), right.fileno()), (-1, -1))
            self.assertIsNone(phase._socketpair_setup.get())
            self.assertIsNone(phase._active_root)
        def failed_setup(*args, **kwargs):
            raise RuntimeError("synthetic socketpair setup failure")
        original = socket.socketpair
        with patch.object(socket, "socketpair", failed_setup), ExitStack() as stack:
            phase.install_network_patches(stack, lambda: self.fail("unexpected transport"))
            with self.assertRaisesRegex(RuntimeError, "synthetic socketpair setup failure"):
                socket.socketpair()
            self.assertIsNone(phase._socketpair_setup.get())
        self.assertIs(socket.socketpair, original)

    def test_permission_is_exact_and_each_observer_is_one_shot(self):
        # Pure state fixtures: no OS socket, bind, DNS or connect is performed.
        endpoint = ("127.0.0.1", 32123)

        class SyntheticSocket:
            type = socket.SOCK_STREAM

            def getsockname(self):
                return endpoint

        owned, peer, foreign = SyntheticSocket(), SyntheticSocket(), SyntheticSocket()
        for first, second in (("phase-a", "a1"), ("a1", "phase-a")):
            args = (owned, ("127.0.0.1", 0))
            self.assertFalse(phase._socketpair_operation("socket.bind", args, observer="a1"))
            token = phase._socketpair_setup.set({})
            try:
                self.assertFalse(phase._socketpair_operation("socket.bind", args, observer="unknown"))
                self.assertFalse(phase._socketpair_operation("socket.bind", (owned, ("192.0.2.1", 0)), observer="a1"))
                self.assertTrue(phase._socketpair_operation("socket.bind", args, observer=first))
                self.assertFalse(phase._socketpair_operation("socket.bind", (foreign, args[1]), observer=second))
                self.assertFalse(phase._socketpair_operation("socket.bind", (owned, ("127.0.0.2", 0)), observer=second))
                self.assertTrue(phase._socketpair_operation("socket.bind", args, observer=second))
                self.assertFalse(phase._socketpair_operation("socket.bind", args, observer="a1"))
                self.assertFalse(phase._socketpair_operation("socket.bind", args, observer="phase-a"))
                self.assertFalse(phase._socketpair_operation("socket.connect", (peer, ("127.0.0.1", 32124)), observer=first))
                self.assertTrue(phase._socketpair_operation("socket.connect", (peer, endpoint), observer=first))
                self.assertFalse(phase._socketpair_operation("socket.connect", (foreign, endpoint), observer=second))
                self.assertFalse(phase._socketpair_operation("socket.connect", (peer, ("127.0.0.1", 32124)), observer=second))
                self.assertTrue(phase._socketpair_operation("socket.connect", (peer, endpoint), observer=second))
                for observer in (first, second):
                    self.assertFalse(phase._socketpair_operation("socket.connect", (peer, endpoint), observer=observer))
                state = phase._socketpair_setup.get()
                self.assertIs(state["listener"], owned)
                self.assertTrue(state["connected"])
                self.assertEqual(state["socket.bind"], (owned, args[1], {first, second}))
                self.assertEqual(state["socket.connect"], (peer, endpoint, {first, second}))
            finally:
                phase._socketpair_setup.reset(token)
            self.assertIsNone(phase._socketpair_setup.get())
            self.assertFalse(phase._socketpair_operation("socket.connect", (peer, endpoint), observer="a1"))

    def test_network_and_subprocess_remain_blocked_with_and_without_phase_a(self):
        events = [(event, (None, (host, port)))
                  for event in ("socket.bind", "socket.connect", "socket.sendto")
                  for host, port in (("127.0.0.1", 0), ("192.0.2.1", 443))]
        events += [(event, ("synthetic.invalid",)) for event in
                   ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo")]
        events += [("socket.sendmsg", (None, ("192.0.2.1", 443)))]
        for nested in (False, True):
            with ExitStack() as stack:
                if nested:
                    stack.enter_context(phase.isolated_runtime())
                for event, args in events:
                    with self.subTest(nested=nested, event=event):
                        if nested:
                            with self.assertRaisesRegex(AssertionError, event):
                                sys.audit(event, *args)
                        else:
                            with BOUNDARY.expect_violation("network"):
                                sys.audit(event, *args)
                for event in ("subprocess.Popen", "os.system"):
                    if nested:
                        with self.assertRaisesRegex(AssertionError, "Phase A harness: subprocess blocked"):
                            sys.audit(event, "synthetic-never-launched")
                    else:
                        with BOUNDARY.expect_violation("subprocess"):
                            sys.audit(event, "synthetic-never-launched")
                for get in (requests.get, curl_requests.get):
                    if nested:
                        with self.assertRaisesRegex(AssertionError, "network blocked"):
                            get("https://synthetic.invalid")
                    else:
                        with BOUNDARY.expect_violation("network"):
                            get("https://synthetic.invalid")
