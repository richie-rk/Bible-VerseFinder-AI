from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SearchMode(str, Enum):

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class QueryType(str, Enum):
    """Query classification types for alpha selection."""

    NAMED_ENTITY = "named_entity"
    EXACT_PHRASE = "exact_phrase"
    SINGLE_CONCEPT = "single_concept"
    MULTI_CONCEPT = "multi_concept"
    GENERAL_TOPIC = "general_topic"
    COMPARATIVE = "comparative"
    VERSE_REFERENCE = "verse_reference"
    DEFAULT = "default"


class VerseResult(BaseModel):

    rank: int = Field(..., description="Result rank (1-based)")
    verse_id: str = Field(..., description="Verse identifier (e.g., 'John_3:16')")
    book: str = Field(..., description="Book name")
    text: str = Field(..., description="Verse text")
    score: float = Field(..., description="Final score (RRF for hybrid, raw for others)")
    faiss_score: Optional[float] = Field(None, description="FAISS similarity score")
    faiss_rank: Optional[int] = Field(None, description="Rank in FAISS results")
    bm25_score: Optional[float] = Field(None, description="BM25 score")
    bm25_rank: Optional[int] = Field(None, description="Rank in BM25 results")


class PaginationMeta(BaseModel):

    total_results: int = Field(..., description="Total matching verses")
    limit: int = Field(..., description="Requested page size")
    offset: int = Field(..., description="Current offset")
    returned: int = Field(..., description="Actual verses returned")
    has_more: bool = Field(..., description="More results available")
    next_offset: Optional[int] = Field(None, description="Next page offset")
    suggested_batch_size: int = Field(default=50, description="Recommended batch size")
    auto_load_until: int = Field(default=150, description="Auto-load threshold")


class ThresholdsApplied(BaseModel):

    faiss: float = Field(..., description="FAISS similarity threshold")
    bm25: float = Field(..., description="BM25 score threshold")
    rrf: float = Field(..., description="RRF score threshold")


class TimingInfo(BaseModel):

    search_ms: float = Field(..., description="Search operation time in ms")
    total_ms: float = Field(..., description="Total response time in ms")


class SearchResponse(BaseModel):

    query: str = Field(..., description="Original search query")
    mode: SearchMode = Field(..., description="Search mode used")
    query_type: QueryType = Field(..., description="Detected query type")
    alpha: Optional[float] = Field(None, description="Alpha weight used (semantic vs keyword). Null for verse-reference lookups where no blending applies.")
    timing: TimingInfo = Field(..., description="Response timing")
    thresholds_applied: ThresholdsApplied = Field(..., description="Thresholds used")
    pagination: PaginationMeta = Field(..., description="Pagination info")
    results: list[VerseResult] = Field(..., description="Verse results")


class HealthResponse(BaseModel):

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    indices_loaded: bool = Field(..., description="Whether indices are loaded")
    total_verses: int = Field(..., description="Total verses in index")


# Summarization Models

class VerseInput(BaseModel):
    """Verse input for summarization (from pre-retrieved search results)."""

    verse_id: str = Field(..., description="Verse identifier (e.g., 'John_3:16')")
    book: str = Field(..., description="Book name")
    text: str = Field(..., description="Full verse text")


class SummarizationDepth(str, Enum):

    QUICK = "quick"              # 300 tokens, top 7 verses
    BALANCED = "balanced"        # 500 tokens, top 12 verses
    COMPREHENSIVE = "comprehensive"  # 800 tokens, top 20 verses


class SummarizeRequest(BaseModel):

    query: str = Field(..., min_length=1, description="Search query (always required for LLM context)")
    verses: Optional[list[VerseInput]] = Field(
        None,
        min_length=1,
        max_length=30,
        description="Pre-retrieved verses. If provided, skips search. Min 1, Max 30.",
    )
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search mode (only used if verses not provided)")
    depth: SummarizationDepth = Field(default=SummarizationDepth.BALANCED, description="Summarization depth")
    top_k: Optional[int] = Field(default=None, ge=5, le=30, description="Number of verses (only used if verses not provided)")
    provider: Optional[str] = Field(default=None, description="LLM provider (openai, gemini, grok)")


class VerseCitation(BaseModel):

    verse_id: str = Field(..., description="Verse identifier (e.g., 'John_3:16')")
    text: str = Field(..., description="Full verse text")
    relevance: str = Field(..., description="primary | supporting | contextual")


class ThematicConnection(BaseModel):
    """Multi-hop thematic connection between verses."""

    theme: str = Field(..., description="Theme name (e.g., 'Salvation')")
    verses: list[str] = Field(..., description="Connected verse IDs")
    explanation: str = Field(..., description="How verses connect thematically")


class SummarizationResponse(BaseModel):

    query: str = Field(..., description="Original search query")
    summary: str = Field(..., description="Main summary with inline [verse_id] citations")
    key_points: list[str] = Field(..., description="Bullet points with citations")
    citations: list[VerseCitation] = Field(..., description="All cited verses")
    thematic_connections: list[ThematicConnection] = Field(..., description="Multi-hop connections")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    verses_analyzed: int = Field(..., description="Number of verses analyzed")
    llm_provider: str = Field(..., description="LLM provider used")
    llm_model: str = Field(..., description="LLM model used")
    tokens_used: int = Field(..., description="Tokens consumed")
    depth: SummarizationDepth = Field(..., description="Summarization depth used")
    timing: TimingInfo = Field(..., description="Response timing")
