import asyncio
import importlib
import json
import os
import sqlite3
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from backend.core import env
from tests.phase_a_isolation import isolated_runtime




class PhaseAOAuthCleanupTest(unittest.TestCase):
    def test_oauth_mocks_restore_in_both_orders(self):
        from tests.test_oauth_login import OAuthLoginTest
        names = (
            "test_oauth_request_timeout_setting_is_capped",
            "test_oauth_app_redirect_uses_one_time_app_ticket_without_session_token",
            "test_kakao_access_token_profile_creates_alphamate_session",
            "test_naver_access_token_profile_creates_alphamate_session",
            "test_kakao_authorization_code_is_exchanged_before_login",
            "test_naver_authorization_code_is_exchanged_before_login",
        )
        for order in (names, tuple(reversed(names))):
            with isolated_runtime():
                from backend.core import oauth_login
                targets = ((oauth_login.requests, "get"), (oauth_login.requests, "post"), (oauth_login, "_request_json"), (oauth_login, "_exchange_json"), (oauth_login, "login_oauth_code"))
                originals = [getattr(target, name) for target, name in targets]
                environment = dict(os.environ)
                temporary = tempfile.tempdir
                for name in order:
                    with self.subTest(test=name, reversed=order != names):
                        result = unittest.TestResult()
                        OAuthLoginTest(name).run(result)
                        self.assertEqual(result.testsRun, 1)
                        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
                        for (target, attribute), original in zip(targets, originals):
                            self.assertIs(getattr(target, attribute), original)
                        self.assertEqual(dict(os.environ), environment)
                        self.assertEqual(tempfile.tempdir, temporary)

    def test_oauth_cleanup_runs_after_an_assertion_failure(self):
        from tests.test_oauth_login import OAuthLoginTest
        with isolated_runtime():
            import requests
            original = requests.get
            environment = dict(os.environ)
            class FailingProbe(OAuthLoginTest):
                def runTest(self):
                    self._replace(requests, "get", lambda *args: None)
                    os.environ["SYNTHETIC_FAILURE"] = "temporary"
                    self.fail("expected synthetic failure to exercise addCleanup")
            result = unittest.TestResult()
            FailingProbe().run(result)
            self.assertEqual(len(result.failures), 1)
            self.assertEqual(result.errors, [])
            self.assertIs(requests.get, original)
            self.assertEqual(dict(os.environ), environment)
