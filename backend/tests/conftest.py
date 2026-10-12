"""
Shared fixtures.

Every test gets throwaway SQLite caches (nothing touches the real
backend/vector_store/cache.db) and fresh rate-limit windows.
"""

import pytest

from app import main
from app.services import embeddings, summarizer
from app.services.cache import SqliteCache
from app.services.search import get_search_service


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(embeddings, "_cache", SqliteCache(db_path, "embeddings"))
    monkeypatch.setattr(summarizer, "_summary_cache_instance", SqliteCache(db_path, "summaries"))


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    main.search_rate_limit.reset()
    main.summarize_rate_limit.reset()


@pytest.fixture
def loaded_service():
    svc = get_search_service()
    svc.load_indices()
    return svc


@pytest.fixture
def stub_embedding(monkeypatch, loaded_service):
    """Make semantic retrieval work offline by embedding every query as the
    stored vector of one verse, so that verse is FAISS's top hit."""

    def install(verse_id: str = "John_3:16") -> None:
        idx = next(i for i, v in enumerate(loaded_service._metadata) if v["verse_id"] == verse_id)
        vector = loaded_service._faiss_index.reconstruct(idx)
        monkeypatch.setattr("app.services.search.get_embedding", lambda text: vector.copy())

    return install


@pytest.fixture
def no_embeddings(monkeypatch):
    """Simulate a missing OPENAI_API_KEY regardless of the environment."""
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "")
