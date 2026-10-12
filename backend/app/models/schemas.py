from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

from ..core.config import LLMProviderName, settings

QueryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=settings.max_query_length),
]


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
    score: float = Field(
        ...,
        description=(
            "Relevance score in [0, 1]. Its meaning depends on the mode: normalized RRF "
            "(hybrid), cosine similarity (semantic), BM25 relative to the top hit (keyword, "
            "and hybrid when it falls back to keyword), 1.0 for verse-reference lookups"
        ),
    )
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

    query: str = Field(..., description="Search query (whitespace-trimmed)")
    mode: SearchMode = Field(..., description="Search mode used")
    query_type: QueryType = Field(..., description="Detected query type")
    alpha: Optional[float] = Field(
        None,
        description=(
            "Alpha weight used (semantic vs keyword). Null when no blending applied: "
            "verse-reference lookups, non-hybrid modes, and hybrid searches that fell back to keyword."
        ),
    )
    notice: Optional[str] = Field(
        None,
        description=(
            "User-facing note when the results differ from what the query implies, e.g. "
            "keyword-only fallback, an Old Testament reference, or no exact match for a quoted phrase."
        ),
    )
    timing: TimingInfo = Field(..., description="Response timing")
    thresholds_applied: ThresholdsApplied = Field(..., description="Thresholds used")
    pagination: PaginationMeta = Field(..., description="Pagination info")
    results: list[VerseResult] = Field(..., description="Verse results")


class HealthResponse(BaseModel):

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    indices_loaded: bool = Field(..., description="Whether indices are loaded")
    total_verses: int = Field(..., description="Total verses in index")


class VerseDetail(BaseModel):

    verse_id: str = Field(..., description="Canonical verse identifier (e.g., 'John_3:16')")
    book: str = Field(..., description="Book name")
    chapter: int = Field(..., description="Chapter number")
    verse_num: int = Field(..., description="Verse number")
    text: str = Field(..., description="Verse text")


class ChapterVerse(BaseModel):

    verse_id: str = Field(..., description="Verse identifier")
    verse_num: int = Field(..., description="Verse number")
    text: str = Field(..., description="Verse text")


class ChapterResponse(BaseModel):

    book: str = Field(..., description="Canonical book name (e.g., '1 John')")
    chapter: int = Field(..., description="Chapter number")
    total_chapters: int = Field(..., description="Number of chapters in this book")
    total_verses: int = Field(..., description="Number of verses in this chapter")
    verses: list[ChapterVerse] = Field(..., description="Verses in canonical order")


class ProvidersResponse(BaseModel):

    available_providers: list[str] = Field(..., description="Providers with an API key configured")
    default_provider: str = Field(..., description="Provider tried first when none is requested")


# Summarization Models

class VerseInput(BaseModel):
    """A pre-retrieved verse to summarize, identified by ID.

    The server looks the text up itself so callers can't inject their own
    wording into the prompt or the shared summary cache. `book` and `text`
    are still accepted for older clients but ignored.
    """

    verse_id: str = Field(..., min_length=1, max_length=64, description="Verse identifier (e.g., 'John_3:16')")
    book: Optional[str] = Field(None, max_length=64, description="Ignored; kept for backward compatibility")
    text: Optional[str] = Field(None, max_length=2000, description="Ignored; the server's copy of the verse is used")


class SummarizationDepth(str, Enum):

    QUICK = "quick"                  # top 7 verses
    BALANCED = "balanced"            # top 12 verses
    COMPREHENSIVE = "comprehensive"  # top 20 verses


class SummarizeRequest(BaseModel):

    query: QueryText = Field(..., description="Search query (always required for LLM context)")
    verses: Optional[list[VerseInput]] = Field(
        None,
        min_length=1,
        max_length=30,
        description="Pre-retrieved verse IDs. If provided, skips search. Min 1, Max 30.",
    )
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search mode (only used if verses not provided)")
    depth: SummarizationDepth = Field(default=SummarizationDepth.BALANCED, description="Summarization depth")
    top_k: Optional[int] = Field(default=None, ge=5, le=30, description="Number of verses (only used if verses not provided)")
    provider: Optional[LLMProviderName] = Field(default=None, description="Preferred LLM provider")


class VerseCitation(BaseModel):

    verse_id: str = Field(..., description="Verse identifier (e.g., 'John_3:16')")
    text: str = Field(..., description="Full verse text")
    relevance: Literal["primary", "supporting", "contextual"] = Field(..., description="How directly the verse answers the query")


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
