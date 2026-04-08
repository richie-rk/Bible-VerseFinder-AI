"""
VerseFinder AI - FastAPI Backend

Hybrid semantic + keyword search for Bible verses using FAISS + BM25 with RRF fusion.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .models.schemas import (
    SearchMode,
    SearchResponse,
    HealthResponse,
    PaginationMeta,
    ThresholdsApplied,
    TimingInfo,
    SummarizationDepth,
    SummarizationResponse,
    SummarizeRequest,
    VerseInput,
)
from .services.search import get_search_service
from .services.summarizer import summarize_verses
from .services.llm import get_available_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    search_service = get_search_service()
    try:
        search_service.load_indices()
        print(f"Loaded {search_service.total_verses} verses into search index")
    except FileNotFoundError as e:
        print(f"Warning: Could not load indices: {e}")
        print("Copy vector_store/ from scripts/ to backend/")
    yield


app = FastAPI(
    title=settings.app_name,
    description="Semantic Bible verse search using FAISS + BM25 hybrid retrieval with Adaptive RRF",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    search_service = get_search_service()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        indices_loaded=search_service.is_loaded,
        total_verses=search_service.total_verses,
    )


@app.get("/search", response_model=SearchResponse)
async def search_verses(
    query: str = Query(..., min_length=1, description="Search query"),
    mode: SearchMode = Query(default=SearchMode.HYBRID, description="Search mode"),
    limit: int = Query(default=50, ge=1, le=100, description="Page size (max 100)"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
):
    """
    Search for Bible verses using semantic, keyword, or hybrid search.

    **Search Modes:**
    - `semantic`: Pure FAISS vector search (best for concepts, themes)
    - `keyword`: Pure BM25 keyword search (best for exact terms, names)
    - `hybrid`: Adaptive RRF fusion of both (recommended)

    **Hybrid Search:**
    Uses Adaptive Weighted Reciprocal Rank Fusion where alpha (α) varies based on query type:
    - Named entities (Jesus, God): α = 0.38 (favor keywords)
    - Exact phrases ("born again"): α = 0.25 (strongly favor keywords)
    - Single concepts (grace): α = 0.65 (favor semantic)
    - General topics (What about...): α = 0.70 (favor semantic)

    **Pagination:**
    - Default page size: 50 verses
    - Maximum page size: 100 verses
    - Use `offset` to paginate through results
    """
    start_time = time.perf_counter()

    search_service = get_search_service()

    if not search_service.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search indices not loaded. Ensure vector_store/ exists in backend/",
        )

    # Perform search
    search_start = time.perf_counter()
    results, total_count, query_type, alpha = search_service.search(
        query=query,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    search_ms = (time.perf_counter() - search_start) * 1000

    # Calculate pagination metadata
    returned = len(results)
    has_more = offset + limit < total_count
    next_offset = offset + limit if has_more else None

    # Build response
    total_ms = (time.perf_counter() - start_time) * 1000

    return SearchResponse(
        query=query,
        mode=mode,
        query_type=query_type,
        alpha=round(alpha, 2),
        timing=TimingInfo(
            search_ms=round(search_ms, 2),
            total_ms=round(total_ms, 2),
        ),
        thresholds_applied=ThresholdsApplied(
            faiss=settings.faiss_threshold,
            bm25=settings.bm25_threshold,
            rrf=settings.rrf_threshold,
        ),
        pagination=PaginationMeta(
            total_results=total_count,
            limit=limit,
            offset=offset,
            returned=returned,
            has_more=has_more,
            next_offset=next_offset,
            suggested_batch_size=settings.default_page_size,
            auto_load_until=settings.auto_load_until,
        ),
        results=results,
    )


@app.get("/verses/{verse_id}")
async def get_verse(verse_id: str):
    """
    Get a specific verse by ID.

    **Verse ID format:** `Book_Chapter:Verse` (e.g., `John_3:16`, `1_John_4:8`)
    """
    search_service = get_search_service()

    if not search_service.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search indices not loaded",
        )

    # Search through metadata
    for verse in search_service._metadata:
        if verse["verse_id"] == verse_id:
            return {
                "verse_id": verse["verse_id"],
                "book": verse["book"],
                "text": verse["text"],
            }

    raise HTTPException(
        status_code=404,
        detail=f"Verse not found: {verse_id}",
    )


@app.post("/summarize", response_model=SummarizationResponse)
async def summarize_search_results(request: SummarizeRequest):
    """
    Generate an AI summary with citations from Bible verses.

    **Two Modes:**

    1. **With pre-retrieved verses (FAST):** Pass `verses` array from previous search.
       Skips search, directly summarizes provided verses. ~500ms response.

    2. **Without verses:** Performs search first, then summarizes. ~800ms response.

    **Request Body:**
    ```json
    {
      "query": "What is grace?",
      "verses": [                          // Optional - if provided, skips search
        {"verse_id": "Eph_2:8", "book": "Ephesians", "text": "For by grace..."}
      ],
      "depth": "balanced",                 // quick | balanced | comprehensive
      "provider": "openai"                 // openai | gemini | grok (optional)
    }
    ```

    **Depth Levels:**
    - `quick`: 300 tokens, top 7 verses - Fast response
    - `balanced`: 500 tokens, top 12 verses - Recommended
    - `comprehensive`: 800 tokens, top 20 verses - Deep analysis

    **Features:**
    - Multi-hop reasoning (connects related verses thematically)
    - Citation tracking (every claim cites [verse_id])
    - Grounded in retrieved verses (no hallucination)
    - Automatic fallback if primary LLM fails (OpenAI → Gemini → Grok)

    **Caching:**
    - Canonical queries (grace, faith, love, etc.) are cached for 7 days
    """
    start_time = time.perf_counter()
    search_ms = 0.0

    # Check if verses were provided (skip search)
    if request.verses:
        # Use pre-retrieved verses directly
        verses_for_summary = request.verses
    else:
        # Need to perform search
        search_service = get_search_service()

        if not search_service.is_loaded:
            raise HTTPException(
                status_code=503,
                detail="Search indices not loaded. Ensure vector_store/ exists in backend/",
            )

        # Determine top_k based on depth if not specified
        top_k = request.top_k
        if top_k is None:
            top_k = {
                SummarizationDepth.QUICK: 7,
                SummarizationDepth.BALANCED: 12,
                SummarizationDepth.COMPREHENSIVE: 20,
            }[request.depth]

        # Search for relevant verses
        search_start = time.perf_counter()
        results, total_count, query_type, alpha = search_service.search(
            query=request.query,
            mode=request.mode,
            limit=top_k,
            offset=0,
        )
        search_ms = (time.perf_counter() - search_start) * 1000

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No verses found for query: {request.query}",
            )

        # Convert VerseResult to VerseInput format
        verses_for_summary = [
            VerseInput(verse_id=v.verse_id, book=v.book, text=v.text)
            for v in results
        ]

    # Generate summary
    try:
        response = await summarize_verses(
            query=request.query,
            verses=verses_for_summary,
            depth=request.depth,
            provider=request.provider,
        )
        # Update search timing
        response.timing.search_ms = round(search_ms, 2)
        return response

    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Summarization failed: {str(e)}",
        )


@app.get("/chapters/{book}/{chapter}")
async def get_chapter(book: str, chapter: int):
    """
    Get all verses from a specific chapter.

    **Parameters:**
    - `book`: Book name (e.g., "John", "1_John", "1 John")
    - `chapter`: Chapter number

    **Returns:**
    - Book name, chapter number, total verses, and ordered verse list

    **Use Case:**
    Show full chapter context when user clicks on a search result verse.
    """
    search_service = get_search_service()

    if not search_service.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search indices not loaded",
        )

    # Normalize book name (handle both "1_John" and "1 John" formats)
    book_normalized = book.replace("_", " ")

    # Find all verses matching book and chapter
    chapter_verses = []
    for verse in search_service._metadata:
        verse_book = verse.get("book", "")
        verse_chapter = verse.get("chapter")

        if verse_book == book_normalized and verse_chapter == chapter:
            chapter_verses.append({
                "verse_id": verse["verse_id"],
                "verse_num": verse.get("verse_num", 0),
                "text": verse["text"],
            })

    if not chapter_verses:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found: {book_normalized} {chapter}",
        )

    # Sort by verse number
    chapter_verses.sort(key=lambda v: v["verse_num"])

    return {
        "book": book_normalized,
        "chapter": chapter,
        "total_verses": len(chapter_verses),
        "verses": chapter_verses,
    }


@app.get("/providers")
async def list_providers():
    try:
        available = get_available_providers()
        return {
            "available_providers": available,
            "default_provider": settings.llm_provider,
        }
    except Exception:
        return {
            "available_providers": [],
            "default_provider": settings.llm_provider,
        }
