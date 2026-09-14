from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests import api_test_modules as api

import logging
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def state_snapshot():
    main = api._main
    account = api._stores[0]
    error_logger = logging.getLogger("uvicorn.error")
    handlers = []
    current = error_logger
    while current is not None:
        handlers.extend((handler, list(handler.filters)) for handler in current.handlers)
        if not current.propagate:
            break
        current = current.parent
    return (
        dict(os.environ), list(sys.path), Path.cwd(),
        main.app, main.app.openapi_schema, main.authenticate_session,
        main._admin_rate_limiter, main._callback_rate_limiter,
        account.PRIVACY_CONSENT_VERSION, account.authenticate_session,
        logging.getLogger("yfinance").level, list(error_logger.filters), handlers,
    )


class ApiModuleStateTest(unittest.TestCase):
    def test_route_state_and_patches_restore_after_each_testcase_outcome(self):
        baseline = state_snapshot()
        roots = []
        for outcome in ("success", "assertion", "exception", "setup"):
            with self.subTest(outcome=outcome):
                class Writer(unittest.TestCase):
                    def setUp(case):
                        storage = case.enterContext(storage_fixture(
                            ALPHAMATE_PRIVACY_CONSENT_VERSION="synthetic-case-version",
                            ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE="1"))
                        roots.append(storage.root)
                        modules = case.enterContext(api.api_module_state())
                        main = modules.main
                        case.assertEqual("synthetic-case-version", modules.account_store.PRIVACY_CONSENT_VERSION)
                        case.assertIsNone(main.app.openapi_schema)
                        case.assertTrue(main._enforce_admin_rate_limit("synthetic-client"))
                        case.assertIn("/api/me/data-summary", main.app.openapi()["paths"])
                        case.enterContext(patch.object(main, "authenticate_session", object()))
                        case.enterContext(patch.object(main, "_callback_rate_limiter", object()))
                        os.environ["API_CASE_MARKER"] = "synthetic"
                        if outcome == "setup":
                            raise RuntimeError("synthetic setUp failure")

                    def runTest(case):
                        if outcome == "assertion":
                            case.fail("synthetic assertion failure")
                        if outcome == "exception":
                            raise RuntimeError("synthetic testcase exception")

                result = unittest.TestResult()
                Writer().run(result)
                self.assertEqual(1, result.testsRun)
                self.assertEqual(int(outcome == "assertion"), len(result.failures))
                self.assertEqual(int(outcome in ("setup", "exception")), len(result.errors))
                self.assertEqual(baseline, state_snapshot())
                self.assertTrue(all(not root.parent.exists() for root in roots))
                with storage_fixture(ALPHAMATE_ADMIN_RATE_LIMIT_PER_MINUTE="1") as storage:
                    with api.api_module_state() as modules:
                        self.assertNotIn(storage.root, roots)
                        self.assertNotIn("API_CASE_MARKER", os.environ)
                        self.assertEqual(baseline[8], modules.account_store.PRIVACY_CONSENT_VERSION)
                        self.assertIsNone(modules.main.app.openapi_schema)
                        self.assertTrue(modules.main._enforce_admin_rate_limit("synthetic-client"))
                self.assertEqual(baseline, state_snapshot())

    def test_partial_reload_failure_restores_modules_and_logger_filters(self):
        baseline = state_snapshot()
        original_reload = api.importlib.reload
        handler = logging.NullHandler()
        logger = logging.getLogger("uvicorn.error")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(handler.close)
        filters = list(handler.filters)

        def reload_then_fail(module):
            result = original_reload(module)
            if module is api._main:
                self.assertTrue(handler.filters)
                raise RuntimeError("synthetic reload failure")
            return result

        with storage_fixture(ALPHAMATE_PRIVACY_CONSENT_VERSION="synthetic-reload-version") as storage:
            root = storage.root
            with patch.object(api.importlib, "reload", side_effect=reload_then_fail):
                with self.assertRaisesRegex(RuntimeError, "synthetic reload failure"):
                    with api.api_module_state():
                        self.fail("failed reload must not enter the test context")
        self.assertFalse(root.parent.exists())
        self.assertEqual(filters, handler.filters)
        logger.removeHandler(handler)
        self.assertEqual(baseline, state_snapshot())
