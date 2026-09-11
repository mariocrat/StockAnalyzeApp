"""Run only the reviewed Phase A tests, with temporary storage and no network.

Usage: python -B -m tests.run_phase_a_tests
"""

import unittest
import sys
import os
import socket
import tempfile

from tests.phase_a_isolation import isolated_runtime


class IsolatedRegression(unittest.TestCase):
    def __init__(self, case):
        super().__init__()
        self.case = case

    def id(self):
        return self.case.id()

    def __str__(self):
        return str(self.case)

    def run(self, result=None):
        with isolated_runtime():
            return self.case.run(result)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


class RunnerCleanupCheck(unittest.TestCase):
    """Observe known patch targets after the suite; never restore module globals."""

    def __init__(self):
        super().__init__()
        with isolated_runtime():
            import requests
            from curl_cffi import requests as curl_requests
            from backend.core import oauth_login
        self.targets = (
            (requests, "get"), (requests, "post"),
            (requests.sessions.Session, "request"), (curl_requests.Session, "request"),
            (socket, "socketpair"),
            (oauth_login, "_request_json"), (oauth_login, "_exchange_json"),
            (oauth_login, "login_oauth_code"),
        )
        self.originals = [getattr(target, name) for target, name in self.targets]
        self.environment = dict(os.environ)
        self.temporary = tempfile.tempdir
        self.import_path = list(sys.path)

    def runTest(self):
        for (target, name), original in zip(self.targets, self.originals):
            with self.subTest(module=target.__name__, name=name):
                self.assertIs(getattr(target, name), original)
        self.assertEqual(dict(os.environ), self.environment)
        self.assertEqual(tempfile.tempdir, self.temporary)
        self.assertEqual(sys.path, self.import_path)


def main():
    loader = unittest.TestLoader()
    cleanup = RunnerCleanupCheck()
    selected = sys.argv[1:]
    suite = unittest.TestSuite() if selected else loader.loadTestsFromName("tests.test_phase_a_environment")
    for name in selected or ("tests.test_credential_safe_logging", "tests.test_render_blueprint", "tests.test_event_log", "tests.test_oauth_login"):
        with isolated_runtime():
            cases = list(flatten(loader.loadTestsFromName(name)))
        suite.addTests(IsolatedRegression(case) for case in cases)
    suite.addTest(cleanup)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
