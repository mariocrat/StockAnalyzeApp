"""Restore the import/reload state used by direct data-access route tests.

Storage belongs to storage_fixture; this context never starts app lifespan.
"""

from tests.storage_fixture import require_storage_boundary

require_storage_boundary()

import importlib
import logging
from pathlib import Path
import sys
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch


@contextmanager
def _import_state():
    with ExitStack() as stack:
        backend = str(Path(__file__).resolve().parents[1] / "backend")
        stack.enter_context(patch.object(sys, "path", [backend, *sys.path]))
        # main installs filters on uvicorn.error and its ancestor handlers.
        logger = logging.getLogger("uvicorn.error")
        stack.enter_context(patch.object(logger, "filters", list(logger.filters)))
        handlers = set()
        while logger is not None:
            handlers.update(logger.handlers)
            if not logger.propagate:
                break
            logger = logger.parent
        for handler in handlers:
            stack.enter_context(patch.object(handler, "filters", list(handler.filters)))
        yfinance_logger = logging.getLogger("yfinance")
        stack.callback(yfinance_logger.setLevel, yfinance_logger.level)
        yield


# Establish a sanitized module-level baseline before any testcase overrides.
# Keep dependencies loaded; clearing sys.modules would reinitialize third-party
# libraries and is neither needed nor part of this bounded fixture migration.
with _import_state():
    _stores = tuple(importlib.import_module("core." + name) for name in (
        "account_store", "access_control", "journal", "review_history", "event_log"))
    _main = importlib.import_module("main")


@contextmanager
def api_module_state():
    require_storage_boundary()
    with ExitStack() as stack:
        stack.enter_context(_import_state())
        for module in (*_stores, _main):
            # Snapshot before reload: failures during reload/setup restore too.
            stack.enter_context(patch.dict(module.__dict__))
            importlib.reload(module)
        yield SimpleNamespace(main=_main, **{
            module.__name__.rsplit(".", 1)[1]: module for module in _stores
        })
