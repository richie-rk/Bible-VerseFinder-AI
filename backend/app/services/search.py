"""
Search service implementing FAISS, BM25, and Hybrid RRF search.

Hybrid Search Formula (Adaptive Weighted RRF):
RRF_Score = α × (1/(faiss_rank + 60)) + (1-α) × (1/(bm25_rank + 60))

Where α varies based on query type.
"""

import json
from pathlib import Path

import bm25s
import faiss
import numpy as np
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
        self._stemmer = Stemmer.Stemmer("english")
        self._loaded = False

    def load_indices(self) -> None:
        if self._loaded:
            return

        vector_store = settings.vector_store_path

        # Load FAISS index
        faiss_path = vector_store / "bible_index.faiss"
        if not faiss_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
        self._faiss_index = faiss.read_index(str(faiss_path))

        # Load metadata
        metadata_path = vector_store / "verse_metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")
        with open(metadata_path, "r", encoding="utf-8") as f:
            self._metadata = json.load(f)

        # Load BM25 index
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
        """
        Search FAISS index for semantic matches.

        Returns:
            List of (index_id, score) tuples, filtered by threshold
        """
        if self._faiss_index is None:
            raise RuntimeError("FAISS index not loaded")

        # Get query embedding
        query_embedding = get_embedding(query)
        query_embedding = query_embedding.reshape(1, -1)

        # Search FAISS
        scores, indices = self._faiss_index.search(query_embedding, k)

        # Filter by threshold and return
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and score >= settings.faiss_threshold:
                results.append((int(idx), float(score)))

        return results

    def _search_bm25(self, query: str, k: int) -> list[tuple[int, float]]:
        """
        Search BM25 index for keyword matches.

        Returns:
            List of (index_id, score) tuples, filtered by threshold
        """
        if self._bm25_index is None:
            raise RuntimeError("BM25 index not loaded")

        # Tokenize query
        query_tokens = self._tokenize_query(query)

        # Search BM25
        indices, scores = self._bm25_index.retrieve(
            query_tokens,
            k=k,
            show_progress=False,
        )

        # Filter by threshold and return
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if score >= settings.bm25_threshold:
                results.append((int(idx), float(score)))

        return results

    def _compute_rrf(
        self,
        faiss_results: list[tuple[int, float]],
        bm25_results: list[tuple[int, float]],
        alpha: float,
    ) -> list[tuple[int, float, dict]]:
        """
        Compute Reciprocal Rank Fusion scores.

        Formula: RRF = α × (1/(faiss_rank + k)) + (1-α) × (1/(bm25_rank + k))

        Returns:
            List of (index_id, rrf_score, metadata) tuples sorted by score
        """
        k = settings.rrf_k  # Typically 60

        # Build rank dictionaries
        faiss_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(faiss_results)}
        faiss_scores = {idx: score for idx, score in faiss_results}

        bm25_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(bm25_results)}
        bm25_scores = {idx: score for idx, score in bm25_results}

        # Get all unique indices
        all_indices = set(faiss_ranks.keys()) | set(bm25_ranks.keys())

        # Compute RRF scores
        rrf_results = []
        for idx in all_indices:
            # Get ranks (use large rank if not in results)
            faiss_rank = faiss_ranks.get(idx, 10000)
            bm25_rank = bm25_ranks.get(idx, 10000)

            # Compute RRF score
            rrf_score = alpha * (1 / (faiss_rank + k)) + (1 - alpha) * (1 / (bm25_rank + k))

            # Include detailed scoring info
            score_info = {
                "faiss_score": faiss_scores.get(idx),
                "faiss_rank": faiss_ranks.get(idx),
                "bm25_score": bm25_scores.get(idx),
                "bm25_rank": bm25_ranks.get(idx),
            }

            rrf_results.append((idx, rrf_score, score_info))

        # Sort by RRF score descending
        rrf_results.sort(key=lambda x: x[1], reverse=True)

        # Filter by RRF threshold
        rrf_results = [(idx, score, info) for idx, score, info in rrf_results
                       if score >= settings.rrf_threshold]

        # Normalize scores to 0-1 range
        # Theoretical max RRF score is 1/(1+k) when a result is rank 1 in both indices
        max_rrf = 1 / (1 + k)
        rrf_results = [(idx, score / max_rrf, info) for idx, score, info in rrf_results]

        return rrf_results

    def _lookup_by_verse_ids(self, verse_ids: list[str]) -> list[dict]:
        """
        Return metadata entries for the given verse_ids, preserving input order.
        Unknown verse_ids are silently skipped (out-of-range verse numbers, etc.).

        Linear scan over _metadata; Phase 4 will replace with an O(1) dict.
        """
        if self._metadata is None:
            return []
        wanted = set(verse_ids)
        by_id: dict[str, dict] = {}
        for verse in self._metadata:
            vid = verse["verse_id"]
            if vid in wanted:
                by_id[vid] = verse
        return [by_id[vid] for vid in verse_ids if vid in by_id]

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VerseResult], int, QueryType, float | None]:
        """
        Perform search and return paginated results.

        Args:
            query: Search query
            mode: Search mode (semantic, keyword, hybrid)
            limit: Page size
            offset: Page offset

        Returns:
            Tuple of (results, total_count, query_type, alpha). Alpha is None
            for verse-reference lookups, where no FAISS/BM25 blending applies.
        """
        if not self._loaded:
            self.load_indices()

        # Verse-reference short-circuit: queries like "John 3:16" or
        # "1 Cor 13:4-7" skip FAISS + BM25 entirely.
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

        # Classify query and get alpha
        query_type, alpha = classify_query(query)

        # Override alpha based on mode
        if mode == SearchMode.SEMANTIC:
            alpha = 1.0
        elif mode == SearchMode.KEYWORD:
            alpha = 0.0

        k = settings.search_k

        # Perform search based on mode
        if mode == SearchMode.SEMANTIC:
            # Pure semantic search
            faiss_results = self._search_faiss(query, k)
            all_results = [
                (idx, score, {"faiss_score": score, "faiss_rank": rank + 1,
                              "bm25_score": None, "bm25_rank": None})
                for rank, (idx, score) in enumerate(faiss_results)
            ]

        elif mode == SearchMode.KEYWORD:
            # Pure keyword search
            bm25_results = self._search_bm25(query, k)
            # Normalize BM25 scores to 0-1 range relative to the top result
            max_bm25 = bm25_results[0][1] if bm25_results else 1.0
            all_results = [
                (idx, score / max_bm25, {"faiss_score": None, "faiss_rank": None,
                              "bm25_score": score, "bm25_rank": rank + 1})
                for rank, (idx, score) in enumerate(bm25_results)
            ]

        else:  # HYBRID
            # Get results from both indices
            faiss_results = self._search_faiss(query, k)
            bm25_results = self._search_bm25(query, k)

            # Compute RRF fusion
            all_results = self._compute_rrf(faiss_results, bm25_results, alpha)

        # Get total count before pagination
        total_count = len(all_results)

        # Apply pagination
        paginated = all_results[offset:offset + limit]

        # Build VerseResult objects
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


# Singleton instance
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
