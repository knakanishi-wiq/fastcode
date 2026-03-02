---
phase: 14-embedding-cache-migration
plan: "01"
subsystem: database
tags: [sqlite, embedding-cache, tdd, numpy, blob]

# Dependency graph
requires:
  - phase: 11-sqlite-schema-and-db-init
    provides: init_db(), SQLite schema pattern
provides:
  - "fastcode/db.py: embedding_cache DDL (content_hash, model, embedding BLOB, composite PK)"
  - "fastcode/embedder.py: SQLite cache lookup/store in embed_text() via _db_conn"
  - "fastcode/main.py: embedder._db_conn wired from retriever._db_conn after init"
  - "tests/test_embedder_cache.py: 5 unit tests covering hit, miss, mismatch, no-conn"
affects:
  - 14-02-diskcache-removal (can now remove diskcache — embedding cache is fully SQLite)

# Tech tracking
tech-stack:
  added: [hashlib (stdlib), sqlite3 (stdlib, already imported)]
  patterns:
    - "numpy BLOB round-trip: ndarray.tobytes() / np.frombuffer(row[0], dtype=float32)"
    - "Optional db_conn param on CodeEmbedder.__init__ — None = no-cache (backward compat)"
    - "content_hash = hashlib.sha256(text.encode()).hexdigest() as cache key"
    - "INSERT OR IGNORE preserves existing cache entries; no overwrites"

key-files:
  created:
    - tests/test_embedder_cache.py
  modified:
    - fastcode/db.py
    - fastcode/embedder.py
    - fastcode/main.py

key-decisions:
  - "Wired embedder._db_conn from retriever._db_conn in FastCode.__init__ (post-init assignment) — avoids changing constructor order"
  - "Cache only in embed_text() (single-text path), not embed_batch() — per locked decision"
  - "normalize_embeddings=False in test config to simplify vector equality assertions"
  - "content_hash variable scoped to if-block; reused in INSERT after cache miss — no double hash"

patterns-established:
  - "embedding_cache table: (content_hash TEXT, model TEXT, embedding BLOB), PK (content_hash, model)"
  - "Shape validation on retrieval: ValueError if cached dim != embedding_dim"

requirements-completed: [EMB-01, EMB-02]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 14 Plan 01: Embedding Cache TDD Summary

**SQLite embedding_cache table added to db.py; embed_text() checks/stores via BLOB; 5 unit tests green**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-02
- **Tasks:** 3 (TDD: RED + GREEN + wire)
- **Files modified:** 4

## Accomplishments

1. Added `embedding_cache` DDL to `fastcode/db.py` `_DDL` string — idempotent `CREATE TABLE IF NOT EXISTS`
2. Updated `CodeEmbedder.__init__` to accept `db_conn: Optional[sqlite3.Connection] = None`
3. Replaced `embed_text()` with cache-aware version: check → return cached | call `embed_batch()` → store → return
4. Shape mismatch guard raises `ValueError` with `--clear-cache` hint
5. Wired `embedder._db_conn = retriever._db_conn` in `FastCode.__init__` post-retriever-init
6. TDD: 5 unit tests written first (RED), then implementation (GREEN)

## Test Results

```
tests/test_embedder_cache.py: 5 passed
tests/test_db.py: 7 passed
Full suite: 42 passed, 0 failed
```

## Self-Check: PASSED
