"""
Unit tests for CacheManager-backed embedding cache in CodeEmbedder.

Tests use in-memory SQLite (via CacheManager with backend="disk") and
mocked embed_batch to avoid VertexAI calls.
Covers cache hit, cache miss, shape mismatch, no-cache-manager guard,
and bulk embed_code_elements caching.
"""
import hashlib
from unittest.mock import patch

import numpy as np
import pytest

from fastcode.cache import CacheManager
from fastcode.embedder import CodeEmbedder

CONFIG = {
    "embedding": {
        "model": "vertex_ai/gemini-embedding-001",
        "embedding_dim": 3,
        "batch_size": 32,
        "normalize_embeddings": False,
    },
    "vector_store": {"db_path": ":memory:"},
    "cache": {"backend": "disk"},
}

MODEL = "vertex_ai/gemini-embedding-001"
TEXT = "hello world"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_cache_and_embedder():
    """Return a (CacheManager, CodeEmbedder) pair sharing an in-memory SQLite DB."""
    cm = CacheManager(CONFIG)
    embedder = CodeEmbedder(CONFIG, cache_manager=cm)
    return cm, embedder


class TestEmbedderCache:
    def test_cache_miss_calls_embed_batch_and_stores(self):
        """Cache miss: embed_batch called once; result retrievable via CacheManager."""
        cm, embedder = _make_cache_and_embedder()

        fake_vec = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result = embedder.embed_text(TEXT)

        mock_batch.assert_called_once_with([TEXT], task_type="RETRIEVAL_QUERY")
        assert np.array_equal(result, fake_vec[0])

        cached_emb = cm.get_embedding(_content_hash(TEXT), MODEL)
        assert cached_emb is not None, "Cache row should have been inserted"
        assert np.array_equal(cached_emb, fake_vec[0])

    def test_cache_hit_skips_embed_batch(self):
        """Cache hit: embed_batch called only once for two embed_text calls."""
        cm, embedder = _make_cache_and_embedder()

        fake_vec = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result1 = embedder.embed_text(TEXT)
            result2 = embedder.embed_text(TEXT)

        assert mock_batch.call_count == 1, "embed_batch must be called exactly once (cache hit on second call)"
        assert np.array_equal(result1, result2)

    def test_cache_shape_mismatch_raises(self):
        """Shape mismatch between cached embedding and embedding_dim raises ValueError."""
        cm, embedder = _make_cache_and_embedder()

        # Insert a 2-element BLOB instead of the expected 3-element vector.
        wrong_blob = np.array([9.0, 9.0], dtype=np.float32).tobytes()
        cm._db_conn.execute(
            "INSERT INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
            (_content_hash(TEXT), MODEL, wrong_blob),
        )
        cm._db_conn.commit()

        with pytest.raises(ValueError, match="--clear-cache"):
            embedder.embed_text(TEXT)

    def test_no_cache_manager_works(self):
        """embed_text works without a CacheManager (no-cache mode)."""
        embedder = CodeEmbedder(CONFIG, cache_manager=None)

        fake_vec = np.array([[4.0, 5.0, 6.0]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec) as mock_batch:
            result = embedder.embed_text(TEXT)

        mock_batch.assert_called_once()
        assert np.array_equal(result, fake_vec[0])

    def test_embed_text_returns_correct_vector(self):
        """embed_text returns the vector produced by embed_batch on a cache miss."""
        _, embedder = _make_cache_and_embedder()

        expected = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        fake_vec = np.array([[0.5, 0.5, 0.5]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=fake_vec):
            result = embedder.embed_text(TEXT)

        assert np.array_equal(result, expected)

    def test_embed_code_elements_uses_cache(self):
        """embed_batch called only for uncached elements on the second embed_code_elements call."""
        cm, embedder = _make_cache_and_embedder()

        elements = [
            {"type": "function", "name": "foo", "code": "def foo(): pass"},
            {"type": "function", "name": "bar", "code": "def bar(): pass"},
        ]
        fake_embeddings = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)

        with patch.object(embedder, "embed_batch", return_value=fake_embeddings) as mock_batch:
            result1 = embedder.embed_code_elements([dict(e) for e in elements])

        assert mock_batch.call_count == 1
        assert len(result1) == 2
        assert np.array_equal(result1[0]["embedding"], fake_embeddings[0])
        assert np.array_equal(result1[1]["embedding"], fake_embeddings[1])

        # Second call with the same elements — embed_batch must not be invoked.
        with patch.object(embedder, "embed_batch") as mock_batch2:
            result2 = embedder.embed_code_elements([dict(e) for e in elements])

        mock_batch2.assert_not_called()
        assert np.array_equal(result2[0]["embedding"], fake_embeddings[0])
        assert np.array_equal(result2[1]["embedding"], fake_embeddings[1])
