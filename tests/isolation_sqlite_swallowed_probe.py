"""F1: a swallowed SQLite error must still fail the final child result."""
from contextlib import closing
import sqlite3
import unittest
from tests.module_isolation import current_boundary


class SwallowedSQLiteProbe(unittest.TestCase):
    def test_application_catches_database_error(self):
        boundary = current_boundary()
        with closing(sqlite3.connect(boundary.root / "owned.sqlite3")) as connection:
            try:
                connection.execute("ATTACH DATABASE ? AS extra", (str(boundary.root.parent / "attach-output.sqlite3"),))
            except sqlite3.DatabaseError:
                pass
        # No expected-violation scope: the runner must fail despite this test passing.
        self.assertFalse((boundary.root.parent / "attach-output.sqlite3").exists())
