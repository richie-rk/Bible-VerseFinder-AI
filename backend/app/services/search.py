"""
FAISS + BM25 hybrid search with adaptive weighted RRF fusion.

Canonical RRF formula (see `_compute_rrf`):
    rrf = α × (1/(faiss_rank + k))    if doc in faiss, else 0
        + (1-α) × (1/(bm25_rank + k)) if doc in bm25,  else 0

α comes from `query_classifier.classify_query`.

Every method here blocks (OpenAI embeddings, FAISS, SQLite), so callers on
the event loop must hop to a worker thread first. The service is safe to
share between threads: the indices are read-only after load_indices(), and
the stemmer, the one stateful piece, is kept per thread.
"""

import json
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass

import bm25s
import faiss
import Stemmer
from bm25s.tokenization import Tokenized

from ..core.config import settings
from ..core.stopwords import BIBLICAL_STOPWORDS
from ..models.schemas import QueryType, SearchMode, VerseResult
from .embeddings import EmbeddingUnavailableError, get_embedding
from .query_classifier import classify_query, extract_quoted_phrases
from .verse_reference import (
    ParsedReference,
    canonical_verse_id,
    normalize_book,
    old_testament_reference_book,
    parse_verse_reference,
)

logger = logging.getLogger(__name__)

SEMANTIC_FALLBACK_NOTICE = (
    "Semantic search is temporarily unavailable, so these are keyword matches only."
)
NO_PHRASE_MATCH_NOTICE = (
    "No verses contain the exact quoted wording, so these are the closest matches."
)

_REQUIRED_METADATA_KEYS = ("verse_id", "book", "chapter", "verse_num", "text")
_NON_WORD = re.compile(r"[\W_]+")

# (index into metadata, score, scoring details)
Candidate = tuple[int, float, dict]


class IndexLoadError(RuntimeError):
    """The index files exist but don't line up with each other."""


class IndexNotLoadedError(RuntimeError):
    """A lookup ran before load_indices() succeeded."""


@dataclass(frozen=True)
class SearchOutcome:
    results: list[VerseResult]
    total: int
    query_type: QueryType
    # None when no blending applied: verse-reference lookups, non-hybrid
    # modes, and hybrid searches that fell back to BM25 alone.
    alpha: float | None
    notice: str | None = None


def _phrase_key(text: str) -> str:
    """Lowercased words separated by single spaces, so punctuation and curly
    vs straight apostrophes don't affect phrase matching."""
    return _NON_WORD.sub(" ", text.lower()).strip()


def _round_or_none(value: float | None, ndigits: int) -> float | None:
    return None if value is None else round(value, ndigits)


