# Phase 13: BM25 Retriever Swap - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Swap `HybridRetriever`'s BM25 backend from `BM25Okapi` (rank_bm25 library) + pkl files to SQLite
FTS5. Eliminate all pkl file reads and writes. No new retrieval capabilities — same interface, new
backend.

</domain>

<decisions>
## Implementation Decisions

### pkl removal
- Stop writing and reading pkl files — no automated migration or cleanup of existing files on disk
- Remove all pkl read/write code and imports from wherever they live (research should find all sites)
- Remove `rank_bm25` (BM25Okapi) from `pyproject.toml` entirely — it will be unused after this phase

### Repository scoping
- Scope FTS5 results to a repo using `source_path LIKE '{repo_path}/%'` — no schema change needed
- Implementation: FTS5 MATCH + JOIN to chunks table with WHERE clause on `source_path`
  (`SELECT c.* FROM chunks_fts fts JOIN chunks c ON fts.rowid = c.id WHERE c.source_path LIKE ?
  ORDER BY fts.rank`)
- Result count: match existing `full_bm25()` behavior (research should check current return count)
- The exact form of `repo_path` argument (absolute vs relative) should be confirmed by research
  against existing `full_bm25()` call sites

### Retrieval API shape
- `full_bm25()` public signature stays identical — no breaking changes to callers
- Return type stays identical to current BM25Okapi output — callers don't need updating
- SQLite connection sourced from `db.get_connection()` (or equivalent) from the existing `db.py`
  module — same path used by the indexer, no duplication

### Edge case behavior
- No chunks for queried repo → return empty list (matches BM25Okapi behavior on empty corpus)
- DB file doesn't exist → auto-create via `init_db()` on first use, no error thrown
- Malformed FTS5 query → let `sqlite3` exception propagate — fail fast, no swallowing

### Claude's Discretion
- Exact `db.py` function to call for the connection (get_connection, init_db, or context manager)
- Whether to cache the SQLite connection on the HybridRetriever instance or open per-query
- How to handle the `source_path` prefix matching if paths are stored differently than expected

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches as long as the API contract is preserved.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-bm25-retriever-swap*
*Context gathered: 2026-03-02*
