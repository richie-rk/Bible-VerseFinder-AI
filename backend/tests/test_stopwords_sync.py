"""
The BM25 index is built by scripts/create_bm25_index.py with scripts/stopwords.py,
and queries are tokenized with app/core/stopwords.py. If the lists drift,
query tokens stop matching index tokens, so keep them identical.
"""

import ast
from pathlib import Path

from app.core.stopwords import BIBLICAL_STOPWORDS

SCRIPTS_STOPWORDS = Path(__file__).resolve().parents[2] / "scripts" / "stopwords.py"


def _scripts_stopwords() -> list[str]:
    tree = ast.parse(SCRIPTS_STOPWORDS.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BIBLICAL_STOPWORDS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"BIBLICAL_STOPWORDS not found in {SCRIPTS_STOPWORDS}")


def test_index_time_and_query_time_stopwords_match():
    assert _scripts_stopwords() == BIBLICAL_STOPWORDS


def test_stopwords_have_no_duplicates():
    assert len(BIBLICAL_STOPWORDS) == len(set(BIBLICAL_STOPWORDS))
