import numpy as np
from openai import OpenAI

from ..core.config import settings
from .cache import SqliteCache


# Lazy singletons — created on first call so tests can monkeypatch settings
# before the cache is ever opened.
_client: OpenAI | None = None
_cache: SqliteCache | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def _get_cache() -> SqliteCache:
    global _cache
    if _cache is None:
        _cache = SqliteCache(
            db_path=settings.vector_store_path / "cache.db",
            table_name="embeddings",
            ttl_seconds=settings.embedding_cache_ttl_days * 24 * 3600,
            max_entries=settings.embedding_cache_max_entries,
        )
    return _cache


def _cache_key(text: str) -> str:
    # Include the model in the key so upgrading to text-embedding-3-large (or
    # OpenAI publishing a v2 under a new name) naturally invalidates old rows.
    return f"{settings.embedding_model}:{text.strip()}"


def get_embedding(text: str) -> np.ndarray:
    """
    Return a normalized embedding for `text`.

    Uses a SQLite-backed cache keyed by (model, stripped text). Embeddings are
    deterministic given the same input and model, so cache hits are free wins:
    no OpenAI call, no network round-trip, no $.
    """
    cache = _get_cache()
    key = _cache_key(text)

    cached = cache.get(key)
    if cached is not None:
        # np.frombuffer returns a read-only view; copy so callers can mutate.
        return np.frombuffer(cached, dtype=np.float32).copy()

    response = _get_client().embeddings.create(
        model=settings.embedding_model,
        input=text.strip(),
    )
    embedding = np.array(response.data[0].embedding, dtype=np.float32)

    # Normalize for cosine similarity (FAISS IndexFlatIP).
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    cache.set(key, embedding.tobytes())
    return embedding
