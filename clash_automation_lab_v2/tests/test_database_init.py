import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import task_page


class DatabaseInitializationTests(unittest.TestCase):
    def test_fresh_database_creates_profiles_and_task_tables(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "profiles.db"
            with patch.object(task_page, "DB", database):
                con = task_page.db()
                try:
                    tables = {
                        row[0] for row in con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    self.assertTrue({"profiles", "app_settings", "tasks"}.issubset(tables))
                    profile_columns = {
                        row[1] for row in con.execute("PRAGMA table_info(profiles)")
                    }
                    self.assertTrue({"id", "name", "serial", "enabled"}.issubset(profile_columns))
                    task_columns = {
                        row[1] for row in con.execute("PRAGMA table_info(tasks)")
                    }
                    self.assertIn("params", task_columns)
                finally:
                    con.close()

    def test_legacy_database_gets_missing_profiles_and_params(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "profiles.db"
            with sqlite3.connect(database) as con:
                con.execute(
                    "CREATE TABLE tasks (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "profile_id INTEGER, serial TEXT DEFAULT '', action TEXT NOT NULL, "
                    "status TEXT DEFAULT 'جاهزة', result TEXT DEFAULT '', "
                    "created TEXT DEFAULT CURRENT_TIMESTAMP)"
                )
            with patch.object(task_page, "DB", database):
                con = task_page.db()
                try:
                    tables = {
                        row[0] for row in con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    self.assertIn("profiles", tables)
                    columns = {
                        row[1] for row in con.execute("PRAGMA table_info(tasks)")
                    }
                    self.assertIn("params", columns)
                finally:
                    con.close()

    def test_initialization_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "profiles.db"
            with patch.object(task_page, "DB", database):
                for _ in range(3):
                    con = task_page.db()
                    con.close()
                with sqlite3.connect(database) as con:
                    count = con.execute(
                        "SELECT COUNT(*) FROM sqlite_master "
                        "WHERE type='table' AND name='profiles'"
                    ).fetchone()[0]
                    self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
