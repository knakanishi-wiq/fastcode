"""
Unit tests for SQLite-backed embedding cache in CodeEmbedder.

Tests use in-memory SQLite and mocked embed_batch to avoid VertexAI calls.
Covers cache hit, cache miss, shape mismatch, and no-connection guard.
"""
import hashlib
import sqlite3
from unittest.mock import patch

import numpy as np
import pytest

from fastcode.db import init_db
from fastcode.embedder import CodeEmbedder

CONFIG = {
    "embedding": {
        "model": "vertex_ai/gemini-embedding-001",
        "embedding_dim": 3,
        "batch_size": 32,
        "normalize_embeddings": False,
    }
}

MODEL = "vertex_ai/gemini-embedding-001"
TEXT = "hello world"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class TestEmbedderCache:
    def test_cache_miss_calls_embed_batch_and_stores(self):
        """Cache miss: embed_batch called once; result stored in embedding_cache."""
        conn = init_db(":memory:")
        embedder = CodeEmbedder(CONFIG, db_conn=conn)

        fake_vec = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result = embedder.embed_text(TEXT)

        mock_batch.assert_called_once_with([TEXT], task_type="RETRIEVAL_QUERY")
        assert np.array_equal(result, fake_vec[0])

        row = conn.execute(
            "SELECT embedding FROM embedding_cache WHERE content_hash=? AND model=?",
            (_content_hash(TEXT), MODEL),
        ).fetchone()
        assert row is not None, "Cache row should have been inserted"
        cached = np.frombuffer(row[0], dtype=np.float32)
        assert np.array_equal(cached, fake_vec[0])

    def test_cache_hit_skips_embed_batch(self):
        """Cache hit: embed_batch called only once for two embed_text calls."""
        conn = init_db(":memory:")
        embedder = CodeEmbedder(CONFIG, db_conn=conn)

        fake_vec = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result1 = embedder.embed_text(TEXT)
            result2 = embedder.embed_text(TEXT)

        assert mock_batch.call_count == 1, "embed_batch must be called exactly once (cache hit on second call)"
        assert np.array_equal(result1, result2)

    def test_cache_shape_mismatch_raises(self):
        """Shape mismatch between cached embedding and embedding_dim raises ValueError."""
        conn = init_db(":memory:")
        embedder = CodeEmbedder(CONFIG, db_conn=conn)

        # Insert a 2-element BLOB instead of 3-element
        wrong_blob = np.array([9.0, 9.0], dtype=np.float32).tobytes()
        conn.execute(
            "INSERT INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
            (_content_hash(TEXT), MODEL, wrong_blob),
        )
        conn.commit()

        with pytest.raises(ValueError, match="--clear-cache"):
            embedder.embed_text(TEXT)

    def test_no_db_conn_works(self):
        """embed_text works without a DB connection (no-cache mode)."""
        embedder = CodeEmbedder(CONFIG, db_conn=None)

        fake_vec = np.array([[4.0, 5.0, 6.0]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result = embedder.embed_text(TEXT)

        mock_batch.assert_called_once()
        assert np.array_equal(result, fake_vec[0])

    def test_embed_text_returns_correct_vector(self):
        """embed_text returns the vector produced by embed_batch on a cache miss."""
        conn = init_db(":memory:")
        embedder = CodeEmbedder(CONFIG, db_conn=conn)

        expected = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        fake_vec = np.array([[0.5, 0.5, 0.5]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec):
            result = embedder.embed_text(TEXT)

        assert np.array_equal(result, expected)
