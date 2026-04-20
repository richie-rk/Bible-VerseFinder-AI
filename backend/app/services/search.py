"""
FAISS + BM25 hybrid search with adaptive weighted RRF fusion.

Canonical RRF formula (see `_compute_rrf`):
    rrf = α × (1/(faiss_rank + k))    if doc in faiss, else 0
        + (1-α) × (1/(bm25_rank + k)) if doc in bm25,  else 0

α comes from `query_classifier.classify_query`.
"""

import json
from collections import defaultdict

import bm25s
import faiss
import Stemmer

from ..core.config import settings
from ..core.stopwords import BIBLICAL_STOPWORDS
from ..models.schemas import QueryType, SearchMode, VerseResult
from .embeddings import get_embedding
from .query_classifier import classify_query
from .verse_reference import parse_verse_reference, verse_ids_for


class SearchService:

    def __init__(self):
        self._faiss_index: faiss.IndexFlatIP | None = None
        self._bm25_index: bm25s.BM25 | None = None
        self._metadata: list[dict] | None = None
        self._by_verse_id: dict[str, dict] | None = None
        self._by_chapter: dict[tuple[str, int], list[dict]] | None = None
        self._stemmer = Stemmer.Stemmer("english")
        self._loaded = False

    def load_indices(self) -> None:
        if self._loaded:
            return

        vector_store = settings.vector_store_path

        faiss_path = vector_store / "bible_index.faiss"
        if not faiss_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
        self._faiss_index = faiss.read_index(str(faiss_path))

        metadata_path = vector_store / "verse_metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")
        with open(metadata_path, "r", encoding="utf-8") as f:
            self._metadata = json.load(f)

        self._by_verse_id = {v["verse_id"]: v for v in self._metadata}
        chapters: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for v in self._metadata:
            chapters[(v["book"], v["chapter"])].append(v)
        for verses in chapters.values():
            verses.sort(key=lambda v: v["verse_num"])
        self._by_chapter = dict(chapters)

        bm25_path = vector_store / "bm25_index.bm25s"
        if not bm25_path.exists():
            raise FileNotFoundError(f"BM25 index not found: {bm25_path}")
        self._bm25_index = bm25s.BM25.load(str(bm25_path), load_corpus=False)

        self._loaded = True

    @property
    def total_verses(self) -> int:
        if self._metadata is None:
            return 0
        return len(self._metadata)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _tokenize_query(self, query: str) -> list[list[str]]:
        return bm25s.tokenize(
            [query],
            stemmer=self._stemmer,
            stopwords=BIBLICAL_STOPWORDS,
            show_progress=False,
        )

    def _search_faiss(self, query: str, k: int) -> list[tuple[int, float]]:
        if self._faiss_index is None:
            raise RuntimeError("FAISS index not loaded")

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
            raise RuntimeError("BM25 index not loaded")

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
    ) -> list[tuple[int, float, dict]]:
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

    def get_verse(self, verse_id: str) -> dict | None:
        if not self._loaded:
            self.load_indices()
        assert self._by_verse_id is not None
        return self._by_verse_id.get(verse_id)

    def get_chapter(self, book: str, chapter: int) -> list[dict]:
        if not self._loaded:
            self.load_indices()
        assert self._by_chapter is not None
        return list(self._by_chapter.get((book, chapter), []))

    def _lookup_by_verse_ids(self, verse_ids: list[str]) -> list[dict]:
        # Preserves input order; skips verse_ids not in the corpus
        # (out-of-range verse numbers from user-typed refs).
        if self._by_verse_id is None:
            return []
        return [
            self._by_verse_id[vid] for vid in verse_ids if vid in self._by_verse_id
        ]

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VerseResult], int, QueryType, float | None]:
        """alpha is None for verse-reference lookups and non-hybrid modes — no blending applies."""
        if not self._loaded:
            self.load_indices()

        ref = parse_verse_reference(query)
        if ref is not None:
            verse_metas = self._lookup_by_verse_ids(verse_ids_for(ref))
            total = len(verse_metas)
            paginated = verse_metas[offset:offset + limit]
            results = [
                VerseResult(
                    rank=offset + i + 1,
                    verse_id=v["verse_id"],
                    book=v["book"],
                    text=v["text"],
                    score=1.0,
                    faiss_score=None,
                    faiss_rank=None,
                    bm25_score=None,
                    bm25_rank=None,
                )
                for i, v in enumerate(paginated)
            ]
            return results, total, QueryType.VERSE_REFERENCE, None

        query_type, alpha = classify_query(query)

        # Non-hybrid modes run a single retriever; blending doesn't apply.
        # Returning None avoids the UI showing a misleading "α: 1.0" chip.
        if mode != SearchMode.HYBRID:
            alpha = None

        k = settings.search_k

        if mode == SearchMode.SEMANTIC:
            faiss_results = self._search_faiss(query, k)
            all_results = [
                (idx, score, {"faiss_score": score, "faiss_rank": rank + 1,
                              "bm25_score": None, "bm25_rank": None})
                for rank, (idx, score) in enumerate(faiss_results)
            ]

        elif mode == SearchMode.KEYWORD:
            bm25_results = self._search_bm25(query, k)
            # Scale to [0, 1] relative to the top hit so pure-keyword scores
            # are comparable across queries with wildly different raw BM25.
            max_bm25 = bm25_results[0][1] if bm25_results else 1.0
            all_results = [
                (idx, score / max_bm25, {"faiss_score": None, "faiss_rank": None,
                              "bm25_score": score, "bm25_rank": rank + 1})
                for rank, (idx, score) in enumerate(bm25_results)
            ]

        else:  # HYBRID
            faiss_results = self._search_faiss(query, k)
            bm25_results = self._search_bm25(query, k)
            all_results = self._compute_rrf(faiss_results, bm25_results, alpha)

        total_count = len(all_results)
        paginated = all_results[offset:offset + limit]

        results = []
        for rank, (idx, score, info) in enumerate(paginated, start=offset + 1):
            verse = self._metadata[idx]
            results.append(VerseResult(
                rank=rank,
                verse_id=verse["verse_id"],
                book=verse["book"],
                text=verse["text"],
                score=round(score, 6),
                faiss_score=round(info["faiss_score"], 4) if info["faiss_score"] else None,
                faiss_rank=info["faiss_rank"],
                bm25_score=round(info["bm25_score"], 4) if info["bm25_score"] else None,
                bm25_rank=info["bm25_rank"],
            ))

        return results, total_count, query_type, alpha


_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
