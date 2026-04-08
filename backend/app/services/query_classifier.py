"""
Query classifier using heuristics to determine query type and alpha value.

Query Types and Alpha Values:
- Named Entities (0.35-0.40): "Jesus teaches", "What does God say"
- Exact Phrases (0.20-0.30): "I AM that I AM", "born again"
- Single Concepts (0.60-0.70): "grace", "redemption", "faith"
- Multi-Concepts (0.55-0.65): "grace and faith", "love and mercy"
- General Topics (0.65-0.75): "What about suffering?"
- Comparative (0.60-0.70): "grace vs mercy"
- Default (0.50): Unknown type
"""

import re

from ..core.config import settings
from ..models.schemas import QueryType


# Biblical named entities (common names, places, titles)
BIBLICAL_NAMES = {
    "jesus", "christ", "god", "lord", "father", "spirit", "holy spirit",
    "moses", "abraham", "david", "paul", "peter", "john", "james",
    "mary", "joseph", "adam", "eve", "noah", "jacob", "isaac",
    "elijah", "elisha", "isaiah", "jeremiah", "daniel", "solomon",
    "pharisee", "sadducee", "apostle", "disciple",
    "israel", "jerusalem", "galilee", "judea", "nazareth", "bethlehem",
    "heaven", "hell", "satan", "devil", "angel", "demon",
}

# Exact phrase indicators (quotes or well-known phrases)
EXACT_PHRASE_PATTERNS = [
    r'"[^"]+?"',  # Quoted phrases
    r"'[^']+?'",  # Single quoted phrases
    r"\bi am\b.*\bi am\b",  # "I AM that I AM" pattern
    r"\bborn again\b",
    r"\bkingdom of (god|heaven)\b",
    r"\bson of (god|man|david)\b",
    r"\bword of god\b",
    r"\blamb of god\b",
    r"\bbread of life\b",
    r"\blight of the world\b",
    r"\bgood shepherd\b",
    r"\bthe way,? the truth,? (and )?the life\b",
    r"\bfruit of the spirit\b",
    r"\barmor of god\b",
    r"\blord's prayer\b",
    r"\bbeatitudes\b",
    r"\bten commandments\b",
    r"\bgolden rule\b",
]

# Comparative indicators
COMPARATIVE_PATTERNS = [
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bcompare[d]?\b",
    r"\bdifference between\b",
    r"\bor\b.*\bwhich\b",
    r"\bbetter\b.*\bthan\b",
]

# General topic indicators (questions, broad topics)
GENERAL_TOPIC_PATTERNS = [
    r"^what\s+(is|are|does|about)\b",
    r"^how\s+(do|does|can|should)\b",
    r"^why\s+(do|does|did|is|are)\b",
    r"^where\s+(is|are|does)\b",
    r"^when\s+(did|does|will)\b",
    r"^who\s+(is|are|was|were)\b",
    r"\babout\b",
    r"\bteaching[s]?\s+on\b",
    r"\bverses?\s+(about|on)\b",
]

# Multi-concept indicators
MULTI_CONCEPT_PATTERNS = [
    r"\band\b",
    r"\bwith\b",
    r"\b,\s*\w+\s*,",  # Comma-separated list
]


def classify_query(query: str) -> tuple[QueryType, float]:
    """
    Classify a search query and return the appropriate alpha value.

    Args:
        query: The search query string

    Returns:
        Tuple of (QueryType, alpha_value)
    """
    query_lower = query.lower().strip()

    # Check for exact phrases (highest priority)
    for pattern in EXACT_PHRASE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryType.EXACT_PHRASE, settings.alpha_exact_phrase

    # Check for comparative queries
    for pattern in COMPARATIVE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryType.COMPARATIVE, settings.alpha_comparative

    # Check for general topic questions
    for pattern in GENERAL_TOPIC_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryType.GENERAL_TOPIC, settings.alpha_general_topic

    # Check for named entities
    words = set(re.findall(r"\b\w+\b", query_lower))
    if words & BIBLICAL_NAMES:
        return QueryType.NAMED_ENTITY, settings.alpha_named_entity

    # Check for multi-concept queries
    for pattern in MULTI_CONCEPT_PATTERNS:
        if re.search(pattern, query_lower):
            # Must have at least 2 substantial words
            word_count = len([w for w in words if len(w) > 3])
            if word_count >= 2:
                return QueryType.MULTI_CONCEPT, settings.alpha_multi_concept

    # Check for single concept (1-2 words, typically abstract)
    word_list = [w for w in re.findall(r"\b\w+\b", query_lower) if len(w) > 2]
    if len(word_list) <= 2:
        return QueryType.SINGLE_CONCEPT, settings.alpha_single_concept

    # Default fallback
    return QueryType.DEFAULT, settings.alpha_default
