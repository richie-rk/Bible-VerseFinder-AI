import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API
    app_name: str = "Bible Verse Finder AI"
    app_version: str = "0.1.0"
    debug: bool = False

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # LLM Providers
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")  # openai | gemini | grok

    # OpenAI Summarization
    openai_summarization_model: str = os.getenv("OPENAI_SUMMARIZATION_MODEL", "gpt-4o-mini")

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_summarization_model: str = os.getenv("GEMINI_SUMMARIZATION_MODEL", "gemini-1.5-flash")

    # Grok (xAI)
    grok_api_key: str = os.getenv("GROK_API_KEY", "")
    grok_summarization_model: str = os.getenv("GROK_SUMMARIZATION_MODEL", "grok-beta")

    # Paths
    vector_store_path: Path = Path(__file__).parent.parent.parent / "vector_store"

    # Search Parameters
    # search_k: how many candidates each retriever returns before RRF fusion.
    # Larger pool = more recall for hybrid (a doc at rank 60 in FAISS and rank 140
    # in BM25 only makes it into fusion if both k's are >=140). FAISS IndexFlatIP
    # over ~8k vectors is ~1-2ms so 200 is not a latency concern.
    search_k: int = int(os.getenv("SEARCH_K", "200"))

    # Thresholds (3-layer filtering)
    faiss_threshold: float = 0.20    # Layer 1: Semantic similarity minimum (lowered from 0.35)

    # Layer 2: BM25 dynamic threshold. Absolute BM25 scores vary wildly with
    # query-term rarity, so a single fixed cutoff is wrong for most queries.
    # Keep results scoring >= max(bm25_min_score, top_bm25 * bm25_relative_threshold).
    bm25_min_score: float = 0.1              # Absolute floor for noise rejection
    bm25_relative_threshold: float = 0.05    # Fraction of top BM25 score to keep

    # Layer 3: RRF threshold, applied to the NORMALIZED (0-1) score.
    # The raw RRF formula peaks at 1/(1+k) ≈ 0.0164 for k=60, so a raw cutoff like
    # 0.003 was really ~0.18 on the normalized scale — confusing to tune. We now
    # normalize first and threshold on a 0-1 scale users can reason about directly.
    rrf_threshold: float = 0.15

    # RRF constant (standard is 60)
    rrf_k: int = 60

    # Pagination
    default_page_size: int = 50
    max_page_size: int = 100
    auto_load_until: int = 150

    # Alpha values for query types
    alpha_named_entity: float = 0.38
    alpha_exact_phrase: float = 0.25
    alpha_single_concept: float = 0.65
    alpha_multi_concept: float = 0.60
    alpha_general_topic: float = 0.70
    alpha_comparative: float = 0.65
    alpha_default: float = 0.50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
