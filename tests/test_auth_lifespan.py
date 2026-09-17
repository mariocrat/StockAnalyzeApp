"""Real lifespan orchestration with non-running startup thread doubles."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests import api_test_modules as api

import asyncio
import os
import sys
import inspect
import logging
from pathlib import Path
import tempfile
import threading
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from yfinance import cache as yf_cache


_CACHE_MANAGERS = (yf_cache._TzDBManager, yf_cache._CookieDBManager,
                   yf_cache._ISINDBManager)


def _state():
    logger = logging.getLogger("uvicorn.error")
    filters = [(logger, logger.filters, tuple(logger.filters))]
    while logger is not None:
        filters.extend((handler, handler.filters, tuple(handler.filters))
                       for handler in logger.handlers)
        if not logger.propagate:
            break
        logger = logger.parent
    return (
        dict(os.environ), list(sys.path), Path.cwd(), tempfile.tempdir,
        [{key: id(value) for key, value in module.__dict__.items()}
         for module in (*api._stores, api._main)],
        [(id(owner), id(items), tuple(map(id, contents)))
         for owner, items, contents in filters],
        logging.getLogger("yfinance").level,
        [(manager._cache_dir, id(manager._db)) for manager in _CACHE_MANAGERS],
        (id(yf_cache._TzCacheManager._tz_cache),
         id(yf_cache._CookieCacheManager._Cookie_cache),
         id(yf_cache._ISINCacheManager._isin_cache)),
        id(asyncio.events._event_loop_policy), threading.Thread,
        frozenset(threading.enumerate()),
    )


@contextmanager
def patched_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AuthLifespanTest(unittest.TestCase):
    def setUp(self):
        baseline = _state()
        # Registered first: verification runs after every restoring context,
        # including when setup or the testcase raises.
        self.addCleanup(lambda: self.assertEqual(baseline, _state()))
        roots = []
        self.addCleanup(lambda: self.assertTrue(all(not root.exists() for root in roots)))
        storage = self.enterContext(storage_fixture())
        roots.append(storage.root)
        self.cache_path = storage.cache / "yfinance"
        self.enterContext(api.api_module_state())
        # asyncio.run must not replace a caller's existing policy/loop state.
        self.enterContext(patch.object(asyncio.events, "_event_loop_policy", None))
        for manager in _CACHE_MANAGERS:
            self.enterContext(patch.object(manager, "_cache_dir", manager._cache_dir))
            # set_location closes an existing DB: keep any baseline handle out
            # of reach, while running the real setter on testcase-owned state.
            self.enterContext(patch.object(manager, "_db", None))

    def _run_lifespan(self, main, started):
        loops = []
        stops = []

        async def run_lifespan():
            loops.append(asyncio.get_running_loop())
            async with main.lifespan(main.app):
                scheduler = started[-2]["target"]
                stop = inspect.getclosurevars(scheduler).nonlocals["scheduler_stop"]
                stops.append(stop)
                self.assertFalse(stop.is_set())
                self.assertTrue(self.cache_path.is_dir())
                for manager in _CACHE_MANAGERS:
                    self.assertEqual(str(self.cache_path), manager._cache_dir)
                    self.assertIsNone(manager._db)

        # Spies call the real startup functions; none is replaced by a no-op.
        with patch.object(main, "validate_configuration", wraps=main.validate_configuration) as config, \
             patch.object(main, "initialize_yfinance_cache", wraps=main.initialize_yfinance_cache) as cache, \
             patch.object(main, "install_credential_safe_error_logging",
                          wraps=main.install_credential_safe_error_logging) as logging_setup:
            try:
                asyncio.run(run_lifespan())
            finally:
                for loop in loops:
                    self.assertTrue(loop.is_closed())
                    self.assertEqual(set(), asyncio.all_tasks(loop))
                for stop in stops:
                    self.assertTrue(stop.is_set())
            config.assert_called_once_with()
            cache.assert_called_once_with()
            logging_setup.assert_called_once_with()
        self.assertEqual(1, len(loops))
        self.assertEqual(1, len(stops))

    def test_lifespan_skips_theme_warmup_when_disabled_for_render(self):
        import main

        started = []

        class FakeThread:
            def __init__(self, target, daemon):
                started.append({"target": target, "daemon": daemon})

            def start(self):
                started.append("started")

        original_thread = main.threading.Thread
        try:
            main.threading.Thread = FakeThread
            with patched_env(ALPHAMATE_WARM_CACHE_ON_STARTUP="false"):
                self._run_lifespan(main, started)
        finally:
            main.threading.Thread = original_thread

        self.assertEqual(2, len(started))
        self.assertTrue(callable(started[0]["target"]))
        self.assertNotEqual(main._warm_cache, started[0]["target"])
        self.assertTrue(started[0]["daemon"])
        self.assertEqual("started", started[1])

    def test_lifespan_can_enable_theme_warmup_for_manual_prewarming(self):
        import main

        started = []

        class FakeThread:
            def __init__(self, target, daemon):
                started.append({"target": target, "daemon": daemon})

            def start(self):
                started.append("started")

        original_thread = main.threading.Thread
        try:
            main.threading.Thread = FakeThread
            with patched_env(ALPHAMATE_WARM_CACHE_ON_STARTUP="true"):
                self._run_lifespan(main, started)
        finally:
            main.threading.Thread = original_thread

        self.assertEqual(main._warm_cache, started[0]["target"])
        self.assertTrue(started[0]["daemon"])
        self.assertEqual("started", started[1])
        self.assertTrue(callable(started[2]["target"]))
        self.assertNotEqual(main._warm_cache, started[2]["target"])
        self.assertTrue(started[2]["daemon"])
        self.assertEqual("started", started[3])


if __name__ == "__main__":
    unittest.main()
