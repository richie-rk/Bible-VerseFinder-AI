"""
Generic SQLite-backed key/bytes cache with optional TTL and optional size cap.

Used by:
- embeddings.py  — caches OpenAI query embeddings (long TTL, deterministic inputs)
- summarizer.py  — caches LLM summaries (short TTL, non-deterministic outputs)

Design notes:
- Both caches share the same DB file (backend/vector_store/cache.db) but live
  in different tables. Phase 4 keeps ops simple: one file to back up, delete,
  or ship.
- SQLite handles cross-process safety via its own locking. Cross-thread safety
  is handled by opening a fresh connection per operation — FastAPI runs sync
  routes on a threadpool and a single long-lived connection would need
  check_same_thread=False plus locking anyway, so the overhead of
  per-op connects is acceptable at the call volume we see.
- Eviction is lazy: expired rows are deleted on read, size cap is enforced on
  write. No background sweeper.
- A TTL of 0 means never expire. A max_entries of 0 means no cap. This keeps
  the common "embeddings cache" case (effectively permanent) a plain config.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from threading import Lock


class SqliteCache:
    """Thread-safe key/bytes cache backed by a single SQLite table."""

    def __init__(
        self,
        db_path: Path,
        table_name: str,
        ttl_seconds: int = 0,
        max_entries: int = 0,
    ) -> None:
        self._db_path = Path(db_path)
        self._table = table_name
        self._ttl_seconds = max(0, int(ttl_seconds))
        self._max_entries = max(0, int(max_entries))

        # Protects the eviction-on-write path, which does a read-then-write.
        # SQLite itself is fine with concurrent writers, but without the lock
        # two threads can race on the "am I over cap?" check and overshoot.
        self._write_lock = Lock()

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ---------- public API ----------

    def get(self, key: str) -> bytes | None:
        """Return cached bytes for `key`, or None on miss or expiry."""
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT value, created_at FROM {self._table} WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None

            value, created_at = row
            if self._ttl_seconds > 0 and (now - float(created_at)) > self._ttl_seconds:
                conn.execute(f"DELETE FROM {self._table} WHERE key = ?", (key,))
                conn.commit()
                return None

            # Update accessed_at so the LRU eviction sees this as recent.
            conn.execute(
                f"UPDATE {self._table} SET accessed_at = ? WHERE key = ?",
                (now, key),
            )
            conn.commit()
            return bytes(value)

    def set(self, key: str, value: bytes) -> None:
        """Insert or replace an entry. Evicts the least-recently-used rows if over cap."""
        now = time.time()
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO {self._table} "
                    f"(key, value, created_at, accessed_at) VALUES (?, ?, ?, ?)",
                    (key, value, now, now),
                )
                if self._max_entries > 0:
                    count = conn.execute(
                        f"SELECT COUNT(*) FROM {self._table}"
                    ).fetchone()[0]
                    overflow = count - self._max_entries
                    if overflow > 0:
                        conn.execute(
                            f"DELETE FROM {self._table} WHERE key IN ("
                            f"SELECT key FROM {self._table} "
                            f"ORDER BY accessed_at ASC LIMIT ?)",
                            (overflow,),
                        )
                conn.commit()

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self._table} WHERE key = ?", (key,))
            conn.commit()

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self._table}")
            conn.commit()

    def size(self) -> int:
        with self._connect() as conn:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()[0]
            )

    # ---------- internals ----------

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False lets the connection cross threads; we still
        # open one per op so no connection is actually shared. Explicit for
        # future-proofing if a caller holds the object briefly.
        conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=5.0,
        )
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
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
            conn.commit()
