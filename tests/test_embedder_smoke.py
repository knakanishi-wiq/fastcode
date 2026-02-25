"""
Embedder smoke test — validates litellm.embedding() + ADC integration for
fastcode.embedder.CodeEmbedder.

Skips when VERTEXAI_PROJECT is not set (CI without credentials).
"""
import os

import numpy as np
import pytest
from dotenv import load_dotenv

load_dotenv()


class TestEmbedderSmoke:
    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test",
    )
    def test_embed_text_returns_normalized_vector(self):
        """embed_text() returns a 3072-dim L2-normalized ndarray via VertexAI ADC."""
        from fastcode.embedder import CodeEmbedder

        config = {
            "embedding": {
                "model": "vertex_ai/gemini-embedding-001",
                "embedding_dim": 3072,
                "batch_size": 32,
                "normalize_embeddings": True,
            }
        }
        embedder = CodeEmbedder(config)
        result = embedder.embed_text("hello world", task_type="RETRIEVAL_QUERY")

        assert isinstance(result, np.ndarray), f"Expected ndarray, got {type(result)}"
        assert result.shape == (3072,), f"Expected shape (3072,), got {result.shape}"
        assert np.all(np.isfinite(result)), "Expected all finite values"
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5, f"Expected L2 norm ≈ 1.0, got {norm}"
