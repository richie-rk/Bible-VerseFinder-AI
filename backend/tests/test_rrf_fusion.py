"""
Unit tests for the Reciprocal Rank Fusion math in SearchService._compute_rrf.

These are pure-Python tests that construct synthetic (idx, score) lists and
call _compute_rrf directly. No FAISS/BM25 indices or OpenAI keys required.
Instantiating SearchService() without load_indices() is fine — __init__ just
sets up empty attributes.
"""

import pytest

from app.core.config import settings
from app.services.search import SearchService


# ---------- Helpers ----------

def _rrf(faiss_results, bm25_results, alpha):
    """Thin wrapper so tests don't have to construct SearchService each time."""
    svc = SearchService()
    return svc._compute_rrf(faiss_results, bm25_results, alpha)


def _score_for(idx, results):
    for i, score, _ in results:
        if i == idx:
            return score
    return None


def _info_for(idx, results):
    for i, _, info in results:
        if i == idx:
            return info
    return None


# ---------- Canonical RRF: no ghost contribution ----------

def test_doc_only_in_faiss_has_no_bm25_contribution():
    """
    A doc missing from BM25 must not receive a (1-α) * 1/(10000+k) phantom
    contribution. Its BM25 side contributes exactly 0.
    """
    faiss = [(1, 0.9)]                    # doc 1 at rank 1 in FAISS
    bm25 = [(2, 5.0)]                     # different doc in BM25
    results = _rrf(faiss, bm25, alpha=0.5)

    k = settings.rrf_k
    max_rrf = 1 / (1 + k)

    doc1_score = _score_for(1, results)
    assert doc1_score is not None
    # Expected: 0.5 * 1/(1+k) / max_rrf = 0.5 (exact)
    expected_normalized = (0.5 * (1 / (1 + k))) / max_rrf
    assert doc1_score == pytest.approx(expected_normalized)
    # Sanity: info records None for missing side
    info1 = _info_for(1, results)
    assert info1["bm25_score"] is None
    assert info1["bm25_rank"] is None


def test_doc_only_in_bm25_has_no_faiss_contribution():
    faiss = [(1, 0.9)]
    bm25 = [(2, 5.0)]
    results = _rrf(faiss, bm25, alpha=0.5)

    k = settings.rrf_k
    max_rrf = 1 / (1 + k)

    doc2_score = _score_for(2, results)
    expected_normalized = (0.5 * (1 / (1 + k))) / max_rrf
    assert doc2_score == pytest.approx(expected_normalized)
    info2 = _info_for(2, results)
    assert info2["faiss_score"] is None
    assert info2["faiss_rank"] is None


def test_doc_in_both_beats_doc_in_one_at_equal_ranks():
    """
    A doc at rank 1 in both retrievers must outscore a doc at rank 1 in only
    one, because the canonical formula sums both contributions.
    """
    faiss = [(1, 0.9), (2, 0.8)]  # doc 1 rank 1, doc 2 rank 2 in FAISS
    bm25 = [(1, 5.0), (3, 4.0)]   # doc 1 rank 1 in BM25, doc 3 rank 2
    results = _rrf(faiss, bm25, alpha=0.5)

    score1 = _score_for(1, results)
    score2 = _score_for(2, results)
    score3 = _score_for(3, results)

    assert score1 > score2
    assert score1 > score3


def test_alpha_1_zeros_out_bm25_side():
    """α=1.0 means only FAISS contributes; BM25-only docs get score 0."""
    faiss = [(1, 0.9)]
    bm25 = [(2, 5.0)]
    results = _rrf(faiss, bm25, alpha=1.0)

    doc2_score = _score_for(2, results)
    # BM25-only doc gets 0 from both sides at α=1.0 — filtered out by threshold.
    assert doc2_score is None  # Below rrf_threshold, so removed


def test_alpha_0_zeros_out_faiss_side():
    faiss = [(1, 0.9)]
    bm25 = [(2, 5.0)]
    results = _rrf(faiss, bm25, alpha=0.0)

    doc1_score = _score_for(1, results)
    assert doc1_score is None  # Filtered out


# ---------- Normalization & max score ----------

def test_rank_1_in_both_reaches_max_normalized_score():
    """A doc at rank 1 in BOTH retrievers with α=0.5 should hit the max (1.0)."""
    faiss = [(1, 0.9)]
    bm25 = [(1, 5.0)]
    results = _rrf(faiss, bm25, alpha=0.5)

    doc1_score = _score_for(1, results)
    # 0.5 * 1/(1+k) + 0.5 * 1/(1+k) = 1/(1+k); normalized = 1.0
    assert doc1_score == pytest.approx(1.0)


def test_normalized_scores_are_in_0_1_range():
    """Every returned score should be in [0, 1] after normalization."""
    # Synthetic: 20 docs in FAISS, 20 in BM25, partial overlap
    faiss = [(i, 1.0 - i * 0.01) for i in range(1, 21)]
    bm25 = [(i, 5.0 - i * 0.1) for i in range(15, 35)]
    results = _rrf(faiss, bm25, alpha=0.5)

    for _, score, _ in results:
        assert 0.0 <= score <= 1.0


