from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

LLMProviderName = Literal["openai", "gemini", "grok"]


class Settings(BaseSettings):
    """Application settings.

    Every field can be overridden by an environment variable of the same name
    (case-insensitive, e.g. OPENAI_API_KEY or SEARCH_K) or by backend/.env.
    The .env path is absolute so it's found whichever directory uvicorn is
    started from.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Bible Verse Finder AI"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # Comma-separated origins allowed to call the API from a browser. The
    # defaults cover the Vite dev server; set this for any deployed frontend.
    cors_origins: str = (
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    # Embedding calls sit on the search path, so fail fast rather than use
    # the SDK's 10-minute default; hybrid search falls back to BM25.
    openai_timeout_seconds: float = 15.0
    openai_max_retries: int = 2

    llm_provider: LLMProviderName = "openai"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1

    openai_summarization_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    # Google-maintained alias that tracks the current Flash model. Pin a
    # specific version here if you need reproducible output.
    gemini_summarization_model: str = "gemini-flash-latest"
    # Gemini 3 models think at "high" unless told otherwise, which is slow
    # for summarization. Set to "" for models without thinking levels.
    gemini_thinking_level: str = "low"

    grok_api_key: str = ""
    grok_summarization_model: str = "grok-4.20-non-reasoning"

    vector_store_path: Path = BACKEND_DIR / "vector_store"
    # SQLite file holding the embedding and summary caches. Unset means
    # vector_store/cache.db.
    cache_db_path: Path | None = None

    # k candidates per retriever before RRF fusion. Must exceed the typical
    # rank gap between FAISS and BM25 for a given doc or that doc never
    # reaches fusion.
    search_k: int = 200

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
    max_query_length: int = 500

    # Per client IP, per minute. Each /search miss costs an embedding call and
    # each /summarize an LLM call. 0 disables the limit.
    rate_limit_search_per_minute: int = 120
    rate_limit_summarize_per_minute: int = 10

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
    # disables the LRU cap. Every distinct query adds an embedding row
    # (~6 KB), so the cap keeps the file from growing without bound.
    embedding_cache_ttl_days: int = 90
    embedding_cache_max_entries: int = 10_000
    summary_cache_ttl_days: int = 7
    summary_cache_max_entries: int = 1_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_cache_db_path(self) -> Path:
        return self.cache_db_path or self.vector_store_path / "cache.db"


settings = Settings()
