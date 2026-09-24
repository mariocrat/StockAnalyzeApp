"""Testcase storage contexts inside the approved H4-A1 module boundary."""

import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import ExitStack, closing, contextmanager
from unittest.mock import patch

from backend.core.env import validate_configuration
from tests.module_isolation import current_boundary, sanitized_environment


def require_storage_boundary():
    """Fail before storage/dependency imports or temp creation outside A1."""
    boundary = current_boundary()
    if os.environ.get("ALPHAMATE_ENV") != "test" or "ALPHAMATE_ENV_FILE" in os.environ:
        raise RuntimeError("storage tests require the isolated test environment")
    root = Path(os.environ.get("ALPHAMATE_TEST_ROOT", "")).resolve()
    if not root.is_relative_to(boundary.root):
        raise RuntimeError("storage tests require an A1-owned root")
    # Validates all five paths, cache, collisions and the temporary-root invariant.
    validate_configuration()
    return boundary


class StorageFixture:
    def __init__(self, root, stack):
        self.root = root
        self.paths = validate_configuration()
        self.cache = self.paths["ALPHAMATE_CACHE_DIR"]
        self._stack = stack

    def connect(self, name):
        """Real guarded SQLite; close even if the testcase/setup raises."""
        return self._stack.enter_context(closing(sqlite3.connect(self.paths[name])))

    def patch_object(self, target, name, value):
        return self._stack.enter_context(patch.object(target, name, value))


@contextmanager
def storage_fixture(**overrides):
    """A fresh full path set; restore env/temp/CWD and release resources on exit.

    Use directly in a test body or through TestCase.enterContext in setUp.
    Only scenario settings may be overridden, never isolation configuration.
    """
    boundary = require_storage_boundary()
    values = sanitized_environment(os.environ, boundary.root)
    reserved = (set(values) | {"ALPHAMATE_ENV_FILE"}) - {"ALPHAMATE_ALLOW_DEV_ACCESS"}
    if set(overrides) & reserved:
        raise ValueError("storage isolation settings cannot be overridden")
    with ExitStack() as stack:
        directory = stack.enter_context(tempfile.TemporaryDirectory(
            prefix="storage-case-", dir=boundary.root / "temp"))
        # The resolver requires TEST_ROOT strictly below TMPDIR. Own the whole
        # per-case container so explicit TEMP/TMP/TMPDIR users are isolated too.
        root = Path(directory).resolve() / "runtime"
        root.mkdir()
        values = sanitized_environment(os.environ, root)
        for key, value in overrides.items():
            if value is None:
                values.pop(key, None)
            else:
                values[key] = value
        stack.enter_context(patch.dict(os.environ, values, clear=True))
        stack.enter_context(patch.object(tempfile, "tempdir", str(root / "temp")))
        for name in ("cache", "temp", "config"):
            (root / name).mkdir()
        previous_cwd = Path.cwd()
        stack.callback(os.chdir, previous_cwd)
        os.chdir(root)
        require_storage_boundary()
        yield StorageFixture(root, stack)
