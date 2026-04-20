import numpy as np
from openai import OpenAI

from ..core.config import settings
from .cache import SqliteCache


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
    # Model name in the key so a switch to text-embedding-3-large (or a v2
    # under a new name) ages old entries out naturally.
    return f"{settings.embedding_model}:{text.strip()}"


def get_embedding(text: str) -> np.ndarray:
    cache = _get_cache()
    key = _cache_key(text)

    cached = cache.get(key)
    if cached is not None:
        # np.frombuffer yields a read-only view; copy so callers may mutate.
        return np.frombuffer(cached, dtype=np.float32).copy()

    response = _get_client().embeddings.create(
        model=settings.embedding_model,
        input=text.strip(),
    )
    embedding = np.array(response.data[0].embedding, dtype=np.float32)

    # Required for IndexFlatIP to behave as cosine similarity.
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    cache.set(key, embedding.tobytes())
    return embedding
