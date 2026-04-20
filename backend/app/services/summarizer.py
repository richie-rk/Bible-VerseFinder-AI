"""
Summarization service for Bible verses.

Uses Query-Focused Abstractive Summarization with:
- Multi-Hop Reasoning (link verses together)
- Citation Tracking (every claim cites [verse_id])
- Structured JSON responses
- Grounding in retrieved verses (no hallucination)
"""

import hashlib
import json
import logging
import time
from typing import Any

from ..core.config import settings
from ..core.vocabularies import CANONICAL_QUERIES
from ..models.schemas import (
    VerseResult,
    VerseInput,
    SummarizationResponse,
    VerseCitation,
    ThematicConnection,
    TimingInfo,
    SummarizationDepth,
)
from .cache import SqliteCache
from .llm import get_llm_with_fallback

# Type alias for verses (can be either VerseResult or VerseInput)
VerseType = VerseResult | VerseInput

logger = logging.getLogger(__name__)

# Persistent summary cache — backed by SQLite so we don't re-pay the LLM for
# canonical queries across restarts. See cache.py for storage details.
_summary_cache_instance: SqliteCache | None = None


def _get_summary_cache() -> SqliteCache:
    global _summary_cache_instance
    if _summary_cache_instance is None:
        _summary_cache_instance = SqliteCache(
            db_path=settings.vector_store_path / "cache.db",
            table_name="summaries",
            ttl_seconds=settings.summary_cache_ttl_days * 24 * 3600,
            max_entries=settings.summary_cache_max_entries,
        )
    return _summary_cache_instance

SUMMARIZATION_SYSTEM_PROMPT = """You are a Biblical scholar assistant. Your task is to summarize and synthesize Bible verses to answer the user's question.

STRICT RULES:
1. ONLY use information from the provided verses. Never add external knowledge or interpretation beyond what the text states.
2. EVERY claim MUST cite the source verse using [verse_id] format inline.
3. If the verses don't adequately answer the question, acknowledge this honestly.
4. Connect related verses to show thematic relationships (multi-hop reasoning).
5. Respond ONLY with valid JSON in the exact format specified below.

RESPONSE FORMAT (JSON):
{
  "summary": "A 2-4 sentence overview answering the query with inline [verse_id] citations.",
  "key_points": [
    "First key insight with [verse_id] citation",
    "Second key insight with [verse_id] citation",
    "Third key insight with [verse_id] citation"
  ],
  "citations": [
    {"verse_id": "John_3:16", "relevance": "primary"},
    {"verse_id": "Romans_5:8", "relevance": "supporting"}
  ],
  "thematic_connections": [
    {
      "theme": "Theme Name",
      "verses": ["verse_id_1", "verse_id_2"],
      "explanation": "How these verses connect thematically"
    }
  ],
  "confidence": 0.85
}

RELEVANCE VALUES: "primary" (directly answers query), "supporting" (provides context), "contextual" (background info)

CONFIDENCE SCORING:
- 0.9-1.0: Direct, clear answer from multiple verses
- 0.7-0.8: Good coverage but some inference needed
- 0.5-0.6: Partial answer, limited verse coverage
- <0.5: Verses don't adequately address the query

CITATION FORMAT EXAMPLES:
- "God demonstrates His love for humanity [Romans_5:8] through the gift of His Son [John_3:16]."
- "Salvation comes through faith [Ephesians_2:8], not by works [Ephesians_2:9]."
"""


def _get_cache_key(query: str, verse_ids: list[str], depth: str) -> str:
    content = f"{query.lower().strip()}|{','.join(sorted(verse_ids))}|{depth}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _is_cacheable_query(query: str) -> bool:
    query_lower = query.lower().strip()
    return query_lower in CANONICAL_QUERIES


def _get_cached_summary(cache_key: str) -> SummarizationResponse | None:
    """Return the cached summary for this key, or None on miss / expiry."""
    payload = _get_summary_cache().get(cache_key)
    if payload is None:
        return None
    try:
        response = SummarizationResponse.model_validate_json(payload)
    except Exception as e:
        # Schema drifted since this row was cached — treat as miss and move on.
        logger.warning(f"Summary cache row deserialization failed for {cache_key[:8]}: {e}")
        _get_summary_cache().delete(cache_key)
        return None
    logger.info(f"Cache hit for key {cache_key[:8]}...")
    return response