class SearchService:

    def __init__(self):
        self._faiss_index: faiss.IndexFlatIP | None = None
        self._bm25_index: bm25s.BM25 | None = None
        self._metadata: list[dict] = []
        self._by_verse_id: dict[str, dict] = {}
        self._by_chapter: dict[tuple[str, int], list[dict]] = {}
        self._chapters_per_book: dict[str, int] = {}
        # " word word ... " per verse, for whole-word phrase matching.
        self._phrase_keys: list[str] = []
        self._loaded = False
        self._load_lock = threading.Lock()
        # PyStemmer objects must not be used from two threads at once.
        self._thread_local = threading.local()

    def load_indices(self) -> None:
        with self._load_lock:
            if self._loaded:
                return

            vector_store = settings.vector_store_path
            faiss_path = vector_store / "bible_index.faiss"
            metadata_path = vector_store / "verse_metadata.json"
            bm25_path = vector_store / "bm25_index.bm25s"

            if not faiss_path.exists():
                raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata not found: {metadata_path}")
            if not bm25_path.exists():
                raise FileNotFoundError(f"BM25 index not found: {bm25_path}")

            faiss_index = faiss.read_index(str(faiss_path))
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            bm25_index = bm25s.BM25.load(str(bm25_path), load_corpus=False)

            self._validate_indices(faiss_index, bm25_index, metadata)

            chapters: dict[tuple[str, int], list[dict]] = defaultdict(list)
            for v in metadata:
                chapters[(v["book"], v["chapter"])].append(v)
            for verses in chapters.values():
                verses.sort(key=lambda v: v["verse_num"])

            chapters_per_book: dict[str, int] = {}
            for book, chapter in chapters:
                chapters_per_book[book] = max(chapters_per_book.get(book, 0), chapter)

            self._faiss_index = faiss_index
            self._bm25_index = bm25_index
            self._metadata = metadata
            self._by_verse_id = {v["verse_id"]: v for v in metadata}
            self._by_chapter = dict(chapters)
            self._chapters_per_book = chapters_per_book
            self._phrase_keys = [f" {_phrase_key(v['text'])} " for v in metadata]
            self._loaded = True

    @staticmethod
    def _validate_indices(faiss_index, bm25_index, metadata: list[dict]) -> None:
        # Results are joined by position: FAISS row i, BM25 doc i and
        # metadata[i] must all describe the same verse.
        if faiss_index.d != settings.embedding_dim:
            raise IndexLoadError(
                f"FAISS index has {faiss_index.d} dimensions but {settings.embedding_model} "
                f"embeddings have {settings.embedding_dim}"
            )
        if faiss_index.ntotal != len(metadata):
            raise IndexLoadError(
                f"FAISS index holds {faiss_index.ntotal} vectors but verse_metadata.json "
                f"has {len(metadata)} verses"
            )
        bm25_docs = getattr(bm25_index, "scores", {}).get("num_docs")
        if bm25_docs is not None and bm25_docs != len(metadata):
            raise IndexLoadError(
                f"BM25 index holds {bm25_docs} documents but verse_metadata.json "
                f"has {len(metadata)} verses"
            )
        for i, verse in enumerate(metadata):
            missing = [key for key in _REQUIRED_METADATA_KEYS if key not in verse]
            if missing:
                raise IndexLoadError(f"verse_metadata.json entry {i} is missing {missing}")
            if verse.get("index_id", i) != i:
                raise IndexLoadError(
                    f"verse_metadata.json entry {i} has index_id {verse['index_id']}"
                )

    @property
    def total_verses(self) -> int:
        return len(self._metadata)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise IndexNotLoadedError("Search indices are not loaded; call load_indices() first")

    def _stemmer(self) -> Stemmer.Stemmer:
        stemmer = getattr(self._thread_local, "stemmer", None)
        if stemmer is None:
            stemmer = Stemmer.Stemmer("english")
            self._thread_local.stemmer = stemmer
        return stemmer

    def _tokenize_query(self, query: str) -> Tokenized:
        return bm25s.tokenize(
            [query],
            stemmer=self._stemmer(),
            stopwords=BIBLICAL_STOPWORDS,
            show_progress=False,
        )

    def _search_faiss(self, query: str, k: int) -> list[tuple[int, float]]:
        """Raises EmbeddingUnavailableError if the query can't be embedded."""
        if self._faiss_index is None:
            raise IndexNotLoadedError("FAISS index not loaded")

        query_embedding = get_embedding(query).reshape(1, -1)
        scores, indices = self._faiss_index.search(query_embedding, k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and score >= settings.faiss_threshold:
                results.append((int(idx), float(score)))
        return results

    def _search_bm25(self, query: str, k: int) -> list[tuple[int, float]]:
        # Dynamic threshold: BM25 scores scale with query-term rarity. A fixed
        # cutoff is too loose for rare-word queries and too strict for common
        # ones, so keep results above a fraction of the top score with an
        # absolute floor as noise guard.
        if self._bm25_index is None:
            raise IndexNotLoadedError("BM25 index not loaded")

        query_tokens = self._tokenize_query(query)
        indices, scores = self._bm25_index.retrieve(
            query_tokens,
            k=k,
            show_progress=False,
        )

        if indices.size == 0 or scores.size == 0:
            return []

        top_score = float(scores[0][0])
        if top_score <= 0.0:
            return []

        threshold = max(
            settings.bm25_min_score,
            top_score * settings.bm25_relative_threshold,
        )

        results = []
        for idx, score in zip(indices[0], scores[0]):
            s = float(score)
            if s >= threshold:
                results.append((int(idx), s))
        return results

    def _compute_rrf(
        self,
        faiss_results: list[tuple[int, float]],
        bm25_results: list[tuple[int, float]],
        alpha: float,
    ) -> list[Candidate]:
        # Canonical RRF: each retriever only contributes when it actually
        # returned the doc. Normalize to [0, 1] so rrf_threshold reads as a
        # fraction of the theoretical max (rank 1 in both retrievers).
        k = settings.rrf_k

        faiss_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(faiss_results)}
        faiss_scores = {idx: score for idx, score in faiss_results}
        bm25_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(bm25_results)}
        bm25_scores = {idx: score for idx, score in bm25_results}

        all_indices = set(faiss_ranks.keys()) | set(bm25_ranks.keys())

        rrf_results = []
        for idx in all_indices:
            rrf_score = 0.0
            if idx in faiss_ranks:
                rrf_score += alpha * (1 / (faiss_ranks[idx] + k))
            if idx in bm25_ranks:
                rrf_score += (1 - alpha) * (1 / (bm25_ranks[idx] + k))

            score_info = {
                "faiss_score": faiss_scores.get(idx),
                "faiss_rank": faiss_ranks.get(idx),
                "bm25_score": bm25_scores.get(idx),
                "bm25_rank": bm25_ranks.get(idx),
            }
            rrf_results.append((idx, rrf_score, score_info))

        max_rrf = 1 / (1 + k)
        rrf_results = [(idx, score / max_rrf, info) for idx, score, info in rrf_results]
        rrf_results = [
            (idx, score, info) for idx, score, info in rrf_results
            if score >= settings.rrf_threshold
        ]
        rrf_results.sort(key=lambda x: x[1], reverse=True)
        return rrf_results

    def _semantic_candidates(self, query: str, k: int) -> list[Candidate]:
        return [
            (idx, score, {"faiss_score": score, "faiss_rank": rank,
                          "bm25_score": None, "bm25_rank": None})
            for rank, (idx, score) in enumerate(self._search_faiss(query, k), start=1)
        ]

    def _keyword_candidates(self, query: str, k: int) -> list[Candidate]:
        bm25_results = self._search_bm25(query, k)
        # Scale to [0, 1] relative to the top hit so pure-keyword scores
        # are comparable across queries with wildly different raw BM25.
        max_bm25 = bm25_results[0][1] if bm25_results else 1.0
        return [
            (idx, score / max_bm25, {"faiss_score": None, "faiss_rank": None,
                                     "bm25_score": score, "bm25_rank": rank})
            for rank, (idx, score) in enumerate(bm25_results, start=1)
        ]

    def _filter_by_phrases(self, candidates: list[Candidate], phrases: list[str]) -> list[Candidate]:
        """Keep candidates whose text contains every quoted phrase as whole words."""
        keys = [f" {key} " for key in map(_phrase_key, phrases) if key]
        if not keys:
            return candidates
        return [
            c for c in candidates
            if all(key in self._phrase_keys[c[0]] for key in keys)
        ]

    def get_verse(self, verse_id: str) -> dict | None:
        """Look up a verse by ID, tolerating case and book abbreviations
        ("john_3:16", "1 Jn_4:8")."""
        self._require_loaded()
        verse = self._by_verse_id.get(verse_id)
        if verse is None:
            canonical = canonical_verse_id(verse_id)
            if canonical is not None:
                verse = self._by_verse_id.get(canonical)
        return verse

    def get_chapter(self, book: str, chapter: int) -> list[dict]:
        """Verses of a chapter in order; `book` may be any recognised alias."""
        self._require_loaded()
        canonical = normalize_book(book) or book
        return list(self._by_chapter.get((canonical, chapter), []))

    def chapter_count(self, book: str) -> int:
        """Number of chapters in `book` (0 if unknown)."""
        self._require_loaded()
        return self._chapters_per_book.get(normalize_book(book) or book, 0)

    def _lookup_reference(self, ref: ParsedReference) -> list[dict]:
        # Walks the chapter instead of expanding verse_start..verse_end, so a
        # wide range costs no more than the chapter's real length.
        return [
            v for v in self._by_chapter.get((ref.book, ref.chapter), [])
            if ref.verse_start <= v["verse_num"] <= ref.verse_end
        ]

    def _to_result(self, verse: dict, rank: int, score: float, info: dict | None = None) -> VerseResult:
        info = info or {}
        return VerseResult(
            rank=rank,
            verse_id=verse["verse_id"],
            book=verse["book"],
            text=verse["text"],
            score=round(score, 6),
            faiss_score=_round_or_none(info.get("faiss_score"), 4),
            faiss_rank=info.get("faiss_rank"),
            bm25_score=_round_or_none(info.get("bm25_score"), 4),
            bm25_rank=info.get("bm25_rank"),
        )

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchOutcome:
        """Raises EmbeddingUnavailableError only in SEMANTIC mode; HYBRID
        falls back to BM25 alone and says so in `notice`."""
        self._require_loaded()

        ref = parse_verse_reference(query)
        if ref is not None:
            verses = self._lookup_reference(ref)
            results = [
                self._to_result(v, rank=offset + i + 1, score=1.0)
                for i, v in enumerate(verses[offset:offset + limit])
            ]
            return SearchOutcome(results, len(verses), QueryType.VERSE_REFERENCE, None)

        ot_book = old_testament_reference_book(query)
        if ot_book is not None:
            return SearchOutcome(
                [], 0, QueryType.VERSE_REFERENCE, None,
                notice=(
                    f"{ot_book} is in the Old Testament, which isn't indexed. "
                    "Only New Testament verses are searchable."
                ),
            )

        query_type, alpha = classify_query(query)

        # Non-hybrid modes run a single retriever; blending doesn't apply.
        # Returning None avoids the UI showing a misleading "α: 1.0" chip.
        if mode != SearchMode.HYBRID:
            alpha = None

        k = settings.search_k
        notice = None

        if mode == SearchMode.SEMANTIC:
            candidates = self._semantic_candidates(query, k)
        elif mode == SearchMode.KEYWORD:
            candidates = self._keyword_candidates(query, k)
        else:  # HYBRID
            try:
                faiss_results = self._search_faiss(query, k)
            except EmbeddingUnavailableError as e:
                logger.warning("Semantic retrieval unavailable, serving BM25 only: %s", e)
                candidates = self._keyword_candidates(query, k)
                alpha = None
                notice = SEMANTIC_FALLBACK_NOTICE
            else:
                bm25_results = self._search_bm25(query, k)
                candidates = self._compute_rrf(faiss_results, bm25_results, alpha)

        # Neither retriever honours word order (BM25 even drops stopwords such
        # as "again"), so an explicitly quoted phrase is enforced here.
        phrases = extract_quoted_phrases(query)
        if phrases and candidates:
            phrase_matches = self._filter_by_phrases(candidates, phrases)
            if phrase_matches:
                candidates = phrase_matches
            else:
                notice = notice or NO_PHRASE_MATCH_NOTICE

        page = candidates[offset:offset + limit]
        results = [
            self._to_result(self._metadata[idx], rank=rank, score=score, info=info)
            for rank, (idx, score, info) in enumerate(page, start=offset + 1)
        ]
        return SearchOutcome(results, len(candidates), query_type, alpha, notice)


_search_service = SearchService()


def get_search_service() -> SearchService:
    return _search_service
