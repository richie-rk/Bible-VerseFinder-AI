"""
Tests for the verse-reference parser and verse_id expander.

Parser must accept common NT reference formats (full name, abbreviations,
Roman-numeral ordinals, dot or colon separator, ranges with hyphen or en-dash)
and reject everything that doesn't match the grammar or names an unknown book.
"""

import pytest

from app.services.verse_reference import (
    ParsedReference,
    parse_verse_reference,
    verse_ids_for,
)


# ---------- Parser: positive cases ----------

POSITIVE_CASES = [
    # Plain forms
    ("John 3:16", ParsedReference("John", 3, 16, 16)),
    ("john 3:16", ParsedReference("John", 3, 16, 16)),
    ("JOHN 3:16", ParsedReference("John", 3, 16, 16)),
    ("Matthew 5:3", ParsedReference("Matthew", 5, 3, 3)),
    ("Revelation 22:21", ParsedReference("Revelation", 22, 21, 21)),
    # Surrounding whitespace
    ("  John 3:16  ", ParsedReference("John", 3, 16, 16)),
    # Dot separator
    ("Rom 8.28", ParsedReference("Romans", 8, 28, 28)),
    ("Matthew 5.3", ParsedReference("Matthew", 5, 3, 3)),
    # Common abbreviations
    ("Mt 5:3", ParsedReference("Matthew", 5, 3, 3)),
    ("Mk 10:45", ParsedReference("Mark", 10, 45, 45)),
    ("Lk 15:11", ParsedReference("Luke", 15, 11, 11)),
    ("Jn 3:16", ParsedReference("John", 3, 16, 16)),
    ("Rom 8:28", ParsedReference("Romans", 8, 28, 28)),
    ("Gal 5:22", ParsedReference("Galatians", 5, 22, 22)),
    ("Eph 2:8", ParsedReference("Ephesians", 2, 8, 8)),
    ("Heb 11:1", ParsedReference("Hebrews", 11, 1, 1)),
    ("Rev 3:20", ParsedReference("Revelation", 3, 20, 20)),
    # Ordinal-prefix books — space, no space, Roman numerals
    ("1 John 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("1John 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("1 Jn 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("1Jn 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("I John 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("i john 4:8", ParsedReference("1 John", 4, 8, 8)),
    ("2 Peter 3:9", ParsedReference("2 Peter", 3, 9, 9)),
    ("II Peter 3:9", ParsedReference("2 Peter", 3, 9, 9)),
    ("ii pet 3:9", ParsedReference("2 Peter", 3, 9, 9)),
    ("3 John 1:4", ParsedReference("3 John", 1, 4, 4)),
    ("III John 1:4", ParsedReference("3 John", 1, 4, 4)),
    ("1 Cor 13:4", ParsedReference("1 Corinthians", 13, 4, 4)),
    ("1Cor 13:4", ParsedReference("1 Corinthians", 13, 4, 4)),
    ("1 Corinthians 13:4", ParsedReference("1 Corinthians", 13, 4, 4)),
    ("2 Corinthians 5:17", ParsedReference("2 Corinthians", 5, 17, 17)),
    # Ranges
    ("1 Cor 13:4-7", ParsedReference("1 Corinthians", 13, 4, 7)),
    ("1 Cor 13:4-13", ParsedReference("1 Corinthians", 13, 4, 13)),
    ("Rom 8:28-30", ParsedReference("Romans", 8, 28, 30)),
    ("John 14:1-6", ParsedReference("John", 14, 1, 6)),
    # En-dash range
    ("1 Cor 13:4\u20137", ParsedReference("1 Corinthians", 13, 4, 7)),
    # Disambiguating tricky abbreviations
    ("Phil 4:13", ParsedReference("Philippians", 4, 13, 13)),
    ("Phlm 1:5", ParsedReference("Philemon", 1, 5, 5)),
    ("Col 3:14", ParsedReference("Colossians", 3, 14, 14)),
    ("Jude 1:3", ParsedReference("Jude", 1, 3, 3)),
]


@pytest.mark.parametrize("query,expected", POSITIVE_CASES)
def test_parse_positive(query, expected):
    assert parse_verse_reference(query) == expected


# ---------- Parser: negative cases ----------

NEGATIVE_CASES = [
    # Empty / whitespace
    "",
    "   ",
    # Not a verse-reference grammar
    "what is grace?",
    "grace",
    "Jesus loves me",
    "verses about faith",
    # Book-like but unknown / out of NT corpus
    "Jesus 3:16",             # Jesus isn't a book alias
    "Genesis 1:1",            # OT, not in corpus / alias map
    "Psalms 23:1",            # OT
    "randomword 1:1",         # nonsense
    # Incomplete references
    "John 3",                 # no verse
    "John",
    "John :16",
    "3:16",                   # no book
    # Trailing content
    "John 3:16 and grace",
    "see John 3:16",
    # End-before-start range
    "John 3:10-5",
    # Ambiguous short forms deliberately omitted from the alias map
    "co 1:1",                 # 'co' could be Col or 1/2 Cor
    "ti 1:1",                 # 'ti' could be Titus or 1/2 Tim
]


@pytest.mark.parametrize("query", NEGATIVE_CASES)
def test_parse_negative(query):
    assert parse_verse_reference(query) is None


# ---------- verse_ids_for ----------

def test_verse_ids_single():
    ref = ParsedReference("John", 3, 16, 16)
    assert verse_ids_for(ref) == ["John_3:16"]


def test_verse_ids_range():
    ref = ParsedReference("1 Corinthians", 13, 4, 7)
    assert verse_ids_for(ref) == [
        "1_Corinthians_13:4",
        "1_Corinthians_13:5",
        "1_Corinthians_13:6",
        "1_Corinthians_13:7",
    ]


def test_verse_ids_preserves_book_spaces_as_underscores():
    ref = ParsedReference("2 Thessalonians", 1, 3, 5)
    assert verse_ids_for(ref) == [
        "2_Thessalonians_1:3",
        "2_Thessalonians_1:4",
        "2_Thessalonians_1:5",
    ]


# ---------- Integration with SearchService ----------

def test_search_short_circuits_verse_reference():
    """SearchService.search('John 3:16') returns the exact verse with QueryType.VERSE_REFERENCE."""
    from app.services.search import get_search_service
    from app.models.schemas import QueryType, SearchMode

    svc = get_search_service()
    svc.load_indices()
    results, total, qtype, alpha = svc.search("John 3:16", mode=SearchMode.HYBRID, limit=10)

    assert qtype == QueryType.VERSE_REFERENCE
    assert alpha is None
    assert total == 1
    assert len(results) == 1
    assert results[0].verse_id == "John_3:16"
    assert results[0].book == "John"
    assert results[0].score == 1.0
    assert results[0].faiss_score is None
    assert results[0].bm25_score is None


def test_search_verse_reference_range():
    """SearchService.search('1 Cor 13:4-7') returns 4 verses in order."""
    from app.services.search import get_search_service
    from app.models.schemas import QueryType

    svc = get_search_service()
    svc.load_indices()
    results, total, qtype, alpha = svc.search("1 Cor 13:4-7", limit=10)

    assert qtype == QueryType.VERSE_REFERENCE
    assert alpha is None
    assert total == 4
    assert [r.verse_id for r in results] == [
        "1_Corinthians_13:4",
        "1_Corinthians_13:5",
        "1_Corinthians_13:6",
        "1_Corinthians_13:7",
    ]


def test_search_verse_reference_out_of_range_returns_empty():
    """Valid verse-ref format but verse doesn't exist: return empty, not fall through."""
    from app.services.search import get_search_service
    from app.models.schemas import QueryType

    svc = get_search_service()
    svc.load_indices()
    results, total, qtype, alpha = svc.search("John 3:999")

    assert qtype == QueryType.VERSE_REFERENCE
    assert alpha is None
    assert total == 0
    assert results == []


def test_search_non_reference_still_falls_through():
    """Non-reference queries go through the normal classify + FAISS/BM25 flow."""
    from app.services.search import get_search_service
    from app.models.schemas import QueryType

    svc = get_search_service()
    svc.load_indices()
    # This query requires an OpenAI embedding call, so skip if no key set.
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; cannot run live search.")

    results, total, qtype, alpha = svc.search("grace")
    assert qtype != QueryType.VERSE_REFERENCE
    assert alpha is not None
    assert total > 0
