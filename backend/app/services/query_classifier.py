"""
Query classifier — signal-blending design.

Computes a continuous alpha (RRF fusion weight between FAISS and BM25) as a
weighted blend of feature signals, rather than picking one branch from a
mutually-exclusive cascade. A mixed query like "What does Jesus say about
grace?" fires three signals (named entity + concept + general topic) and the
resulting alpha sits between each signal's target — not pinned to whichever
branch happened to match first.

Public API is unchanged:
    classify_query(query: str) -> tuple[QueryType, float]

The second element is the blended alpha (used by search.py for RRF fusion).
The first element is the highest-strength signal — used only for UI display
(ResultsHeader.tsx) and for debugging. Retrieval quality depends on alpha, not
on the reported QueryType.
"""

import re

from ..core.config import settings
from ..core.stopwords import BIBLICAL_STOPWORDS
from ..core.vocabularies import BIBLICAL_NAMES, CONCEPT_VOCAB
from ..models.schemas import QueryType


_STOPWORDS = frozenset(BIBLICAL_STOPWORDS)

# Weight given to the baseline (alpha_default) in the blend. Lower values let
# signal alphas pull further from the default; higher values pin alpha close
# to default. 0.3 gives strong signals meaningful influence without letting a
# single weak match swing alpha to an extreme.
_BASELINE_WEIGHT = 0.3

# Any signal below this strength is ignored when picking the dominant query
# type (the blend still includes it). Prevents DEFAULT queries from reporting
# a noise signal as their type.
_SIGNAL_FLOOR = 0.2

# Damping applied to multi-concept strength when there is no explicit
# conjunction ("and", "with", comma list).
_IMPLICIT_MULTI_DAMPING = 0.7

# General-topic strength when a boilerplate wrapper ("verses about X") matches
# but the query isn't otherwise phrased as a question. Kept below 0.5 so
# concept/named-entity signals on the stripped query can still dominate.
_BOILERPLATE_GENERAL_STRENGTH = 0.3

# General-topic strength when a soft topic indicator matches ("teachings on",
# "what does X say").
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

# Interrogative openings — strong signal the user is asking a general question.
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

# Softer topic indicators — weaker general-topic signal.
_SOFT_TOPIC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bteaching[s]?\s+(on|about)\b",
        r"\bwhat\s+(does|do)\b.*\b(say|teach)\b",
    ]
]

# Boilerplate wrappers that should be stripped before content tokenization.
# The inner query is the user's real intent.
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


# Dominant-type preference order for breaking strength ties.
# More specific signals win. DEFAULT is never chosen by tie-break — it's only
# the fallback when no signal clears _SIGNAL_FLOOR. GENERAL_TOPIC sits above
# SINGLE/MULTI so interrogative queries ("How should I pray?") report as
# GENERAL_TOPIC rather than SINGLE_CONCEPT when strengths tie at 1.0.
_TYPE_PRIORITY = [
    QueryType.EXACT_PHRASE,
    QueryType.COMPARATIVE,
    QueryType.NAMED_ENTITY,
    QueryType.GENERAL_TOPIC,
    QueryType.MULTI_CONCEPT,
    QueryType.SINGLE_CONCEPT,
]


def _strip_boilerplate(query_lower: str) -> str:
    """Remove "verses about X" style wrappers so the inner query dominates."""
    for pat in _BOILERPLATE_PATTERNS:
        stripped = pat.sub("", query_lower)
        if stripped != query_lower:
            return stripped.strip()
    return query_lower


def _tokenize_content(text: str) -> list[str]:
    """Word-boundary tokenize, drop tokens ≤2 chars or in the stopword list."""
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
    """
    Split concept_strength into (single, multi) based on content-token count
    and whether an explicit conjunction is present.

    - Explicit conjunction: pure multi.
    - 1 content token, no conjunction: pure single.
    - 2 content tokens, no conjunction: ambiguous — half single, half multi.
    - ≥3 content tokens, no conjunction: multi (damped).
    """
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

    # Collect all types at the max strength (within float tolerance).
    tied = {qt for qt, s, _ in signals if abs(s - max_strength) < 1e-9}
    for qt in _TYPE_PRIORITY:
        if qt in tied:
            return qt
    return QueryType.DEFAULT


def classify_query(query: str) -> tuple[QueryType, float]:
    """
    Classify a search query and return (dominant_type, blended_alpha).

    The blended alpha is the weighted mean of each signal's target alpha, with
    a baseline anchor at alpha_default. The dominant type is the
    highest-strength signal (tie-broken by _TYPE_PRIORITY), used for
    observability. Retrieval uses the alpha.
    """
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
