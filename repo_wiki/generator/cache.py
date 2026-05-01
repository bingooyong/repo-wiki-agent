"""Generation cache backed by SQLite and optional diskcache."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .io import ensure_dir


class GenerationCache:
    def __init__(self, sqlite_path: Path, diskcache_dir: Path) -> None:
        ensure_dir(sqlite_path.parent)
        ensure_dir(diskcache_dir)
        self.sqlite_path = sqlite_path
        self.diskcache_dir = diskcache_dir
        self._init_db()
        self._disk = self._init_diskcache()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _init_diskcache(self):
        try:
            from diskcache import Cache  # type: ignore

            return Cache(str(self.diskcache_dir))
        except Exception:
            return None

    def get(self, key: str) -> Optional[str]:
        if self._disk is not None:
            value = self._disk.get(key, default=None)
            if isinstance(value, str):
                return value

        conn = sqlite3.connect(self.sqlite_path)
        try:
            row = conn.execute("SELECT value FROM generation_cache WHERE key = ?", (key,)).fetchone()
            if row:
                return str(row[0])
            return None
        finally:
            conn.close()

    def set(self, key: str, value: str) -> None:
        if self._disk is not None:
            self._disk[key] = value

        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute(
                "INSERT INTO generation_cache(key, value, created_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, created_at=excluded.created_at",
                (key, value, time.time()),
            )
            conn.commit()
        finally:
            conn.close()
