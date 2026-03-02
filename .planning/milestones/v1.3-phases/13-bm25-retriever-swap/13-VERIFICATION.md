---
phase: 13-bm25-retriever-swap
verified: 2026-03-02T00:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 13: BM25 Retriever Swap Verification Report

**Phase Goal:** `HybridRetriever` performs BM25 search via FTS5; pkl files are never written or read
**Verified:** 2026-03-02
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

#### Plan 01 — BM25-01, BM25-02

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `HybridRetriever.full_bm25(query, repo_path, top_k)` returns FTS5-ranked results from the SQLite `chunks_fts` table | VERIFIED | Method exists at `retriever.py:152`; body executes `chunks_fts MATCH ?` joined to `chunks`; ordered by `fts.rank` |
| 2 | BM25 results are scoped to the queried `repo_path`: chunks from other repos are excluded | VERIFIED | `LIKE '{repo_path}/%'` predicate at `retriever.py:173`; `test_full_bm25_scoped_to_repo` and `test_full_bm25_no_cross_repo_contamination` pass |
| 3 | An empty result list is returned when no chunks match the query for the given repo | VERIFIED | `test_full_bm25_empty_when_no_match` passes (NOMATCH_XYZZY returns `[]`) |
| 4 | Most-relevant chunk appears first in the returned list (FTS5 `rank` ordering) | VERIFIED | `ORDER BY fts.rank` at `retriever.py:174`; `test_full_bm25_ranking_order` passes (3-occurrence chunk ranks before 1-occurrence) |
| 5 | `_keyword_search()` calls `full_bm25()` instead of using a `BM25Okapi` object | VERIFIED | `retriever.py:787` — `chunks = self.full_bm25(query, repo_path=repo_path, top_k=top_k)`; `test_keyword_search_uses_full_bm25` passes |

