"""
Tests for the O(1) verse and chapter lookups in SearchService.

Previously the /verses/{id} and /chapters/{book}/{chapter} endpoints — plus
Phase 2's verse-reference short-circuit — did linear scans over all ~8k
verses. Phase 4 precomputes two dicts in load_indices(): _by_verse_id and
_by_chapter. These tests pin the public surface of that change, plus the
alias handling and the consistency checks run at load time.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.search import (
    IndexLoadError,
    IndexNotLoadedError,
    SearchService,
    get_search_service,
)
from app.services.verse_reference import ParsedReference


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


# ---------- Loosely written IDs and book names ----------

@pytest.mark.parametrize("raw", ["john_3:16", "JOHN_3:16", "Jn_3:16", "John 3:16"])
def test_get_verse_tolerates_case_and_abbreviations(raw):
    svc = get_search_service()
    svc.load_indices()
    verse = svc.get_verse(raw)
    assert verse is not None
    assert verse["verse_id"] == "John_3:16"


def test_get_verse_ordinal_book_aliases():
    svc = get_search_service()
    svc.load_indices()
    for raw in ["1 John_4:8", "1jn_4:8", "I John 4:8"]:
        verse = svc.get_verse(raw)
        assert verse is not None and verse["verse_id"] == "1_John_4:8", raw


@pytest.mark.parametrize("book", ["john", "JOHN", "Jn"])
def test_get_chapter_tolerates_case_and_abbreviations(book):
    svc = get_search_service()
    svc.load_indices()
    verses = svc.get_chapter(book, 3)
    assert verses and all(v["book"] == "John" for v in verses)


def test_chapter_count():
    svc = get_search_service()
    svc.load_indices()
    assert svc.chapter_count("John") == 21
    assert svc.chapter_count("1 jn") == 5
    assert svc.chapter_count("FakeBook") == 0


# ---------- Verse-ref short-circuit walks the chapter ----------

def test_lookup_reference_returns_range_in_order():
    svc = get_search_service()
    svc.load_indices()
    verses = svc._lookup_reference(ParsedReference("1 Corinthians", 13, 4, 7))
    assert [v["verse_id"] for v in verses] == [
        "1_Corinthians_13:4",
        "1_Corinthians_13:5",
        "1_Corinthians_13:6",
        "1_Corinthians_13:7",
    ]


def test_lookup_reference_wide_range_is_clamped_to_chapter():
    svc = get_search_service()
    svc.load_indices()
    verses = svc._lookup_reference(ParsedReference("John", 3, 30, 999))
    assert [v["verse_num"] for v in verses] == list(range(30, 37))


# ---------- Index consistency checks ----------

class _FakeFaiss:
    def __init__(self, d, ntotal):
        self.d = d
        self.ntotal = ntotal


class _FakeBM25:
    def __init__(self, num_docs):
        self.scores = {"num_docs": num_docs}


def _metadata(n):
    return [
        {"index_id": i, "verse_id": f"John_1:{i + 1}", "book": "John",
         "chapter": 1, "verse_num": i + 1, "text": "x"}
        for i in range(n)
    ]


DIM = settings.embedding_dim


def test_validate_indices_accepts_consistent_files():
    SearchService._validate_indices(_FakeFaiss(DIM, 3), _FakeBM25(3), _metadata(3))


@pytest.mark.parametrize(
    "faiss_index,bm25_index,metadata,message",
    [
        (_FakeFaiss(768, 3), _FakeBM25(3), _metadata(3), "dimensions"),
        (_FakeFaiss(DIM, 4), _FakeBM25(3), _metadata(3), "vectors"),
        (_FakeFaiss(DIM, 3), _FakeBM25(2), _metadata(3), "BM25"),
        (_FakeFaiss(DIM, 3), _FakeBM25(3), [*_metadata(2), {**_metadata(3)[2], "index_id": 7}], "index_id"),
        (_FakeFaiss(DIM, 3), _FakeBM25(3), [*_metadata(2), {"index_id": 2}], "missing"),
    ],
)
def test_validate_indices_rejects_mismatches(faiss_index, bm25_index, metadata, message):
    with pytest.raises(IndexLoadError, match=message):
        SearchService._validate_indices(faiss_index, bm25_index, metadata)


def test_lookups_before_load_raise():
    svc = SearchService()
    with pytest.raises(IndexNotLoadedError):
        svc.get_verse("John_3:16")
    with pytest.raises(IndexNotLoadedError):
        svc.search("grace")


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