def _cache_summary(cache_key: str, response: SummarizationResponse) -> None:
    _get_summary_cache().set(cache_key, response.model_dump_json().encode("utf-8"))
    logger.info(f"Cached summary for key {cache_key[:8]}...")


def _format_verses_for_llm(verses: list[VerseType]) -> str:
    lines = []
    for verse in verses:
        lines.append(f"[{verse.verse_id}] ({verse.book}): {verse.text}")
    return "\n\n".join(lines)


def _get_max_tokens(depth: SummarizationDepth) -> int:
    return {
        SummarizationDepth.QUICK: 300,
        SummarizationDepth.BALANCED: 500,
        SummarizationDepth.COMPREHENSIVE: 800,
    }[depth]


def _get_top_k(depth: SummarizationDepth) -> int:
    return {
        SummarizationDepth.QUICK: 7,
        SummarizationDepth.BALANCED: 12,
        SummarizationDepth.COMPREHENSIVE: 20,
    }[depth]


def _parse_llm_response(
    content: str,
    verses: list[VerseType],
) -> dict[str, Any]:
    """Parse and validate LLM JSON response."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        # Return minimal valid response
        return {
            "summary": content[:500] if content else "Failed to generate summary.",
            "key_points": [],
            "citations": [],
            "thematic_connections": [],
            "confidence": 0.3,
        }

    # Build verse lookup for enriching citations
    verse_lookup = {v.verse_id: v for v in verses}

    # Enrich citations with full verse text
    enriched_citations = []
    for citation in data.get("citations", []):
        verse_id = citation.get("verse_id", "")
        if verse_id in verse_lookup:
            enriched_citations.append({
                "verse_id": verse_id,
                "text": verse_lookup[verse_id].text,
                "relevance": citation.get("relevance", "supporting"),
            })

    data["citations"] = enriched_citations
    return data


async def summarize_verses(
    query: str,
    verses: list[VerseType],
    depth: SummarizationDepth = SummarizationDepth.BALANCED,
    provider: str | None = None,
) -> SummarizationResponse:
    """
    Generate a summary of verses answering the query.

    Args:
        query: User's search query
        verses: Retrieved verses to summarize (VerseResult or VerseInput)
        depth: Summarization depth (quick/balanced/comprehensive)
        provider: Preferred LLM provider (optional)

    Returns:
        SummarizationResponse with summary, citations, and connections
    """
    start_time = time.perf_counter()

    # Check cache for canonical queries
    verse_ids = [v.verse_id for v in verses]
    cache_key = _get_cache_key(query, verse_ids, depth.value)

    if _is_cacheable_query(query):
        cached = _get_cached_summary(cache_key)
        if cached:
            # Update timing for cached response
            cached.timing.total_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return cached

    # Format verses as context
    context = _format_verses_for_llm(verses)

    # Build user prompt
    user_prompt = f"""Query: {query}

Retrieved Verses ({len(verses)} total):

{context}

Based ONLY on these verses, provide a summary answering the query. Follow the JSON format exactly."""

    # Get max tokens for depth
    max_tokens = _get_max_tokens(depth)

    # Generate summary with fallback
    llm_start = time.perf_counter()
    llm_response = await get_llm_with_fallback(
        system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=0.3,
        response_format={"type": "json"},
        primary_provider=provider,
    )
    llm_ms = (time.perf_counter() - llm_start) * 1000

    # Parse response
    parsed = _parse_llm_response(llm_response.content, verses)

    # Build response
    total_ms = (time.perf_counter() - start_time) * 1000

    response = SummarizationResponse(
        query=query,
        summary=parsed.get("summary", ""),
        key_points=parsed.get("key_points", []),
        citations=[
            VerseCitation(
                verse_id=c["verse_id"],
                text=c["text"],
                relevance=c["relevance"],
            )
            for c in parsed.get("citations", [])
        ],
        thematic_connections=[
            ThematicConnection(
                theme=tc.get("theme", ""),
                verses=tc.get("verses", []),
                explanation=tc.get("explanation", ""),
            )
            for tc in parsed.get("thematic_connections", [])
        ],
        confidence=parsed.get("confidence", 0.5),
        verses_analyzed=len(verses),
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
        tokens_used=llm_response.tokens_used,
        depth=depth,
        timing=TimingInfo(
            search_ms=0,  # Will be set by endpoint
            total_ms=round(total_ms, 2),
        ),
    )

    # Cache if canonical query
    if _is_cacheable_query(query):
        _cache_summary(cache_key, response)

    return response
