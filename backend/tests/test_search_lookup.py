"""
Tests for the O(1) verse and chapter lookups in SearchService.

Previously the /verses/{id} and /chapters/{book}/{chapter} endpoints — plus
Phase 2's verse-reference short-circuit — did linear scans over all ~8k
verses. Phase 4 precomputes two dicts in load_indices(): _by_verse_id and
_by_chapter. These tests pin the public surface of that change.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.search import get_search_service


# ---------- Accessor methods ----------

def test_get_verse_known_returns_verse():
    svc = get_search_service()
    svc.load_indices()
    verse = svc.get_verse("John_3:16")
    assert verse is not None
    assert verse["verse_id"] == "John_3:16"
    assert verse["book"] == "John"
    assert verse["chapter"] == 3
    assert verse["verse_num"] == 16
    assert "loved the world" in verse["text"].lower()


def test_get_verse_unknown_returns_none():
    svc = get_search_service()
    svc.load_indices()
    assert svc.get_verse("FakeBook_1:1") is None
    assert svc.get_verse("John_3:9999") is None


def test_get_chapter_returns_sorted_verses():
    svc = get_search_service()
    svc.load_indices()
    verses = svc.get_chapter("John", 3)
    assert len(verses) > 0
    # Verses must be in canonical order
    verse_nums = [v["verse_num"] for v in verses]
    assert verse_nums == sorted(verse_nums)
    assert verse_nums[0] == 1  # chapters start at verse 1


def test_get_chapter_unknown_returns_empty():
    svc = get_search_service()
    svc.load_indices()
    assert svc.get_chapter("FakeBook", 1) == []
    assert svc.get_chapter("John", 9999) == []


def test_get_chapter_ordinal_prefix_book():
    svc = get_search_service()
    svc.load_indices()
    verses = svc.get_chapter("1 John", 4)
    assert len(verses) > 0
    assert all(v["book"] == "1 John" and v["chapter"] == 4 for v in verses)


# ---------- Verse-ref short-circuit now uses the dict ----------

def test_lookup_by_verse_ids_preserves_order():
    svc = get_search_service()
    svc.load_indices()
    ids = ["Romans_8:28", "John_3:16", "1_Corinthians_13:4"]
    results = svc._lookup_by_verse_ids(ids)
    assert [r["verse_id"] for r in results] == ids


def test_lookup_by_verse_ids_skips_unknown():
    svc = get_search_service()
    svc.load_indices()
    ids = ["John_3:16", "FakeBook_1:1", "Romans_8:28"]
    results = svc._lookup_by_verse_ids(ids)
    assert [r["verse_id"] for r in results] == ["John_3:16", "Romans_8:28"]


# ---------- Endpoint regression (main.py no longer pokes _metadata) ----------

def test_verses_endpoint_happy_path():
    with TestClient(app) as client:
        r = client.get("/verses/John_3:16")
        assert r.status_code == 200
        data = r.json()
        assert data["verse_id"] == "John_3:16"
        assert data["book"] == "John"


def test_verses_endpoint_unknown_returns_404():
    with TestClient(app) as client:
        r = client.get("/verses/Made_Up:1")
        assert r.status_code == 404


def test_chapters_endpoint_happy_path():
    with TestClient(app) as client:
        r = client.get("/chapters/John/3")
        assert r.status_code == 200
        data = r.json()
        assert data["book"] == "John"
        assert data["chapter"] == 3
        assert data["total_verses"] > 0
        # Verses should be in sorted order
        verse_nums = [v["verse_num"] for v in data["verses"]]
        assert verse_nums == sorted(verse_nums)


def test_chapters_endpoint_underscore_book_name():
    """Frontend may pass "1_John" instead of "1 John"; endpoint normalizes."""
    with TestClient(app) as client:
        r = client.get("/chapters/1_John/4")
        assert r.status_code == 200
        data = r.json()
        assert data["book"] == "1 John"
        assert data["chapter"] == 4


def test_chapters_endpoint_unknown_returns_404():
    with TestClient(app) as client:
        r = client.get("/chapters/Fake/1")
        assert r.status_code == 404
