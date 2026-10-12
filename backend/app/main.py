"""
Bible Verse Finder AI — FastAPI backend.

Hybrid semantic + keyword Bible verse search with FAISS + BM25 + RRF fusion.

Routes that search or look up verses are plain `def`, so FastAPI runs them
on its threadpool: they call blocking code (the OpenAI embeddings client,
FAISS, SQLite) that would otherwise stall the event loop for every request.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .core.config import settings
from .models.schemas import (
    ChapterResponse,
    ChapterVerse,
    HealthResponse,
    PaginationMeta,
    ProvidersResponse,
    SearchMode,
    SearchResponse,
    SummarizationResponse,
    SummarizeRequest,
    ThresholdsApplied,
    TimingInfo,
    VerseDetail,
    VerseInput,
)
from .services.embeddings import EmbeddingUnavailableError
from .services.llm import LLMUnavailableError, get_available_providers
from .services.rate_limit import RateLimiter
from .services.search import IndexLoadError, SearchService, get_search_service
from .services.summarizer import LLMOutputError, SourceVerse, summarize_verses, top_k_for_depth
from .services.verse_reference import normalize_book

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
# The OpenAI and Gemini SDKs log every HTTP request through httpx at INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

search_rate_limit = RateLimiter(settings.rate_limit_search_per_minute)
summarize_rate_limit = RateLimiter(settings.rate_limit_summarize_per_minute)

SEMANTIC_UNAVAILABLE_DETAIL = (
    "Semantic search is temporarily unavailable. Try keyword or hybrid mode."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    search_service = get_search_service()
    try:
        search_service.load_indices()
        logger.info("Loaded %d verses into search index", search_service.total_verses)
    except FileNotFoundError as e:
        logger.error(
            "Search indices not found (%s). Rebuild them with scripts/create_faiss_index.py "
            "and scripts/create_bm25_index.py.", e,
        )
    except IndexLoadError as e:
        logger.error("Search indices are inconsistent, refusing to serve them: %s", e)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Semantic Bible verse search using FAISS + BM25 hybrid retrieval with Adaptive RRF",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


def _loaded_search_service() -> SearchService:
    search_service = get_search_service()
    if not search_service.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search indices are not loaded. Check the server log.",
        )
    return search_service


def _non_blank(query: str) -> str:
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be blank.")
    return query


@app.get("/health", response_model=HealthResponse)
async def health_check():
    search_service = get_search_service()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        indices_loaded=search_service.is_loaded,
        total_verses=search_service.total_verses,
    )


@app.get("/search", response_model=SearchResponse, dependencies=[Depends(search_rate_limit)])
def search_verses(
    query: str = Query(..., min_length=1, max_length=settings.max_query_length, description="Search query"),
    mode: SearchMode = Query(default=SearchMode.HYBRID, description="Search mode"),
    limit: int = Query(
        default=settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Page size (max {settings.max_page_size})",
    ),
    offset: int = Query(default=0, ge=0, description="Page offset"),
):
    """
    Search for Bible verses using semantic, keyword, or hybrid search.

    **Search Modes:**
    - `semantic`: Pure FAISS vector search (best for concepts, themes)
    - `keyword`: Pure BM25 keyword search (best for exact terms, names)
    - `hybrid`: Adaptive RRF fusion of both (recommended). Falls back to
      keyword results, with a `notice`, if embeddings are unavailable.

    **Hybrid Search:**
    Uses Adaptive Weighted Reciprocal Rank Fusion where alpha (α) is blended
    from the query's signals, starting from these per-type targets:
    - Named entities (Jesus, God): α ≈ 0.38 (favor keywords)
    - Exact phrases ("born again"): α ≈ 0.25 (strongly favor keywords)
    - Single concepts (grace): α ≈ 0.65 (favor semantic)
    - General topics (What about...): α ≈ 0.70 (favor semantic)

    Quoted phrases ("...", “...”, '...') restrict results to verses that
    contain the phrase.

    **Pagination:**
    - Default page size: 50 verses
    - Maximum page size: 100 verses
    - Use `offset` to paginate through results
    """
    start_time = time.perf_counter()
    query = _non_blank(query)
    search_service = _loaded_search_service()

    search_start = time.perf_counter()
    try:
        outcome = search_service.search(query=query, mode=mode, limit=limit, offset=offset)
    except EmbeddingUnavailableError as e:
        logger.warning("Semantic search unavailable: %s", e)
        raise HTTPException(status_code=503, detail=SEMANTIC_UNAVAILABLE_DETAIL) from e
    search_ms = (time.perf_counter() - search_start) * 1000

    has_more = offset + limit < outcome.total
    next_offset = offset + limit if has_more else None

    total_ms = (time.perf_counter() - start_time) * 1000

    return SearchResponse(
        query=query,
        mode=mode,
        query_type=outcome.query_type,
        alpha=round(outcome.alpha, 2) if outcome.alpha is not None else None,
        notice=outcome.notice,
        timing=TimingInfo(
            search_ms=round(search_ms, 2),
            total_ms=round(total_ms, 2),
        ),
        thresholds_applied=ThresholdsApplied(
            faiss=settings.faiss_threshold,
            # bm25 threshold is dynamic per query; report the absolute floor.
            bm25=settings.bm25_min_score,
            rrf=settings.rrf_threshold,
        ),
        pagination=PaginationMeta(
            total_results=outcome.total,
            limit=limit,
            offset=offset,
            returned=len(outcome.results),
            has_more=has_more,
            next_offset=next_offset,
            suggested_batch_size=settings.default_page_size,
            auto_load_until=settings.auto_load_until,
        ),
        results=outcome.results,
    )


@app.get("/verses/{verse_id}", response_model=VerseDetail)
def get_verse(verse_id: str = Path(..., max_length=64)):
    """
    Get a specific verse by ID.

    **Verse ID format:** `Book_Chapter:Verse` (e.g., `John_3:16`, `1_John_4:8`).
    Case and common book abbreviations are tolerated (`john_3:16`, `1jn_4:8`).
    """
    verse = _loaded_search_service().get_verse(verse_id)
    if verse is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verse not found: {verse_id}",
        )
    return VerseDetail(
        verse_id=verse["verse_id"],
        book=verse["book"],
        chapter=verse["chapter"],
        verse_num=verse["verse_num"],
        text=verse["text"],
    )


def _resolve_requested_verses(
    search_service: SearchService, requested: list[VerseInput]
) -> list[SourceVerse]:
    # Only the IDs come from the caller. Text comes from the corpus so nobody
    # can put their own words into the prompt or the shared summary cache.
    verses: list[SourceVerse] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for item in requested:
        verse = search_service.get_verse(item.verse_id)
        if verse is None:
            unknown.append(item.verse_id)
        elif verse["verse_id"] not in seen:
            seen.add(verse["verse_id"])
            verses.append(SourceVerse(verse["verse_id"], verse["book"], verse["text"]))
    if unknown:
        shown = ", ".join(unknown[:5]) + (", ..." if len(unknown) > 5 else "")
        raise HTTPException(status_code=422, detail=f"Unknown verse_id(s): {shown}")
    return verses


@app.post(
    "/summarize",
    response_model=SummarizationResponse,
    dependencies=[Depends(summarize_rate_limit)],
)
async def summarize_search_results(request: SummarizeRequest):
    """
    Generate an AI summary with citations from Bible verses.

    **Two Modes:**

    1. **With pre-retrieved verses (FAST):** Pass the `verse_id`s from a
       previous search. Skips search; the server looks up each verse's text.

    2. **Without verses:** Performs search first, then summarizes.

    **Request Body:**
    ```json
    {
      "query": "What is grace?",
      "verses": [                          // Optional - if provided, skips search
        {"verse_id": "Ephesians_2:8"}      // book/text are accepted but ignored
      ],
      "depth": "balanced",                 // quick | balanced | comprehensive
      "provider": "openai"                 // openai | gemini | grok (optional)
    }
    ```

    **Depth Levels** (number of verses retrieved when none are passed):
    - `quick`: top 7 verses - Fast response
    - `balanced`: top 12 verses - Recommended
    - `comprehensive`: top 20 verses - Deep analysis

    **Features:**
    - Multi-hop reasoning (connects related verses thematically)
    - Citation tracking (every claim cites [verse_id])
    - Citations are checked against the verses provided; others are removed
    - Automatic fallback if primary LLM fails (OpenAI → Gemini → Grok)

    **Caching:**
    - Canonical queries (grace, faith, love, etc.) are cached for 7 days
    """
    start_time = time.perf_counter()
    search_service = _loaded_search_service()
    search_ms = 0.0

    if request.verses:
        verses = _resolve_requested_verses(search_service, request.verses)
    else:
        top_k = request.top_k or top_k_for_depth(request.depth)
        search_start = time.perf_counter()
        try:
            outcome = await run_in_threadpool(
                search_service.search,
                query=request.query,
                mode=request.mode,
                limit=top_k,
                offset=0,
            )
        except EmbeddingUnavailableError as e:
            logger.warning("Semantic search unavailable: %s", e)
            raise HTTPException(status_code=503, detail=SEMANTIC_UNAVAILABLE_DETAIL) from e
        search_ms = (time.perf_counter() - search_start) * 1000

        if not outcome.results:
            raise HTTPException(
                status_code=404,
                detail=f"No verses found for query: {request.query}",
            )

        verses = [SourceVerse(v.verse_id, v.book, v.text) for v in outcome.results]

    try:
        response = await summarize_verses(
            query=request.query,
            verses=verses,
            depth=request.depth,
            provider=request.provider,
        )
    except LLMOutputError as e:
        logger.warning("Unusable LLM output: %s", e)
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an unusable summary. Please try again.",
        ) from e
    except LLMUnavailableError as e:
        logger.warning("Summarization unavailable: %s", e)
        raise HTTPException(
            status_code=503,
            detail="AI summarization is temporarily unavailable. Please try again later.",
        ) from e

    response.timing.search_ms = round(search_ms, 2)
    response.timing.total_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return response


@app.get("/chapters/{book}/{chapter}", response_model=ChapterResponse)
def get_chapter(book: str = Path(..., max_length=40), chapter: int = Path(...)):
    """
    Get all verses from a specific chapter.

    **Parameters:**
    - `book`: Book name or abbreviation, any case (e.g., "John", "1_John", "1 John", "1jn")
    - `chapter`: Chapter number

    **Returns:**
    - Canonical book name, chapter number, chapter count for the book, total
      verses, and ordered verse list

    **Use Case:**
    Show full chapter context when user clicks on a search result verse.
    """
    search_service = _loaded_search_service()

    canonical_book = normalize_book(book)
    verses = search_service.get_chapter(canonical_book, chapter) if canonical_book else []
    if not verses:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found: {book.replace('_', ' ')} {chapter}",
        )

    return ChapterResponse(
        book=canonical_book,
        chapter=chapter,
        total_chapters=search_service.chapter_count(canonical_book),
        total_verses=len(verses),
        verses=[
            ChapterVerse(verse_id=v["verse_id"], verse_num=v["verse_num"], text=v["text"])
            for v in verses
        ],
    )


@app.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    return ProvidersResponse(
        available_providers=get_available_providers(),
        default_provider=settings.llm_provider,
    )
