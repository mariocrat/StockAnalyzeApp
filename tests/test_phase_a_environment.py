"""H4-D OAuth cleanup orchestration inside the real A1 boundary."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

BOUNDARY = require_storage_boundary()

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from tests import test_phase_a_runtime_environment as runtime

# Aliases keep nested source classes out of top-level unittest discovery.
# Their original A1 gates and storage fixtures remain unchanged.
with storage_fixture():
    from tests import test_oauth_login as local
    from tests import test_oauth_login_transport as transport
    from backend.core import oauth_login


def _state():
    modules = dict(sys.modules)
    namespaces = {
        name: {key: id(value) for key, value in vars(module).items()}
        for name, module in modules.items()
        if isinstance(module, ModuleType) and
        (name == __name__ or name == "main" or name.startswith(("core.", "backend.core."))
         or "__path__" in vars(module))
    }
    targets = ((oauth_login.requests, "get"), (oauth_login.requests, "post"),
               (oauth_login, "_request_json"), (oauth_login, "_exchange_json"),
               (oauth_login, "login_oauth_code"))
    return (dict(os.environ), Path.cwd(), list(sys.path), tempfile.tempdir,
            {name: id(module) for name, module in modules.items()}, namespaces,
            tuple(id(getattr(target, name)) for target, name in targets),
            dict(oauth_login.OAUTH_APP_TICKETS),
            frozenset((BOUNDARY.root / "temp").iterdir()), len(BOUNDARY.violations))


class PhaseAOAuthCleanupTest(runtime._OwnedCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        baseline = _state()
        # Observe before outer restoring contexts can hide nested leaks.
        self.addCleanup(lambda: self.assertEqual(_state(), baseline))
        self.assertTrue(Path.home().is_relative_to(BOUNDARY.root))

    def test_oauth_mocks_restore_in_both_orders(self):
        cases = (
            (transport.OAuthTransportTest, "test_oauth_request_timeout_setting_is_capped"),
            (local.OAuthLoginTest, "test_oauth_app_redirect_uses_one_time_app_ticket_without_session_token"),
            (transport.OAuthTransportTest, "test_kakao_access_token_profile_creates_alphamate_session"),
            (transport.OAuthTransportTest, "test_naver_access_token_profile_creates_alphamate_session"),
            (transport.OAuthTransportTest, "test_kakao_authorization_code_is_exchanged_before_login"),
            (transport.OAuthTransportTest, "test_naver_authorization_code_is_exchanged_before_login"),
        )
        for order in (cases, tuple(reversed(cases))):
            with storage_fixture():
                targets = ((oauth_login.requests, "get"), (oauth_login.requests, "post"), (oauth_login, "_request_json"), (oauth_login, "_exchange_json"), (oauth_login, "login_oauth_code"))
                originals = [getattr(target, name) for target, name in targets]
                environment = dict(os.environ)
                temporary = tempfile.tempdir
                for case_class, name in order:
                    with self.subTest(test=name, reversed=order != cases):
                        baseline = _state()
                        result = unittest.TestResult()
                        case_class(name).run(result)
                        self.assertEqual(result.testsRun, 1)
                        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
                        for (target, attribute), original in zip(targets, originals):
                            self.assertIs(getattr(target, attribute), original)
                        self.assertEqual(dict(os.environ), environment)
                        self.assertEqual(tempfile.tempdir, temporary)
                        self.assertEqual(_state(), baseline)

    def test_oauth_cleanup_runs_after_an_assertion_failure(self):
        for case_class in (local.OAuthLoginTest, transport.OAuthTransportTest):
            with self.subTest(fixture=case_class.__name__), storage_fixture():
                import requests
                original = requests.get
                environment = dict(os.environ)
                baseline = _state()

                class FailingProbe(case_class):
                    def runTest(self):
                        self._replace(requests, "get", lambda *args: None)
                        os.environ["SYNTHETIC_FAILURE"] = "temporary"
                        self.fail("expected synthetic failure to exercise addCleanup")

                result = unittest.TestResult()
                FailingProbe().run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertEqual(len(result.failures), 1)
                self.assertIn("expected synthetic failure to exercise addCleanup", result.failures[0][1])
                self.assertEqual(result.errors, [])
                self.assertIs(requests.get, original)
                self.assertEqual(dict(os.environ), environment)
                self.assertEqual(_state(), baseline)
