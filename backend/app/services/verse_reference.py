"""
Verse-reference parsing and lookup.

Detects queries that name an exact verse or verse range ("John 3:16",
"1 Cor 13:4-7", "Rom 8.28", "I John 4:8") and returns the matching verse IDs.
When a query is a verse reference, search.py short-circuits the full FAISS +
BM25 + RRF pipeline and returns these verses directly — no embedding call,
no scoring, score=1.0.

Covers all 27 NT books with their standard abbreviations. Book-name lookup
is deliberately strict: only recognised aliases return a canonical book,
which means queries like "Jesus 3:16" fail the normalizer and fall through
to normal search instead of returning wrong results.
"""

from dataclasses import dataclass
import re


# Verse reference regex — matches queries of the form:
#   John 3:16
#   1 Cor 13:4-7
#   Rom 8.28
#   1 John 4:8
#
# Captures:
#   1. book name (letters, optionally prefixed with 1/2/3 + whitespace)
#   2. chapter (int)
#   3. verse start (int)
#   4. verse end (int, optional)
_VERSE_REF_PATTERN = re.compile(
    r"^\s*((?:[123]\s*)?[A-Za-z]+)\s+(\d+)\s*[:.]\s*(\d+)(?:\s*[-\u2013]\s*(\d+))?\s*$",
)

# Roman-ordinal preprocessing: convert "I John" / "II Peter" / "III John"
# at the start of a query to digit form before running the main regex.
# Anchored to start-of-string so "I am the way" doesn't get mangled.
_ROMAN_III = re.compile(r"^III\s+", re.IGNORECASE)
_ROMAN_II = re.compile(r"^II\s+", re.IGNORECASE)
_ROMAN_I = re.compile(r"^I\s+(?=[A-Za-z])", re.IGNORECASE)


# Canonical book name per the metadata schema (see scripts/create_faiss_index.py).
# Map of {normalized_alias: canonical_name}. Normalization drops whitespace
# and lowercases. Ambiguous short forms (e.g. bare "co" — Colossians vs
# Corinthians) are intentionally omitted.
_BOOK_ALIASES: dict[str, str] = {
    # Matthew
    "matthew": "Matthew", "matt": "Matthew", "mat": "Matthew", "mt": "Matthew",
    # Mark
    "mark": "Mark", "mrk": "Mark", "mk": "Mark",
    # Luke
    "luke": "Luke", "luk": "Luke", "lk": "Luke",
    # John
    "john": "John", "jhn": "John", "joh": "John", "jn": "John",
    # Acts
    "acts": "Acts", "act": "Acts",
    # Romans
    "romans": "Romans", "rom": "Romans", "rmn": "Romans",
    # 1 Corinthians
    "1corinthians": "1 Corinthians", "1cor": "1 Corinthians",
    "1co": "1 Corinthians",
    # 2 Corinthians
    "2corinthians": "2 Corinthians", "2cor": "2 Corinthians",
    "2co": "2 Corinthians",
    # Galatians
    "galatians": "Galatians", "gal": "Galatians",
    # Ephesians
    "ephesians": "Ephesians", "eph": "Ephesians",
    # Philippians (phil — not philemon)
    "philippians": "Philippians", "phil": "Philippians",
    "php": "Philippians", "pp": "Philippians",
    # Colossians
    "colossians": "Colossians", "col": "Colossians",
    # 1 Thessalonians
    "1thessalonians": "1 Thessalonians", "1thess": "1 Thessalonians",
    "1thes": "1 Thessalonians", "1th": "1 Thessalonians",
    # 2 Thessalonians
    "2thessalonians": "2 Thessalonians", "2thess": "2 Thessalonians",
    "2thes": "2 Thessalonians", "2th": "2 Thessalonians",
    # 1 Timothy
    "1timothy": "1 Timothy", "1tim": "1 Timothy", "1ti": "1 Timothy",
    # 2 Timothy
    "2timothy": "2 Timothy", "2tim": "2 Timothy", "2ti": "2 Timothy",
    # Titus
    "titus": "Titus", "tit": "Titus",
    # Philemon (phlm, philem — disambiguated from Philippians)
    "philemon": "Philemon", "philem": "Philemon",
    "phlm": "Philemon", "phm": "Philemon",
    # Hebrews
    "hebrews": "Hebrews", "heb": "Hebrews", "hbr": "Hebrews",
    # James
    "james": "James", "jas": "James", "jam": "James",
    # 1 Peter
    "1peter": "1 Peter", "1pet": "1 Peter", "1pt": "1 Peter",
    "1pe": "1 Peter",
    # 2 Peter
    "2peter": "2 Peter", "2pet": "2 Peter", "2pt": "2 Peter",
    "2pe": "2 Peter",
    # 1 John
    "1john": "1 John", "1jhn": "1 John", "1jn": "1 John", "1jo": "1 John",
    # 2 John
    "2john": "2 John", "2jhn": "2 John", "2jn": "2 John", "2jo": "2 John",
    # 3 John
    "3john": "3 John", "3jhn": "3 John", "3jn": "3 John", "3jo": "3 John",
    # Jude
    "jude": "Jude", "jud": "Jude",
    # Revelation
    "revelation": "Revelation", "rev": "Revelation", "rv": "Revelation",
}


@dataclass(frozen=True)
class ParsedReference:
    """Parsed verse reference, all fields canonical."""

    book: str             # e.g. "John", "1 Corinthians"
    chapter: int
    verse_start: int
    verse_end: int        # same as verse_start for a single-verse ref


def _preprocess(query: str) -> str:
    """Normalize Roman ordinals at the start so the main regex works uniformly."""
    q = query.strip()
    q = _ROMAN_III.sub("3 ", q)
    q = _ROMAN_II.sub("2 ", q)
    q = _ROMAN_I.sub("1 ", q)
    return q


def _normalize_book(raw: str) -> str | None:
    """Look up a user-typed book string in _BOOK_ALIASES. Returns canonical name or None."""
    key = re.sub(r"\s+", "", raw).lower()
    return _BOOK_ALIASES.get(key)


def parse_verse_reference(query: str) -> ParsedReference | None:
    """
    Parse a verse-reference query. Returns ParsedReference on success, None if
    the query doesn't match the verse-reference grammar or names an unknown book.
    """
    if not query or not query.strip():
        return None

    preprocessed = _preprocess(query)
    match = _VERSE_REF_PATTERN.match(preprocessed)
    if match is None:
        return None

    raw_book, chapter_s, verse_start_s, verse_end_s = match.groups()
    book = _normalize_book(raw_book)
    if book is None:
        return None

    chapter = int(chapter_s)
    verse_start = int(verse_start_s)
    verse_end = int(verse_end_s) if verse_end_s is not None else verse_start

    # Reject nonsense like "John 3:10-5" (end before start).
    if verse_end < verse_start:
        return None

    return ParsedReference(
        book=book,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
    )


def verse_ids_for(ref: ParsedReference) -> list[str]:
    """Expand a ParsedReference into the list of verse_id strings to look up."""
    book_id = ref.book.replace(" ", "_")
    return [
        f"{book_id}_{ref.chapter}:{v}"
        for v in range(ref.verse_start, ref.verse_end + 1)
    ]
