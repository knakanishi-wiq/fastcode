# Roadmap: FastCode — LiteLLM Provider Migration

## Milestones

- ✅ **v1.0 LiteLLM Provider Migration** — Phases 1–5 (shipped 2026-02-25)
- ✅ **v1.1 VertexAI Embedding Migration** — Phases 6–7 (shipped 2026-02-25)
- ✅ **v1.2 uv Migration & Tech Debt Cleanup** — Phases 8–10 (shipped 2026-02-27)
- 🔄 **v1.3 SQLite FTS5 BM25 Migration** — Phases 11–14 (in progress)

## Phases

<details>
<summary>✅ v1.0 LiteLLM Provider Migration (Phases 1–5) — SHIPPED 2026-02-25</summary>

- [x] Phase 1: Config and Dependencies (1/1 plans) — completed 2026-02-24
- [x] Phase 2: Core Infrastructure (2/2 plans) — completed 2026-02-24
- [x] Phase 3: Non-Streaming Migration (4/4 plans) — completed 2026-02-24
- [x] Phase 4: Streaming Migration and Finalization (2/2 plans) — completed 2026-02-25
- [x] Phase 5: Fix answer_generator.py Wiring and Cleanup (1/1 plan) — completed 2026-02-25

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 VertexAI Embedding Migration (Phases 6–7) — SHIPPED 2026-02-25</summary>

- [x] Phase 6: Embedder Migration (1/1 plans) — completed 2026-02-25
- [x] Phase 7: Dependency Cleanup and Smoke Test (2/2 plans) — completed 2026-02-25

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 uv Migration & Tech Debt Cleanup (Phases 8–10) — SHIPPED 2026-02-27</summary>

- [x] Phase 8: Package System Foundation (2/2 plans) — completed 2026-02-26
- [x] Phase 9: Dockerfile and Code Cleanup (2/2 plans) — completed 2026-02-26
- [x] Phase 10: Config Consolidation and Verification (2/2 plans) — completed 2026-02-26

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

### v1.3 SQLite FTS5 BM25 Migration (Phases 11–14)

- [x] **Phase 11: SQLite Schema and DB Init** — Database foundation: chunks, sources, and FTS5 tables *(1 plan)* (completed 2026-02-27)
- [x] **Phase 12: Indexer Integration** — Write chunks to SQLite during indexing; skip unchanged files (completed 2026-02-27)
- [x] **Phase 13: BM25 Retriever Swap** — HybridRetriever queries FTS5; pkl files eliminated (completed 2026-03-01)
- [x] **Phase 14: Embedding Cache Migration** — SQLite embedding_cache replaces DiskCache (completed 2026-03-02)

## Phase Details

### Phase 11: SQLite Schema and DB Init
**Goal**: The SQLite database with all required tables and triggers exists and is ready for use by indexer and retriever
**Depends on**: Nothing (foundation for all v1.3 phases)
**Requirements**: STOR-01, STOR-02, STOR-03
**Success Criteria** (what must be TRUE):
  1. A `chunks` table exists with columns `id`, `source_path`, `content`, `content_hash`, `chunk_index`, `start_offset`, `end_offset`
  2. A `sources` table exists with columns `path`, `content_hash`, `mtime_ns`, `size`
  3. A `chunks_fts` FTS5 virtual table exists and is content-linked to `chunks`
  4. SQL triggers on `chunks` (insert, update, delete) automatically keep `chunks_fts` in sync — verified by inserting a row and querying `chunks_fts MATCH` to find it
  5. DB init is idempotent: running it twice on an existing database raises no errors and does not corrupt data
**Plans**: 1 plan

Plans:
- [ ] 11-01-PLAN.md — Create fastcode/db.py with SQLite schema (chunks, sources, chunks_fts) and automated tests

