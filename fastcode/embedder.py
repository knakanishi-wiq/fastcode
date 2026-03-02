"""
Code Embedder - Generate embeddings for code snippets
"""

import hashlib
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional
import numpy as np
import litellm
from tqdm import tqdm

if TYPE_CHECKING:
    from .cache import CacheManager


class CodeEmbedder:
    """Generate embeddings for code using litellm/VertexAI"""

    def __init__(self, config: Dict[str, Any],
                 cache_manager: Optional["CacheManager"] = None):
        self.config = config
        self.embedding_config = config.get("embedding", {})
        self.logger = logging.getLogger(__name__)

        self.model_name = self.embedding_config.get("model", "vertex_ai/gemini-embedding-001")
        self.batch_size = self.embedding_config.get("batch_size", 32)
        self.normalize = self.embedding_config.get("normalize_embeddings", True)
        self.embedding_dim = self.embedding_config.get("embedding_dim", 3072)

        self.logger.info(f"Embedding model: {self.model_name} (dim={self.embedding_dim})")
        # No model download at init — litellm routes to VertexAI API at call time
        self._cache_manager = cache_manager

    def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
        """
        Generate embedding for a single text, checking the cache first.

        Args:
            text: Input text
            task_type: Vertex AI task type — "RETRIEVAL_QUERY" (default) or "RETRIEVAL_DOCUMENT"

        Returns:
            Embedding vector (from cache or freshly computed)
        """
        content_hash = None
        if self._cache_manager is not None:
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            cached = self._cache_manager.get_embedding(content_hash, self.model_name)
            if cached is not None:
                if cached.shape[0] != self.embedding_dim:
                    raise ValueError(
                        f"Cached embedding dim {cached.shape[0]} != expected {self.embedding_dim}. "
                        f"Run: fastcode index --clear-cache to rebuild after a model change."
                    )
                return cached

        result = self.embed_batch([text], task_type=task_type)[0]

        if content_hash is not None:
            self._cache_manager.set_embedding(content_hash, self.model_name, result)

        return result

    def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
        """
        Generate embeddings for a batch of texts via litellm/VertexAI.

        Args:
            texts: List of input texts
            task_type: Vertex AI task type — "RETRIEVAL_QUERY" (default) or "RETRIEVAL_DOCUMENT"

        Returns:
            Array of embedding vectors, shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])

        all_vectors: List[List[float]] = []
        chunk_indices = range(0, len(texts), self.batch_size)

        if len(texts) > 100:
            chunk_indices = tqdm(chunk_indices, desc="Generating embeddings")

        for i in chunk_indices:
            batch = texts[i : i + self.batch_size]
            response = litellm.embedding(
                model=self.model_name,
                input=batch,
                task_type=task_type,
            )
            for item in response.data:
                all_vectors.append(item["embedding"])

        vectors = np.array(all_vectors, dtype=np.float32)

        if self.normalize and len(vectors) > 0:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero on degenerate input
            vectors = vectors / norms

        return vectors

    def embed_code_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for code elements (functions, classes, etc.)

        When a CacheManager is available, cached embeddings are looked up in bulk
        and only cache-miss elements are sent to the embedding API.

        Args:
            elements: List of code element dictionaries

        Returns:
            List of elements with embeddings added
        """
        if not elements:
            return []

        texts = [self._prepare_code_text(elem) for elem in elements]

        if self._cache_manager is None:
            # No cache — embed everything directly.
            self.logger.info(f"Generating embeddings for {len(texts)} code elements")
            embeddings = self.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
            self.logger.info(
                f"✓ Successfully generated embeddings for {len(embeddings)} code elements"
            )
            for i, (elem, emb) in enumerate(zip(elements, embeddings)):
                elem["embedding"] = emb
                elem["embedding_text"] = texts[i]
            return elements

        # Cache-aware bulk path: one DB query for all hashes, API only for misses.
        content_hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        cached = self._cache_manager.get_embeddings_batch(content_hashes, self.model_name)

        miss_indices = [i for i, h in enumerate(content_hashes) if h not in cached]
        if miss_indices:
            miss_texts = [texts[i] for i in miss_indices]
            self.logger.info(
                f"Generating embeddings for {len(miss_texts)} code elements "
                f"({len(elements) - len(miss_indices)} cached)"
            )
            new_embeddings = self.embed_batch(miss_texts, task_type="RETRIEVAL_DOCUMENT")
            self.logger.info(
                f"✓ Successfully generated embeddings for {len(new_embeddings)} code elements"
            )
            entries = [
                {"content_hash": content_hashes[i], "model": self.model_name,
                 "embedding": new_embeddings[j]}
                for j, i in enumerate(miss_indices)
            ]
            self._cache_manager.set_embeddings_batch(entries)
            for j, i in enumerate(miss_indices):
                cached[content_hashes[i]] = new_embeddings[j]

        for i, (elem, text) in enumerate(zip(elements, texts)):
            elem["embedding"] = cached[content_hashes[i]]
            elem["embedding_text"] = text

        return elements

    def _prepare_code_text(self, element: Dict[str, Any]) -> str:
        """
        Prepare code element for embedding

        Combines various parts of the code element into a single text
        suitable for embedding
        """
        parts = []

        # Add type
        if "type" in element:
            parts.append(f"Type: {element['type']}")

        # Add name
        if "name" in element:
            parts.append(f"Name: {element['name']}")

        # Add signature (for functions)
        if "signature" in element:
            parts.append(f"Signature: {element['signature']}")

        # Add docstring/description
        if "docstring" in element and element["docstring"]:
            parts.append(f"Documentation: {element['docstring']}")

        # Add summary
        if "summary" in element and element["summary"]:
            parts.append(element["summary"])

        # Add code snippet (truncated)
        if "code" in element:
            code = element["code"]
            if len(code) > 10000:  # Truncate long code
                code = code[:10000] + "..."
            parts.append(f"Code:\n{code}")

        return "\n".join(parts)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score (0-1)
        """
        if self.normalize:
            # Already normalized, just dot product
            return float(np.dot(embedding1, embedding2))
        else:
            # Compute cosine similarity
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    def compute_similarities(self, query_embedding: np.ndarray,
                            embeddings: np.ndarray) -> np.ndarray:
        """
        Compute similarities between query and multiple embeddings

        Args:
            query_embedding: Query embedding vector
            embeddings: Array of embedding vectors

        Returns:
            Array of similarity scores
        """
        if self.normalize:
            # Simple dot product for normalized embeddings
            similarities = np.dot(embeddings, query_embedding)
        else:
            # Compute cosine similarities
            norms = np.linalg.norm(embeddings, axis=1)
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                return np.zeros(len(embeddings))
            similarities = np.dot(embeddings, query_embedding) / (norms * query_norm)

        return similarities
