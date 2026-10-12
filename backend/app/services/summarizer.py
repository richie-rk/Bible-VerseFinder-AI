"""
LLM-based summarization of retrieved verses. Strictly grounded: the prompt
forbids the model from adding facts beyond what's in the passed verses, and
every claim must inline-cite its source verse_id. Citations of verses that
weren't passed in are removed before the response goes out.

Verse text always comes from the server's corpus (search results or ID
lookups), never from the API caller, so cached summaries can't be poisoned.
"""

import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..core.config import settings
from ..core.vocabularies import CANONICAL_QUERIES
from ..models.schemas import (
    SummarizationResponse,
    VerseCitation,
    ThematicConnection,
    TimingInfo,
    SummarizationDepth,
)
from .cache import SqliteCache
from .llm import LLMResponse, get_llm_with_fallback

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceVerse:
    verse_id: str
    book: str
    text: str


class LLMOutputError(RuntimeError):
    """The provider answered, but not with anything usable as a summary."""


# Verses retrieved when the caller doesn't pass any.
DEPTH_TOP_K: dict[SummarizationDepth, int] = {
    SummarizationDepth.QUICK: 7,
    SummarizationDepth.BALANCED: 12,
    SummarizationDepth.COMPREHENSIVE: 20,
}

# Output token caps. The JSON envelope is expensive (the citations list alone
# is ~15 tokens per verse), and the old 300/500/800 caps routinely cut the
# JSON off mid-object. The prompt, not the cap, keeps answers short.
DEPTH_MAX_TOKENS: dict[SummarizationDepth, int] = {
    SummarizationDepth.QUICK: 700,
    SummarizationDepth.BALANCED: 1000,
    SummarizationDepth.COMPREHENSIVE: 1500,
}

# Bump when the prompt or response handling changes so stale cached
# summaries stop being served.
_CACHE_KEY_VERSION = "2"

_DEFAULT_CONFIDENCE = 0.5
_PROSE_FALLBACK_CONFIDENCE = 0.3
_RELEVANCE_VALUES = {"primary", "supporting", "contextual"}

_CODE_FENCE = re.compile(r"^```[A-Za-z]*\s*(.*?)\s*```$", re.DOTALL)
# Inline citation markers: [John_3:16], [1_John_4:8, 1_John_4:9], [Romans_8:28-30]
_CITATION_MARKER = re.compile(r"(\s?)\[([^\[\]]{1,200})\]")
_VERSE_ID_SHAPE = re.compile(r"(?:[1-3]_)?[A-Za-z]+_\d+:\d+(?:-\d+)?")


def top_k_for_depth(depth: SummarizationDepth) -> int:
    return DEPTH_TOP_K[depth]


# SQLite-backed so canonical-query summaries survive restarts.
_summary_cache_instance: SqliteCache | None = None


