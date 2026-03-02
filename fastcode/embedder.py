"""
Code Embedder - Generate embeddings for code snippets
"""

import hashlib
import logging
import sqlite3
from typing import List, Dict, Any, Optional
import numpy as np
import litellm
from tqdm import tqdm


class CodeEmbedder:
    """Generate embeddings for code using litellm/VertexAI"""

    def __init__(self, config: Dict[str, Any], db_conn: Optional[sqlite3.Connection] = None):
        self.config = config
        self.embedding_config = config.get("embedding", {})
        self.logger = logging.getLogger(__name__)

        self.model_name = self.embedding_config.get("model", "vertex_ai/gemini-embedding-001")
        self.batch_size = self.embedding_config.get("batch_size", 32)
        self.normalize = self.embedding_config.get("normalize_embeddings", True)
        self.embedding_dim = self.embedding_config.get("embedding_dim", 3072)

        self.logger.info(f"Embedding model: {self.model_name} (dim={self.embedding_dim})")
        # No model download at init — litellm routes to VertexAI API at call time
        self._db_conn = db_conn

    def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
        """
        Generate embedding for a single text, checking SQLite embedding_cache first.

        Args:
            text: Input text
            task_type: Vertex AI task type — "RETRIEVAL_QUERY" (default) or "RETRIEVAL_DOCUMENT"

        Returns:
            Embedding vector (from cache or freshly computed)
        """
        if self._db_conn is not None:
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            row = self._db_conn.execute(
                "SELECT embedding FROM embedding_cache WHERE content_hash=? AND model=?",
                (content_hash, self.model_name),
            ).fetchone()
            if row is not None:
                cached = np.frombuffer(row[0], dtype=np.float32)
                if cached.shape[0] != self.embedding_dim:
                    raise ValueError(
                        f"Cached embedding dim {cached.shape[0]} != expected {self.embedding_dim}. "
                        f"Run: fastcode index --clear-cache to rebuild after a model change."
                    )
                return cached

        result = self.embed_batch([text], task_type=task_type)[0]

        if self._db_conn is not None:
            self._db_conn.execute(
                "INSERT OR IGNORE INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
                (content_hash, self.model_name, result.astype(np.float32).tobytes()),
            )
            self._db_conn.commit()

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

        Args:
            elements: List of code element dictionaries

        Returns:
            List of elements with embeddings added
        """
        if not elements:
            return []

        # Prepare texts for embedding
        texts = [self._prepare_code_text(elem) for elem in elements]

        # Generate embeddings
        self.logger.info(f"Generating embeddings for {len(texts)} code elements")
        embeddings = self.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
        self.logger.info(f"✓ Successfully generated embeddings for {len(embeddings)} code elements")

        # Add embeddings to elements
        for elem, embedding in zip(elements, embeddings):
            elem["embedding"] = embedding
            elem["embedding_text"] = texts[elements.index(elem)]

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
