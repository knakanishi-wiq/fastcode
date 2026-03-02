# Phase 14: Embedding Cache Migration - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace DiskCache with a SQLite `embedding_cache` table in `CodeEmbedder`. Cache hits skip
`litellm.embedding()` calls entirely. DiskCache library and its data directory are removed.
Scope: `fastcode/embedder.py`, `fastcode/db.py` (schema addition), `pyproject.toml`, CLI index command.

</domain>

<decisions>
## Implementation Decisions

### DiskCache removal
- Remove `diskcache` from `pyproject.toml` entirely — no remaining callers after this phase
- Researcher should grep for all `diskcache` usages in the codebase before planning (caller list not yet confirmed)
- Delete the existing DiskCache data directory as part of the migration — document the exact path once
  discovered by the researcher/executor
- Add a migration note in README (Known Consequences section) — same pattern as v1.1 FAISS reindex note

### Cache invalidation policy
- Cache entries are **permanent** — embeddings are deterministic for `(content_hash, model)`, no
  automatic invalidation needed
- Old model entries persist harmlessly when model changes — different model = different cache key,
  old rows are never retrieved but cause no errors
- **Validate embedding shape on retrieval**: if the cached embedding's dimension doesn't match the
  expected `embedding_dim`, raise an error (not silently re-embed) — this catches model-switch bugs early

### Migration path from DiskCache
- **Start fresh** — no migration of existing DiskCache entries to SQLite; clean break
- Full re-index required after upgrade; document as Known Consequence in README
- DiskCache directory path: let executor discover from codebase (grep for DiskCache init in embedder.py)
- Deletion of old DiskCache directory: documented manual step in README, not automated cleanup code

### Cache entry point
- Cache-check logic lives **inside `embed_text()` on `CodeEmbedder`** — same location as current
  DiskCache check; all callers benefit transparently with zero signature changes
- Storage format: **BLOB of float32 bytes** (`numpy.ndarray.tobytes()`), deserialized via
  `numpy.frombuffer(..., dtype=float32)` on retrieval — compact, fast, matches schema spec
- `embed_text()` signature **unchanged** — caching is a transparent implementation detail
- `--clear-cache` flag attached to the **`index` CLI command** (`fastcode index --clear-cache`);
  truncates `embedding_cache` table before indexing begins

### Claude's Discretion
- Exact SQL for `embedding_cache` table DDL (beyond what REQUIREMENTS.md specifies)
- Whether to add `embedding_cache` to `db.py`'s `init_db()` or a separate migration function
- Test structure: TDD (write failing tests first) vs execute-style plan
- Whether `--clear-cache` truncates only `embedding_cache` or also `chunks`/FTS tables

</decisions>

<specifics>
## Specific Ideas

- Embedding dimension validation on cache retrieval should raise an error (not silently re-embed) —
  this surfaces model-switch misconfiguration clearly rather than silently producing wrong-dim vectors

</specifics>

<deferred>
## Deferred Ideas

- `fastcode cache clear` as a standalone CLI command — Phase 14 attaches --clear-cache to `index`
  only; a dedicated cache management command could be a future phase
- Cache size monitoring / eviction policies — out of scope; cache is append-only for v1.3

</deferred>

---

*Phase: 14-embedding-cache-migration*
*Context gathered: 2026-03-02*
