"""
Verse-reference parsing and lookup.

Detects queries that name an exact verse or verse range ("John 3:16",
"1 Cor 13:4-7", "Rom 8.28", "I John 4:8") and parses them into a
ParsedReference. `search.search()` uses this to skip FAISS + BM25 entirely
when a query is really an exact lookup. Also normalizes loosely written book
names and verse IDs for the /verses and /chapters endpoints.

Book-name matching is deliberately strict: only recognised aliases return a
canonical book, so "Jesus 3:16" fails here and falls through to normal
search rather than producing a wrong result.

The corpus is New Testament only. Old Testament references are recognised
separately (`old_testament_reference_book`) so search can say so instead of
returning unrelated NT verses.
"""

from dataclasses import dataclass
import re


# Four groups: book (letters with optional 1/2/3 ordinal prefix), chapter,
# verse start, verse end (optional). Accepts ":" or "." as separator and
# "-" or en-dash for ranges. Numbers are capped at three digits (no book has
# 1000 chapters or verses), which also keeps "John 1:1-99999999" from
# expanding into a giant range and huge digit strings from reaching int().
_VERSE_REF_PATTERN = re.compile(
    r"^\s*((?:[123]\s*)?[A-Za-z]+)\s+(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?\s*$",
)

# "John_3:16", "1_John_4:8", "1 John 4:8", "jn_3:16". Applied only to short
# inputs (see canonical_verse_id) so the lazy book group can't backtrack
# quadratically on long junk.
_VERSE_ID_PATTERN = re.compile(r"^\s*(.+?)[\s_]+(\d{1,3})\s*[:.]\s*(\d{1,3})\s*$")
_MAX_VERSE_ID_LENGTH = 64
_MAX_BOOK_NAME_LENGTH = 40

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


# Old Testament books (not in the corpus). Only used to explain an empty
# result, so a few ambiguous short forms are acceptable here.
_OLD_TESTAMENT_ALIASES: dict[str, str] = {
    "genesis": "Genesis", "gen": "Genesis", "gn": "Genesis",
    "exodus": "Exodus", "exod": "Exodus", "exo": "Exodus", "ex": "Exodus",
    "leviticus": "Leviticus", "lev": "Leviticus", "lv": "Leviticus",
    "numbers": "Numbers", "num": "Numbers", "nm": "Numbers",
    "deuteronomy": "Deuteronomy", "deut": "Deuteronomy", "dt": "Deuteronomy",
    "joshua": "Joshua", "josh": "Joshua", "jos": "Joshua",
    "judges": "Judges", "judg": "Judges", "jdg": "Judges",
    "ruth": "Ruth", "rth": "Ruth",
    "1samuel": "1 Samuel", "1sam": "1 Samuel", "1sa": "1 Samuel",
    "2samuel": "2 Samuel", "2sam": "2 Samuel", "2sa": "2 Samuel",
    "1kings": "1 Kings", "1kgs": "1 Kings", "1ki": "1 Kings",
    "2kings": "2 Kings", "2kgs": "2 Kings", "2ki": "2 Kings",
    "1chronicles": "1 Chronicles", "1chron": "1 Chronicles", "1chr": "1 Chronicles",
    "2chronicles": "2 Chronicles", "2chron": "2 Chronicles", "2chr": "2 Chronicles",
    "ezra": "Ezra", "ezr": "Ezra",
    "nehemiah": "Nehemiah", "neh": "Nehemiah",
    "esther": "Esther", "esth": "Esther", "est": "Esther",
    "job": "Job",
    "psalms": "Psalms", "psalm": "Psalms", "psa": "Psalms", "ps": "Psalms", "pss": "Psalms",
    "proverbs": "Proverbs", "prov": "Proverbs", "prv": "Proverbs", "pr": "Proverbs",
    "ecclesiastes": "Ecclesiastes", "eccl": "Ecclesiastes", "ecc": "Ecclesiastes",
    "song": "Song of Solomon", "sos": "Song of Solomon",
    "isaiah": "Isaiah", "isa": "Isaiah",
    "jeremiah": "Jeremiah", "jer": "Jeremiah",
    "lamentations": "Lamentations", "lam": "Lamentations",
    "ezekiel": "Ezekiel", "ezek": "Ezekiel", "ezk": "Ezekiel",
    "daniel": "Daniel", "dan": "Daniel", "dn": "Daniel",
    "hosea": "Hosea", "hos": "Hosea",
    "joel": "Joel", "jl": "Joel",
    "amos": "Amos",
    "obadiah": "Obadiah", "obad": "Obadiah", "ob": "Obadiah",
    "jonah": "Jonah", "jon": "Jonah", "jnh": "Jonah",
    "micah": "Micah", "mic": "Micah",
    "nahum": "Nahum", "nah": "Nahum",
    "habakkuk": "Habakkuk", "hab": "Habakkuk",
    "zephaniah": "Zephaniah", "zeph": "Zephaniah", "zep": "Zephaniah",
    "haggai": "Haggai", "hag": "Haggai",
    "zechariah": "Zechariah", "zech": "Zechariah", "zec": "Zechariah",
    "malachi": "Malachi", "mal": "Malachi",
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


def _book_key(raw: str) -> str:
    return re.sub(r"\s+", "", raw).lower()


def _normalize_book(raw: str) -> str | None:
    return _BOOK_ALIASES.get(_book_key(raw))


def normalize_book(raw: str) -> str | None:
    """Map a user-supplied NT book name or abbreviation to its canonical name.

    Accepts any case, underscores for spaces and Roman-numeral ordinals:
    "john", "1_John", "1 jn" and "I John" all resolve. Returns None for
    unknown books.
    """
    if not raw or len(raw) > _MAX_BOOK_NAME_LENGTH:
        return None
    return _normalize_book(_preprocess(raw.replace("_", " ")))


def canonical_verse_id(raw: str) -> str | None:
    """Rewrite a loosely formatted verse ID ("john_3:16", "1 Jn 4:8") into
    the corpus form ("John_3:16", "1_John_4:8"). Returns None if it doesn't
    parse or names an unknown book."""
    if not raw or len(raw) > _MAX_VERSE_ID_LENGTH:
        return None
    match = _VERSE_ID_PATTERN.match(raw)
    if match is None:
        return None
    raw_book, chapter_s, verse_s = match.groups()
    book = normalize_book(raw_book)
    if book is None:
        return None
    return f"{book.replace(' ', '_')}_{int(chapter_s)}:{int(verse_s)}"


def old_testament_reference_book(query: str) -> str | None:
    """Canonical book name if `query` is a verse reference into the Old
    Testament ("Genesis 1:1", "Ps 23:1"), else None."""
    if not query or not query.strip():
        return None
    match = _VERSE_REF_PATTERN.match(_preprocess(query))
    if match is None:
        return None
    return _OLD_TESTAMENT_ALIASES.get(_book_key(match.group(1)))


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
