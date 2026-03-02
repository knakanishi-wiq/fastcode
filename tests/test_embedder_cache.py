"""
Unit tests for CacheManager-backed embedding cache in CodeEmbedder.

Tests use in-memory SQLite (via CacheManager with backend="disk") and
mocked embed_batch to avoid VertexAI calls.
Covers cache hit, cache miss, shape mismatch, no-cache-manager guard,
bulk embed_code_elements caching (all-miss, all-hit, partial-hit),
and CacheManager embedding methods in isolation.
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

    def test_embed_code_elements_partial_cache_hit(self):
        """embed_batch receives only uncached elements; results reassembled in original order."""
        cm, embedder = _make_cache_and_embedder()

        elements = [
            {"type": "function", "name": "cached",      "code": "def cached(): pass"},
            {"type": "function", "name": "uncached",    "code": "def uncached(): pass"},
            {"type": "function", "name": "also_cached", "code": "def also_cached(): pass"},
        ]
        # Pre-seed the cache for elements 0 and 2 using the same text the embedder will produce.
        texts = [embedder._prepare_code_text(e) for e in elements]
        vec0 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        cm.set_embedding(_content_hash(texts[0]), MODEL, vec0)
        cm.set_embedding(_content_hash(texts[2]), MODEL, vec2)

        # embed_batch should be called with only the text for element 1 (the miss).
        miss_vec = np.array([[0.5, 0.5, 0.5]], dtype=np.float32)
        with patch.object(embedder, "embed_batch", return_value=miss_vec) as mock_batch:
            result = embedder.embed_code_elements([dict(e) for e in elements])

        mock_batch.assert_called_once_with([texts[1]], task_type="RETRIEVAL_DOCUMENT")
        assert np.array_equal(result[0]["embedding"], vec0)
        assert np.array_equal(result[1]["embedding"], miss_vec[0])
        assert np.array_equal(result[2]["embedding"], vec2)


class TestCacheManagerEmbeddings:
    """CacheManager embedding methods tested in isolation (disk/SQLite backend)."""

    def _make_cm(self):
        return CacheManager(CONFIG)

    def test_get_embedding_miss(self):
        """Returns None when the hash is not in the cache."""
        cm = self._make_cm()
        assert cm.get_embedding("no_such_hash", MODEL) is None

    def test_set_and_get_embedding_roundtrip(self):
        """set_embedding stores; get_embedding retrieves identical values."""
        cm = self._make_cm()
        h = _content_hash("roundtrip text")
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert cm.set_embedding(h, MODEL, vec)
        result = cm.get_embedding(h, MODEL)
        assert result is not None
        assert np.array_equal(result, vec)

    def test_set_embedding_is_idempotent(self):
        """Second set_embedding for the same key does not overwrite (INSERT OR IGNORE)."""
        cm = self._make_cm()
        h = _content_hash("idempotent text")
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([9.0, 9.0, 9.0], dtype=np.float32)
        cm.set_embedding(h, MODEL, vec1)
        cm.set_embedding(h, MODEL, vec2)
        assert np.array_equal(cm.get_embedding(h, MODEL), vec1)

    def test_get_embeddings_batch_partial_hit(self):
        """get_embeddings_batch returns only the hashes that are present."""
        cm = self._make_cm()
        h1, h2, h3 = (_content_hash(t) for t in ("a", "b", "c"))
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec3 = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        cm.set_embedding(h1, MODEL, vec1)
        cm.set_embedding(h3, MODEL, vec3)

        result = cm.get_embeddings_batch([h1, h2, h3], MODEL)

        assert set(result.keys()) == {h1, h3}
        assert np.array_equal(result[h1], vec1)
        assert np.array_equal(result[h3], vec3)

    def test_set_embeddings_batch_idempotent(self):
        """set_embeddings_batch: duplicate entries for existing keys are silently ignored."""
        cm = self._make_cm()
        h = _content_hash("batch dup")
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([9.0, 9.0, 9.0], dtype=np.float32)
        cm.set_embedding(h, MODEL, vec1)
        cm.set_embeddings_batch([{"content_hash": h, "model": MODEL, "embedding": vec2}])
        assert np.array_equal(cm.get_embedding(h, MODEL), vec1)

    def test_get_embeddings_batch_chunking(self):
        """get_embeddings_batch retrieves all entries when count exceeds the 900-param chunk size."""
        cm = self._make_cm()
        n = 901
        hashes = [_content_hash(f"chunk_text_{i}") for i in range(n)]
        vecs = [np.array([float(i), float(i), float(i)], dtype=np.float32) for i in range(n)]
        cm.set_embeddings_batch(
            [{"content_hash": h, "model": MODEL, "embedding": v} for h, v in zip(hashes, vecs)]
        )

        result = cm.get_embeddings_batch(hashes, MODEL)

        assert len(result) == n
        for h, v in zip(hashes, vecs):
            assert np.array_equal(result[h], v)

    def test_clear_embedding_cache_removes_all_rows(self):
        """clear_embedding_cache deletes every row; subsequent gets return None."""
        cm = self._make_cm()
        h = _content_hash("to be cleared")
        cm.set_embedding(h, MODEL, np.array([1.0, 2.0, 3.0], dtype=np.float32))
        assert cm.get_embedding(h, MODEL) is not None

        assert cm.clear_embedding_cache()

        assert cm.get_embedding(h, MODEL) is None
