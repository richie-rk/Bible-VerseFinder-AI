"""
Endpoint tests for /search, /verses, /chapters and /providers, plus CORS
and rate limiting. Semantic retrieval is stubbed (see conftest.py), so none
of these need an OpenAI key.
"""

import sqlite3
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# ---------- /search ----------

def test_hybrid_search_with_embeddings(client, stub_embedding):
    stub_embedding("John_3:16")
    r = client.get("/search", params={"query": "For God so loved the world", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "hybrid"
    assert isinstance(data["alpha"], float)
    assert data["notice"] is None
    by_id = {v["verse_id"]: v for v in data["results"]}
    # The stub makes John 3:16 FAISS's exact match; BM25 decides the rest.
    assert by_id["John_3:16"]["faiss_rank"] == 1
    assert by_id["John_3:16"]["bm25_rank"] is not None


def test_hybrid_search_falls_back_to_keyword_without_embeddings(client, no_embeddings):
    r = client.get("/search", params={"query": "grace", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["alpha"] is None
    assert "keyword" in data["notice"]
    assert data["results"]
    assert all(v["faiss_rank"] is None for v in data["results"])


def test_semantic_search_without_embeddings_is_503_with_generic_detail(client, no_embeddings):
    r = client.get("/search", params={"query": "grace", "mode": "semantic"})
    assert r.status_code == 503
    assert r.json()["detail"] == main.SEMANTIC_UNAVAILABLE_DETAIL


@pytest.mark.parametrize("query", ["   ", "\t"])
def test_blank_query_is_rejected(client, query):
    r = client.get("/search", params={"query": query, "mode": "keyword"})
    assert r.status_code == 422


def test_overlong_query_is_rejected(client):
    r = client.get("/search", params={"query": "a" * 501, "mode": "keyword"})
    assert r.status_code == 422


def test_huge_verse_range_is_fast_and_not_an_error(client):
    start = time.perf_counter()
    r = client.get("/search", params={"query": "John 1:1-3000000", "mode": "keyword", "limit": 1})
    assert r.status_code == 200
    assert time.perf_counter() - start < 1.0


def test_huge_verse_number_is_not_a_500(client):
    r = client.get("/search", params={"query": "John 1:1-" + "9" * 480, "mode": "keyword"})
    assert r.status_code == 200


def test_old_testament_reference_returns_notice(client):
    r = client.get("/search", params={"query": "Psalm 23:1"})
    assert r.status_code == 200
    data = r.json()
    assert data["query_type"] == "verse_reference"
    assert data["results"] == []
    assert "Old Testament" in data["notice"]


def test_quoted_phrase_restricts_results(client):
    r = client.get("/search", params={"query": '"born again"', "mode": "keyword"})
    assert r.status_code == 200
    data = r.json()
    assert data["results"]
    assert all("born again" in v["text"].lower() for v in data["results"])
    assert data["pagination"]["total_results"] == len(data["results"])


def test_quoted_phrase_with_no_exact_match_falls_back_with_notice(client):
    r = client.get("/search", params={"query": '"grace upon grace upon grace"', "mode": "keyword"})
    assert r.status_code == 200
    data = r.json()
    assert data["results"]
    assert "exact quoted wording" in data["notice"]


def test_query_is_trimmed_in_response(client):
    r = client.get("/search", params={"query": "  John 3:16  ", "mode": "keyword"})
    assert r.status_code == 200
    assert r.json()["query"] == "John 3:16"


# ---------- /verses and /chapters ----------

@pytest.mark.parametrize("verse_id", ["John_3:16", "john_3:16", "Jn_3:16"])
def test_verse_endpoint_accepts_aliases(client, verse_id):
    r = client.get(f"/verses/{verse_id}")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "verse_id": "John_3:16",
        "book": "John",
        "chapter": 3,
        "verse_num": 16,
        "text": r.json()["text"],
    }


def test_verse_endpoint_rejects_overlong_ids(client):
    assert client.get("/verses/" + "_" * 100).status_code == 422


@pytest.mark.parametrize("book", ["john", "JOHN", "jn"])
def test_chapter_endpoint_is_case_insensitive(client, book):
    r = client.get(f"/chapters/{book}/3")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["book"] == "John"
    assert data["total_chapters"] == 21
    assert data["total_verses"] == len(data["verses"])


def test_chapter_endpoint_unknown_chapter_is_404(client):
    assert client.get("/chapters/John/22").status_code == 404


# ---------- /providers ----------

def test_providers_lists_only_configured(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "grok_api_key", "")
    r = client.get("/providers")
    assert r.status_code == 200
    assert r.json()["available_providers"] == ["gemini"]


# ---------- CORS ----------

def test_cors_allows_configured_origin_without_credentials(client):
    r = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8080"
    assert "access-control-allow-credentials" not in r.headers


def test_cors_ignores_unknown_origin(client):
    r = client.get("/health", headers={"Origin": "https://evil.example", "Cookie": "a=b"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_preflight_for_summarize(client):
    r = client.options(
        "/summarize",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8080"


# ---------- Rate limiting ----------

def test_search_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(main.search_rate_limit, "limit", 2)
    params = {"query": "John 3:16", "mode": "keyword"}
    assert client.get("/search", params=params).status_code == 200
    assert client.get("/search", params=params).status_code == 200
    r = client.get("/search", params=params)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


def test_rate_limit_of_zero_disables_it(client, monkeypatch):
    monkeypatch.setattr(main.search_rate_limit, "limit", 0)
    for _ in range(5):
        assert client.get("/search", params={"query": "John 3:16", "mode": "keyword"}).status_code == 200


# ---------- Cache failures don't break requests ----------

class _BrokenCache:
    def get(self, key):
        raise sqlite3.OperationalError("unable to open database file")

    def set(self, key, value):
        raise sqlite3.OperationalError("attempt to write a readonly database")


def test_search_survives_unusable_embedding_cache(client, monkeypatch):
    from app.core.config import settings
    from app.services import embeddings

    vector = [0.0] * settings.embedding_dim
    vector[0] = 1.0
    fake_response = SimpleNamespace(data=[SimpleNamespace(embedding=vector)])
    fake_client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda model, input: fake_response))

    monkeypatch.setattr(embeddings, "_cache", _BrokenCache())
    monkeypatch.setattr(embeddings, "_client", fake_client)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    r = client.get("/search", params={"query": "grace", "mode": "semantic", "limit": 3})
    assert r.status_code == 200, r.text
