# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02)

**Core value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.
**Current focus:** Planning next milestone

## Current Position

Phase: v1.3 complete (Phases 11–14)
Plan: All plans complete (6/6)
Status: v1.3 milestone shipped — SQLite FTS5 BM25 Migration done
Last activity: 2026-03-02 — v1.3 milestone archived; ROADMAP.md, PROJECT.md, REQUIREMENTS.md updated

```
Progress: v1.3 complete ████████████████████████████████ 100% (14/14 phases)
v1.3:     Phase 11 ████ Phase 12 ████ Phase 13 ████ Phase 14 ████ ✓ SHIPPED
```

## Performance Metrics

**Velocity:**
- Total plans completed: 22 (v1.0: 10, v1.1: 3, v1.2: 3, v1.3: 6)
- Average duration: ~5–6 min/plan (v1.3 plans were larger TDD tasks)
- Total execution time: ~1 hour (v1.3 alone)

**By Phase:**

| Phase | Plans | Avg/Plan |
|-------|-------|----------|
| 01–05 (v1.0) | 10 | ~2 min |
| 06–07 (v1.1) | 3 | ~2 min |
| 08–10 (v1.2) | 6 | ~3 min |
| 11–14 (v1.3) | 6 | ~6 min |

## Accumulated Context

### Decisions

Key v1.3 decisions (full log in PROJECT.md Key Decisions):

- [Phase 11]: FTS5 content-linked table (content=chunks) — retriever reads chunk text from FTS without extra JOIN
- [Phase 12]: mtime_ns fast-path before SHA-256 hash — avoids hashing unchanged files on repeated index runs
- [Phase 13]: full_bm25() is a method (not attr); score=1.0 placeholder in _keyword_search()
- [Phase 13]: _simple_bm25_scores TF sum for repo overview; repo_overview_bm25=True sentinel
- [Phase 14]: BLOB (float32 bytes) for embedding storage; validate shape on retrieval, raise ValueError
- [Phase 14]: embed_text() signature unchanged; --clear-cache on index command (not standalone)
- [Phase 14]: Start fresh on DiskCache → SQLite (no data migration)

### Blockers/Concerns

None.

### Pending Todos

None.

## Session Continuity

Last session: 2026-03-02
Stopped at: v1.3 milestone complete and archived — ready for next milestone
Resume file: None
