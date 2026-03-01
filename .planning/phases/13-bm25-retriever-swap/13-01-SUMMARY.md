---
phase: 13-bm25-retriever-swap
plan: "01"
subsystem: retriever
tags: [bm25, fts5, sqlite, tdd, keyword-search]
requirements: [BM25-01, BM25-02]

dependency_graph:
  requires:
    - "fastcode/db.py (init_db, Phase 11 schema)"
    - "SQLite chunks_fts FTS5 table (Phase 12 indexer populates)"
  provides:
    - "HybridRetriever.full_bm25(query, repo_path, top_k) — FTS5-backed BM25 method"
    - "HybridRetriever._keyword_search() — delegates to full_bm25()"
  affects:
    - "fastcode/retriever.py — keyword search path"

tech_stack:
  added:
    - "fastcode.db.init_db — SQLite connection with FTS5 schema"
  patterns:
    - "FTS5 MATCH with LIKE-based repo scoping"
    - "TDD with _FakeBM25Retriever test double to isolate SQL logic"

key_files:
  created:
    - tests/test_retriever_bm25.py
  modified:
    - fastcode/retriever.py

decisions:
  - "Used _FakeBM25Retriever test double to test FTS5 SQL logic without HybridRetriever constructor complexity"
  - "Removed self.full_bm25/filtered_bm25 BM25Okapi attrs from __init__; full_bm25 is now a method"
  - "score=1.0 placeholder in _keyword_search() — FTS5 rank used for ordering, not exposed as float"
  - "Fixed index_for_bm25() and load_bm25() to not shadow full_bm25 method (BM25Okapi assignments removed)"

metrics:
  duration: "~6 min"
  completed: "2026-03-02"
  tasks: 2
  files_modified: 2
---

# Phase 13 Plan 01: FTS5-backed full_bm25() with repo scoping Summary

**One-liner:** Replaced BM25Okapi pkl-backed keyword search with live SQLite FTS5 queries via `full_bm25()` method on `HybridRetriever`.

## What Was Built

- `HybridRetriever.full_bm25(query, repo_path, top_k)` — queries `chunks_fts` FTS5 table via `MATCH`, joined to `chunks`, filtered by `source_path LIKE '{repo_path}/%'`, ordered by `fts.rank`
- `HybridRetriever._keyword_search()` — replaced entire BM25Okapi code path with a single delegation to `self.full_bm25()`
- `HybridRetriever._db_conn` — SQLite connection opened via `init_db()` in `__init__`, using `config["vector_store"]["db_path"]`
- 6 TDD tests in `tests/test_retriever_bm25.py` covering FTS5 results, repo scoping, empty results, ranking order, and cross-repo contamination

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing tests for full_bm25() | 3a164eb | tests/test_retriever_bm25.py |
| 2 (GREEN) | Implement full_bm25() and update _keyword_search() | d53b02c | fastcode/retriever.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed BM25Okapi method-shadowing assignments**
- **Found during:** Task 2 verification
- **Issue:** `index_for_bm25()` (line 141) and `load_bm25()` (line 1267) both assigned `self.full_bm25 = BM25Okapi(...)`, which would shadow the new `full_bm25()` method as an instance attribute if either method was called
- **Fix:** Removed `self.full_bm25 = BM25Okapi(...)` from both methods; replaced with a comment noting the FTS5 migration. `full_bm25_corpus` list is retained for `save_bm25()`/`load_bm25()` compatibility until Plan 02 removes those methods
- **Files modified:** fastcode/retriever.py (lines 141, 1267)
- **Commit:** d53b02c

## Verification Results

```
python -m pytest tests/test_retriever_bm25.py -v  → 6 passed
python -m pytest tests/ -x -q                     → 37 passed
grep "def full_bm25" fastcode/retriever.py         → found
grep "chunks_fts MATCH" fastcode/retriever.py      → found
grep "self.full_bm25(" fastcode/retriever.py       → found in _keyword_search
grep "self.full_bm25 = " fastcode/retriever.py     → (none found — method, not attr)
```

## Self-Check: PASSED
