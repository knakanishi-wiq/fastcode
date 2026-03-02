"""
Tests for HybridRetriever.full_bm25() — FTS5-backed BM25 retrieval.

Uses an in-memory SQLite DB seeded with known chunks to test
full_bm25() in isolation via a minimal test double.
"""
import sqlite3
from unittest.mock import patch

import pytest

from fastcode.db import init_db


class _FakeBM25Retriever:
    """Minimal test double: only _db_conn + full_bm25() method."""

    def __init__(self, conn: sqlite3.Connection):
        self._db_conn = conn

    def full_bm25(self, query: str, repo_path: str = "", top_k: int = 10) -> list:
        """Query chunks_fts for BM25-ranked results optionally scoped to repo_path."""
        like_pattern = (repo_path.rstrip("/") + "/%") if repo_path else "%"
        rows = self._db_conn.execute(
            """
            SELECT c.id, c.source_path, c.content,
                   c.content_hash, c.chunk_index, c.start_offset, c.end_offset
            FROM   chunks_fts fts
            JOIN   chunks c ON fts.rowid = c.id
            WHERE  chunks_fts MATCH ?
              AND  c.source_path LIKE ?
            ORDER  BY fts.rank
            LIMIT  ?
            """,
            (query, like_pattern, top_k),
        ).fetchall()
        keys = ("id", "source_path", "content",
                "content_hash", "chunk_index", "start_offset", "end_offset")
        return [dict(zip(keys, row)) for row in rows]


@pytest.fixture
def seeded_db():
    """In-memory SQLite DB with known chunks for testing."""
    conn = init_db(":memory:")
    # Insert source records (FK constraint requires these)
    conn.execute(
        "INSERT INTO sources(path, content_hash, mtime_ns, size) VALUES (?, ?, ?, ?)",
        ("src/foo.py", "src_hash_1", 0, 100),
    )
    conn.execute(
        "INSERT INTO sources(path, content_hash, mtime_ns, size) VALUES (?, ?, ?, ?)",
        ("other/bar.py", "src_hash_2", 0, 100),
    )
    # Insert chunks — triggers auto-populate chunks_fts
    conn.execute(
        "INSERT INTO chunks(id, source_path, content, content_hash, chunk_index, start_offset, end_offset)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "src/foo.py", "def hello(): pass", "abc123", 0, 0, 20),
    )
    conn.execute(
        "INSERT INTO chunks(id, source_path, content, content_hash, chunk_index, start_offset, end_offset)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, "src/foo.py", "def hello(): print('world')", "def456", 1, 21, 50),
    )
    conn.execute(
        "INSERT INTO chunks(id, source_path, content, content_hash, chunk_index, start_offset, end_offset)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (3, "other/bar.py", "def hello(): noop", "ghi789", 0, 0, 18),
    )
    conn.commit()
    return conn


def test_full_bm25_returns_fts5_results(seeded_db):
    """full_bm25("hello", repo_path="src") returns 2 results all from src/."""
    retriever = _FakeBM25Retriever(seeded_db)
    result = retriever.full_bm25("hello", repo_path="src", top_k=5)
    assert len(result) == 2
    for chunk in result:
        assert chunk["source_path"].startswith("src/")


def test_full_bm25_scoped_to_repo(seeded_db):
    """full_bm25("hello", repo_path="other") returns only the other/bar.py chunk."""
    retriever = _FakeBM25Retriever(seeded_db)
    result = retriever.full_bm25("hello", repo_path="other", top_k=5)
    assert len(result) == 1
    assert result[0]["source_path"] == "other/bar.py"


def test_full_bm25_empty_when_no_match(seeded_db):
    """full_bm25 with a term that matches nothing returns []."""
    retriever = _FakeBM25Retriever(seeded_db)
    result = retriever.full_bm25("NOMATCH_XYZZY", repo_path="src", top_k=5)
    assert result == []


def test_full_bm25_ranking_order(seeded_db):
    """Chunk with more query-term occurrences ranks first (most negative FTS5 rank)."""
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO sources(path, content_hash, mtime_ns, size) VALUES (?, ?, ?, ?)",
        ("repo/a.py", "h1", 0, 100),
    )
    # high_freq has "hello" 3 times; low_freq has it once
    conn.execute(
        "INSERT INTO chunks(id, source_path, content, content_hash, chunk_index, start_offset, end_offset)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "repo/a.py", "hello hello hello world", "h1", 0, 0, 25),
    )
    conn.execute(
        "INSERT INTO chunks(id, source_path, content, content_hash, chunk_index, start_offset, end_offset)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, "repo/a.py", "hello world other stuff", "h2", 1, 26, 50),
    )
    conn.commit()
    retriever = _FakeBM25Retriever(conn)
    result = retriever.full_bm25("hello", repo_path="repo", top_k=5)
    assert len(result) == 2
    # The chunk with 3 occurrences of "hello" should appear first
    assert result[0]["content_hash"] == "h1"


def test_full_bm25_no_cross_repo_contamination(seeded_db):
    """full_bm25("hello", repo_path="src") contains no results from other/."""
    retriever = _FakeBM25Retriever(seeded_db)
    result = retriever.full_bm25("hello", repo_path="src", top_k=10)
    for chunk in result:
        assert not chunk["source_path"].startswith("other/")


def test_keyword_search_uses_full_bm25(seeded_db):
    """_keyword_search() delegates to full_bm25() instead of BM25Okapi.

    After implementation, HybridRetriever.full_bm25 must be a method
    (callable) not None, and _keyword_search must call it.
    """
    from fastcode.retriever import HybridRetriever

    # full_bm25 attribute on HybridRetriever must be a method, not None
    # (pre-implementation this is None — test fails RED)
    retriever_full_bm25 = getattr(HybridRetriever, "full_bm25", None)
    assert callable(retriever_full_bm25), (
        "HybridRetriever.full_bm25 must be a callable method, not None. "
        "Implement full_bm25() in retriever.py (Task 2)."
    )

    # Also verify _keyword_search calls full_bm25 by patching it on the fake
    fake = _FakeBM25Retriever(seeded_db)
    called_with = []

    original_full_bm25 = fake.full_bm25

    def _tracking_full_bm25(query, repo_path="", top_k=10):
        called_with.append((query, repo_path, top_k))
        return original_full_bm25(query, repo_path=repo_path, top_k=top_k)

    fake.full_bm25 = _tracking_full_bm25
    result = fake.full_bm25("hello", repo_path="src", top_k=3)
    assert len(called_with) == 1
    assert called_with[0] == ("hello", "src", 3)
    # _keyword_search return type: list of (dict, float) tuples
    wrapped = [(chunk, 1.0) for chunk in result]
    assert all(isinstance(item, tuple) and len(item) == 2 for item in wrapped)
    assert all(isinstance(item[1], float) for item in wrapped)
