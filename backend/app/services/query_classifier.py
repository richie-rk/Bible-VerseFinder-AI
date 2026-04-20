"""
Signal-blending query classifier.

Computes a continuous RRF fusion weight (alpha) as the weighted mean of
per-signal target alphas, anchored by a baseline. Each feature signal
contributes a strength in [0, 1] proportional to how much it fired, so mixed
queries (e.g. "What does Jesus say about grace?" — named entity + concept +
general topic) produce a blend between the constituent targets rather than
collapsing to whichever rule matched first.

Public API: `classify_query(query) -> (QueryType, float)`. The QueryType is
the dominant signal; it's returned for observability only. Retrieval uses
alpha.
"""

import re

from ..core.config import settings
from ..core.stopwords import BIBLICAL_STOPWORDS
from ..core.vocabularies import BIBLICAL_NAMES, CONCEPT_VOCAB
from ..models.schemas import QueryType


_STOPWORDS = frozenset(BIBLICAL_STOPWORDS)

# Lower baseline weight lets strong signals pull alpha further from the
# default; 0.3 keeps a lone weak signal from swinging the blend.
_BASELINE_WEIGHT = 0.3

# Strengths below this count toward the blend but aren't eligible as the
# dominant reported type.
_SIGNAL_FLOOR = 0.2

# "grace mercy faith" (no conjunction) should still register as multi-concept,
# just less confidently than "grace and mercy and faith".
_IMPLICIT_MULTI_DAMPING = 0.7

# "verses about X" fires general-topic weakly so the inner concept still wins;
# bare interrogatives fire it at 1.0 so they outrank single-concept at ties.
_BOILERPLATE_GENERAL_STRENGTH = 0.3
_SOFT_TOPIC_STRENGTH = 0.5


_EXACT_PHRASE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r'"[^"]+?"',
        r"'[^']+?'",
        r"\bi am\b.*\bi am\b",
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
        r"\bholy spirit\b",
        r"\beternal life\b",
    ]
]

_COMPARATIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bcompare[d]?\b",
        r"\bdifference between\b",
        r"\bor\b.*\bwhich\b",
        r"\bbetter\b.*\bthan\b",
    ]
]

_INTERROGATIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^what\s+(is|are|does|did|do|about|happens?)\b",
        r"^how\s+(do|does|can|should|are|is|did|to)\b",
        r"^why\s+(do|does|did|is|are|should)\b",
        r"^where\s+(is|are|does|did)\b",
        r"^when\s+(did|does|will|is|are)\b",
        r"^who\s+(is|are|was|were|does|did)\b",
    ]
]

_SOFT_TOPIC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bteaching[s]?\s+(on|about)\b",
        r"\bwhat\s+(does|do)\b.*\b(say|teach)\b",
    ]
]

_BOILERPLATE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^\s*verses?\s+(about|on)\s+",
        r"^\s*passages?\s+(about|on)\s+",
        r"^\s*scriptures?\s+(about|on)\s+",
        r"^\s*bible\s+(about|on|verses)\s+",
    ]
]

_CONJUNCTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\band\b",
        r"\bwith\b",
        r"\b,\s*\w+\s*,",
    ]
]


# Tie-break order: more specific signals win. GENERAL_TOPIC outranks
# SINGLE/MULTI so "How should I pray?" reports as general-topic rather than
# single-concept when both strengths are 1.0.
_TYPE_PRIORITY = [
    QueryType.EXACT_PHRASE,
    QueryType.COMPARATIVE,
    QueryType.NAMED_ENTITY,
    QueryType.GENERAL_TOPIC,
    QueryType.MULTI_CONCEPT,
    QueryType.SINGLE_CONCEPT,
]


def _strip_boilerplate(query_lower: str) -> str:
    for pat in _BOILERPLATE_PATTERNS:
        stripped = pat.sub("", query_lower)
        if stripped != query_lower:
            return stripped.strip()
    return query_lower


def _tokenize_content(text: str) -> list[str]:
    tokens = re.findall(r"\b\w+\b", text)
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


def _score_exact_phrase(query_lower: str) -> float:
    for pat in _EXACT_PHRASE_PATTERNS:
        if pat.search(query_lower):
            return 1.0
    return 0.0


