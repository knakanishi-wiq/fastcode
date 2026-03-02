---
phase: 13-bm25-retriever-swap
plan: "02"
subsystem: retriever
tags: [bm25, pkl, cleanup, rank-bm25, fts5]
dependency_graph:
  requires: [13-01]
  provides: [BM25-03]
  affects: [fastcode/retriever.py, fastcode/main.py, pyproject.toml]
tech_stack:
  added: []
  removed: [rank-bm25]
  patterns: [simple-tf-scorer, fts5-only-bm25]
key_files:
  created: []
  modified:
    - fastcode/retriever.py
    - fastcode/main.py
    - pyproject.toml
    - uv.lock
decisions:
  - "Replace BM25Okapi repo-overview scoring with simple TF sum (_simple_bm25_scores); adequate for <20 repos"
  - "repo_overview_bm25 attribute is now True sentinel (not None); guard `is not None` still works"
  - "Removed {repo_name}_bm25.pkl from delete_repository() cleanup list — no longer written"
metrics:
  duration: "~5 min"
  completed: "2026-03-02"
  tasks: 2
  files: 4
---

# Phase 13 Plan 02: Remove pkl BM25 Infrastructure Summary

**One-liner:** Deleted all pkl BM25 methods (save/load/index_for_bm25), removed rank-bm25 dependency, and replaced BM25Okapi repo-overview scorer with a simple Python TF sum helper.

## What Was Built

Completed the pkl BM25 elimination. After Plan 01 replaced `full_bm25()` with FTS5, Plan 02 removes all the infrastructure that wrote and read `{repo_name}_bm25.pkl` files:

- `save_bm25()`, `load_bm25()`, `index_for_bm25()` methods deleted from `HybridRetriever`
- All call sites in `main.py` removed (indexing, cache loading, multi-repo loading)
- `build_repo_overview_bm25()` retained but now uses `_simple_bm25_scores()` — a pure Python term-frequency scorer — instead of `BM25Okapi`
- `rank-bm25` removed from `pyproject.toml`; `uv.lock` regenerated

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Delete pkl methods and imports from retriever.py; replace repo_overview_bm25 | dc6148c | fastcode/retriever.py |
| 2 | Remove pkl call sites from main.py and rank-bm25 from pyproject.toml | 6f563c3 | fastcode/main.py, pyproject.toml, uv.lock |

## Verification Results

```
grep -rn "rank_bm25|BM25Okapi|_bm25.pkl|save_bm25|load_bm25|index_for_bm25" fastcode/  → 0 hits (source files only)
grep "rank-bm25" pyproject.toml                                                          → 0 hits
python -m pytest tests/ -x -q                                                           → 37 passed
python -m pytest tests/test_retriever_bm25.py -v                                        → 6 passed
uv sync                                                                                 → exit 0, rank-bm25==0.2.2 removed
ls ./data/*_bm25.pkl                                                                    → no files
```

## Decisions Made

1. **Simple TF scorer vs BM25Okapi for repo overviews:** The corpus is tiny (typically <10 repos). A simple term-frequency sum (`_simple_bm25_scores`) is correct and removes the external dependency.

2. **`repo_overview_bm25 = True` sentinel:** `build_repo_overview_bm25()` sets this to `True` when the corpus is ready. The existing `if self.repo_overview_bm25 is not None` guard in `_select_relevant_repositories()` correctly treats `True` as truthy.

3. **Removed `{repo_name}_bm25.pkl` from `delete_repository()` cleanup list:** Since we no longer write this file, keeping it in the cleanup list would be misleading. Removed cleanly.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- fastcode/retriever.py modified: FOUND
- fastcode/main.py modified: FOUND
- pyproject.toml modified: FOUND
- uv.lock updated: FOUND
- Commit dc6148c: FOUND
- Commit 6f563c3: FOUND
- 37 tests pass: VERIFIED
- Zero BM25/pkl source references: VERIFIED
