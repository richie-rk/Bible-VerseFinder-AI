"""
Acceptance tests for the signal-blending query classifier.

Each case asserts (a) the dominant QueryType is one of the acceptable options
(some mixed queries legitimately have multiple valid dominant types) and
(b) the blended alpha lands within the expected range.

Alpha ranges are slightly wider than each signal's raw target to account for
the baseline-anchored blend, which pulls alpha a bit toward alpha_default.
"""

import pytest

from app.models.schemas import QueryType
from app.services.query_classifier import classify_query


# (query, acceptable_dominant_types, (alpha_min, alpha_max))
CASES = [
    # Empty / whitespace
    ("", {QueryType.DEFAULT}, (0.49, 0.51)),
    ("   ", {QueryType.DEFAULT}, (0.49, 0.51)),

    # Exact phrases — strongly keyword-biased
    ('"born again"', {QueryType.EXACT_PHRASE}, (0.22, 0.35)),
    ("born again", {QueryType.EXACT_PHRASE}, (0.22, 0.35)),
    ("kingdom of god", {QueryType.EXACT_PHRASE}, (0.22, 0.38)),
    ("good shepherd", {QueryType.EXACT_PHRASE}, (0.22, 0.38)),
    ("the way, the truth, and the life", {QueryType.EXACT_PHRASE}, (0.22, 0.40)),
    ("holy spirit", {QueryType.EXACT_PHRASE}, (0.22, 0.38)),

    # Named entities — keyword-biased but not as much
    ("Paul", {QueryType.NAMED_ENTITY}, (0.35, 0.45)),
    ("Jesus teaches", {QueryType.NAMED_ENTITY}, (0.35, 0.48)),
    ("Peter denies Christ", {QueryType.NAMED_ENTITY}, (0.35, 0.48)),
    ("Ephesus", {QueryType.NAMED_ENTITY}, (0.35, 0.45)),

    # Single concepts — semantic-biased
    ("grace", {QueryType.SINGLE_CONCEPT}, (0.58, 0.68)),
    ("faith", {QueryType.SINGLE_CONCEPT}, (0.58, 0.68)),
    ("righteousness", {QueryType.SINGLE_CONCEPT}, (0.58, 0.68)),

    # Multi-concept — slight semantic bias
    ("grace and faith", {QueryType.MULTI_CONCEPT}, (0.55, 0.65)),
    ("repentance and forgiveness", {QueryType.MULTI_CONCEPT}, (0.55, 0.65)),
    ("grace mercy faith", {QueryType.MULTI_CONCEPT}, (0.52, 0.62)),

    # General topic — semantic-biased
    ("What about suffering?", {QueryType.GENERAL_TOPIC}, (0.62, 0.75)),
    ("How should I pray?", {QueryType.GENERAL_TOPIC}, (0.60, 0.75)),
    ("Why does God allow evil?", {QueryType.GENERAL_TOPIC}, (0.50, 0.70)),

    # Comparative — moderate semantic
    ("grace vs mercy", {QueryType.COMPARATIVE}, (0.58, 0.70)),
    ("faith versus works", {QueryType.COMPARATIVE}, (0.55, 0.70)),

    # Mixed queries — these are the cases the old cascade got wrong.
    # The key assertion is the α lands in a sensible blended zone, not at
    # either signal's extreme.
    (
        "What does Jesus say about grace?",
        {QueryType.GENERAL_TOPIC, QueryType.NAMED_ENTITY},
        (0.50, 0.65),  # blended — not pinned at 0.70 (old GENERAL_TOPIC)
    ),
    (
        "God's love",
        {QueryType.NAMED_ENTITY, QueryType.SINGLE_CONCEPT, QueryType.MULTI_CONCEPT},
        (0.45, 0.58),  # blended — not pinned at 0.38 (old NAMED_ENTITY)
    ),
    (
        "verses about faith",
        {QueryType.SINGLE_CONCEPT, QueryType.GENERAL_TOPIC},
        (0.55, 0.68),  # boilerplate stripped → faith dominates
    ),
]


@pytest.mark.parametrize("query,acceptable_types,alpha_range", CASES)
def test_classify_query(query, acceptable_types, alpha_range):
    qtype, alpha = classify_query(query)
    alpha_min, alpha_max = alpha_range

    assert qtype in acceptable_types, (
        f"Query {query!r}: expected dominant type in {acceptable_types}, "
        f"got {qtype}. Alpha was {alpha:.3f}."
    )
    assert alpha_min <= alpha <= alpha_max, (
        f"Query {query!r}: expected alpha in [{alpha_min}, {alpha_max}], "
        f"got {alpha:.3f}. Dominant type: {qtype}."
    )


def test_return_type():
    """Public contract: always returns (QueryType, float)."""
    qtype, alpha = classify_query("grace")
    assert isinstance(qtype, QueryType)
    assert isinstance(alpha, float)


def test_alpha_always_in_reasonable_range():
    """Sanity: blended alpha stays within a reasonable band for any input."""
    wild_inputs = [
        "Jesus Paul Peter John James Matthew Mark Luke",
        "grace faith hope love joy peace patience kindness",
        "!!! ??? ...",
        "a b c d e",
        "    grace    ",
        "GRACE",
    ]
    for q in wild_inputs:
        _, alpha = classify_query(q)
        assert 0.20 <= alpha <= 0.75, (
            f"Query {q!r}: alpha {alpha:.3f} outside sanity band [0.20, 0.75]"
        )
