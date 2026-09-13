"""F1 SQLite child regressions. The coordinator prepares only a synthetic decoy."""
from contextlib import closing
from pathlib import Path
import sqlite3
import _sqlite3
from sqlite3 import connect as connect_alias
import unittest

from tests.module_isolation import current_boundary

BOUNDARY = current_boundary()
ROOT = BOUNDARY.root


class SQLiteIsolationProbe(unittest.TestCase):
    def test_owned_crud_commit_close_and_backup(self):
        with closing(sqlite3.connect(ROOT / "source.sqlite3")) as source:
            source.execute("CREATE TABLE sample(value INTEGER)")
            source.execute("INSERT INTO sample VALUES (7)")
            source.commit()
            self.assertEqual(source.execute("SELECT value FROM sample").fetchone(), (7,))
            with closing(sqlite3.connect(ROOT / "backup.sqlite3")) as target:
                source.backup(target)
                self.assertEqual(target.execute("SELECT value FROM sample").fetchone(), (7,))
        # Reopen proves committed data survives explicit close.
        with closing(sqlite3.connect(ROOT / "source.sqlite3")) as reopened:
            self.assertEqual(reopened.execute("SELECT value FROM sample").fetchone(), (7,))

    def test_attach_is_denied_for_all_standard_connect_aliases(self):
        decoy = ROOT.parent / "existing-decoy.sqlite3"
        self.assertTrue(decoy.exists())
        creators = (sqlite3.connect, sqlite3.dbapi2.connect, _sqlite3.connect, connect_alias)
        for index, creator in enumerate(creators):
            with closing(creator(ROOT / f"allowed-{index}.sqlite3")) as connection:
                for target in (ROOT / "inside-attach.sqlite3", ROOT.parent / "attach-output.sqlite3", decoy):
                    with self.subTest(creator=index, target=target.name):
                        with BOUNDARY.expect_violation("sqlite-attach"):
                            with self.assertRaises(sqlite3.DatabaseError):
                                connection.execute("ATTACH DATABASE ? AS extra", (str(target),))
                self.assertEqual([row[1] for row in connection.execute("PRAGMA database_list")], ["main"])
                self.assertFalse((ROOT / "inside-attach.sqlite3").exists())
                self.assertFalse((ROOT.parent / "attach-output.sqlite3").exists())
        with closing(sqlite3.connect(ROOT / "script.sqlite3")) as connection:
            with BOUNDARY.expect_violation("sqlite-attach"):
                with self.assertRaises(sqlite3.DatabaseError):
                    connection.executescript("ATTACH DATABASE 'script-attach.sqlite3' AS extra;")
            self.assertFalse((ROOT / "script-attach.sqlite3").exists())

    def test_vacuum_into_is_denied_by_same_authorizer(self):
        with closing(sqlite3.connect(ROOT / "vacuum-source.sqlite3")) as connection:
            connection.execute("CREATE TABLE sample(value INTEGER)")
            connection.commit()
            for target in (ROOT / "inside-vacuum.sqlite3", ROOT.parent / "vacuum-output.sqlite3"):
                with BOUNDARY.expect_violation("sqlite-attach"):
                    with self.assertRaises(sqlite3.DatabaseError):
                        connection.execute("VACUUM INTO ?", (str(target),))
                self.assertFalse(target.exists())

    def test_backup_destination_cannot_open_outside_root(self):
        target = ROOT.parent / "backup-output.sqlite3"
        with BOUNDARY.expect_violation("write"):
            sqlite3.connect(target)
        self.assertFalse(target.exists())
        # No repo call uses direct constructors; unsupported raw creation is fail-closed.
        with BOUNDARY.expect_violation("sqlite-connect"):
            sqlite3.Connection(ROOT / "unguarded.sqlite3")
        self.assertFalse((ROOT / "unguarded.sqlite3").exists())


    def test_custom_factories_cannot_run_sql_before_authorizer(self):
        invoked = []
        output = ROOT.parent / "factory-output.sqlite3"

        class EscapingFactory(sqlite3.Connection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                invoked.append(True)
                try:
                    self.execute("ATTACH DATABASE ? AS extra", (str(output),))
                finally:
                    self.close()

        path = ROOT / "factory-source.sqlite3"
        for positional in (False, True):
            with BOUNDARY.expect_violation("sqlite-factory"):
                if positional:
                    sqlite3.connect(path, 5.0, 0, "", True, EscapingFactory)
                else:
                    sqlite3.connect(path, factory=EscapingFactory)
            self.assertEqual(invoked, [])
            self.assertFalse(path.exists())
            self.assertFalse(output.exists())
        with closing(sqlite3.connect(ROOT / "explicit-default.sqlite3", factory=sqlite3.Connection)) as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
