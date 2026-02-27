# Requirements: FastCode v1.3 SQLite FTS5 BM25 Migration

**Defined:** 2026-02-27
**Core Value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.

## v1.3 Requirements

### Storage Layer

- [x] **STOR-01**: System stores chunked content in a SQLite `chunks` table with fields: `id`, `source_path`, `content`, `content_hash`, `chunk_index`, `start_offset`, `end_offset`
- [x] **STOR-02**: System tracks indexed file state in a SQLite `sources` table with `path`, `content_hash`, `mtime_ns`, `size` for change detection
- [x] **STOR-03**: A `chunks_fts` FTS5 virtual table is content-synced to `chunks` and maintained by SQL triggers on insert, update, and delete

### BM25 Retrieval

- [ ] **BM25-01**: `HybridRetriever` BM25 search path queries `chunks_fts` using `bm25(chunks_fts)` ranking instead of loading a `BM25Okapi` object
- [ ] **BM25-02**: FTS5 BM25 query supports filtering by `source_path` prefix to scope results to a specific indexed repository
- [ ] **BM25-03**: The `{repo_name}_bm25.pkl` index files are no longer written or loaded; BM25 corpus is derived entirely from the SQLite database

### Indexing

- [x] **IDX-01**: `Indexer` writes each chunk to the SQLite `chunks` table during repository indexing (replaces in-memory BM25 corpus construction)
- [x] **IDX-02**: Re-indexing detects unchanged files via `content_hash` comparison against the `sources` table and skips them without re-chunking or re-embedding

### Embedding Cache

- [ ] **EMB-01**: An `embedding_cache` table in SQLite stores embeddings keyed on `(content_hash, model)` with the embedding stored as a BLOB
- [ ] **EMB-02**: `CodeEmbedder` checks the SQLite `embedding_cache` before calling `litellm.embedding()`; cache hits avoid a VertexAI API round-trip

## Future Requirements

### Vector Store Integration (deferred)

- **VEC-01**: Replace FAISS with sqlite-vec for vector similarity search
- **VEC-02**: Single `.db` file holds chunks, FTS5 index, embedding cache, and ANN index

## Out of Scope

| Feature | Reason |
|---------|--------|
| Replace FAISS with sqlite-vec | FAISS is better at ANN search at FastCode's scale; sqlite-vec deferred to future milestone |
| Multi-process SQLite access | Single-process CLI tool; WAL mode sufficient for read concurrency |
| Migration tooling for existing pkl files | Existing pkl files are simply ignored on first run; SQLite DB is rebuilt from source |
| Full-text query syntax exposure | FTS5 used with AND-joined quoted terms only; no user-facing query syntax |
| Graph-based retrieval changes | Call/dependency/inheritance graph traversal unchanged |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 11 | Complete |
| STOR-02 | Phase 11 | Complete |
| STOR-03 | Phase 11 | Complete |
| BM25-01 | Phase 13 | Pending |
| BM25-02 | Phase 13 | Pending |
| BM25-03 | Phase 13 | Pending |
| IDX-01 | Phase 12 | Complete |
| IDX-02 | Phase 12 | Complete |
| EMB-01 | Phase 14 | Pending |
| EMB-02 | Phase 14 | Pending |

**Coverage:**
- v1.3 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 — traceability updated after roadmap creation*