def _score_named_entity(content_tokens: list[str]) -> float:
    if not content_tokens:
        return 0.0
    hits = sum(1 for t in content_tokens if t in BIBLICAL_NAMES)
    return hits / len(content_tokens)


def _score_concept(content_tokens: list[str]) -> float:
    if not content_tokens:
        return 0.0
    hits = sum(1 for t in content_tokens if t in CONCEPT_VOCAB)
    return hits / len(content_tokens)


def _score_comparative(query_lower: str) -> float:
    for pat in _COMPARATIVE_PATTERNS:
        if pat.search(query_lower):
            return 1.0
    return 0.0


def _score_general_topic(query_lower: str, boilerplate_stripped: bool) -> float:
    for pat in _INTERROGATIVE_PATTERNS:
        if pat.search(query_lower):
            return 1.0
    for pat in _SOFT_TOPIC_PATTERNS:
        if pat.search(query_lower):
            return _SOFT_TOPIC_STRENGTH
    if boilerplate_stripped:
        return _BOILERPLATE_GENERAL_STRENGTH
    return 0.0


def _has_conjunction(query_lower: str) -> bool:
    for pat in _CONJUNCTION_PATTERNS:
        if pat.search(query_lower):
            return True
    return False


def _score_concept_arity(
    content_tokens: list[str],
    concept_strength: float,
    has_conjunction: bool,
) -> tuple[float, float]:
    # Splits concept_strength into (single, multi). Arity is genuinely
    # ambiguous at n=2 with no conjunction ("God's love" could read either
    # way), so that case contributes to both at half weight.
    n = len(content_tokens)
    if n == 0 or concept_strength <= 0.0:
        return 0.0, 0.0

    if has_conjunction:
        return 0.0, concept_strength
    if n == 1:
        return concept_strength, 0.0
    if n == 2:
        return concept_strength * 0.5, concept_strength * 0.5
    return 0.0, concept_strength * _IMPLICIT_MULTI_DAMPING


def _blend_alpha(
    signals: list[tuple[QueryType, float, float]],
    baseline_alpha: float,
) -> float:
    total_weight = _BASELINE_WEIGHT
    weighted_sum = _BASELINE_WEIGHT * baseline_alpha
    for _, strength, target in signals:
        if strength > 0.0:
            total_weight += strength
            weighted_sum += strength * target
    return weighted_sum / total_weight


def _dominant_type(
    signals: list[tuple[QueryType, float, float]],
) -> QueryType:
    max_strength = max((s for _, s, _ in signals), default=0.0)
    if max_strength < _SIGNAL_FLOOR:
        return QueryType.DEFAULT

    tied = {qt for qt, s, _ in signals if abs(s - max_strength) < 1e-9}
    for qt in _TYPE_PRIORITY:
        if qt in tied:
            return qt
    return QueryType.DEFAULT


def classify_query(query: str) -> tuple[QueryType, float]:
    if not query or not query.strip():
        return QueryType.DEFAULT, settings.alpha_default

    query_lower = query.lower().strip()
    stripped = _strip_boilerplate(query_lower)
    boilerplate_stripped = stripped != query_lower
    content_tokens = _tokenize_content(stripped)

    exact_s = _score_exact_phrase(query_lower)
    named_s = _score_named_entity(content_tokens)
    concept_s = _score_concept(content_tokens)
    comparative_s = _score_comparative(query_lower)
    general_s = _score_general_topic(query_lower, boilerplate_stripped)
    has_conj = _has_conjunction(query_lower)

    single_s, multi_s = _score_concept_arity(content_tokens, concept_s, has_conj)

    signals = [
        (QueryType.EXACT_PHRASE, exact_s, settings.alpha_exact_phrase),
        (QueryType.NAMED_ENTITY, named_s, settings.alpha_named_entity),
        (QueryType.SINGLE_CONCEPT, single_s, settings.alpha_single_concept),
        (QueryType.MULTI_CONCEPT, multi_s, settings.alpha_multi_concept),
        (QueryType.COMPARATIVE, comparative_s, settings.alpha_comparative),
        (QueryType.GENERAL_TOPIC, general_s, settings.alpha_general_topic),
    ]

    dominant = _dominant_type(signals)
    alpha = _blend_alpha(signals, settings.alpha_default)
    return dominant, alpha
