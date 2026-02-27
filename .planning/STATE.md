# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.
**Current focus:** Planning next milestone

## Current Position

Milestone: v1.2 — uv Migration & Tech Debt Cleanup — SHIPPED 2026-02-27
Status: All phases complete; milestone archived
Last activity: 2026-02-27 — v1.2 milestone completed and tagged

Progress: [██████████] 100% (v1.0 + v1.1 + v1.2 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 16 (v1.0: 10 plans, v1.1: 3 plans, v1.2: 3 plans so far)
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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 10 — RESOLVED]: DEBT-03 and DEBT-05 required live GCP credentials — both verified successfully via .env ADC on 2026-02-26

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 10-02-PLAN.md (DEBT-03 and DEBT-05 resolved; live smoke tests added and verified against GCP)
Resume file: None