### Phase 12: Indexer Integration
**Goal**: Repository indexing writes all chunks to the SQLite `chunks` table and skips unchanged files using content hash comparison
**Depends on**: Phase 11
**Requirements**: IDX-01, IDX-02
**Success Criteria** (what must be TRUE):
  1. After indexing a repository, the `chunks` table contains one row per parsed chunk with the correct `source_path` and `content`
  2. After indexing a repository, the `sources` table contains one row per indexed file with `path`, `content_hash`, `mtime_ns`, and `size` populated
  3. Re-indexing a repository where no files have changed produces zero new chunk writes (confirmed by row count staying the same)
  4. Re-indexing after modifying one file updates only that file's chunks and source record; other files' rows are untouched
**Plans**: 1 plan

Plans:
- [ ] 12-01-PLAN.md — Implement index_repo() with SQLite chunk writing and mtime+hash change detection (TDD)

### Phase 13: BM25 Retriever Swap
**Goal**: `HybridRetriever` performs BM25 search via FTS5; pkl files are never written or read
**Depends on**: Phase 12
**Requirements**: BM25-01, BM25-02, BM25-03
**Success Criteria** (what must be TRUE):
  1. `HybridRetriever.full_bm25()` returns results from an FTS5 `bm25(chunks_fts)` query, not from a `BM25Okapi` object
  2. BM25 results are scoped to the queried repository: chunks from other indexed repositories do not appear in results
  3. No `{repo_name}_bm25.pkl` file is written during indexing or read during retrieval — the `./data/` directory contains no pkl files after a fresh index
  4. BM25 result ranking for a known query against a known corpus returns the highest-scoring chunk as the first result
**Plans**: 2 plans

Plans:
- [ ] 13-01-PLAN.md — TDD: full_bm25() method + _keyword_search() update via FTS5 (BM25-01, BM25-02)
- [ ] 13-02-PLAN.md — Remove pkl BM25 infrastructure and rank-bm25 dependency (BM25-03)

### Phase 14: Embedding Cache Migration
**Goal**: `CodeEmbedder` checks a SQLite `embedding_cache` table before calling `litellm.embedding()`, eliminating DiskCache
**Depends on**: Phase 11
**Requirements**: EMB-01, EMB-02
**Success Criteria** (what must be TRUE):
  1. An `embedding_cache` table exists with columns `content_hash`, `model`, and `embedding` (BLOB); `(content_hash, model)` is the primary key
  2. Embedding a chunk that is already in the cache returns the stored embedding without making a `litellm.embedding()` API call
  3. Embedding a chunk not in the cache calls `litellm.embedding()`, stores the result in `embedding_cache`, and returns the embedding
  4. After a full index run, re-running the indexer on the same unchanged repository makes zero `litellm.embedding()` calls (all served from cache)
**Plans**: 2 plans

Plans:
- [ ] 14-01-PLAN.md — TDD: embedding_cache DDL + CodeEmbedder cache logic in embed_text() (EMB-01, EMB-02)
- [ ] 14-02-PLAN.md — Remove diskcache dep, add --clear-cache CLI flag, update README

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Config and Dependencies | v1.0 | 1/1 | Complete | 2026-02-24 |
| 2. Core Infrastructure | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Non-Streaming Migration | v1.0 | 4/4 | Complete | 2026-02-24 |
| 4. Streaming Migration and Finalization | v1.0 | 2/2 | Complete | 2026-02-25 |
| 5. Fix answer_generator.py Wiring | v1.0 | 1/1 | Complete | 2026-02-25 |
| 6. Embedder Migration | v1.1 | 1/1 | Complete | 2026-02-25 |
| 7. Dependency Cleanup and Smoke Test | v1.1 | 2/2 | Complete | 2026-02-25 |
| 8. Package System Foundation | v1.2 | 2/2 | Complete | 2026-02-26 |
| 9. Dockerfile and Code Cleanup | v1.2 | 2/2 | Complete | 2026-02-26 |
| 10. Config Consolidation and Verification | v1.2 | 2/2 | Complete | 2026-02-26 |
| 11. SQLite Schema and DB Init | 1/1 | Complete    | 2026-02-27 | — |
| 12. Indexer Integration | 1/1 | Complete    | 2026-02-27 | — |
| 13. BM25 Retriever Swap | 2/2 | Complete    | 2026-03-01 | — |
| 14. Embedding Cache Migration | 2/2 | Complete   | 2026-03-02 | — |
