# Roadmap: FastCode — LiteLLM Provider Migration

## Milestones

- ✅ **v1.0 LiteLLM Provider Migration** — Phases 1–5 (shipped 2026-02-25)
- ✅ **v1.1 VertexAI Embedding Migration** — Phases 6–7 (shipped 2026-02-25)
- ✅ **v1.2 uv Migration & Tech Debt Cleanup** — Phases 8–10 (shipped 2026-02-27)
- ✅ **v1.3 SQLite FTS5 BM25 Migration** — Phases 11–14 (shipped 2026-03-02)

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

<details>
<summary>✅ v1.3 SQLite FTS5 BM25 Migration (Phases 11–14) — SHIPPED 2026-03-02</summary>

- [x] **Phase 11: SQLite Schema and DB Init** — Database foundation: chunks, sources, and FTS5 tables (1/1 plans) — completed 2026-02-27
- [x] **Phase 12: Indexer Integration** — Write chunks to SQLite during indexing; skip unchanged files (1/1 plans) — completed 2026-02-27
- [x] **Phase 13: BM25 Retriever Swap** — HybridRetriever queries FTS5; pkl files eliminated (2/2 plans) — completed 2026-03-02
- [x] **Phase 14: Embedding Cache Migration** — SQLite embedding_cache replaces DiskCache (2/2 plans) — completed 2026-03-02

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

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
| 11. SQLite Schema and DB Init | v1.3 | 1/1 | Complete | 2026-02-27 |
| 12. Indexer Integration | v1.3 | 1/1 | Complete | 2026-02-27 |
| 13. BM25 Retriever Swap | v1.3 | 2/2 | Complete | 2026-03-02 |
| 14. Embedding Cache Migration | v1.3 | 2/2 | Complete | 2026-03-02 |