def _get_summary_cache() -> SqliteCache:
    global _summary_cache_instance
    if _summary_cache_instance is None:
        _summary_cache_instance = SqliteCache(
            db_path=settings.resolved_cache_db_path,
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
    content = f"v{_CACHE_KEY_VERSION}|{query.lower().strip()}|{','.join(sorted(verse_ids))}|{depth}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _is_cacheable_query(query: str) -> bool:
    query_lower = query.lower().strip()
    return query_lower in CANONICAL_QUERIES


def _get_cached_summary(cache_key: str) -> SummarizationResponse | None:
    """Return the cached summary for this key, or None on miss / expiry."""
    try:
        payload = _get_summary_cache().get(cache_key)
    except (sqlite3.Error, OSError) as e:
        # The cache is an optimization; summarize without it.
        logger.warning("Summary cache read failed: %s", e)
        return None
    if payload is None:
        return None
    try:
        response = SummarizationResponse.model_validate_json(payload)
    except ValueError as e:
        # Schema drifted since this row was cached — treat as miss and move on.
        logger.warning("Summary cache row deserialization failed for %s: %s", cache_key[:8], e)
        try:
            _get_summary_cache().delete(cache_key)
        except (sqlite3.Error, OSError):
            pass
        return None
    logger.info("Cache hit for key %s...", cache_key[:8])
    return response


def _cache_summary(cache_key: str, response: SummarizationResponse) -> None:
    try:
        _get_summary_cache().set(cache_key, response.model_dump_json().encode("utf-8"))
    except (sqlite3.Error, OSError) as e:
        logger.warning("Summary cache write failed: %s", e)
        return
    logger.info("Cached summary for key %s...", cache_key[:8])


def _format_verses_for_llm(verses: Sequence[SourceVerse]) -> str:
    lines = []
    for verse in verses:
        lines.append(f"[{verse.verse_id}] ({verse.book}): {verse.text}")
    return "\n\n".join(lines)


def _extract_json_object(content: str) -> dict[str, Any] | None:
    """The JSON object in an LLM reply, tolerating ```json fences and text
    around it. None if there isn't a complete object (e.g. truncated)."""
    text = content.strip()
    fence = _CODE_FENCE.match(text)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            data, _ = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [text for text in map(_as_text, value) if text]


def _as_confidence(value: Any) -> float:
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return _DEFAULT_CONFIDENCE
    if math.isnan(confidence) or math.isinf(confidence):
        return _DEFAULT_CONFIDENCE
    if 1.0 < confidence <= 100.0:
        # Models sometimes answer in percent.
        confidence /= 100.0
    return min(max(confidence, 0.0), 1.0)


def _strip_unknown_citations(text: str, known_ids: set[str]) -> str:
    """Drop inline [verse_id] markers that cite verses the model wasn't
    given. Bracketed text that isn't shaped like verse IDs is left alone."""

    def replace(match: re.Match) -> str:
        lead, inner = match.group(1), match.group(2)
        ids = [part.strip() for part in re.split(r"[,;]", inner)]
        if not all(_VERSE_ID_SHAPE.fullmatch(vid) for vid in ids):
            return match.group(0)
        kept = [vid for vid in ids if vid.split("-", 1)[0] in known_ids]
        return f"{lead}[{', '.join(kept)}]" if kept else ""

    return _CITATION_MARKER.sub(replace, text).strip()


def _summary_fields(payload: dict[str, Any], verses: Sequence[SourceVerse]) -> dict[str, Any]:
    """Coerce an LLM JSON payload into SummarizationResponse fields, keeping
    only citations of verses that were actually supplied."""
    by_id = {v.verse_id: v for v in verses}
    known_ids = set(by_id)

    citations = []
    seen: set[str] = set()
    raw_citations = payload.get("citations")
    for item in raw_citations if isinstance(raw_citations, list) else []:
        if isinstance(item, str):
            item = {"verse_id": item}
        if not isinstance(item, dict):
            continue
        verse_id = _as_text(item.get("verse_id"))
        if verse_id not in by_id or verse_id in seen:
            continue
        seen.add(verse_id)
        relevance = _as_text(item.get("relevance")).lower()
        citations.append(VerseCitation(
            verse_id=verse_id,
            text=by_id[verse_id].text,
            relevance=relevance if relevance in _RELEVANCE_VALUES else "supporting",
        ))

    connections = []
    raw_connections = payload.get("thematic_connections")
    for item in raw_connections if isinstance(raw_connections, list) else []:
        if not isinstance(item, dict):
            continue
        connected = [vid for vid in _as_text_list(item.get("verses")) if vid in known_ids]
        if not connected:
            continue
        connections.append(ThematicConnection(
            theme=_as_text(item.get("theme")),
            verses=list(dict.fromkeys(connected)),
            explanation=_strip_unknown_citations(_as_text(item.get("explanation")), known_ids),
        ))

    return {
        "summary": _strip_unknown_citations(_as_text(payload.get("summary")), known_ids),
        "key_points": [
            point for point in (
                _strip_unknown_citations(p, known_ids) for p in _as_text_list(payload.get("key_points"))
            ) if point
        ],
        "citations": citations,
        "thematic_connections": connections,
        "confidence": _as_confidence(payload.get("confidence", _DEFAULT_CONFIDENCE)),
    }


def _prose_fields(content: str, verses: Sequence[SourceVerse]) -> dict[str, Any] | None:
    """Fields for a reply that ignored JSON mode and answered in plain prose.
    None if the reply is empty or is broken JSON (which mustn't be shown)."""
    text = content.strip()
    if not text or text[0] in "{[" or text.startswith("```"):
        return None
    return {
        "summary": _strip_unknown_citations(text[:2000], {v.verse_id for v in verses}),
        "key_points": [],
        "citations": [],
        "thematic_connections": [],
        "confidence": _PROSE_FALLBACK_CONFIDENCE,
    }


async def _generate(user_prompt: str, max_tokens: int, provider: str | None) -> LLMResponse:
    return await get_llm_with_fallback(
        system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=0.3,
        json_output=True,
        primary_provider=provider,
    )


async def summarize_verses(
    query: str,
    verses: Sequence[SourceVerse],
    depth: SummarizationDepth = SummarizationDepth.BALANCED,
    provider: str | None = None,
) -> SummarizationResponse:
    """
    Generate a summary of verses answering the query.

    Args:
        query: User's search query
        verses: Verses to summarize, with text from the server's corpus
        depth: Summarization depth (quick/balanced/comprehensive)
        provider: Preferred LLM provider (optional)

    Returns:
        SummarizationResponse with summary, citations, and connections

    Raises:
        LLMUnavailableError: no provider could be reached
        LLMOutputError: the provider's reply couldn't be turned into a summary
    """
    start_time = time.perf_counter()

    cacheable = _is_cacheable_query(query)
    cache_key = _get_cache_key(query, [v.verse_id for v in verses], depth.value)

    if cacheable:
        cached = await asyncio.to_thread(_get_cached_summary, cache_key)
        if cached is not None:
            # The row may have been written for another casing of the query.
            return cached.model_copy(update={
                "query": query,
                "timing": TimingInfo(
                    search_ms=0,
                    total_ms=round((time.perf_counter() - start_time) * 1000, 2),
                ),
            })

    user_prompt = f"""Query: {query}

Retrieved Verses ({len(verses)} total):

{_format_verses_for_llm(verses)}

Based ONLY on these verses, provide a summary answering the query. Follow the JSON format exactly."""

    max_tokens = DEPTH_MAX_TOKENS[depth]
    llm_response = await _generate(user_prompt, max_tokens, provider)
    tokens_used = llm_response.tokens_used
    payload = _extract_json_object(llm_response.content)

    if payload is None and llm_response.finish_reason == "length":
        # Cut off mid-JSON: retry once with twice the budget, starting with
        # the provider that just answered.
        logger.info(
            "LLM output truncated at %d tokens by %s; retrying with %d",
            max_tokens, llm_response.provider, max_tokens * 2,
        )
        llm_response = await _generate(user_prompt, max_tokens * 2, llm_response.provider)
        tokens_used += llm_response.tokens_used
        payload = _extract_json_object(llm_response.content)

    if payload is not None:
        fields = _summary_fields(payload, verses)
        if not fields["summary"] and not fields["key_points"]:
            raise LLMOutputError(f"{llm_response.provider} returned JSON without a summary")
    else:
        logger.warning("LLM response from %s was not a JSON object", llm_response.provider)
        fields = _prose_fields(llm_response.content, verses)
        if fields is None:
            raise LLMOutputError(
                f"{llm_response.provider} returned an incomplete or malformed JSON summary "
                f"(finish_reason={llm_response.finish_reason})"
            )

    response = SummarizationResponse(
        query=query,
        **fields,
        verses_analyzed=len(verses),
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
        tokens_used=tokens_used,
        depth=depth,
        timing=TimingInfo(
            search_ms=0,  # Will be set by endpoint
            total_ms=round((time.perf_counter() - start_time) * 1000, 2),
        ),
    )

    # Only well-formed JSON answers are worth keeping for a week.
    if cacheable and payload is not None:
        await asyncio.to_thread(_cache_summary, cache_key, response)

    return response
