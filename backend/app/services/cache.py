"""
SQLite-backed key/bytes cache with optional TTL and optional LRU cap.

Backs both the embedding cache (long TTL, deterministic inputs) and the
summary cache (short TTL, non-deterministic outputs) in a single DB file so
ops only has one thing to back up, delete, or ship.

Every operation opens and closes its own connection, so one instance is safe
to share across threads (sync FastAPI routes run on a threadpool). The file
runs in WAL mode so readers don't block on writers. LRU eviction is a single
DELETE inside the writing transaction, and SQLite serializes write
transactions, so concurrent writers — even in different processes — can't
both see "under the cap" and overshoot it.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

_TABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class SqliteCache:
    """Thread-safe key/bytes cache backed by a single SQLite table."""

    def __init__(
        self,
        db_path: Path,
        table_name: str,
        ttl_seconds: int = 0,
        max_entries: int = 0,
    ) -> None:
        # The table name is interpolated into SQL, so it must be an identifier.
        if not _TABLE_NAME.fullmatch(table_name):
            raise ValueError(f"Invalid cache table name: {table_name!r}")
        self._db_path = Path(db_path)
        self._table = table_name
        self._ttl_seconds = max(0, int(ttl_seconds))
        self._max_entries = max(0, int(max_entries))

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, key: str) -> bytes | None:
        now = time.time()
        with self._transaction() as conn:
            row = conn.execute(
                f"SELECT value, created_at FROM {self._table} WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None

            value, created_at = row
            if self._ttl_seconds > 0 and (now - float(created_at)) > self._ttl_seconds:
                conn.execute(f"DELETE FROM {self._table} WHERE key = ?", (key,))
                return None

            conn.execute(
                f"UPDATE {self._table} SET accessed_at = ? WHERE key = ?",
                (now, key),
            )
            return bytes(value)

    def set(self, key: str, value: bytes) -> None:
        now = time.time()
        with self._transaction() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {self._table} "
                f"(key, value, created_at, accessed_at) VALUES (?, ?, ?, ?)",
                (key, value, now, now),
            )
            if self._ttl_seconds > 0:
                # Expired rows are otherwise only removed when read again.
                conn.execute(
                    f"DELETE FROM {self._table} WHERE created_at < ?",
                    (now - self._ttl_seconds,),
                )
            if self._max_entries > 0:
                # Keep the max_entries most recently used rows.
                conn.execute(
                    f"DELETE FROM {self._table} WHERE key IN ("
                    f"SELECT key FROM {self._table} "
                    f"ORDER BY accessed_at DESC LIMIT -1 OFFSET ?)",
                    (self._max_entries,),
                )

    def delete(self, key: str) -> None:
        with self._transaction() as conn:
            conn.execute(f"DELETE FROM {self._table} WHERE key = ?", (key,))

    def clear(self) -> None:
        with self._transaction() as conn:
            conn.execute(f"DELETE FROM {self._table}")

    def size(self) -> int:
        with self._transaction() as conn:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()[0]
            )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        # A sqlite3 connection's own context manager commits or rolls back but
        # never closes, so closing() is what actually releases the handle.
        with closing(sqlite3.connect(self._db_path, timeout=5.0)) as conn:
            with conn:
                yield conn

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self._db_path, timeout=5.0)) as conn:
            # Persistent per database file; a no-op on filesystems without WAL.
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table} (
                        key TEXT PRIMARY KEY,
                        value BLOB NOT NULL,
                        created_at REAL NOT NULL,
                        accessed_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS "
                    f"{self._table}_accessed_idx ON {self._table}(accessed_at)"
                )
