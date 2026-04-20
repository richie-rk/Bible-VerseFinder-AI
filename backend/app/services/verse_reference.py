"""
Verse-reference parsing and lookup.

Detects queries that name an exact verse or verse range ("John 3:16",
"1 Cor 13:4-7", "Rom 8.28", "I John 4:8") and returns the matching verse
IDs. `search.search()` uses this to skip FAISS + BM25 entirely when a query
is really an exact lookup.

Book-name matching is deliberately strict: only recognised aliases return a
canonical book, so "Jesus 3:16" fails here and falls through to normal
search rather than producing a wrong result.
"""

from dataclasses import dataclass
import re


# Four groups: book (letters with optional 1/2/3 ordinal prefix), chapter,
# verse start, verse end (optional). Accepts ":" or "." as separator and
# "-" or en-dash for ranges.
_VERSE_REF_PATTERN = re.compile(
    r"^\s*((?:[123]\s*)?[A-Za-z]+)\s+(\d+)\s*[:.]\s*(\d+)(?:\s*[-\u2013]\s*(\d+))?\s*$",
)

# Convert "I John" / "II Peter" / "III John" to digit form before matching.
# Anchored to start-of-string so "I am the way" survives untouched.
_ROMAN_III = re.compile(r"^III\s+", re.IGNORECASE)
_ROMAN_II = re.compile(r"^II\s+", re.IGNORECASE)
_ROMAN_I = re.compile(r"^I\s+(?=[A-Za-z])", re.IGNORECASE)


# Canonical book name matches the string in verse_metadata.json. Ambiguous
# short forms (bare "co", bare "ti") are omitted on purpose — better to fail
# the parse and fall through to full search than guess wrong.
_BOOK_ALIASES: dict[str, str] = {
    "matthew": "Matthew", "matt": "Matthew", "mat": "Matthew", "mt": "Matthew",
    "mark": "Mark", "mrk": "Mark", "mk": "Mark",
    "luke": "Luke", "luk": "Luke", "lk": "Luke",
    "john": "John", "jhn": "John", "joh": "John", "jn": "John",
    "acts": "Acts", "act": "Acts",
    "romans": "Romans", "rom": "Romans", "rmn": "Romans",
    "1corinthians": "1 Corinthians", "1cor": "1 Corinthians",
    "1co": "1 Corinthians",
    "2corinthians": "2 Corinthians", "2cor": "2 Corinthians",
    "2co": "2 Corinthians",
    "galatians": "Galatians", "gal": "Galatians",
    "ephesians": "Ephesians", "eph": "Ephesians",
    "philippians": "Philippians", "phil": "Philippians",
    "php": "Philippians", "pp": "Philippians",
    "colossians": "Colossians", "col": "Colossians",
    "1thessalonians": "1 Thessalonians", "1thess": "1 Thessalonians",
    "1thes": "1 Thessalonians", "1th": "1 Thessalonians",
    "2thessalonians": "2 Thessalonians", "2thess": "2 Thessalonians",
    "2thes": "2 Thessalonians", "2th": "2 Thessalonians",
    "1timothy": "1 Timothy", "1tim": "1 Timothy", "1ti": "1 Timothy",
    "2timothy": "2 Timothy", "2tim": "2 Timothy", "2ti": "2 Timothy",
    "titus": "Titus", "tit": "Titus",
    "philemon": "Philemon", "philem": "Philemon",
    "phlm": "Philemon", "phm": "Philemon",
    "hebrews": "Hebrews", "heb": "Hebrews", "hbr": "Hebrews",
    "james": "James", "jas": "James", "jam": "James",
    "1peter": "1 Peter", "1pet": "1 Peter", "1pt": "1 Peter",
    "1pe": "1 Peter",
    "2peter": "2 Peter", "2pet": "2 Peter", "2pt": "2 Peter",
    "2pe": "2 Peter",
    "1john": "1 John", "1jhn": "1 John", "1jn": "1 John", "1jo": "1 John",
    "2john": "2 John", "2jhn": "2 John", "2jn": "2 John", "2jo": "2 John",
    "3john": "3 John", "3jhn": "3 John", "3jn": "3 John", "3jo": "3 John",
    "jude": "Jude", "jud": "Jude",
    "revelation": "Revelation", "rev": "Revelation", "rv": "Revelation",
}


@dataclass(frozen=True)
class ParsedReference:
    book: str
    chapter: int
    verse_start: int
    verse_end: int


def _preprocess(query: str) -> str:
    q = query.strip()
    q = _ROMAN_III.sub("3 ", q)
    q = _ROMAN_II.sub("2 ", q)
    q = _ROMAN_I.sub("1 ", q)
    return q


def _normalize_book(raw: str) -> str | None:
    key = re.sub(r"\s+", "", raw).lower()
    return _BOOK_ALIASES.get(key)


def parse_verse_reference(query: str) -> ParsedReference | None:
    """Returns None if `query` is not a verse-reference grammar or names an unknown book."""
    if not query or not query.strip():
        return None

    match = _VERSE_REF_PATTERN.match(_preprocess(query))
    if match is None:
        return None

    raw_book, chapter_s, verse_start_s, verse_end_s = match.groups()
    book = _normalize_book(raw_book)
    if book is None:
        return None

    chapter = int(chapter_s)
    verse_start = int(verse_start_s)
    verse_end = int(verse_end_s) if verse_end_s is not None else verse_start

    # Reject "John 3:10-5" — end before start is almost certainly a typo.
    if verse_end < verse_start:
        return None

    return ParsedReference(
        book=book,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
    )


def verse_ids_for(ref: ParsedReference) -> list[str]:
    book_id = ref.book.replace(" ", "_")
    return [
        f"{book_id}_{ref.chapter}:{v}"
        for v in range(ref.verse_start, ref.verse_end + 1)
    ]
