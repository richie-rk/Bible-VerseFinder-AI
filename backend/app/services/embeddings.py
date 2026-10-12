import logging
import sqlite3
import threading

import numpy as np
import openai
from openai import OpenAI

from ..core.config import settings
from .cache import SqliteCache

logger = logging.getLogger(__name__)


class EmbeddingUnavailableError(RuntimeError):
    """The embeddings API isn't configured or didn't answer. Hybrid search
    degrades to BM25 on this; semantic-only search reports 503."""


_client: OpenAI | None = None
_cache: SqliteCache | None = None
_init_lock = threading.Lock()


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        with _init_lock:
            if _client is None:
                _client = OpenAI(
                    api_key=settings.openai_api_key,
                    timeout=settings.openai_timeout_seconds,
                    max_retries=settings.openai_max_retries,
                )
    return _client


def _get_cache() -> SqliteCache:
    global _cache
    if _cache is None:
        with _init_lock:
            if _cache is None:
                _cache = SqliteCache(
                    db_path=settings.resolved_cache_db_path,
                    table_name="embeddings",
                    ttl_seconds=settings.embedding_cache_ttl_days * 24 * 3600,
                    max_entries=settings.embedding_cache_max_entries,
                )
    return _cache


def _cache_key(text: str) -> str:
    # Model name in the key so a switch to text-embedding-3-large (or a v2
    # under a new name) ages old entries out naturally.
    return f"{settings.embedding_model}:{text}"


# The cache is an optimization: if the file can't be opened or written
# (read-only volume, locked database), search carries on without it.

def _cache_get(key: str) -> bytes | None:
    try:
        return _get_cache().get(key)
    except (sqlite3.Error, OSError) as e:
        logger.warning("Embedding cache read failed: %s", e)
        return None


def _cache_set(key: str, value: bytes) -> None:
    try:
        _get_cache().set(key, value)
    except (sqlite3.Error, OSError) as e:
        logger.warning("Embedding cache write failed: %s", e)


def get_embedding(text: str) -> np.ndarray:
    """Unit-normalized float32 embedding of `text`.

    Blocking (network + SQLite): call it from a worker thread, not the event
    loop. Raises EmbeddingUnavailableError if the API key is missing or the
    request fails.
    """
    text = text.strip()
    if not text:
        raise ValueError("Cannot embed empty text")

    key = _cache_key(text)

    cached = _cache_get(key)
    expected_bytes = settings.embedding_dim * np.dtype(np.float32).itemsize
    if cached is not None and len(cached) == expected_bytes:
        # np.frombuffer yields a read-only view; copy so callers may mutate.
        return np.frombuffer(cached, dtype=np.float32).copy()

    if not settings.openai_api_key:
        raise EmbeddingUnavailableError("OPENAI_API_KEY is not configured")

    try:
        response = _get_client().embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
    except openai.OpenAIError as e:
        raise EmbeddingUnavailableError(
            f"Embedding request failed: {type(e).__name__}: {e}"
        ) from e

    embedding = np.array(response.data[0].embedding, dtype=np.float32)
    if embedding.shape != (settings.embedding_dim,):
        raise EmbeddingUnavailableError(
            f"{settings.embedding_model} returned {embedding.shape[0]} dimensions; "
            f"the index expects {settings.embedding_dim}"
        )

    # Required for IndexFlatIP to behave as cosine similarity.
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    _cache_set(key, embedding.tobytes())
    return embedding
