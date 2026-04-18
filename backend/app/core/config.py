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
    search_k: int = int(os.getenv("SEARCH_K", "100"))  # k=100 default, upgrade to 200 later

    # Thresholds (3-layer filtering)
    faiss_threshold: float = 0.20    # Layer 1: Semantic similarity minimum (lowered from 0.35)
    bm25_threshold: float = 0.5      # Layer 2: BM25 score minimum (lowered from 5.0)
    rrf_threshold: float = 0.003     # Layer 3: Final RRF score minimum (lowered from 0.005)

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
