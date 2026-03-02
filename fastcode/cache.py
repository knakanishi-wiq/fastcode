"""
Caching Module - Cache embeddings, queries, and results
"""

import os
import pickle
import hashlib
import logging
import json
import time
from typing import Any, Optional, List, Dict
import numpy as np

from .db import init_db


class CacheManager:
    """Manage caching for FastCode"""
    
    def __init__(self, config: dict):
        self.config = config
        self.cache_config = config.get("cache", {})
        self.logger = logging.getLogger(__name__)
        
        self.enabled = self.cache_config.get("enabled", True)
        self.backend = self.cache_config.get("backend", "disk")
        self.ttl = self.cache_config.get("ttl", 3600)
        self.cache_queries = self.cache_config.get("cache_queries", False)

        # Dialogue history TTL (default: 30 days for long-term conversation history)
        self.dialogue_ttl = self.cache_config.get("dialogue_ttl", 2592000)  # 30 days in seconds

        # Always open SQLite — chunks/FTS/embedding_cache tables live here
        # regardless of which cache backend is selected for Redis/query caching.
        db_path = config.get("vector_store", {}).get("db_path", "./data/fastcode.db")
        self._db_conn = init_db(db_path)

        self.cache = None

        if self.enabled:
            self._initialize_cache()
    
    def _initialize_cache(self):
        """Initialize Redis cache backend (SQLite embedding cache uses self._db_conn)."""
        if self.backend == "redis":
            try:
                import redis
                self.cache = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=0,
                    decode_responses=False
                )
                self.cache.ping()
                self.logger.info("Initialized Redis cache")
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis cache: {e}")
                self.enabled = False
        elif self.backend == "disk":
            # Disk backend supports only the SQLite embedding cache (self._db_conn).
            # Query result and dialogue caching require Redis; disable them.
            self.enabled = False
        else:
            self.logger.warning(f"Unknown cache backend: {self.backend}")
            self.enabled = False
    
    def _generate_key(self, prefix: str, *args) -> str:
        """Generate cache key from arguments"""
        # Create a hash of all arguments
        content = "_".join(str(arg) for arg in args)
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return f"{prefix}_{hash_val}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled or self.cache is None:
            return None
        
        try:
            if self.backend == "redis":
                value = self.cache.get(key)
                if value:
                    self.logger.debug(f"Cache hit: {key}")
                    return pickle.loads(value)
                return None
        
        except Exception as e:
            self.logger.warning(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if not self.enabled or self.cache is None:
            return False
        
        if ttl is None:
            ttl = self.ttl
        
        try:
            if self.backend == "redis":
                self.cache.setex(key, ttl, pickle.dumps(value))
                return True
        
        except Exception as e:
            self.logger.warning(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled or self.cache is None:
            return False
        
        try:
            if self.backend == "redis":
                return bool(self.cache.delete(key))
        except Exception as e:
            self.logger.warning(f"Cache delete error: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        if not self.enabled or self.cache is None:
            return False

        try:
            if self.backend == "redis":
                self.cache.flushdb()
                self.logger.info("Cleared Redis cache")
                return True
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")
            return False

    def get_embedding(self, content_hash: str, model: str) -> Optional[np.ndarray]:
        """Fetch a single embedding from Redis or SQLite."""
        if self.backend == "redis" and self.cache is not None:
            key = f"embedding_{content_hash}_{model}"
            try:
                data = self.cache.get(key)
                if data is not None:
                    return np.frombuffer(data, dtype=np.float32).copy()
            except Exception as e:
                self.logger.warning(f"Redis get_embedding error: {e}")
            return None
        try:
            row = self._db_conn.execute(
                "SELECT embedding FROM embedding_cache WHERE content_hash=? AND model=?",
                (content_hash, model),
            ).fetchone()
            if row is not None:
                return np.frombuffer(row[0], dtype=np.float32).copy()
        except Exception as e:
            self.logger.warning(f"SQLite get_embedding error: {e}")
        return None

    def set_embedding(self, content_hash: str, model: str, embedding: np.ndarray) -> bool:
        """Store a single embedding in Redis or SQLite."""
        if self.backend == "redis" and self.cache is not None:
            key = f"embedding_{content_hash}_{model}"
            try:
                # No TTL — embeddings are permanent until explicitly cleared.
                self.cache.set(key, embedding.astype(np.float32).tobytes())
                return True
            except Exception as e:
                self.logger.warning(f"Redis set_embedding error: {e}")
                return False
        try:
            self._db_conn.execute(
                "INSERT OR IGNORE INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
                (content_hash, model, embedding.astype(np.float32).tobytes()),
            )
            self._db_conn.commit()
            return True
        except Exception as e:
            self.logger.warning(f"SQLite set_embedding error: {e}")
            return False

    def get_embeddings_batch(self, content_hashes: List[str], model: str) -> Dict[str, np.ndarray]:
        """Fetch multiple embeddings from Redis or SQLite, returning hits as a dict."""
        result: Dict[str, np.ndarray] = {}
        if not content_hashes:
            return result

        if self.backend == "redis" and self.cache is not None:
            try:
                keys = [f"embedding_{h}_{model}" for h in content_hashes]
                values = self.cache.mget(keys)
                for h, v in zip(content_hashes, values):
                    if v is not None:
                        result[h] = np.frombuffer(v, dtype=np.float32).copy()
            except Exception as e:
                self.logger.warning(f"Redis get_embeddings_batch error: {e}")
            return result

        # SQLite path — chunk at 900 to stay under the 999-param SQLITE_MAX_VARIABLE_NUMBER.
        _CHUNK = 900
        try:
            for i in range(0, len(content_hashes), _CHUNK):
                chunk = content_hashes[i : i + _CHUNK]
                placeholders = ",".join("?" * len(chunk))
                rows = self._db_conn.execute(
                    f"SELECT content_hash, embedding FROM embedding_cache "
                    f"WHERE model=? AND content_hash IN ({placeholders})",
                    [model] + chunk,
                ).fetchall()
                for h, blob in rows:
                    result[h] = np.frombuffer(blob, dtype=np.float32).copy()
        except Exception as e:
            self.logger.warning(f"SQLite get_embeddings_batch error: {e}")
        return result

    def set_embeddings_batch(self, entries: List[Dict[str, Any]]) -> bool:
        """Store multiple embeddings in Redis or SQLite.

        Args:
            entries: List of dicts with keys "content_hash", "model", "embedding".
        """
        if not entries:
            return True

        if self.backend == "redis" and self.cache is not None:
            try:
                pipe = self.cache.pipeline()
                for e in entries:
                    key = f"embedding_{e['content_hash']}_{e['model']}"
                    pipe.set(key, e["embedding"].astype(np.float32).tobytes())
                pipe.execute()
                return True
            except Exception as e:
                self.logger.warning(f"Redis set_embeddings_batch error: {e}")
                return False
        try:
            self._db_conn.executemany(
                "INSERT OR IGNORE INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
                [(e["content_hash"], e["model"], e["embedding"].astype(np.float32).tobytes())
                 for e in entries],
            )
            self._db_conn.commit()
            return True
        except Exception as e:
            self.logger.warning(f"SQLite set_embeddings_batch error: {e}")
            return False

    def clear_embedding_cache(self) -> bool:
        """Clear all cached embeddings from Redis or SQLite."""
        if self.backend == "redis" and self.cache is not None:
            try:
                keys = list(self.cache.scan_iter(match="embedding_*"))
                if keys:
                    self.cache.delete(*keys)
                self.logger.info("Cleared Redis embedding cache")
                return True
            except Exception as e:
                self.logger.error(f"Redis embedding cache clear error: {e}")
                return False
        try:
            self._db_conn.execute("DELETE FROM embedding_cache")
            self._db_conn.commit()
            self.logger.info("Cleared SQLite embedding cache")
            return True
        except Exception as e:
            self.logger.error(f"Embedding cache clear error: {e}")
            return False
    
    def get_query_result(self, query: str, repo_hash: str) -> Optional[Any]:
        """Get cached query result"""
        if not self.cache_queries:
            return None
        key = self._generate_key("query", query, repo_hash)
        return self.get(key)
    
    def set_query_result(self, query: str, repo_hash: str, result: Any) -> bool:
        """Cache query result"""
        if not self.cache_queries:
            return False
        key = self._generate_key("query", query, repo_hash)
        return self.set(key, result)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled or self.cache is None:
            return {"enabled": False}
        
        try:
            if self.backend == "redis":
                info = self.cache.info()
                return {
                    "enabled": True,
                    "backend": "redis",
                    "size": info.get("used_memory", 0),
                    "items": self.cache.dbsize(),
                }
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}
    
    # ===== Multi-turn Dialogue Session Cache Methods =====
    
    def save_dialogue_turn(self, session_id: str, turn_number: int,
                           query: str, answer: str, summary: str,
                           retrieved_elements: Optional[List[Dict[str, Any]]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a single dialogue turn to cache

        Args:
            session_id: Unique session identifier
            turn_number: Turn number (1-indexed)
            query: User query
            answer: Generated answer
            summary: Brief summary of the dialogue turn
            retrieved_elements: Retrieved code elements (optional)
            metadata: Additional metadata (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Create turn data
            turn_data = {
                "session_id": session_id,
                "turn_number": turn_number,
                "timestamp": time.time(),
                "query": query,
                "answer": answer,
                "summary": summary,
                "retrieved_elements": retrieved_elements or [],
                "metadata": metadata or {}
            }

            # Generate key
            key = f"dialogue_{session_id}_turn_{turn_number}"

            # Save to cache (with longer TTL for dialogue history)
            # Use configurable dialogue_ttl instead of hardcoded value
            self.set(key, turn_data, ttl=self.dialogue_ttl)

            # Update session index (propagate multi_turn flag from metadata)
            multi_turn = (metadata or {}).get("multi_turn")
            self._update_session_index(session_id, turn_number, multi_turn=multi_turn)

            self.logger.debug(f"Saved dialogue turn: {session_id} turn {turn_number}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save dialogue turn: {e}")
            return False
    
    def get_dialogue_turn(self, session_id: str, turn_number: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific dialogue turn from cache
        
        Args:
            session_id: Session identifier
            turn_number: Turn number to retrieve
        
        Returns:
            Turn data dictionary or None
        """
        if not self.enabled:
            return None
        
        key = f"dialogue_{session_id}_turn_{turn_number}"
        return self.get(key)
    
    def get_dialogue_history(self, session_id: str, max_turns: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get dialogue history for a session
        
        Args:
            session_id: Session identifier
            max_turns: Maximum number of recent turns to retrieve (None = all)
        
        Returns:
            List of turn data dictionaries, ordered from oldest to newest
        """
        if not self.enabled:
            return []
        
        try:
            # Get session index
            session_index = self._get_session_index(session_id)
            if not session_index:
                return []
            
            total_turns = session_index.get("total_turns", 0)
            if total_turns == 0:
                return []
            
            # Determine which turns to retrieve
            if max_turns is None or max_turns >= total_turns:
                start_turn = 1
            else:
                start_turn = total_turns - max_turns + 1
            
            # Retrieve turns
            history = []
            for turn_num in range(start_turn, total_turns + 1):
                turn_data = self.get_dialogue_turn(session_id, turn_num)
                if turn_data:
                    history.append(turn_data)
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get dialogue history: {e}")
            return []
    
    def get_recent_summaries(self, session_id: str, num_rounds: int) -> List[Dict[str, Any]]:
        """
        Get recent dialogue summaries for context
        
        Args:
            session_id: Session identifier
            num_rounds: Number of recent rounds to retrieve
        
        Returns:
            List of summary data with turn_number, query, and summary
        """
        if not self.enabled:
            return []
        
        try:
            history = self.get_dialogue_history(session_id, max_turns=num_rounds)
            
            summaries = []
            for turn in history:
                summaries.append({
                    "turn_number": turn.get("turn_number"),
                    "query": turn.get("query"),
                    "summary": turn.get("summary"),
                })
            
            return summaries
            
        except Exception as e:
            self.logger.error(f"Failed to get recent summaries: {e}")
            return []
    
    def _update_session_index(self, session_id: str, turn_number: int,
                              multi_turn: Optional[bool] = None) -> bool:
        """Update session index with new turn"""
        try:
            key = f"dialogue_session_{session_id}_index"
            session_index = self.get(key) or {
                "session_id": session_id,
                "created_at": time.time(),
                "total_turns": 0,
                "last_updated": time.time(),
                "multi_turn": False
            }

            session_index["total_turns"] = max(session_index["total_turns"], turn_number)
            session_index["last_updated"] = time.time()

            # Once a session is marked as multi_turn, keep it that way
            if multi_turn is True:
                session_index["multi_turn"] = True

            # Use configurable dialogue_ttl instead of hardcoded value
            self.set(key, session_index, ttl=self.dialogue_ttl)
            return True

        except Exception as e:
            self.logger.error(f"Failed to update session index: {e}")
            return False
    
    def _get_session_index(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session index"""
        key = f"dialogue_session_{session_id}_index"
        return self.get(key)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete an entire dialogue session
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Get session index
            session_index = self._get_session_index(session_id)
            if not session_index:
                return False
            
            total_turns = session_index.get("total_turns", 0)
            
            # Delete all turns
            for turn_num in range(1, total_turns + 1):
                key = f"dialogue_{session_id}_turn_{turn_num}"
                self.delete(key)
            
            # Delete session index
            index_key = f"dialogue_session_{session_id}_index"
            self.delete(index_key)
            
            self.logger.info(f"Deleted session {session_id} with {total_turns} turns")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete session: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all dialogue sessions
        
        Returns:
            List of session metadata dictionaries
        """
        if not self.enabled or self.cache is None:
            return []
        
        try:
            sessions = []

            if self.backend == "redis":
                # Scan for session index keys
                for key in self.cache.scan_iter(match="dialogue_session_*_index"):
                    session_data = self.get(key.decode() if isinstance(key, bytes) else key)
                    if session_data:
                        sessions.append(session_data)
            
            # Sort by creation time descending (fallback to last_updated)
            sessions.sort(
                key=lambda x: (
                    x.get("created_at", 0),
                    x.get("last_updated", 0)
                ),
                reverse=True
            )
            return sessions
            
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return []

