"""
Tests for the SQLite-backed cache used by embeddings and summaries.

Each test uses pytest's tmp_path fixture so nothing touches the real
backend/vector_store/cache.db.
"""

import time

import pytest

from app.services.cache import SqliteCache


# ---------- Basic get / set / delete ----------

def test_miss_returns_none(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t")
    assert cache.get("nope") is None


def test_roundtrip_bytes(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t")
    cache.set("k", b"\x00\x01\x02hello")
    assert cache.get("k") == b"\x00\x01\x02hello"


def test_overwrite_updates_value(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t")
    cache.set("k", b"first")
    cache.set("k", b"second")
    assert cache.get("k") == b"second"
    assert cache.size() == 1


def test_delete_removes_entry(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t")
    cache.set("k", b"v")
    cache.delete("k")
    assert cache.get("k") is None
    assert cache.size() == 0


def test_clear_wipes_everything(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t")
    for i in range(5):
        cache.set(f"k{i}", b"v")
    assert cache.size() == 5
    cache.clear()
    assert cache.size() == 0


# ---------- TTL ----------

def test_ttl_zero_means_never_expire(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t", ttl_seconds=0)
    cache.set("k", b"v")
    # Nothing should expire regardless of elapsed time — we don't wait long
    # enough for wall-clock drift to matter, we just rely on ttl=0 semantics.
    assert cache.get("k") == b"v"


def test_ttl_expires_old_entries(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t", ttl_seconds=1)
    cache.set("k", b"v")
    # Under TTL → hit
    assert cache.get("k") == b"v"
    # Past TTL → miss, row also deleted as side-effect
    time.sleep(1.1)
    assert cache.get("k") is None
    assert cache.size() == 0


# ---------- LRU eviction ----------

def test_max_entries_zero_means_unlimited(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t", max_entries=0)
    for i in range(50):
        cache.set(f"k{i}", b"v")
    assert cache.size() == 50


def test_max_entries_caps_and_evicts_lru(tmp_path):
    cache = SqliteCache(tmp_path / "c.db", "t", max_entries=3)
    cache.set("a", b"1")
    time.sleep(0.01)
    cache.set("b", b"2")
    time.sleep(0.01)
    cache.set("c", b"3")
    # Touch 'a' to refresh its accessed_at — now 'b' is the LRU candidate
    assert cache.get("a") == b"1"
    time.sleep(0.01)
    # Insert 4th entry; cache must evict the least-recently-used, which is 'b'.
    cache.set("d", b"4")
    assert cache.size() == 3
    assert cache.get("a") == b"1"
    assert cache.get("b") is None    # evicted
    assert cache.get("c") == b"3"
    assert cache.get("d") == b"4"


def test_get_updates_accessed_at_for_lru(tmp_path):
    """Repeatedly touching a key should protect it from LRU eviction."""
    cache = SqliteCache(tmp_path / "c.db", "t", max_entries=2)
    cache.set("a", b"1")
    time.sleep(0.01)
    cache.set("b", b"2")
    time.sleep(0.01)
    cache.get("a")                    # refresh 'a'
    time.sleep(0.01)
    cache.set("c", b"3")              # should evict 'b', not 'a'
    assert cache.get("a") == b"1"
    assert cache.get("b") is None
    assert cache.get("c") == b"3"


# ---------- Persistence ----------

def test_persists_across_instances(tmp_path):
    db_path = tmp_path / "c.db"
    c1 = SqliteCache(db_path, "t")
    c1.set("k", b"hello")
    del c1

    c2 = SqliteCache(db_path, "t")
    assert c2.get("k") == b"hello"


def test_separate_tables_isolated(tmp_path):
    """Two caches on the same DB file but different tables don't collide."""
    db_path = tmp_path / "c.db"
    a = SqliteCache(db_path, "embeddings")
    b = SqliteCache(db_path, "summaries")
    a.set("k", b"in-a")
    b.set("k", b"in-b")
    assert a.get("k") == b"in-a"
    assert b.get("k") == b"in-b"
    assert a.size() == 1
    assert b.size() == 1