#### Plan 02 — BM25-03

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | No `{repo_name}_bm25.pkl` file is written or read anywhere in the codebase | VERIFIED | `ls ./data/*_bm25.pkl` → no files; zero `_bm25.pkl` / `save_bm25` / `load_bm25` / `index_for_bm25` hits in `fastcode/retriever.py` and `fastcode/main.py` |
| 7 | `rank-bm25` is removed from `pyproject.toml` dependencies | VERIFIED | `grep "rank-bm25" pyproject.toml` → zero hits; `uv sync` removed `rank-bm25==0.2.2` |
| 8 | `import pickle` and `from rank_bm25 import BM25Okapi` are deleted from `retriever.py` and `main.py` | VERIFIED | `grep -rn "pickle\|BM25Okapi\|rank_bm25" fastcode/retriever.py fastcode/main.py` → zero hits |
| 9 | `save_bm25()`, `load_bm25()`, and `index_for_bm25()` methods are deleted from `HybridRetriever` | VERIFIED | `grep "def save_bm25\|def load_bm25\|def index_for_bm25" fastcode/retriever.py` → zero hits |
| 10 | `build_repo_overview_bm25()` and `_select_relevant_repositories()` work without `BM25Okapi` (simple token-frequency scorer) | VERIFIED | `_simple_bm25_scores()` at `retriever.py:95`; wired at `retriever.py:434` — `scores = self._simple_bm25_scores(self.repo_overview_bm25_corpus, query_tokens)`; sentinel `self.repo_overview_bm25 = True` at `retriever.py:149` |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_retriever_bm25.py` | Failing-then-passing tests for BM25-01 and BM25-02 | VERIFIED | 6 tests; all pass: `6 passed, 3 warnings in 1.37s` |
| `fastcode/retriever.py` | `full_bm25()` method + updated `_keyword_search()` + no pkl/rank_bm25 refs | VERIFIED | Method at line 152; `_keyword_search()` delegates at line 787; zero pkl/BM25Okapi hits |
| `fastcode/main.py` | No pkl BM25 call sites | VERIFIED | Zero hits for `index_for_bm25\|save_bm25\|load_bm25\|BM25Okapi\|rank_bm25\|_bm25\.pkl` |
| `pyproject.toml` | `rank-bm25` removed from dependencies | VERIFIED | Zero hits for `rank-bm25` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `retriever.py:_keyword_search` | `retriever.py:full_bm25` | method call | WIRED | `self.full_bm25(query, repo_path=repo_path, top_k=top_k)` at line 787 |
| `retriever.py:full_bm25` | `chunks_fts` | SQLite FTS5 query | WIRED | `WHERE chunks_fts MATCH ?` at line 172 |
| `retriever.py:build_repo_overview_bm25` | `retriever.py:_simple_bm25_scores` | internal scorer call | WIRED | `self._simple_bm25_scores(self.repo_overview_bm25_corpus, query_tokens)` at line 434 |
| `fastcode/main.py` | `fastcode/retriever.py` | no pkl method calls | WIRED | Zero hits for `save_bm25\|load_bm25\|index_for_bm25` in main.py |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BM25-01 | 13-01 | `HybridRetriever` BM25 search path queries `chunks_fts` using `bm25(chunks_fts)` ranking instead of loading a `BM25Okapi` object | SATISFIED | `full_bm25()` at `retriever.py:152` queries `chunks_fts MATCH` ordered by `fts.rank`; `_keyword_search()` delegates to it; 6 TDD tests pass |
| BM25-02 | 13-01 | FTS5 BM25 query supports filtering by `source_path` prefix to scope results to a specific indexed repository | SATISFIED | `LIKE '{repo_path}/%'` predicate in `full_bm25()`; `test_full_bm25_scoped_to_repo` and `test_full_bm25_no_cross_repo_contamination` pass |
| BM25-03 | 13-02 | `{repo_name}_bm25.pkl` index files are no longer written or loaded; BM25 corpus derived entirely from SQLite database | SATISFIED | Zero pkl hits in all source files; `save_bm25`/`load_bm25`/`index_for_bm25` deleted; `rank-bm25` removed from `pyproject.toml`; no pkl files in `./data/` |

No orphaned requirements: REQUIREMENTS.md maps BM25-01, BM25-02, BM25-03 all to Phase 13; all are claimed by plans 13-01 and 13-02 respectively.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `fastcode/__pycache__/retriever.cpython-313.pyc` | — | Stale bytecode containing old BM25Okapi/pickle strings | Info | Not source code; auto-regenerated; no runtime impact |
| `fastcode/__pycache__/main.cpython-313.pyc` | — | Stale bytecode containing old BM25Okapi/pickle strings | Info | Not source code; auto-regenerated; no runtime impact |

No source-level TODOs, FIXMEs, placeholder returns, or empty implementations found.

The `score=1.0` placeholder in `_keyword_search()` is documented in both the plan and the code docstring as intentional: FTS5 rank is used for ordering, and a normalized score float is not exposed. This is an acknowledged design decision, not a stub.

### Human Verification Required

None — all truths are mechanically verifiable via grep and test execution.

---

## Summary

Phase 13 goal is **fully achieved**.

Both plans executed without deviations from the second plan. The critical chain is intact:

1. `HybridRetriever.__init__` opens `self._db_conn = init_db(db_path)` (line 90)
2. `full_bm25()` queries `chunks_fts MATCH` with repo scoping via `LIKE` (lines 152-181)
3. `_keyword_search()` delegates entirely to `full_bm25()` — no `BM25Okapi` code path remains (lines 772-789)
4. `build_repo_overview_bm25()` uses `_simple_bm25_scores()` — a pure Python TF scorer — with `True` sentinel (lines 111-150)
5. `_select_relevant_repositories()` calls `_simple_bm25_scores()` for scoring (line 434)
6. `save_bm25()`, `load_bm25()`, `index_for_bm25()` are deleted; all call sites in `main.py` are removed
7. `rank-bm25` is absent from `pyproject.toml`; no `{repo_name}_bm25.pkl` files exist

Full test suite: 37 passed. BM25-specific tests: 6 passed. Zero source references to pickle, BM25Okapi, rank_bm25, or pkl files.

---

_Verified: 2026-03-02_
_Verifier: Claude (gsd-verifier)_
