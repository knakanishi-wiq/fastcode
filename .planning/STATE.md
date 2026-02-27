# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.
**Current focus:** v1.3 — SQLite FTS5 BM25 Migration (Phase 12: Indexer SQLite Integration)

## Current Position

Phase: 11 — SQLite Schema and DB Init
Plan: 01 (Complete)
Status: Phase 11 complete — ready for Phase 12
Last activity: 2026-02-27 — Phase 11 Plan 01 complete; fastcode/db.py and tests/test_db.py created

```
Progress: Phases 1–11 complete █████████████████████░░░░░░░░ 79% (11/14)
v1.3:     Phase 11 ████ Phase 12 ░░░░ Phase 13 ░░░░ Phase 14 ░░░░
```

## Performance Metrics

**Velocity:**
- Total plans completed: 16 (v1.0: 10 plans, v1.1: 3 plans, v1.2: 3 plans)
- Average duration: ~2–3 min/plan
- Total execution time: ~0.6 hours

**By Phase:**

| Phase | Plans | Avg/Plan |
|-------|-------|----------|
| 01–05 (v1.0) | 10 | ~2 min |
| 06–07 (v1.1) | 3 | ~2 min |
| 08 (v1.2) | 2 | 2 min |
| 09-01 (v1.2) | 1 | ~3 min |
| 09-02 (v1.2) | 1 | 3 min |
| 10-01 (v1.2) | 1 | 2 min |
| 10-02 (v1.2) | 1 | 3 min |

**Recent Trend:**
- Last 5 plans: 2min, 3min, 2min, 3min, 3min
- Trend: Stable

*Updated after each plan completion*
| Phase 11-sqlite-schema-and-db-init P01 | 2 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Recent decisions affecting v1.2 (full log in PROJECT.md Key Decisions):

- [v1.2 scope]: PKG-01 requires hatchling editable install — follow PKG-01 spec (editable install for importability), not research recommendation (no build-system)
- [v1.2 scope]: Pin uv to `0.10.6` in Dockerfile; never use `:latest`
- [10-01]: Removed MODEL env var entirely (not aliased) — aliasing would preserve confusion; clean break with MIGRATION NOTE (v1.2) is clearer
- [10-01]: Kept import os and load_dotenv() in answer_generator.py — both still used by other code in the file
- [v1.1 deferred → Phase 10, now DONE]: MODEL/LITELLM_MODEL independence was operational confusion risk — DEBT-04 resolved in 10-01
- [v1.1 deferred → Phase 9]: embed_text() default task_type latent fragility — DEBT-02 makes line 415 explicit
- [08-01]: Used [dependency-groups] dev (PEP 735) rather than [project.optional-dependencies] — stricter isolation, uv recommended approach
- [08-01]: Did NOT add [tool.hatch.build.targets.wheel] — hatchling auto-discovered fastcode/ at repo root without it
- [08-02]: Used git rm to delete requirements.txt atomically; all four Phase 8 success criteria passed on first attempt
- [09-01]: uv pinned to 0.10.6 via COPY --from (never :latest); Task 1 required no .dockerignore changes; TOKENIZERS_PARALLELISM removed as dead env var
- [09-02]: Delete all six dead lines from __init__.py (import os, import platform, and Darwin if-block) — leaving either import unused would fail F401 linting
- [09-02]: Use uppercase RETRIEVAL_QUERY in retriever.py task_type kwarg — matches embedder.py default exactly to avoid runtime validation error
- [Phase 10-02]: DEBT-03 confirmed live: gemini-embedding-001 accepts CODE_RETRIEVAL_QUERY task_type — asymmetric pairing at retriever.py line 734 is valid
- [Phase 10-02]: DEBT-05 confirmed live: _stream_with_summary_filter() correctly suppresses SUMMARY tags — no leakage observed
- [Phase 11-sqlite-schema-and-db-init]: Used executescript() for all DDL — cleaner single call vs N individual execute() calls
- [Phase 11-sqlite-schema-and-db-init]: FTS5 content=chunks (content-linked) over contentless — Phase 13 retriever can get chunk text from FTS without extra join
- [Phase 11-sqlite-schema-and-db-init]: WAL mode omitted — single-process CLI tool; no concurrent readers

### v1.3 Context

**Key files for this milestone:**
- `fastcode/retriever.py` — `HybridRetriever.full_bm25()` uses `rank_bm25.BM25Okapi`; pkl at `./data/{repo_name}_bm25.pkl`
- `fastcode/indexer.py` — builds BM25 index (pkl) and FAISS index during indexing
- `fastcode/embedder.py` — `CodeEmbedder` calls `litellm.embedding()`; uses DiskCache for embedding caching
- `fastcode/vector_store.py` — manages FAISS index; FAISS stays unchanged in v1.3

**Architecture decisions resolved (Phase 11):**
- DB init location: `fastcode/db.py` module (resolved)
- FTS5 content-linked table (content=chunks) chosen for retriever convenience

**Architecture decisions pending:**
- SQLite DB file path: likely `./data/{repo_name}.db` or a single `./data/fastcode.db` (Phase 12)
- EMB-01/EMB-02 (Phase 14) depends on Phase 11 schema but is independent of Phases 12-13

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-27
Stopped at: Completed 11-01-PLAN.md — fastcode/db.py (init_db), tests/test_db.py (7 tests), STOR-01/02/03 done
Resume file: None
