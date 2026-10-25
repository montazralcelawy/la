from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / "AppData" / "Local" / "ClashAutomationLab"
DB_PATH = APP_DIR / "clash_lab.sqlite3"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE,
 serial TEXT NOT NULL DEFAULT '',
 enabled INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 profile_id INTEGER,
 task_type TEXT NOT NULL DEFAULT 'general',
 name TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 0,
 config_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS settings (
 key TEXT PRIMARY KEY,
 value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 level TEXT NOT NULL,
 message TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def log(self, level: str, message: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO logs(level, message) VALUES (?, ?)", (level.upper(), message))

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value_json) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def list_profiles(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM profiles ORDER BY id")]

    def add_profile(self, name: str, serial: str = "") -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("اسم القرية مطلوب.")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO profiles(name,serial) VALUES (?,?)",
                (clean_name, serial.strip()),
            )
            return int(cur.lastrowid)

    def delete_profile(self, profile_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM profiles WHERE id=?", (int(profile_id),))

    def list_tasks(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        params: tuple[Any, ...] = ()
        if profile_id is not None:
            query += " WHERE profile_id=?"
            params = (int(profile_id),)
        query += " ORDER BY id"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def add_task(
        self,
        name: str,
        task_type: str = "general",
        profile_id: int | None = None,
        config: dict[str, Any] | None = None,
        enabled: bool = False,
    ) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("اسم المهمة مطلوب.")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks(profile_id,task_type,name,enabled,config_json) VALUES (?,?,?,?,?)",
                (
                    profile_id,
                    task_type.strip() or "general",
                    clean_name,
                    int(enabled),
                    json.dumps(config or {}, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def set_task_enabled(self, task_id: int, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE tasks SET enabled=? WHERE id=?", (int(enabled), int(task_id)))