def test_results_sorted_descending():
    faiss = [(i, 1.0 - i * 0.01) for i in range(1, 11)]
    bm25 = [(i, 5.0 - i * 0.1) for i in range(5, 15)]
    results = _rrf(faiss, bm25, alpha=0.5)

    scores = [s for _, s, _ in results]
    assert scores == sorted(scores, reverse=True)


# ---------- Threshold on 0-1 scale ----------

def test_threshold_filters_deep_tail_one_retriever_only():
    """
    With default threshold 0.15, a doc at rank 150 in only FAISS with α=0.5
    produces normalized score ≈ 0.5 * 1/(150+60) / (1/61) ≈ 0.145 — below 0.15,
    should be filtered. A doc at rank 50 in only FAISS gives ≈ 0.277 — passes.
    """
    # Rank 50 (should pass) and rank 200 (should fail) at α=0.5
    faiss = [(idx, 1.0 - rank * 0.001) for rank, idx in enumerate(range(1, 201))]
    results = _rrf(faiss, [], alpha=0.5)

    rank_50_score = _score_for(50, results)  # at faiss rank 50
    rank_200_score = _score_for(200, results)  # at faiss rank 200

    # Rank 50 / α=0.5 → normalized ≈ 0.5 * 1/110 * 61 ≈ 0.277
    assert rank_50_score is not None
    assert rank_50_score > settings.rrf_threshold

    # Rank 200 / α=0.5 → normalized ≈ 0.5 * 1/260 * 61 ≈ 0.117 → filtered
    assert rank_200_score is None


def test_threshold_not_applied_when_both_retrievers_contribute():
    """
    A doc appearing in both retrievers even at mid-depth easily clears 0.15.
    """
    faiss = [(i, 1.0 - i * 0.01) for i in range(1, 51)]   # doc 1..50 in FAISS
    bm25 = [(i, 5.0 - i * 0.1) for i in range(1, 51)]     # same docs in BM25
    results = _rrf(faiss, bm25, alpha=0.5)

    # Every doc that appears at rank <=50 in both should survive the threshold.
    returned_indices = {idx for idx, _, _ in results}
    assert returned_indices == set(range(1, 51))


# ---------- Edge cases ----------

def test_empty_faiss_and_bm25_returns_empty():
    results = _rrf([], [], alpha=0.5)
    assert results == []


def test_empty_faiss_only_bm25_survives():
    bm25 = [(1, 5.0)]
    results = _rrf([], bm25, alpha=0.5)
    # α=0.5, rank 1 BM25 only → normalized = 0.5
    score = _score_for(1, results)
    assert score == pytest.approx(0.5)


def test_scoring_info_preserved():
    """The score_info dict must carry through to the final result."""
    faiss = [(7, 0.95)]
    bm25 = [(7, 4.2)]
    results = _rrf(faiss, bm25, alpha=0.5)

    info = _info_for(7, results)
    assert info["faiss_score"] == 0.95
    assert info["faiss_rank"] == 1
    assert info["bm25_score"] == 4.2
    assert info["bm25_rank"] == 1


# ---------- search() non-hybrid alpha behavior ----------

def test_search_semantic_mode_returns_alpha_none():
    """
    In SEMANTIC mode, alpha has no blending meaning. search() must return None
    so the UI doesn't show a fake "α: 1.0" chip.
    Skipped if no OPENAI_API_KEY available.
    """
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; cannot run live semantic search.")

    from app.services.search import get_search_service
    from app.models.schemas import SearchMode

    svc = get_search_service()
    svc.load_indices()
    _, _, _, alpha = svc.search("grace", mode=SearchMode.SEMANTIC)
    assert alpha is None


def test_search_keyword_mode_returns_alpha_none():
    """In KEYWORD mode, alpha is also None. No OpenAI call needed for BM25."""
    from app.services.search import get_search_service
    from app.models.schemas import SearchMode

    svc = get_search_service()
    svc.load_indices()
    _, _, _, alpha = svc.search("grace", mode=SearchMode.KEYWORD)
    assert alpha is None


def test_search_hybrid_mode_still_returns_numeric_alpha():
    """HYBRID mode must still return the blended alpha from the classifier."""
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; cannot run live hybrid search.")

    from app.services.search import get_search_service
    from app.models.schemas import SearchMode

    svc = get_search_service()
    svc.load_indices()
    _, _, _, alpha = svc.search("grace", mode=SearchMode.HYBRID)
    assert isinstance(alpha, float)
    assert 0.0 < alpha < 1.0


# ---------- /search endpoint regression ----------

def test_search_endpoint_builds_thresholds_applied():
    """
    Regression test: the /search response builder references
    settings.faiss_threshold, settings.bm25_min_score, and
    settings.rrf_threshold. Renaming or removing any of them breaks the
    endpoint with a 500 AttributeError. This test touches the real endpoint
    through FastAPI's TestClient (with lifespan) so the error surfaces here
    rather than in production.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        # KEYWORD mode avoids the OpenAI embedding call; BM25 alone is enough
        # to exercise the full response-building path.
        response = client.get(
            "/search",
            params={"query": "grace", "mode": "keyword", "limit": 5},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "thresholds_applied" in data
        assert set(data["thresholds_applied"].keys()) == {"faiss", "bm25", "rrf"}
        # Non-hybrid mode: alpha must be None (Phase 3 desync fix)
        assert data["alpha"] is None
