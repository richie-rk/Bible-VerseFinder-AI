import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Bible Verse Finder AI"
    app_version: str = "0.1.0"
    debug: bool = False

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # openai | gemini | grok
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")

    openai_summarization_model: str = os.getenv("OPENAI_SUMMARIZATION_MODEL", "gpt-4o-mini")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_summarization_model: str = os.getenv("GEMINI_SUMMARIZATION_MODEL", "gemini-1.5-flash")

    grok_api_key: str = os.getenv("GROK_API_KEY", "")
    grok_summarization_model: str = os.getenv("GROK_SUMMARIZATION_MODEL", "grok-beta")

    vector_store_path: Path = Path(__file__).parent.parent.parent / "vector_store"

    # k candidates per retriever before RRF fusion. Must exceed the typical
    # rank gap between FAISS and BM25 for a given doc or that doc never
    # reaches fusion.
    search_k: int = int(os.getenv("SEARCH_K", "200"))

    faiss_threshold: float = 0.20

    # BM25 dynamic threshold: keep scores >= max(absolute floor, fraction of
    # top). Fixed absolute cutoffs misfire because BM25 scales with term
    # rarity — "grace" tops out ~0.8, "propitiation" tops out ~12.
    bm25_min_score: float = 0.1
    bm25_relative_threshold: float = 0.05

    # Applied to the NORMALIZED (0-1) RRF score. Raw RRF peaks at 1/(1+k) ≈
    # 0.0164 for k=60, so we normalize first to make this threshold readable.
    rrf_threshold: float = 0.15

    rrf_k: int = 60

    default_page_size: int = 50
    max_page_size: int = 100
    auto_load_until: int = 150

    alpha_named_entity: float = 0.38
    alpha_exact_phrase: float = 0.25
    alpha_single_concept: float = 0.65
    alpha_multi_concept: float = 0.60
    alpha_general_topic: float = 0.70
    alpha_comparative: float = 0.65
    alpha_default: float = 0.50

    # Embeddings are a deterministic function of (text, model) — effectively
    # never go stale, so the TTL is long. Summaries are LLM-generated and
    # prompts evolve, so shorter TTL. TTL=0 disables expiry; max_entries=0
    # disables the LRU cap.
    embedding_cache_ttl_days: int = int(os.getenv("EMBEDDING_CACHE_TTL_DAYS", "90"))
    embedding_cache_max_entries: int = int(os.getenv("EMBEDDING_CACHE_MAX_ENTRIES", "0"))
    summary_cache_ttl_days: int = int(os.getenv("SUMMARY_CACHE_TTL_DAYS", "7"))
    summary_cache_max_entries: int = int(os.getenv("SUMMARY_CACHE_MAX_ENTRIES", "0"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
