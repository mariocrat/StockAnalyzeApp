"""H4-B2 deferred auth lifespan tests; excluded from A2 execution."""

import asyncio
import os
import sys
import unittest
from contextlib import contextmanager


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
    def test_lifespan_skips_theme_warmup_when_disabled_for_render(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

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
                async def run_lifespan():
                    async with main.lifespan(main.app):
                        pass

                asyncio.run(run_lifespan())
        finally:
            main.threading.Thread = original_thread

        self.assertEqual(2, len(started))
        self.assertTrue(callable(started[0]["target"]))
        self.assertNotEqual(main._warm_cache, started[0]["target"])
        self.assertTrue(started[0]["daemon"])
        self.assertEqual("started", started[1])

    def test_lifespan_can_enable_theme_warmup_for_manual_prewarming(self):
        backend_dir = os.path.join(os.getcwd(), "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

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
                async def run_lifespan():
                    async with main.lifespan(main.app):
                        pass

                asyncio.run(run_lifespan())
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
